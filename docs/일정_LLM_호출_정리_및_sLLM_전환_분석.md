# 일정 관련 LLM 호출 정리 및 sLLM 전환 분석

> 작성일: 2026-03-13 | 작성자: 윤경은 (AI서브)

## 개요

일정(Schedule) 관련 기능에서 LLM을 호출하는 곳은 **4개 영역, 총 10개 호출**이 존재한다.
모두 `get_llm()` 팩토리 → `json_mode=True` → 낮은 temperature(0.3~0.4)를 사용하며,
구조화된 JSON 출력이라 sLLM(파인튜닝) 전환에 적합한 구조이다.

---

## 1. 챗봇 일정/태스크/결재 파싱 (schedule_agent.py)

챗봇에서 사용자가 자연어로 요청하면 → 구조화 JSON으로 파싱하는 LLM 호출.

| # | 함수 | 하는 일 | 예시 입력 | 출력 JSON | temp | fallback |
|---|------|---------|----------|----------|------|----------|
| 1 | `_parse_schedule_input()` | 일정 생성 파싱 | "내일 3시 회의 잡아줘" | title, start_time, end_time, include_meet | 0.3 | regex 기반 |
| 2 | `_parse_view_request()` | 일정 조회 파싱 | "이번 주 일정 보여줘" | time_min, time_max, schedule_type | 0.3 | 키워드 기반 |
| 3 | `_parse_pipeline_input()` | 태스크 생성 파싱 | "프론트엔드 태스크 추가해줘" | title, assignee, stage, priority, due_date, project | 0.3 | 키워드 기반 |
| 4 | `_parse_approval_input()` | 결재 요청 파싱 | "연차 신청해줘" | type, title, detail, target_team | 0.3 | 키워드 기반 |

- 프롬프트: 전부 **인라인 시스템 프롬프트** (prompts.py 상수가 아님)
- `action_agent.py`에 #3, #4 동일 로직 중복 존재 (schedule_agent에 병합 완료, action_agent는 그래프에서 제거됨)

---

## 2. 대시보드 AI 추천 (approvals.py)

Approvals 페이지 "New Tasks" 탭에서 태스크/일정/결재를 AI로 추천하는 기능.

| # | 함수 | 프롬프트 상수 | 하는 일 | temp | fallback |
|---|------|-------------|---------|------|----------|
| 5 | `generate_checklist()` | `SCHEDULE_CHECKLIST_SYSTEM_PROMPT` | 태스크+일정 분석 → 오늘 할 일 체크리스트 생성 | 0.3 | rule-based |
| 6 | `suggest_schedules()` | `SCHEDULE_SUGGEST_SYSTEM_PROMPT` | 현재 상태 분석 → 일정 추천 (회의, 리뷰, 마일스톤 등) | 0.4 | rule-based |
| 7 | `suggest_approvals()` | `APPROVAL_SUGGEST_SYSTEM_PROMPT` | 현재 상태 분석 → 결재 요청 추천 (연차, 배포승인 등) | 0.4 | rule-based |

- 프롬프트: `ai/llm/prompts.py`에 상수로 정의됨
- max_tokens: 1500
- 3개 모두 **rule-based fallback** 있음 → LLM 실패해도 서비스 정상 동작

---

## 3. Sheets WBS 생성 (sheets_service.py)

프로젝트 내보내기 시 AI가 계층적 WBS를 자동 생성하여 Google Sheets "WBS" 탭에 작성.

| # | 함수 | 프롬프트 상수 | 하는 일 | temp | fallback |
|---|------|-------------|---------|------|----------|
| 8 | `_generate_wbs_tab()` | `WBS_GENERATE_SYSTEM_PROMPT` | 태스크 목록 → 3레벨 계층 WBS JSON 생성 | 0.3 | 없음 (실패 시 WBS 탭 미생성) |

- 출력: Level 1(단계) → Level 2(워크 패키지) → Level 3(개별 태스크) 중첩 JSON
- Google Sheets에 레벨별 색상 포맷팅 적용 (L1 진한 파란, L2 연한 파란, L3 흰색)

---

## 전체 요약 테이블

