# API 스키마 정의 작업 정리

> 작성: 신지용 (PM) | 날짜: 2025-02-10

## 왜 이 작업을 했는가

팀원들이 각자 기능을 개발할 때 **프론트 ↔ 백엔드 ↔ AI 사이에 주고받는 데이터 형식**이 정해져 있어야 합니다.
스키마가 없으면 각자 다른 형식으로 만들어서 나중에 통합할 때 전부 고쳐야 합니다.

PM이 스키마를 먼저 정의해서 → 팀원들이 이 형식에 맞춰 개발하도록 하는 것이 목적입니다.


## 수정한 파일 목록 (8개 + 1개)

### 1. `backend/app/schemas/chat.py` — 챗봇 통신

| 클래스 | 역할 |
|--------|------|
| `ChatRequest` | 프론트가 백엔드에 보내는 채팅 메시지 |
| `SSEIntentEvent` | 어떤 Agent가 처리하는지 알려주는 이벤트 |
| `SSETokenEvent` | 응답 글자가 한 글자씩 오는 스트리밍 이벤트 |
| `SSEResultEvent` | 최종 결과 (카드 UI에 표시할 데이터) |
| `SSEDoneEvent` | 스트리밍 끝 |
| `SSEErrorEvent` | 에러 발생 시 |

**추가한 것:**
- `ChatRequest`에 `template_id`, `template_type` 필드 — 문서/회의록 페이지에서 어떤 템플릿 쓸지 지정
- Agent별 Result 데이터 모델 5개 (`JudgmentResultData`, `MeetingResultData`, `DocGenerateResultData`, `DocSearchResultData`, `ScheduleAddResultData`) — 프론트가 intent별로 어떤 데이터가 오는지 알 수 있도록

### 2. `backend/app/schemas/meeting.py` — 회의록

| 클래스 | 역할 |
|--------|------|
| `MeetingCreate` | 회의 생성 요청 |
| `MeetingGenerateRequest` | 회의 내용 텍스트 → AI가 회의록 생성 |
| `MeetingGenerateResponse` | 생성된 회의록 (요약 + 결정사항 + Action Items + 미리보기) |

**추가한 것:**
- `GeneratedActionItem` — AI가 생성한 Action Item 구조 (content, assignee, due_date)
- `DetectedRisk` — AI가 감지한 리스크 항목 (description, regulation, level)
- `meeting_date`를 `str` → `datetime`으로 통일

### 3. `backend/app/schemas/document.py` — 문서 생성/검색/요약

| 클래스 | 역할 |
|--------|------|
| `DocumentGenerateRequest` | 템플릿 기반 문서 생성 요청 |
| `DocumentGenerateResponse` | 생성된 문서 (미리보기 + 다운로드 URL) |
| `DocumentSearchResult` | 문서 검색 결과 (하이라이트 포함) |
| `DocumentSummarizeRequest` | 문서 요약 요청 (파일 업로드 or 기존 문서) |
| `DocumentSummarizeResponse` | 요약 결과 (필드별 요약 + 미리보기) |

**추가한 것:**
- `DocumentSummarizeRequest`에 입력 검증 — `template_type`과 `custom_fields` 동시 지정 불가 (어느 쪽이 우선인지 모호해지므로)
- `highlights` 타입 명시 (`list` → `list[dict]`)

### 4. `backend/app/schemas/auth.py` — 인증

| 클래스 | 역할 |
|--------|------|
| `LoginRequest` / `LoginResponse` | 로그인 |
| `RegisterRequest` / `RegisterResponse` | 회원가입 |
| `PasswordResetRequest` / `PasswordResetConfirm` | 비밀번호 재설정 |

**수정한 것:**
- `email: str` → `email: EmailStr` — 이메일 형식 자동 검증 (예: `abc` 입력하면 바로 에러)

### 5. `backend/app/schemas/admin.py` — 관리자

| 클래스 | 역할 |
|--------|------|
| `SystemStatsResponse` | 대시보드 통계 (유저 수, 문서 수, 질의 수 등) |
| `QueryLogResponse` / `QueryLogListResponse` | 질의 로그 목록 (페이지네이션) |
| `TopQueryItem` / `TopQueryResponse` | 인기 질의 통계 |

