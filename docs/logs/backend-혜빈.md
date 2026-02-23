# 작업 로그 — 안혜빈 (Backend)

> 세션 종료 시 Claude가 자동으로 업데이트합니다.

---

## 2026-02-11 (세션 1~2)

### 한 일

**#19 DB 스키마 확정 + Alembic 마이그레이션**
- Docker Compose로 PostgreSQL 16 + Redis 7 로컬 실행
- 11개 모델 전체 리뷰 및 수정
  - nullable 필드 타입 어노테이션 `Mapped[Optional[...]]`로 통일
  - TimestampMixin `default` → `server_default` 변경
- PM 피드백 반영: `chat_logs`에 `session_id` 추가, `action_items`에 `assignee_id` FK 추가, `meetings.decisions` + `judgments.regulations_cited` TEXT → JSONB 변환
- Alembic 초기 마이그레이션 생성 및 적용 (11개 테이블)
- 스키마 변경 마이그레이션 생성 및 적용 (JSONB USING 절 포함)
- `docs/ERD.md` Mermaid 다이어그램 작성 (develop에도 push)

**#20 JWT 인증 시스템**
- `app/core/security.py` 구현: JWT 생성/검증, bcrypt 해싱, AES-256 암호화(Fernet)
- `app/api/deps.py` 구현: `get_current_user`, `get_admin_user` 의존성
- `app/api/v1/auth.py` 구현: 회원가입, 로그인, /me, 비밀번호 재설정 (request/confirm)
- `app/schemas/auth.py` 스키마 작성
- curl로 전체 API 테스트 완료 (register, login, me, password-reset)
- `bcrypt==4.1.3` 핀, `greenlet` 설치로 호환성 문제 해결

**#20 Google OAuth 연결 (진행 중)**
- `app/services/google_base_service.py` 구현: GoogleBaseService 클래스 (토큰 조회/갱신, scope 검증, Credentials 생성)
- `app/api/v1/google_connect.py` 구현: 4개 엔드포인트 (status/connect/callback/disconnect)
  - state 파라미터 Fernet 암호화로 CSRF 방지
  - httpx 비동기 토큰 교환
  - scope 병합 로직 (기존 + 신규)
- Google Cloud Console에서 OAuth 2.0 클라이언트 생성 및 `.env` 설정 완료

### 다음 할 일
- google-auth 관련 패키지 설치 (`google-api-python-client`, `google-auth`, `google-auth-oauthlib`) 후 서버 기동 확인
- Google OAuth 플로우 실제 테스트 (브라우저에서 /connect → callback)
- 나머지 Google Services 서브클래스 구현 (Calendar, Tasks, Gmail, Sheets)
- 문서 업로드 API + 텍스트 추출 연동

---

## 2026-02-11 (세션 3~4)

### 한 일

**프론트-백엔드 연동 수정**
- `FRONTEND_URL` 설정 추가 (config.py, .env) — Google OAuth 리다이렉트 URL 동적 처리
- `authStore.js`에 `initialize()` 추가 — 페이지 새로고침 시 `/auth/me` 호출로 로그인 유지
- `App.jsx`에서 초기화 완료 전까지 라우팅 대기 로직 추가
- 비밀번호 재설정 스키마(`PasswordResetConfirm`) 프론트엔드와 필드명 맞춤 (`token`, `new_password`)
- `GoogleStatusResponse`에 `email` 필드 추가

**#20 Google 소셜 로그인 구현**
- `auth.py`에 `GET /auth/google`, `GET /auth/google/callback` 2개 엔드포인트 추가
- Google OAuth → userinfo 조회 → 자동 회원가입 → JWT 발급 → 프론트엔드 리다이렉트
- `LoginPage.jsx`에서 URL 파라미터로 토큰 수신 후 로그인 처리
- 실제 테스트 완료 (Google 로그인 → 대시보드 이동 확인)