| # | 영역 | 함수 | 용도 | temp | json_mode | fallback | sLLM 전환 가능성 |
|---|------|------|------|------|-----------|----------|-----------------|
| 1 | 챗봇 파싱 | `_parse_schedule_input` | 일정 생성 파싱 | 0.3 | YES | YES | **HIGH** |
| 2 | 챗봇 파싱 | `_parse_view_request` | 일정 조회 파싱 | 0.3 | YES | YES | **HIGH** |
| 3 | 챗봇 파싱 | `_parse_pipeline_input` | 태스크 생성 파싱 | 0.3 | YES | YES | **HIGH** |
| 4 | 챗봇 파싱 | `_parse_approval_input` | 결재 요청 파싱 | 0.3 | YES | YES | **VERY HIGH** |
| 5 | AI 추천 | `generate_checklist` | 할 일 체크리스트 | 0.3 | YES | YES | **HIGH** |
| 6 | AI 추천 | `suggest_schedules` | 일정 추천 | 0.4 | YES | YES | **HIGH** |
| 7 | AI 추천 | `suggest_approvals` | 결재 추천 | 0.4 | YES | YES | **HIGH** |
| 8 | Sheets | `_generate_wbs_tab` | WBS 자동 생성 | 0.3 | YES | NO | **MEDIUM-HIGH** |

---

## sLLM 전환 분석

### 공통 특성 (전환에 유리한 점)

1. **전부 json_mode=True** — 출력 스키마가 고정, 학습 데이터 생성 용이
2. **낮은 temperature (0.3~0.4)** — 결정적 작업, 창의성 불필요 → 작은 모델로 충분
3. **8/10에 fallback 존재** — sLLM 품질 부족해도 서비스 영향 최소화
4. **기존 인프라 활용 가능** — `get_llm()` → `create_llm(provider="vllm")` 교체만 하면 됨

### 전환 우선순위

#### Phase 1: 바로 전환 가능 (데이터 수집 쉬움)

| 대상 | 이유 |
|------|------|
| **결재 파싱 (#4)** | type이 10개 enum 분류, 가장 단순한 구조 |
| **체크리스트 (#5)** | 출력 스키마 명확 (category 5종, priority 3종) + fallback |
| **일정 추천 (#6)** | 출력 스키마 명확 (schedule_type 5종) + fallback |
| **결재 추천 (#7)** | 출력 스키마 명확 (type 12종) + fallback |

- 학습 데이터: 각 500~1,000건 JSONL
- 방식: Kanana-1.5-8B + QLoRA (판단 LoRA와 동일 방식)

#### Phase 2: 데이터 더 필요

| 대상 | 이유 |
|------|------|
| **일정 파싱 (#1)** | 날짜/시간 파싱이 복잡 ("내일", "다음주 월요일 3시" 등) |
| **조회 파싱 (#2)** | 상대적 시간 표현 해석 필요 |
| **태스크 파싱 (#3)** | stage/priority 추론이 포함 |

- 학습 데이터: 각 1,000~2,000건 (날짜 표현 다양성 확보 필요)

#### Phase 3: 후순위

| 대상 | 이유 |
|------|------|
| **WBS 생성 (#8)** | 계층 JSON 구조가 복잡, 학습 데이터 만들기 까다로움 |

- LLM API 유지 또는 충분한 데이터 확보 후 전환 검토

### 전환 전략

```
1. 현재 LLM API 호출에서 input/output 로깅 (실사용 데이터 수집)
2. Phase 1 대상으로 JSONL 학습 데이터 생성
3. Kanana-1.5-8B QLoRA 파인튜닝 (judgment LoRA v1과 동일 방식)
4. get_llm() → create_llm(provider="vllm") 교체
5. A/B 테스트: LLM API vs sLLM 정확도 비교
6. fallback 있는 기능부터 점진적 교체
```

### 현재 진행 상황

- `scripts/test_schedule_sllm.py` 작성 완료 (10개 테스트 케이스)
- GPT-4o-mini 기준 파싱 안정적 확인
- RunPod에서 Kanana-8B base model로 비교 테스트 예정

---

## 관련 파일

| 파일 | 내용 |
|------|------|
| `ai/agents/schedule_agent.py` | 챗봇 파싱 LLM 호출 (#1~#4) |
| `ai/agents/action_agent.py` | 구 파싱 로직 (schedule_agent에 병합됨, 그래프에서 제거) |
| `backend/app/api/v1/approvals.py` | AI 추천 LLM 호출 (#5~#7) |
| `backend/app/services/sheets_service.py` | WBS 생성 LLM 호출 (#8) |
| `ai/llm/prompts.py` | 프롬프트 상수 (SCHEDULE_CHECKLIST, SCHEDULE_SUGGEST, APPROVAL_SUGGEST, WBS_GENERATE) |
| `ai/llm/factory.py` | LLM 팩토리 (openai/anthropic/vllm 전환) |
| `scripts/test_schedule_sllm.py` | sLLM 전환 테스트 스크립트 |
