# 2026-03-20 작업 로그 — fill-fields 파이프라인 재설계

> 내일 다른 PC에서 이어 작업할 때 이 파일부터 읽을 것

---

## 한 줄 요약

sLLM(LoRA v3_generate)이 meta 추출에 약하고 body 생성에 강함 → **역할 분리**: meta는 사용자가 폼에서 직접 입력, body만 sLLM이 생성. 정규화(Phase 1) 제거.

---

## 이번 세션에서 한 일

### 1. 정규화(Phase 1) 완전 제거
- `_NORMALIZE_SYSTEM` 상수 삭제
- `_normalize_input()` 함수 삭제
- **이유**: base 모델로 구어체→불릿 정규화 시 오히려 정보 왜곡/누락 발생. 원문 그대로 sLLM에 보내는 게 가장 안정적 (테스트 검증됨)

### 2. fill-fields API 재설계 (`backend/app/api/v1/documents.py`)
- `FillFieldsRequest`에 `meta_values: dict | None` 추가
- 파이프라인 변경:
  ```
  이전: content → 정규화(base) → sLLM(전체 필드)
  현재: content → sLLM(body 필드만) + meta_values(사용자 입력) + Phase 0(fallback)
  ```
- 병합 우선순위:
  - meta: `meta_values` > Phase 0 > null
  - body: sLLM 출력 > null
- Phase 0에 "제안일" 키워드 추가 (기존: 작성일/제출일/보고일만)

### 3. 미사용 코드 정리
- `DOC_FILL_GENERATE_PROMPT` 삭제 (`ai/llm/prompts.py`) — 어디서도 안 쓰임
- `call_sllm_body_generate()` 추가했다가 삭제 (`ai/agents/document/_generate.py`) — 챗봇 구현 시 필요하면 그때 만들기로

### 4. 프론트엔드 UX 재설계 (`frontend/src/pages/DocumentGeneratePage.jsx`)
- 커스텀 템플릿 선택 시 UI:
  ```
  ┌ 기본 정보 — 직접 입력 (meta, 2열 그리드) ┐
  │  제출일: auto-fill(today)               │
  │  담당자: auto-fill(user.name)           │
  │  제출처, 제안사 등: 사용자 입력            │
  ├──────────────────────────────────────────┤
  │ 본문 — AI가 작성합니다                    │
  │  [freeText textarea]                    │
  │  [AI 문서 작성] 버튼                     │
  ├──────────────────────────────────────────┤
  │ (AI 작성 후) body 필드 펼쳐서 표시         │
  │  제안배경 [AI]  "현재 기업에서는..."       │
  │  현황분석 [AI]  "월 200건을..."          │
  │  연락처   [입력 필요]  ← 주황 강조        │
  └──────────────────────────────────────────┘
  ```
- `bodyData` state 분리: meta는 `formData`, body는 `bodyData`로 관리
- `fillFields` API 호출 시 `meta_values` 함께 전달
- 문서 생성 시 `formData(meta) + bodyData(body)` 병합
- 시스템 템플릿(회의록/보고서/제안서)은 기존 DynamicForm 그대로 유지 (영향 없음)

### 5. template_extractor.py v3 메타데이터
- 이전 세션에서 추가한 `group: "meta"/"body"` 분류가 이번 파이프라인의 핵심
- group 기준: 번호 접두사 → body, textarea/array → body, 라벨 6자 이상 → body, 나머지 → meta
- 이번 세션에서 변경한 것 없음 (이전 커밋 변경분만 함께 커밋됨)

---

## 테스트 결과

### 백엔드 API 테스트 (fill-fields)

| 테스트 | body 채움 | meta 채움 | 시간 |
|--------|----------|----------|------|
| 제안서-v3 불릿 + meta 5개 | **7/7 (100%)** | 5/10 | 10s |
| 제안서-v3 구어체 2문장 + meta 2개 | **7/7 (100%)** | 3/10 | 7s |
| 제안서-v3 불릿 상세 + meta 7개(풀) | **7/7 (100%)** | 7/10 | 10s |
| 보고서-v3 불릿 6줄 | 5/6 | 3/7 | 4s |
| 보고서-v3 구어체 장문 | 5/6 | 3/7 | 5s |
| **보고서-v3 3줄 (짧음)** | **0/6** | 3/7 | 4s |

- body 6/7 (첨부자료 빈값)인 경우는 정상 — 첨부자료는 AI가 못 채움
- **보고서 3줄 입력 → body 0/6**: 입력이 너무 짧아서 sLLM이 생성할 근거 부족

### E2E Playwright 테스트

| 항목 | 결과 |
|------|------|
| 로그인 → 문서 생성 페이지 | PASS |
| 시스템 보고서 폼 (기존 동작) | PASS |
| 커스텀 UI 미노출 (시스템 템플릿) | PASS |
| 커스텀 템플릿 선택 (제안서v3) | PASS |
| 기본 정보 섹션 + 2열 그리드 | PASS |
| 본문 섹션 + AI 버튼 | PASS |
| 날짜 auto-fill (today) | PASS |
| 이름 auto-fill (user.name) | PASS |
| AI 문서 작성 → body 7개 필드 생성 | PASS |
| [AI] 태그 표시 | PASS |
| "7/7개 본문 필드 작성됨" 카운트 | PASS |
| DOCX 생성 + 다운로드 버튼 | PASS |
| 콘솔 에러 (이번 변경 관련) | 0개 |

