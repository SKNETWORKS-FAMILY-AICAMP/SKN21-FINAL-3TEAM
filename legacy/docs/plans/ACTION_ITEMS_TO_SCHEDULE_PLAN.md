# Action Items → 일정 제안 기능 설계 플랜

## 1. 개요

문서 생성(회의록/보고서) 완료 후, action_items에 기한(due_date)이 포함된 항목이 있으면 챗봇에서 "이 일정들을 캘린더에 추가할까요?" 형태로 **제안**하는 기능.
자동 등록이 아니라, 사용자가 내용을 확인/수정한 뒤 "등록" 버튼을 누르면 기존 schedule API(`POST /api/v1/schedules/`)를 호출하여 일정을 생성한다.

**설계 원칙:**
- 오케스트레이터/그래프 구조 변경 없음
- AgentState 변경 없음
- 기존 기능(규정 검증, 스트리밍, action_items 표시 등) 절대 훼손하지 않음
- `suggested_schedules` 필드 추가는 순수 additive (기존 필드 수정/삭제 없음)
- 일정 등록은 기존 `POST /api/v1/schedules/` API 재활용

**기존 기능 보호 원칙:**
- `_entry.py`의 규정 검증 블록(281-298행) 수정 금지
- `chat.py`의 generate_config 처리 흐름(505-528행) 수정 금지
- ChatPage.jsx의 기존 GenerateCard props 변경 금지
- 모든 신규 코드는 try/except 비차단 처리 (실패해도 기존 응답 그대로 반환)

---

## 2. 현재 상태 분석

### 2.1 문서 생성 응답 구조 (현재)

`_generate_with_custom_template()` 반환값 (`ai/agents/document/_generate.py`):

```python
{
    "type": "doc_generate",
    "template_type": "meeting_minutes",  # | "report" | "proposal"
    "template_id": 1,
    "template_name": "기본 회의록",
    "preview": "# 회의 제목\n...",
    "data": {
        "title": "...",
        "action_items": [
            {"task": "API 설계 완료", "assignee": "김팀장", "due_date": "2026-03-28"},
            {"task": "프론트 리팩토링", "assignee": "이대리", "due_date": "2026-04-01"},
        ],
        # ... 기타 필드
    },
    "document_id": "uuid",
    "docx_path": "...",
    "download_url": "...",
}
```

### 2.2 action_items 스키마 (템플릿별)

회의록 (`_generate.py` 정규화):
```python
{"task": str, "assignee": str, "due_date": str}
```

보고서 tasks (`_generate.py` 정규화):
```python
{"item": str, "assignee": str, "progress": str, "start_date": str, "end_date": str}
```

제안서 schedule → phase 기반이라 일정 변환 복잡 → **1차 범위에서 제외**

### 2.3 일정 등록 API (현재)

`POST /api/v1/schedules/` — `ScheduleCreate` 스키마 (`backend/app/schemas/schedule.py:9-19`):
```python
title: str
description: Optional[str] = None
start_time: datetime              # 필수
end_time: Optional[datetime] = None
schedule_type: str = "task"
priority: str = "medium"
include_meet: bool = False
attendee_emails: list[str] = []
is_team_visible: bool = False
project_name: Optional[str] = None
```

### 2.4 두 가지 실행 경로 (핵심)

문서 생성은 **두 경로**로 실행된다:

**경로 A — 비스트리밍 (`stream_mode=False`, POST /chat/)**
```
_entry.py → _handle_doc_generate() → _generate_with_custom_template()
→ response_data에 data 필드 포함 → 후처리 가능 → State 업데이트 → 반환
```

**경로 B — 스트리밍 (`stream_mode=True`, POST /chat/stream, 기본)**
```
_entry.py → _handle_doc_generate() → generate_config만 반환 (stream_pending=True)
→ chat.py:505-528에서 generate_document() 직접 호출
→ agent_response.update(result) (520행) → data 필드 생김
→ stream_pending/generate_config 제거 (526-527행)
→ final_state 저장 (528행)
```

**결론: 두 경로 모두에 후처리를 삽입해야 함**

### 2.5 프론트엔드 현재 패턴

**ChatPage.jsx (285-338행) — doc_generate case:**
```jsx
<GenerateCard
  title={String(docData.title || templateName)}
  templateType={data.template_type}
  fields={fields}
  actionItems={actionItems}          // 이미 전달 중
  onDownload={handleDocDownload}
  modelName={data.model_name || ''}
  regulationCheck={data.regulation_check}
  warnings={data.warnings}
/>
```

**GenerateCard.jsx:** action_items를 텍스트로만 표시, 일정 제안 UI 없음