**#21 #33 Google Services 구현 + 테스트**
- Google Services 4개 서브클래스 완성: Calendar, Tasks, Gmail, Sheets
- API 라우터 전체 연결 (calendar, tasks, gmail, sheets)

**Google Tasks 양방향 동기화 테스트 + 버그 수정**
- 테스트 데이터 삽입 (회의 1건 + Action Item 4건)
- `list_tasks` 리팩토링: Google API 직접 조회 → DB 기반 조회 + 프론트엔드 호환 필드 반환
- `sync_action_item` 버그 수정: Google Tasks update 시 `task_body["id"]` 누락 → 추가
- `pull_status` 개선: `showHidden=True` 추가 + Google에서 새로 추가한 Task → DB import 로직 추가
- `action_items.meeting_id` nullable 변경 (ALTER TABLE + 모델 수정) — Google에서 직접 추가한 Task 저장 가능
- Push/Pull 양방향 동기화 테스트 완료

**Google Sheets 테스트**
- Sheets 탭에서 스프레드시트 생성 + Action Items 동기화 확인

### 다음 할 일
- Google Calendar 이벤트 Push/Pull 테스트 (Meet 링크 생성 포함)
- Gmail 알림 메일 발송 테스트
- 전체 Google Services 안정화 후 커밋 정리
- 문서 업로드 API + 텍스트 추출 연동

---

## 2026-02-12 (세션 5)

### 한 일

**문서 업로드 API + 텍스트 추출 연동 구현**
- `backend/app/config.py`에 `UPLOAD_DIR: str = "./uploads"` 추가
- `backend/requirements.txt`에 `PyMuPDF==1.25.2` 추가
- `backend/app/services/document_service.py` 전면 구현:
  - `save_file()`: UploadFile → 디스크 저장 (UUID 파일명)
  - `extract_text()`: PDF/DOCX/TXT 텍스트 추출 (PyMuPDF, python-docx)
  - `upload_and_parse()`: 업로드 → 추출 → DB 저장 (동기 처리)
  - `list_documents()`: scope/keyword 필터, 본인 개인문서 + 회사문서 조회
  - `get_document()`: 문서 상세
  - `delete_document()`: 파일 + DB 레코드 삭제
- `backend/app/services/parsing_service.py` 구현:
  - `get_parsing_status()`: DB status 기반 파싱 상태 조회 (프론트 폴링용)
  - status: processing → parsing(50%) → completed(100%)
- `backend/app/services/template_service.py` 구현:
  - `_build_system_templates()`: 시스템 기본 4종 (회의록/보고서/JD/제안서) 반환 (음수 ID로 구분)
  - `list_templates()`: 시스템 4종 + DB 커스텀 템플릿 병합 조회
  - `get_template()`: 템플릿 상세 (시스템/커스텀 분기)
  - `delete_template()`: 커스텀만 삭제 가능, 시스템 템플릿 보호
  - `generate_document()`, `download_document()`: AI 연동 필요 (NotImplementedError 유지)
- `backend/app/api/v1/documents.py` 11개 엔드포인트 전면 구현:
  - ✅ `POST /upload`: 파일 업로드 + 텍스트 추출
  - ✅ `GET /`: 문서 목록 (scope, keyword 필터)
  - ✅ `GET /{id}`: 문서 상세
  - ✅ `DELETE /{id}`: 문서 삭제
  - ✅ `GET /{id}/parsing-status`: 파싱 상태 조회
  - ✅ `GET /templates/`: 템플릿 목록 (시스템 4종 + 커스텀)
  - ✅ `GET /templates/{id}`: 템플릿 상세
  - ✅ `DELETE /templates/{id}`: 커스텀 템플릿 삭제
  - 🔄 `POST /generate`: AI 필요 (501 반환)
  - 🔄 `GET /{id}/download`: AI 필요 (501 반환)
  - 🔄 `GET /search/highlight`: RAG 필요 (501 반환)
  - 🔄 `POST /templates/upload`: AI 구조추출 필요 (501 반환)