---

## 커밋 정보

```
브랜치: feat/jiyong
커밋: 1264cc9
메시지: refactor: fill-fields 파이프라인 재설계 — meta/body 역할 분리
상태: origin보다 1커밋 ahead (push 안 함)
```

변경 파일 5개:
- `backend/app/api/v1/documents.py` — 정규화 제거, body만 sLLM, meta_values
- `ai/llm/prompts.py` — DOC_FILL_GENERATE_PROMPT 삭제
- `ai/agents/document/_generate.py` — 빈 줄 정리
- `ai/document_parser/template_extractor.py` — 이전 세션 변경분 (v3 메타데이터)
- `frontend/src/pages/DocumentGeneratePage.jsx` — meta/body 분리 UX

---

## 남은 문제 + 고민 중인 것

### 해야 하는 것 (확정)

**1. 레거시 템플릿 DB 정리**
- 시스템 템플릿(id=2,3,4) + 구 커스텀(id=10~20)에 group 정보가 없음
- fill-fields에서 group 없으면 body=0 → 전부 meta로 처리 → sLLM에 아무것도 안 감
- **해결**: 기존 커스텀 템플릿 삭제 후 재업로드 (업로드 시 group 자동 부여)
- **시스템 템플릿**: seed 스크립트(`backend/scripts/seed_templates.py` 또는 startup 로직)에 group 추가 필요
- 런타임 group 추론 코드는 과한 것으로 판단하여 제거함

**2. 짧은 입력 처리**
- 3줄 불릿(50자 내외) → body 0/6 실패
- 프론트에서 최소 입력 길이 가이드 필요 ("3줄 이상, 구체적으로 입력해주세요")
- 또는 `fill-fields`에서 content 길이 체크 후 경고 메시지 리턴
- 현재 최소 20자 제한은 있지만 body 생성에는 부족

**3. 시스템 템플릿 seed에 group 추가**
- `_infer_field_meta()` 로직으로 시스템 템플릿 필드에도 group/type/fill 부여
- seed 스크립트 수정 or DB migration 1회 실행

### 고민 중인 것 (미확정)

**4. 챗봇 연동 (추후)**
- 계획: "제안서 써줘" → 짧은 입력 → 에이전트가 meta 수집 질문 → 2턴 대화 → fill-fields 호출
- `_handle_doc_generate()` 수정 필요: 짧은 입력 → collect_meta 응답 타입
- `_extract_meta_from_text()`: regex 기반 meta 추출 (LLM 불필요)
- 당장은 안 함 — 문서 생성 페이지가 잘 되니까 우선순위 낮음

**5. 첨부자료 필드 처리**
- 첨부자료가 body group으로 분류되는 경우가 있음 → body 채움률에 영향
- `_is_skippable()`이 sLLM 전달 시 제외는 하지만, 프론트에서 "입력 필요"로 보임
- body group 분류 시 첨부 관련 필드를 meta로 강제하는 것도 방법

**6. 구어체 입력 품질**
- 현재 구어체 → sLLM 직접 전달이 잘 되긴 하지만
- 극단적으로 짧거나 정보가 모호한 경우 body 생성 품질이 떨어질 수 있음
- 파인튜닝 재학습 없이는 한계 — v4 학습 데이터에 구어체 샘플 추가 고려

---

## 파이프라인 구조도 (참고)

```
[프론트 — 문서 생성 페이지]
│
│  meta: 사용자 직접 입력 (2열 폼, auto-fill)
│  body: freeText textarea + "AI 문서 작성" 클릭
│
│  POST /fill-fields { template_id, content, meta_values }
│
▼
[백엔드 — fill_fields()]
│
│  1. DB 템플릿 로드 → fields (각 필드에 group: meta/body)
│  2. 필드 분리: meta_fields / body_fields
│
├─── Phase 0 (규칙, LLM 없음) ──┐
│    작성일→today                 │
│    담당자→user.name             │
│    부서→user.team               │
│    (fallback 전용)              │
│                                 │
├─── sLLM (LoRA v3_generate) ────┤
│    body 필드만 전달 (≤12개)     │
│    학습 형식 그대로              │
│    정규화 없음                   │
│                                 │
▼                                 │
[병합]                            │
  meta: meta_values > Phase 0 > null
  body: sLLM > null
│
▼
{ fields, data, model_name } → 프론트
│
▼
[프론트 — 결과]
  meta: 값 표시 (편집 가능)
  body: AI 생성 값 표시 ([AI] 태그, 편집 가능)
  빈 필드: [입력 필요] 주황 강조
│
▼
[문서 생성 (DOCX)] → formData(meta) + bodyData(body) 병합 → /generate
```

---

## 내일 이어서 할 작업 순서 (추천)

1. `git pull origin feat/jiyong` (이 커밋 받기)
2. 시스템 템플릿 seed에 group 추가 → DB 업데이트
3. 레거시 커스텀 템플릿 삭제 → 재업로드 테스트
4. 짧은 입력 가이드 UI 추가
5. (여유 있으면) 챗봇 연동 검토