**MeetingPreview.jsx:** Pipeline/Google Tasks 등록 패턴 이미 구현 (모달+선택+등록) — 참고용

---

## 3. 구현 설계

### 3.1 신규 파일: `_schedule_suggest.py`

**파일:** `ai/agents/document/_schedule_suggest.py` (신규)

```python
def extract_suggested_schedules(response_data: dict) -> list[dict]:
    """doc_generate 응답에서 일정 제안 데이터를 추출한다.

    action_items(회의록), tasks(보고서)에서 기한이 있는 항목을
    ScheduleCreate 호환 형태로 변환.

    Args:
        response_data: doc_generate agent_response dict

    Returns:
        ScheduleCreate 호환 dict 리스트.
        프론트 전용 메타 필드(source, original_index)도 포함.
        날짜 파싱 실패 항목은 자동 제외.
        빈 리스트 반환 시 프론트에서 제안 UI 미표시.
    """
```

**추출 로직:**

| 문서 유형 | 소스 필드 | title 매핑 | due_date 매핑 | 비고 |
|-----------|-----------|------------|---------------|------|
| meeting_minutes | `data.action_items` | `task` | `due_date` | 1차 지원 |
| report | `data.tasks` | `item` | `end_date` | 1차 지원 (end_date 있는 항목만) |
| proposal | — | — | — | 제외 (phase 기반, 추후 확장) |

**반환 형태 (항목 1개):**
```python
{
    # ScheduleCreate 호환 필드
    "title": "API 설계 완료",
    "description": "담당: 김팀장 | 출처: 3월 팀 회의록",
    "start_time": "2026-03-28T09:00:00",
    "end_time": "2026-03-28T10:00:00",
    "schedule_type": "task",
    "priority": "high",
    # 프론트 전용 메타 (API 호출 시 프론트에서 제거)
    "source": "action_item",
    "original_index": 0,
}
```

**날짜 파싱 규칙:**
| 입력 예시 | 파싱 결과 |
|-----------|-----------|
| `"2026-03-28"` | `2026-03-28T09:00:00` |
| `"2026.03.28"` | `2026-03-28T09:00:00` |
| `"3월 28일"` | `{current_year}-03-28T09:00:00` |
| `"3/28"` | `{current_year}-03-28T09:00:00` |
| `"다음주 금요일"` | **제외** (파싱 불가) |
| `""` (빈 문자열) | **제외** |

- 기본 시간: 09:00 시작, 10:00 종료 (1시간 블록, 사용자가 프론트에서 수정 가능)
- 과거 날짜: 제외하지 않음 (사용자가 판단하여 수정 가능, 프론트에서 경고 표시)

**우선순위 계산 (자체 구현, 외부 import 없음):**
```python
def _calc_priority(due_date_str: str) -> str:
    days_left = (due_date - today).days
    if days_left <= 1: return "high"
    if days_left <= 3: return "medium"
    return "low"
```

### 3.2 응답 구조 (agent_response에 additive 추가)

기존 `doc_generate` 응답의 모든 필드를 그대로 유지하고, 2개 필드만 추가:

```python
{
    # ======== 기존 필드 전부 유지 (수정 없음) ========
    "type": "doc_generate",
    "template_type": "meeting_minutes",
    "data": { ... },
    "document_id": "...",
    "docx_path": "...",
    "regulation_check": { ... },
    "warnings": [ ... ],
    # ... 기타 ...

    # ======== 신규 추가 필드 (2개만) ========
    "suggested_schedules": [
        {
            "title": "API 설계 완료",
            "description": "담당: 김팀장 | 출처: 3월 팀 회의록",
            "start_time": "2026-03-28T09:00:00",
            "end_time": "2026-03-28T10:00:00",
            "schedule_type": "task",
            "priority": "high",
            "source": "action_item",
            "original_index": 0,
        },
    ],
    "schedule_suggest_message": "회의록에서 2건의 일정 항목을 발견했습니다. 캘린더에 등록할까요?",
}
```

**보호 규칙:**
- `suggested_schedules`가 빈 배열이면 프론트에서 제안 UI를 표시하지 않음
- 추출 함수가 예외 발생해도 기존 response_data에 영향 없음 (try/except 비차단)
- 기존 필드(regulation_check, warnings, data 등)는 절대 수정하지 않음

### 3.3 후처리 삽입 위치 (두 경로 모두)

#### 경로 A: `_entry.py` (비스트리밍)

**삽입 위치:** 298행(규정 검증 except 블록) 이후, 300행(모델명 추가) 이전