- **라우트 순서 수정**: 정적 경로(`/search`, `/templates`) → 동적 경로(`/{document_id}`)로 재배치 (FastAPI 매칭 우선순위 보장)

**Python 3.13 호환성 업데이트**
- `requirements.txt` 전체 패키지 최신 버전으로 업데이트 (40+ 패키지):
  - FastAPI: 0.115.0 → 0.115.6
  - SQLAlchemy: 2.0.35 → 2.0.36
  - Pydantic: 2.9.0 → 2.10.6
  - PaddleOCR: 2.8.0 → 3.4.0
  - 기타 주요 패키지 업그레이드
- **타입 힌트 모던화 (PEP 604)**: `Optional[T]` → `T | None` 변경
  - `document_service.py`, `template_service.py`, `documents.py` 전체 적용
  - `typing.Optional` import 제거
- Python 3.13.7에서 구문 검증 완료 (py_compile)
- 전체 의존성 패키지 설치 완료 (80+ 패키지)

### 다음 할 일
- 문서 업로드/목록/삭제 API curl 테스트
- AI 연동 엔드포인트(generate, download, search, template upload)는 팀원 C(승언) 작업 후 연동
- Google Calendar/Gmail 테스트 완료 후 전체 커밋

---

## 2026-02-12 (세션 6)

### 한 일

**프론트엔드 문서 관리 연동**
- `frontend/src/pages/DocumentsPage.jsx` 수정:
  - `handleUpload()`: 파일 업로드 후 status 체크하여 사용자에게 적절한 피드백 제공
  - `loadDocuments()`: 문서 목록 자동 로드 및 첫 번째 문서 자동 선택
  - `handleSelectDoc()`: 문서 상세 정보 API 호출 및 표시
  - `handleDeleteDoc()`: 문서 삭제 기능
  - 실제 업로드된 문서와 Mock 데이터 병합 표시
- `frontend/src/components/documents/DocumentDetail.jsx` 수정:
  - 실제 문서 내용(content) 표시
  - Mock 데이터와 실제 데이터 구분하여 렌더링

**문서 업로드 버그 수정**
- **TXT 파일 UTF-16 인코딩 오류 해결**:
  - `document_service.py`의 `_extract_txt()` 함수에 다중 인코딩 지원 추가
  - 인코딩 순서: UTF-8 → UTF-16 → UTF-16-LE → UTF-16-BE → CP949 → EUC-KR → Latin-1
  - 각 인코딩을 순차적으로 시도하여 성공할 때까지 반복
- **PDF 업로드 실패 원인 분석 및 해결**:
  - 문제: 가상환경(.venv)은 Python 3.12 사용, PyMuPDF는 시스템 Python 3.13에만 설치됨
  - 해결: 가상환경을 Python 3.13으로 재생성하고 모든 패키지 재설치
  - 프로세스:
    1. 기존 .venv 삭제
    2. `python3.13 -m venv .venv`로 Python 3.13 가상환경 생성
    3. `pip install -r requirements.txt`로 전체 패키지 설치
    4. PyMuPDF 1.25.2 정상 설치 확인
- `/tmp/upload_debug.log`에 디버깅 로그 추가하여 문제 추적

**인증 시스템 버그 수정**
- **bcrypt 버전 호환성 문제 해결**:
  - 문제: passlib 1.7.4가 bcrypt 5.0.0과 호환되지 않아 회원가입/로그인 시 `ValueError: password cannot be longer than 72 bytes` 발생
  - 원인: Python 3.13 가상환경 재생성 시 bcrypt 5.0.0이 자동 설치됨
  - 해결: bcrypt를 4.0.1로 다운그레이드 (`pip install bcrypt==4.0.1`)
  - `requirements.txt`에 `bcrypt==4.0.1` 명시적으로 추가하여 버전 고정
- **회원가입/로그인 테스트 완료**:
  - curl로 `/auth/register` 테스트 성공
  - curl로 `/auth/login` 테스트 성공 (JWT 토큰 발급 확인)
  - Google 로그인 준비 완료