**수정한 것:**
- `created_at: str` → `datetime` — 다른 스키마와 타입 통일

### 6. `backend/app/schemas/google_services.py` — Google 연동

| 클래스 | 역할 |
|--------|------|
| `GoogleConnectRequest` | OAuth 연결 |
| `TaskSyncRequest` / `TaskSyncResponse` | Google Tasks 동기화 |
| `SendReminderRequest` / `SendMeetingInviteRequest` | Gmail 발송 |
| `SheetCreateRequest` / `SheetSyncRequest` | Sheets 연동 |
| `EventWithMeetRequest` / `EventWithMeetResponse` | Calendar + Meet |
| `GoogleServicesResult` | 전체 연동 결과 요약 |

**추가/수정한 것:**
- `EmailSendResultItem` — 개별 메일 발송 결과 (recipient, success, error)
- 시간 필드 `str` → `datetime` 4곳 통일

### 7. `backend/app/schemas/schedule.py` — 일정 (변경 없음)

이미 `datetime` 타입 사용 중. 수정 불필요.

### 8. `ai/agents/state.py` — AI Agent 공유 상태

모든 Agent가 공유하는 데이터 구조. Agent 간 데이터를 주고받을 때 이 형식을 따릅니다.

| 필드 | 타입 | 용도 |
|------|------|------|
| `user_input` | `str` | 사용자 입력 텍스트 |
| `user_id` | `int` | 사용자 ID |
| `intent` | `str` | 분류된 의도 (7종) |
| `confidence` | `float` | 분류 신뢰도 |
| `context` | `list[str]` | RAG 검색된 문서 chunk |
| `agent_response` | `dict` | Agent가 생성한 응답 |
| `chat_history` | `list[dict]` | 대화 이력 |
| `template_id` | `Optional[int]` | 사용할 템플릿 ID |
| `source_page` | `Optional[str]` | 요청 출처 페이지 |
| `template_fields` | `Optional[list[str]]` | 동적 템플릿 필드 목록 |
| `extracted_text` | `Optional[str]` | 파일에서 추출된 텍스트 |
| `google_services_result` | `Optional[dict]` | Google 서비스 연동 결과 |

**수정한 것:**
- `context: list` → `list[str]`
- `chat_history: list` → `list[dict]`
- `template_fields: Optional[list]` → `Optional[list[str]]`


## QA에서 발견하고 수정한 문제 (총 9건)

| # | 문제 | 수정 |
|---|------|------|
| 1 | `dict`/`Any` 타입 — 프론트가 구조를 모름 | Agent별 Result 타입 모델 추가 |
| 2 | 날짜 `str` vs `datetime` 혼재 | 전부 `datetime` 통일 |
| 3 | `template_fields: list` 너무 느슨 | `list[str]` 지정 |
| 4 | `template_type`과 `custom_fields` 동시 입력 시 모호 | `model_validator`로 상호배타 검증 |
| 5 | `List[str]` vs `list[str]` 혼재 | 전부 소문자 `list` 통일 |
| 6 | `ChatRequest`에 템플릿 지정 방법 없음 | `template_id`, `template_type` 필드 추가 |
| 7 | `EmailStr` import 후 미사용 | 이메일 필드 4곳에 `EmailStr` 적용 |
| 8 | `highlights: list` untyped | `list[dict]` 지정 |
| 9 | `context`, `chat_history` untyped | `list[str]`, `list[dict]` 지정 |


## 팀원별 참고사항

| 팀원 | 주로 볼 스키마 | 해야 할 것 |
|------|---------------|------------|
| **경은** (AI Lead) | `state.py`, `chat.py` Result 모델들 | Agent 구현 시 이 타입에 맞춰 응답 생성 |
| **승언** (AI Sub) | `meeting.py`, `document.py` | 회의록/문서 Agent가 `GeneratedActionItem`, `DetectedRisk` 구조로 리턴 |
| **혜빈** (Backend) | 전체 schemas | API 엔드포인트에서 이 스키마를 request/response 모델로 사용 |
| **지영** (Frontend) | `chat.py` SSE 이벤트, Result 모델 | SSE 파싱 + intent별 카드 UI 렌더링 |