```python
    # ↑ 298행: except ... logger.warning (규정 검증 끝)

    # ── 일정 제안 추출 (doc_generate일 때만, 비차단) ──
    if response_data.get("type") == "doc_generate" and response_data.get("data"):
        try:
            from ai.agents.document._schedule_suggest import extract_suggested_schedules
            suggested = extract_suggested_schedules(response_data)
            if suggested:
                response_data["suggested_schedules"] = suggested
                response_data["schedule_suggest_message"] = (
                    f"문서에서 {len(suggested)}건의 일정 항목을 발견했습니다. 캘린더에 등록할까요?"
                )
        except Exception as e:
            logger.warning("[DocumentEntry] 일정 제안 추출 실패 (비차단): %s", e)

    # ↓ 300행: 모델명 추가 (기존 코드 그대로)
```

**기존 코드 영향: 없음** — 규정 검증과 모델명 추가 사이에 독립 블록 삽입, 실패해도 response_data 변형 없음

#### 경로 B: `chat.py` (스트리밍 — 기본 경로)

**삽입 위치:** 520행(`agent_response.update(result)`) 이후, 526행(pop) 이전

```python
                                agent_response.update(result)     # 520행 (기존)

                                # ── 일정 제안 추출 (비차단, 기존 흐름 변경 없음) ──
                                try:
                                    from ai.agents.document._schedule_suggest import extract_suggested_schedules
                                    suggested = extract_suggested_schedules(agent_response)
                                    if suggested:
                                        agent_response["suggested_schedules"] = suggested
                                        agent_response["schedule_suggest_message"] = (
                                            f"문서에서 {len(suggested)}건의 일정 항목을 발견했습니다. "
                                            f"캘린더에 등록할까요?"
                                        )
                                except Exception as exc:
                                    logger.warning("[Chat] 일정 제안 추출 실패 (비차단): %s", exc)

                            except Exception as e:                # 521행 (기존)
```

**기존 코드 영향: 없음**
- `agent_response.update(result)` 이후이므로 data 필드가 이미 존재
- 526-527행의 pop(stream_pending/generate_config)과 무관 (다른 필드)
- 521행의 기존 except 블록은 그대로 유지
- 실패해도 agent_response의 기존 필드에 영향 없음 (additive only)

### 3.4 프론트엔드 처리 흐름 (설계만, PM 직접 구현)

#### ChatPage.jsx (285행 doc_generate case)

기존 코드에 1줄 추가 + GenerateCard에 prop 1개 추가:
```jsx
const suggestedSchedules = data.suggested_schedules || [];

<GenerateCard
  // ... 기존 props 전부 유지 ...
  suggestedSchedules={suggestedSchedules}   // 추가
/>
```

#### GenerateCard.jsx

`suggestedSchedules` prop이 비어있지 않으면 Action Items 섹션 아래에 제안 UI 렌더링:
- 체크박스로 각 항목 선택/해제 (기본: 전체 선택)
- 제목, 날짜, 시간을 인라인 수정 가능
- "선택한 일정 등록" 버튼
- 등록 완료 시 해당 항목 비활성화 + 체크 표시
- 등록 버튼 클릭 후 loading 중 disable (중복 클릭 방지)

#### 일정 등록 API 호출

```javascript
// 선택된 항목 각각에 대해
const payload = {
  title: item.title,
  description: item.description,
  start_time: item.start_time,
  end_time: item.end_time,
  schedule_type: item.schedule_type,
  priority: item.priority,
  // source, original_index는 제거 (프론트 전용)
};
await api.post('/api/v1/schedules/', payload);
```

- 기존 `POST /api/v1/schedules/` 그대로 사용 (추가 엔드포인트 불필요)
- 부분 실패 시: 성공 건은 체크 표시, 실패 건은 에러 toast + 재시도 가능 상태 유지

---

## 4. 구현 태스크

### Task 1: `_schedule_suggest.py` 작성 (신규 파일)
- **파일:** `ai/agents/document/_schedule_suggest.py`
- **내용:** `extract_suggested_schedules(response_data)` 함수
  - template_type별 action_items/tasks 추출
  - 날짜 파싱 (정규식 기반, 외부 라이브러리 없음)
  - ScheduleCreate 호환 dict 리스트 반환
  - 우선순위 자동 계산
- **수용 기준:** 회의록 action_items에서 due_date 있는 항목이 올바른 형태로 변환됨

### Task 2: `_entry.py` 후처리 삽입 (비스트리밍 경로)
- **파일:** `ai/agents/document/_entry.py`
- **위치:** 298행 이후, 300행 이전 (규정 검증 끝, 모델명 추가 전)
- **내용:** 5-10줄 후처리 블록 (try/except 비차단)
- **수용 기준:** 비스트리밍 모드에서 doc_generate 응답에 suggested_schedules 포함
- **기존 영향:** 없음 (독립 블록, 실패 시 무시)