**팀원 계정 관리**
- `scripts/seed_data.py` 완전 구현:
  - 팀원 5명 + 테스트 계정 자동 생성 스크립트
  - 팀원 정보: 신지용(PM, 관리자), 윤경은, 진승언, 안혜빈, 문지영
  - 기본 비밀번호: `test1234`
  - 이메일 형식: `[이름]@example.com`
  - 중복 체크 로직 포함 (이미 존재하는 계정은 스킵)
- 팀원들이 각자 회원가입할 수 있도록 안내

**Git 저장소 관리**
- `.gitignore`에 `backend/uploads/` 추가:
  - 사용자 업로드 파일을 git 추적에서 제외
  - 저장소 크기 증가 방지 및 민감 정보 보호
  - 각 환경에서 독립적으로 uploads 디렉토리 관리

**커밋 및 배포**
- 총 3개 커밋 생성 및 push:
  1. `feat: 문서 업로드 API + 텍스트 추출 완전 구현 #8` (bdb7ac4)
     - 문서 업로드 API 8개 엔드포인트 구현
     - 프론트엔드 연동
     - Python 3.13 호환성 업데이트
  2. `fix: bcrypt 버전 호환성 문제 해결 + 시드 스크립트 구현 #8` (c04a1f7)
     - bcrypt 4.0.1로 버전 고정
     - seed_data.py 완성
  3. `chore: uploads 디렉토리를 .gitignore에 추가` (0e561f2)
     - uploads 디렉토리 git 추적 제외

**테스트 및 검증**
- ✅ TXT 파일 업로드 (UTF-8, UTF-16 모두 성공)
- ✅ PDF 파일 업로드 및 텍스트 추출 (PyMuPDF 정상 작동)
- ✅ 문서 목록 조회 (scope, keyword 필터 동작)
- ✅ 문서 상세 조회 (content 표시)
- ✅ 문서 삭제 (파일 + DB 레코드 삭제)
- ✅ 회원가입 API (bcrypt 4.0.1)
- ✅ 로그인 API (JWT 발급)
- ✅ 서버 정상 작동 (Python 3.13 + 모든 의존성)

### 이슈 및 해결

**이슈 1: PDF 업로드 실패**
- 증상: PDF 파일 업로드 시 "성공" 팝업이 뜨지만 실제로는 status='failed'
- 원인: PyMuPDF가 Python 3.13에만 설치되고 가상환경(Python 3.12)에는 없음
- 해결: 가상환경을 Python 3.13으로 재생성

**이슈 2: 회원가입/로그인 500 에러**
- 증상: `/auth/register` 호출 시 `Internal Server Error` 발생
- 원인: passlib 1.7.4가 bcrypt 5.0.0과 호환되지 않음
- 해결: bcrypt를 4.0.1로 다운그레이드하고 requirements.txt에 명시

**이슈 3: UTF-16 TXT 파일 업로드 실패**
- 증상: UTF-16 인코딩 TXT 파일 업로드 시 `UnicodeDecodeError`
- 원인: UTF-8로만 읽기 시도
- 해결: 다중 인코딩 fallback 로직 추가

### 다음 할 일
- DOCX 파일 업로드 테스트 (python-docx) - 완료
- 팀원들에게 개발 환경 세팅 가이드 공유 (Python 3.13, 의존성 설치) - 완료
- AI 연동 엔드포인트는 팀원 C(승언) 작업 대기
- Google Calendar/Gmail 추가 테스트

---

## 2026-02-15 (세션 7)

### 한 일

**#22 schedule_agent 완성**
- `ai/agents/schedule_agent.py` 정리 및 완성:
  - 중복 라인 정리 (docstring, import, logger 중복 제거)
  - Import 경로 수정: `backend.app.*` → `app.*` (sys.path에 backend 추가하여 AI 모듈에서 backend import 가능하게)
  - `_handle_schedule_add()`: 자연어 → Solar API 파싱 → Google Calendar 등록
  - `_handle_schedule_view()`: 자연어 → Solar API 파싱 → Google Calendar 조회
  - Mock 응답 지원 (API 키 없을 때)