### Task 3: `chat.py` 후처리 삽입 (스트리밍 경로)
- **파일:** `backend/app/api/v1/chat.py`
- **위치:** 520행(`agent_response.update(result)`) 이후, 기존 except(521행) 이전
- **내용:** 5-10줄 후처리 블록 (try/except 비차단)
- **수용 기준:** 스트리밍 모드에서 doc_generate 응답에 suggested_schedules 포함
- **기존 영향:** 없음 (additive, 실패 시 무시)

### Task 4: 프론트엔드 UI (PM 직접 구현)
- **파일:** `ChatPage.jsx`, `GenerateCard.jsx`
- **내용:**
  - ChatPage: suggestedSchedules prop 전달 (1줄)
  - GenerateCard: 제안 UI 섹션 + 수정 + 등록 버튼
  - POST /api/v1/schedules/ 호출 (기존 API)
  - 중복 클릭 방지, 부분 실패 처리

---

## 5. 에러 처리 & 엣지 케이스

| 케이스 | 처리 방법 |
|--------|-----------|
| action_items 빈 배열 | suggested_schedules = [] → 프론트 UI 미표시 |
| 날짜 파싱 실패 | 해당 항목만 제외, 나머지는 정상 반환 |
| due_date가 과거 | 제외하지 않음 (프론트에서 ⚠ 아이콘 표시, 사용자 수정 가능) |
| extract_suggested_schedules 예외 | try/except 비차단, 기존 응답 그대로 반환 |
| 프론트 등록 시 부분 실패 | 성공 건 체크, 실패 건 toast + 재시도 가능 |
| 등록 버튼 중복 클릭 | 버튼 loading 상태로 disable |
| 동일 일정 중복 등록 | 프론트에서 등록 완료 항목 비활성화 (서버 측 중복 체크는 scope 외) |
| proposal 템플릿 | suggested_schedules = [] (1차 범위 제외) |

---

## 6. 타임라인

| Task | 내용 | 예상 시간 |
|------|------|-----------|
| Task 1 | `_schedule_suggest.py` 작성 | 1-2h |
| Task 2 | `_entry.py` 후처리 (비스트리밍) | 0.5h |
| Task 3 | `chat.py` 후처리 (스트리밍) | 0.5h |
| Task 4 | 프론트엔드 UI (PM 직접) | 2-4h |
| 테스트 | 회의록 생성 → 제안 → 등록 E2E | 1h |
| **합계** | | **5-8h** |

---

## 7. 파일 변경 요약

| 파일 | 변경 유형 | 내용 | 기존 영향 |
|------|-----------|------|-----------|
| `ai/agents/document/_schedule_suggest.py` | **신규** | `extract_suggested_schedules()` | 없음 (신규 파일) |
| `ai/agents/document/_entry.py` | 수정 | 298행 이후에 후처리 5-10줄 추가 | 없음 (독립 블록) |
| `backend/app/api/v1/chat.py` | 수정 | 520행 이후에 후처리 5-10줄 추가 | 없음 (독립 블록) |
| `frontend/src/pages/ChatPage.jsx` | 수정 | suggestedSchedules prop 전달 (1줄) | 없음 (기존 props 유지) |
| `frontend/src/components/chat/GenerateCard.jsx` | 수정 | 제안 UI 섹션 추가 | 없음 (기존 UI 유지) |

**변경하지 않는 파일:**
- `ai/agents/state.py` — AgentState 변경 없음
- `ai/agents/orchestrator.py` — 그래프 구조 변경 없음
- `backend/app/api/v1/schedules.py` — 기존 API 그대로 사용
- `backend/app/schemas/schedule.py` — ScheduleCreate 변경 없음
- `ai/agents/document/_generate.py` — 생성 로직 변경 없음
- `ai/agents/regulation_validator.py` — 규정 검증 변경 없음

---

## 8. 확장 가능성

1. **보고서 tasks 지원** — `end_date` 필드 있는 보고서 tasks도 일정 제안 (Task 1에서 이미 지원)
2. **제안서 schedule 지원** — phase 기반 일정은 별도 매핑 필요 (낮은 우선순위)
3. **일괄 등록 API** — 항목 많으면 `POST /api/v1/schedules/batch` 고려 (현재는 건별 호출)
4. **Google Calendar 연동** — 기존 schedule_service가 이미 지원, 추가 작업 불필요