- 커밋: `feat: schedule_agent 완성 #22` (1de1c24)

**#33 Google Services 전체 테스트 완료**
- Google Calendar Push/Pull 테스트:
  - ✅ `POST /calendar/sync` — 이벤트 생성 성공
  - ✅ `GET /calendar/events` — 이벤트 조회 성공
  - ✅ `POST /calendar/event-with-meet` — **Meet 링크 자동 생성 성공**
- Gmail 테스트:
  - ✅ `POST /gmail/send-meeting-invite` — **회의 초대 메일 발송 성공**
- Google Services 5개 전체 정상 동작 확인:
  - ✅ Calendar (Push/Pull/Meet)
  - ✅ Tasks (양방향 동기화)
  - ✅ Gmail (초대 메일 발송)
  - ✅ Sheets (스프레드시트 생성 + 동기화)

**일정 추가 시 Meet + Gmail 연쇄 호출 구현**
- `frontend/src/pages/SchedulesPage.jsx` 수정:
  - `sendMeetingInvite` import 추가 (`api/google.js`)
  - `handleAddSchedule`에서 Meet 토글 ON 시:
    1. `createEventWithMeet()` 호출 → meet_link 받기
    2. 참석자 이메일이 있으면 → `sendMeetingInvite()` 자동 호출
  - Gmail scope 없으면 메일 발송 건너뜀
  - 중복 `fetchCalendarEvents()` 호출 제거
- 커밋: `feat: 일정 추가 시 Meet 링크 생성 + 참석자 초대 메일 자동 발송 #33` (c4c3b52)
- develop push 완료

### 다음 할 일
- `schedule_service.py`의 `create_with_google_services()` 구현 (Calendar + Tasks + Gmail + Sheets 통합 오케스트레이션)
- `schedules.py` API 4개 엔드포인트 구현 (일정 CRUD)
- AI 연동 엔드포인트는 팀원 C(승언) 작업 대기

---

## 2026-02-19 (세션 8)

### 한 일

**`create_tables.py` 구문 오류 수정**
- `from app.models` 불완전한 import → `import app.models  # noqa: F401`로 수정
- `app/models/__init__.py`에서 11개 모델 전부 import하므로 한 줄로 모두 등록

**`schedules.py` CRUD API 구현 확인**
- 4개 엔드포인트 정상 동작 확인:
  - `GET /schedules/` — 본인 일정 목록 조회
  - `POST /schedules/` — 일정 생성 (Google Services 통합 오케스트레이션 포함)
  - `PUT /schedules/{id}` — 일정 수정
  - `DELETE /schedules/{id}` — 일정 삭제
- `schedule_service.py`의 `create_with_google_services()` 구현 완료:
  - Calendar + Tasks + Gmail + Sheets 통합 오케스트레이션
  - `calculate_priority()`: 마감일 기반 우선순위 자동 설정

**`meetings.py` CRUD API 구현**
- `meeting_service.py` 기존 빈 클래스 → 함수형으로 전면 재구현:
  - `list_meetings(db, user_id)` — 본인 회의 목록 조회
  - `create_meeting(db, user_id, data)` — 회의 생성
  - `get_meeting(db, meeting_id, user_id)` — 상세 + Action Items
  - `decisions_to_str(decisions)` — JSONB → str 변환 헬퍼
- `meetings.py` 3개 엔드포인트 구현:
  - `GET /meetings/` — 본인 회의 목록 (MeetingResponse)
  - `POST /meetings/` — 회의 생성
  - `GET /meetings/{meeting_id}` — 상세 + Action Items (MeetingDetailResponse)
  - analyze, generate, download → 501 유지 (승언 연동 예정)

**`admin.py` + `statistics_service.py` 전면 구현**
- `statistics_service.py` 기존 빈 클래스 → 함수형으로 전면 재구현:
  - `_period_start(period)` — daily/weekly/monthly 시작점 계산
  - `get_top_queries(db, period, limit)` — 인기 질의 Top N (GROUP BY + ORDER BY count)
  - `get_dashboard_stats(db, user_id)` — 대시보드 통계 카드 4종 (today_queries, processed_meetings, completed_action_items, risk_alerts)
  - `get_query_logs(db, page, per_page)` — 질의 로그 페이지네이션
- `admin.py` 기존 7개 NotImplementedError → 전부 구현:
  - `GET /admin/users` — 사용자 목록 조회
  - `GET /admin/stats` — 시스템 전체 통계
  - `GET /admin/logs` — 질의 로그 조회
  - `GET /admin/regulations` — 규정 목록 조회
  - `GET /admin/query-logs` — 질의 로그 (UI_UX 추가)
  - `GET /admin/top-queries` — 인기 질의 (월/주/일)
  - `PUT /admin/users/{id}/permissions` — 사용자 권한 변경 (is_admin, is_active)
- 모든 엔드포인트에 `get_admin_user` 의존성 적용 (관리자만 접근 가능)

**DB 관리자 권한 설정**
- 시드 데이터에 관리자 없어서 직접 `UPDATE users SET is_admin=true` 실행
- curl로 admin API 전체 테스트 완료

### 이슈 및 해결

**이슈 1: `create_tables.py` SyntaxError**
- 증상: `from app.models` 구문 불완전
- 해결: `import app.models  # noqa: F401`로 변경

**이슈 2: git push 거부**
- 증상: 다른 팀원이 먼저 push하여 reject
- 해결: `git pull origin develop --rebase` 후 재push

**이슈 3: 패키지 미설치 (langgraph, rank_bm25)**
- 증상: `No module named 'langgraph'`, `No module named 'rank_bm25'`
- 원인: venv에 pip 없어서 패키지 누락
- 해결: `python -m ensurepip` → `pip install -r requirements.txt`

**이슈 4: 포트 충돌**
- 증상: `[Errno 48] address already in use` (포트 8000)
- 해결: `lsof -ti :8000 | xargs kill -9` 후 서버 재시작

### 다음 할 일
- AI 연동 엔드포인트 (승언 문서 Agent 완성 대기): `meetings/analyze`, `meetings/generate`, `documents/generate`, `documents/download`, `documents/search/highlight`
- 지영님 admin 페이지 API 연동 결과 확인
- 4단계 데이터 수집: 문서 생성 200건 (혜빈 담당)

---

## 2026-02-23 (세션 9)

### 한 일

**판단 Agent 스트리밍 수정 시도 (#12)**

수정 파일 3개:
- `ai/llm/prompts.py`: `JUDGMENT_STREAMING_SYSTEM_PROMPT` 추가 (자연어 설명 → JSON 코드블록 2파트 출력 프롬프트)
- `ai/agents/orchestrator.py`: `safe_judgment_agent()` 수정 — stream_mode=True일 때 RAG 검색 + 프롬프트 빌드 후 `stream_pending` 패턴으로 chat.py에 위임 (document_agent와 동일)
- `backend/app/api/v1/chat.py`: judgment_agent 핸들러 교체 — OpenAI API 직접 스트리밍 호출, `` ```json `` 마커 이전 토큰은 실시간 전송, 이후 JSON은 조용히 누적 후 파싱 + 3중 검증

현재 상태: **스트리밍 미동작 (디버깅 필요)**
- 프롬프트/오케스트레이터/chat.py 3파일 수정 완료
- 서버 재시작 후 테스트했으나 여전히 답변이 한번에 표시됨
- 원인 미파악 — 다음 세션에서 백엔드 로그 확인 필요

### 다음 할 일
- 판단 Agent 스트리밍 디버깅 (백엔드 터미널 로그로 토큰 전송 여부 확인)
- AI 연동 엔드포인트 (승언 문서 Agent 완성 대기)
