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

## 2026-02-20 (세션 8.5)

### 한 일

**관리자 규정 CRUD + 사용자 추가/삭제 API 구현 (#29)**
- `backend/app/api/v1/admin.py`에 5개 엔드포인트 추가:
  - `POST /admin/regulations` — 규정 추가
  - `PUT /admin/regulations/{id}` — 규정 수정
  - `DELETE /admin/regulations/{id}` — 규정 삭제
  - `POST /admin/users` — 사용자 추가
  - `DELETE /admin/users/{id}` — 사용자 삭제 (본인 삭제 방지)

**관리자 페이지 프론트엔드 API 연동 (#29)**
- `AdminPage.jsx`: mock 데이터 제거 → 실제 API 호출 (useEffect + Promise.all)
- `UserManagement.jsx`: 사용자 추가/삭제/권한변경 API 연동
- `RegulationManagement.jsx`: 규정 추가/수정/삭제 API 연동
- `SystemStats.jsx`: 인기 질의 (기간별) + 질의 로그 실제 데이터 표시
- `frontend/src/api/admin.js`: 누락 API 함수 추가 (CRUD 전체)

**채팅 로그 저장 구현**
- `backend/app/api/v1/chat.py`: 스트리밍/비스트리밍 양쪽에 `chat_logs` 테이블 저장 로직 추가
- `statistics_service.py`: 타임스탬프 UTC 표시(Z) 추가로 시간차 문제 해결

**403 응답 버그 수정**
- `frontend/src/api/client.js`: 인터셉터에서 401만 토큰 제거 (403은 유지)
- 새로고침/권한 없음 시 로그아웃되는 버그 수정
- `backend/run.sh` 실행 스크립트 추가

### 다음 할 일
- 판단 Agent 스트리밍 디버깅
- AI 연동 엔드포인트 (승언 문서 Agent 완성 대기)

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

---

## 2026-02-24 (세션 10)

### 한 일

**KST 시간 표시 수정 push**
- 이전 세션에서 커밋한 `ChatSessionSidebar.jsx` KST 시간 표시 수정을 `develop` + `feat/backend-혜빈` 양쪽에 push

**채팅 초기화 버그 수정**
- 증상: 채팅 초기화 버튼 누르면 현재 채팅이 초기화되지 않고 새 채팅이 생성됨
- 원인: `chatStore.clearMessages()`가 `createSession()`을 호출
- 수정:
  - `backend/app/api/v1/chat.py`: `DELETE /sessions/{id}/messages` 엔드포인트 추가
  - `frontend/src/api/chat.js`: `clearSessionMessagesAPI()` 함수 추가
  - `frontend/src/store/chatStore.js`: `clearMessages`가 현재 세션 메시지만 초기화하도록 변경

**사용자 팀(부서) 기능 추가**
- 6개 부서: 개발, QA기획, UI/UX, 영업, 마케팅, CS
- `backend/app/models/user.py`: `team` 컬럼 + `TEAMS` 상수 추가
- `backend/app/schemas/auth.py`: `RegisterRequest`, `RegisterResponse`에 `team` 필드 추가
- `backend/app/api/v1/auth.py`: 회원가입 시 `team` 저장
- `backend/app/main.py`: startup에서 `ALTER TABLE ADD COLUMN IF NOT EXISTS` + 기존 사용자 랜덤 배정
- `backend/app/api/v1/admin.py`: `UserCreate` 스키마에 team 추가, 사용자 목록/생성에 team 포함
- `frontend/src/components/auth/RegisterForm.jsx`: 팀 선택 드롭다운 추가 (필수)
- `frontend/src/pages/LoginPage.jsx`: `handleRegister`에 team 전달
- `frontend/src/hooks/useAuth.js`: `register()`에 team 파라미터 추가
- `frontend/src/api/auth.js`: team 파라미터 추가
- `frontend/src/components/admin/UserManagement.jsx`: 6개 부서 옵션으로 변경

**채팅 로그 보존 (관리자용)**
- 증상: 사용자가 채팅 삭제하면 관리자 페이지 > 최근 질의 로그에서도 삭제됨
- 원인: `delete_session`, `clear_session_messages`에서 `ChatLog`도 같이 삭제
- 수정: `chat.py`에서 `ChatLog` 삭제 코드 제거 — `ChatSession`만 삭제, `ChatLog`는 관리자 로그용으로 보존
- 테스트 완료: 사용자 채팅 삭제 후에도 관리자 페이지에서 로그 확인 가능

**관리자 권한/부서 저장 위치 확인**
- PostgreSQL `users` 테이블의 `is_admin`, `is_active`, `team` 컬럼에 저장

**Google Tasks Pull/Push 500 에러 디버깅 (진행 중)**
- 이전 세션(9)에서 `asyncio.to_thread` + `_google_call` 패턴 적용했으나 500 에러
- Calendar은 정상 동작 (동기 호출 패턴) — Tasks만 500
- 시도 1: `tasks_service.py`를 Calendar과 동일한 동기 `.execute()` 패턴으로 복원 → 여전히 500
- 시도 2: `google_base_service.py`의 `_refresh_token`에서 `asyncio.to_thread` 제거 → 여전히 500
- 시도 3: `tasks.py` 엔드포인트에 에러 디테일 try-except 추가 (500 원인 확인용) → response body 비어있음
- **여전히 500 에러 — 원인 미파악**
- 다음 단계: 브라우저 Console에서 `fetch()`로 직접 호출하여 에러 상세 확인 예정

### 다음 할 일
- Google Tasks 500 에러 원인 확인 (Console fetch 테스트 결과 확인)
- 판단 Agent 스트리밍 디버깅
- AI 연동 엔드포인트 (승언 문서 Agent 완성 대기)

---

## 2026-02-25 (세션 11)

### 한 일

**AI 채팅 → 일정 등록 + Meet 링크 + 초대 메일 통합 구현 (#22 #33)**

핵심 목표: 채팅에서 "내일 오후 3시 팀 회의 잡아줘" → 캘린더 등록 + Meet 링크 + 초대 메일까지 한번에 처리

**`ai/agents/schedule_agent.py` 대폭 수정:**
- `_handle_schedule_add()`: `calendar_service.push_event()` → `schedule_service.create_with_google_services(include_meet=True)` 변경
- `_handle_schedule_followup()` 신규 구현: 이전 대화에서 일정 정보 추출 → Meet 링크 생성(`calendar_service.create_event_with_meet()`) → 초대 메일 발송(`gmail_service.send_meeting_invite()`)
- `_fallback_parse()` 추가: Solar LLM이 "YYYY-MM-DD" 리터럴 반환 시 규칙 기반 날짜 파싱 fallback
- `_is_valid_datetime()` 추가: 파싱된 날짜 유효성 검증
- `_parse_schedule_input()` 프롬프트 개선: 구체적 날짜 예시 포함 + `include_meet` 필드 추가
- ScheduleCreate datetime 타입 호환: `datetime.fromisoformat()` 변환 추가
- `_has_schedule_in_history()`, `_extract_last_schedule_from_history()` 헬퍼 추가

**`ai/agents/orchestrator.py` 라우팅 수정:**
- `_is_schedule_followup()` 함수 추가: 이메일 + Meet 키워드 + 이전 schedule_add 대화 감지
- `route_by_intent()`에서 followup 체크를 confidence 체크보다 우선 배치

**`frontend/src/components/chat/ScheduleCard.jsx` UI 확장:**
- `meetLink` prop → 클릭 가능한 Google Meet 참여 링크
- `emailSent`/`emailCount` props → 메일 발송 결과 표시

**`frontend/src/pages/ChatPage.jsx` 수정:**
- `schedule_add` 케이스에서 `data.schedule`, `data.google_services`에서 데이터 추출

**`backend/app/api/v1/chat.py` 수정:**
- `chat_history`를 DB(ChatLog)에서 로드하여 multi-turn 맥락 감지 가능하게
- 중복 `from sqlalchemy import select` import 제거

### 이슈 및 해결

**이슈 1: Solar LLM이 "YYYY-MM-DD" 리터럴 반환**
- 원인: 프롬프트의 포맷 예시를 그대로 복사
- 해결: 구체적 날짜 예시 + `_fallback_parse()` 규칙 기반 fallback

**이슈 2: ScheduleCreate에 string 전달 시 타입 에러**
- 해결: `datetime.fromisoformat()` 변환 추가

**이슈 3: chat_history가 항상 빈 배열**
- 원인: `_build_initial_state()`에서 `chat_history: []` 하드코딩
- 해결: ChatLog DB에서 session_id 기반 최근 6건 로드

**이슈 4: schedule_followup이 clarify_candidates로 빠짐**
- 원인: confidence 체크가 followup 체크보다 먼저 실행
- 해결: followup 체크를 route_by_intent 최상단으로 이동

### 다음 할 일
- LangGraph state 덮어쓰기 한계 해결 (followup intent가 agent에 전달 안 됨)
- 서버 배포 후 전체 흐름 테스트

---

## 2026-02-26 (세션 12)

### 한 일

**LangGraph state 덮어쓰기 한계 우회 (#22)**
- 문제: `route_by_intent`에서 `state["intent"] = "schedule_followup"` 설정해도 `schedule_agent`에서는 원래 intent(예: `doc_generate`)가 보임
- 원인: LangGraph가 conditional edge 함수의 state 변경을 다음 노드에 반영하지 않음
- 해결: `schedule_agent()` 진입부에서 직접 followup 재판단 로직 추가
  - intent가 `schedule_*`이 아닌 경우, 이메일/Meet 키워드 + 이전 대화 맥락으로 `schedule_followup` 재판단
- 커밋: `4135951` — `fix: schedule_agent에서 직접 followup 재판단`

**EC2 서버 재시작**
- `dudu_key.pem`으로 SSH 접속하여 서버 재시작
- 프로젝트 루트에서 `backend.app.main:app` 방식으로 uvicorn 실행 확인

**전체 흐름 테스트 성공:**
- ✅ "내일 오후 3시 팀 회의 잡아줘" → 일정 등록 + Meet/참석자 안내
- ✅ "링크 생성해줘, user@gmail.com" → Meet 생성 + 초대 메일 발송

### 다음 할 일
- ~~디버그 로그 정리 (print문 제거)~~ → 세션 13에서 완료
- ~~판단 Agent 스트리밍 디버깅~~ → 세션 12에서 이미 해결
- AI 연동 엔드포인트 (승언 문서 Agent 완성 대기)

---

## 2026-03-04 (세션 13)

### 한 일

**디버그 print문 전체 정리**
- `backend/app/api/v1/chat.py`: print문 40개+ → `logger.info/warning/error`로 전환
  - 민감 정보 출력 제거 (사용자 메시지, 문서 내용, API 키)
  - `traceback.print_exc()` → `logger.error(..., exc_info=True)`
- `ai/agents/schedule_agent.py`: print문 12개 → `logger`로 전환
- `ai/agents/orchestrator.py`: print문 21개 → `logger`로 전환

**일정 등록 시 시간 되묻기 기능 구현**
- 문제: "오늘 오후에 회의 잡아줘" → 시간 불명확한데 기본값(09:00/13:00)으로 바로 등록
- 해결:
  - `_parse_schedule_input()` 프롬프트 수정: 시간 불명확 시 `start_time: null` 반환하도록
  - `_fallback_parse()`: 구체적 시간(N시) 없으면 `start_time: None` 반환
  - `_check_missing_info()`: `start_time`이 null이면 시간 누락 판단
  - `_build_clarify_message()`: "몇 시에 잡을까요?" 메시지 생성
  - `_handle_schedule_add()`: 누락 정보 있으면 `schedule_clarify` 타입으로 되묻기
  - `_register_schedule()`: 등록 로직 분리 (clarify 후속에서도 재사용)

**schedule_clarify 후속 응답 처리 구현**
- 문제 1: "19시" 입력 시 intent 분류기가 schedule_view로 분류 → 일정 조회로 빠짐
- 해결: `schedule_agent()` 진입부에서 clarify 후속 감지를 intent 체크보다 먼저 실행
  - `_extract_clarify_from_history()`: history에서 가장 최근 schedule 응답이 clarify인지 확인
  - `_handle_clarify_response()`: 사용자 시간 입력 파싱 → 기존 일정 정보에 시간 보충 → 등록
  - `_parse_time_from_input()`: "19시", "오후 3시", "14:00", 숫자만("19") 등 다양한 시간 형식 파싱
  - `orchestrator._is_schedule_followup()`: `schedule_clarify` 타입 + 시간 입력도 followup으로 인식

- 문제 2: 일정 등록 후 이메일 초대 요청 시 옛날 clarify를 찾아서 "시간을 인식하지 못했습니다" 응답
- 해결: `_extract_clarify_from_history()`에서 `schedule_add`가 더 최근이면 clarify 무시

- 문제 3: "오전 9시 회의 잡아줘" → T09:00:00 기본값 체크에 걸려서 시간 되묻기
- 해결: T09:00:00 기본값 체크 로직 제거 (LLM이 null 반환하도록 프롬프트로만 처리)

### 커밋 내역
1. `refactor: 디버그 print문 정리 + 일정 등록 시 시간 되묻기 기능 추가` (0ccb456)
2. `feat: 일정 등록 시 시간 되묻기 + orchestrator print문 정리` (8c0ad3d)
3. `fix: schedule_clarify 후속 시간 입력이 schedule_view로 빠지는 문제 수정` (c6626e5)
4. `fix: 일정 등록 후 이메일 초대 시 schedule_clarify로 잘못 라우팅되는 문제 수정` (ba4fca2)
5. `fix: 오전 9시 일정 요청 시 시간 되묻기로 잘못 빠지는 문제 수정` (b7ca6ee)

### 다음 할 일
- 팀서비스 확장 (Slack, Jira 연동) + UI/UX 수정 (#84) — 1~2주차 작업
- AI 연동 엔드포인트 (승언 문서 Agent 완성 대기)
- vLLM 백엔드 연동 + sLLM 교체 및 평가 (#86) — 3주차 작업

---

## 2026-03-04 (세션 14) — Task Pipeline + EC2 배포

### 한 일

**Task Pipeline 기능 구현 (백엔드 + 프론트엔드)**
- `backend/app/models/pipeline_task.py` 신규: PipelineTask ORM 모델 (title, assignee, stage, priority, due_date, team, tags 등)
- `backend/app/api/v1/pipeline.py` 신규: CRUD API 4개 (GET/POST/PUT/DELETE) + 팀별 데이터 격리
- `backend/app/api/v1/router.py` 수정: pipeline 라우터 등록
- `backend/app/api/v1/auth.py` 수정: `/auth/team-members` 엔드포인트 추가 (같은 팀 사용자 목록)
- `frontend/src/api/tasks.js` 신규: Pipeline API 클라이언트
- `frontend/src/pages/TasksPage.jsx` 신규: 칸반 보드 (To Do / In Progress / Review / Done)
  - HTML5 드래그 앤 드롭으로 상태 변경
  - 태스크 추가/수정/삭제 모달 (제목, 설명, 담당자, 우선순위, 마감일, 태그)
  - 같은 팀 멤버만 담당자로 선택 가능
  - 다크모드 대응 완료
- `frontend/src/App.jsx` 수정: `/tasks` 라우트 추가
- `frontend/src/components/common/Sidebar.jsx` 수정: '태스크 관리' 메뉴 추가
- `frontend/src/components/dashboard/TaskPipelineWidget.jsx` 수정: mock 데이터 → 실제 API 연결

**AWS RDS에 pipeline_tasks 테이블 생성**
- EC2 SSH 터널을 통해 RDS PostgreSQL에 직접 접속
- `pipeline_tasks` 테이블 CREATE + 영업팀 초기 데이터 7건 INSERT

**EC2 배포**
- git push → EC2 git pull
- 프론트엔드 로컬 빌드 후 `rsync`로 dist 업로드
- 백엔드 uvicorn 재시작 (`--app-dir backend` 플래그 사용)

**기타**
- `dayjs` 누락 → `npm install dayjs` (이미 package.json에 있었으나 node_modules에 미설치)
- 로컬 git 깨짐(SIGBUS) → 새 clone으로 교체

**Approval Request 시스템 구현 (백엔드 + 프론트엔드)**
- `backend/app/models/approval_request.py` 신규: ApprovalRequest ORM 모델 (type, title, detail, status, requester_id, target_team)
- `backend/app/api/v1/approvals.py` 신규: 7개 엔드포인트
  - `GET /approvals/` — pending 요청 목록
  - `GET /approvals/history` — 처리 완료 요청 (approved/rejected)
  - `POST /approvals/` — 새 요청 생성
  - `PUT /approvals/{id}/approve` — 승인
  - `PUT /approvals/{id}/reject` — 거절
  - `DELETE /approvals/{id}` — 삭제 (본인 요청만)
  - `POST /approvals/seed` — 샘플 데이터 시드
- `frontend/src/api/approvals.js` 신규: API 클라이언트 함수
- `frontend/src/pages/ApprovalsPage.jsx` 신규: Approvals 전용 페이지
  - 전체/Pending/Approved/Rejected 필터 탭 + 카운트 뱃지
  - 유형별 필터 + 검색 (제목/요청자)
  - 요청별 아이콘/상태 뱃지 + 승인/거절/삭제 액션
  - 새 요청 올리기 모달
- `frontend/src/App.jsx` 수정: `/approvals` 라우트 추가
- `frontend/src/components/dashboard/ApprovalQueueWidget.jsx` 수정: 대시보드 위젯 연동
- 팀 필터 제거 — 모든 사용자가 전체 요청 확인 가능
- 요청 올리기 텍스트 → Plus 아이콘 버튼으로 교체

**Approval Requests 유형 확장 (3종 → 10종)**
- `frontend/src/components/dashboard/ApprovalQueueWidget.jsx` 수정:
  - typeConfig 3종(leave, review, budget) → 10종으로 확장 (remote, room, design, certificate, deploy, infra, security 추가)
  - 각 유형별 아이콘/컬러 매핑 (Home, DoorOpen, Palette, Award, Receipt, Rocket, Server, ShieldCheck)
  - 새 요청 모달 select에 10종 옵션 추가
  - 필터 라벨도 10종으로 확장
- `frontend/src/pages/ApprovalsPage.jsx` 수정:
  - typeConfig 동일하게 10종 확장
  - 유형 필터 select + 새 요청 모달 select 10종 옵션 추가

**일정 타입 추가**
- `frontend/src/store/scheduleTypeStore.js` 수정: DEFAULT_TYPES에 '프로젝트' 타입 추가 (#7C6BC4)

### 다음 할 일
- Slack 연동 확장
- AI 연동 엔드포인트 (승언 문서 Agent 완성 대기)
- vLLM 백엔드 연동 + sLLM 교체 및 평가

---

## 2026-03-05 (세션 15) — 쪽지 기능 + 인증 세션 분리

### 한 일

**쪽지(메시지) 기능 전체 구현**
- `backend/app/models/message.py` 신규: Message ORM 모델 (sender_id, receiver_id, content, is_read, timestamps)
- `backend/app/api/v1/messages.py` 신규: 5개 엔드포인트
  - `GET /messages/` — 받은/보낸 쪽지 목록 (box=inbox|sent)
  - `GET /messages/unread-count` — 안 읽은 쪽지 수
  - `POST /messages/` — 쪽지 보내기 (본인에게 보내기 방지, 수신자 존재 확인)
  - `PUT /messages/{id}/read` — 읽음 처리
  - `DELETE /messages/{id}` — 삭제 (본인 관련 쪽지만)
- `backend/app/models/__init__.py` 수정: Message import 추가
- `backend/app/api/v1/router.py` 수정: messages router 등록
- Alembic 마이그레이션: merge heads + messages 테이블 생성 및 적용

**프론트엔드 — 플로팅 팝업 + 전체 페이지**
- `frontend/src/components/messages/MessagePopup.jsx` 신규: 오른쪽 하단 플로팅 아이콘 + 작은 팝업
  - 받은/보낸 쪽지 탭, 쪽지 목록, 상세 보기 (클릭 시 자동 읽음 처리)
  - 쪽지 보내기 (전체 사용자 드롭다운), 삭제
  - 30초마다 안 읽은 수 자동 갱신, 뱃지 표시
- `frontend/src/pages/MessagesPage.jsx` 신규: 전체 페이지 뷰 (사이드바에서 접근)
- `frontend/src/api/messages.js` 신규: API 클라이언트 함수 5개
- `frontend/src/App.jsx` 수정: `/messages` 라우트 추가
- `frontend/src/components/common/Layout.jsx` 수정: `<MessagePopup />` 추가 (모든 페이지에서 표시)
- `frontend/src/components/common/Sidebar.jsx` 수정: 쪽지함 메뉴 추가

**플로팅 아이콘 정렬 + 스타일 통일**
- 쪽지 아이콘: `bottom-24 right-8` (위), AI 챗봇 아이콘: `bottom-8 right-8` (아래)
- 두 아이콘 동일 사이즈 (w-12 h-12) + 동일 스타일 (흰 배경 + primary 테두리)
- `AIChatPopup.jsx` 수정: 아이콘 크기 w-14→w-12, filled→outline 스타일로 변경

**쪽지 기능 — Approvals 위젯 옆 배치 (`ApprovalQueueWidget` 참고)**
- `frontend/src/components/common/Sidebar.jsx` 수정: 관리 섹션에 쪽지함(Mail 아이콘) 네비게이션 추가

**수신자 목록 전체 사용자로 변경**
- `MessagePopup.jsx`, `MessagesPage.jsx`: `/auth/team-members` → `/auth/all-members`로 변경
- 팀 소속 관계없이 전체 사용자에게 쪽지 보내기 가능

**인증 세션 탭 독립 분리**
- 문제: 다른 탭에서 로그인하면 기존 탭도 동기화됨 (localStorage 공유 문제)
- 해결: `access_token` 저장소를 `localStorage` → `sessionStorage`로 변경
- 수정 파일 7개:
  - `store/authStore.js`, `pages/LoginPage.jsx`, `hooks/useAuth.js`
  - `hooks/useSSE.js`, `hooks/useChat.js`, `api/client.js`
- 이제 각 탭/창이 독립적인 로그인 세션 유지

### 다음 할 일
- EC2 서버 재배포 (messages API 반영)
- Slack 연동 확장
- AI 연동 엔드포인트 (승언 문서 Agent 완성 대기)
- vLLM 백엔드 연동 + sLLM 교체 및 평가

---

## 2026-03-05 (세션 16) — UI 개선 + 쪽지 팀 표시

### 한 일

**쪽지 팀 정보 표시**
- `backend/app/api/v1/messages.py`: API 응답에 `sender_team`, `receiver_team` 필드 추가
- `frontend/src/pages/MessagesPage.jsx`: 목록 + 상세에서 이름 옆 (팀) 표시
- `frontend/src/components/messages/MessagePopup.jsx`: 목록 + 상세에서 이름 옆 (팀) 표시

**마이페이지 개선**
- 개인메모에 작성 날짜 표시 추가 (uiStore의 `createdAt` 활용)
- 문서생성 > 문서 목록에서 클릭 시 미리보기 팝업 연결 (`handleDocPreview` + Eye 아이콘)
- AI 활용 통계 카드 삭제

### 다음 할 일
- EC2 서버 재배포 (messages team 필드 반영)
- Slack 연동 확장
- AI 연동 엔드포인트 (승언 문서 Agent 완성 대기)
- vLLM 백엔드 연동 + sLLM 교체 및 평가

---

## 2026-03-06 (세션 17) — Approval Request 문서 첨부 + 상세보기

### 한 일

**Approval Request 문서 첨부 기능 구현**
- `backend/app/models/approval_request.py`: `file_path`, `file_name` 컬럼 추가
- `backend/app/api/v1/approvals.py`: POST를 JSON → Form+UploadFile 방식으로 변경
  - 파일 저장: `uploads/approvals/{uuid}.{ext}`
  - 허용 확장자: PDF, DOCX, DOC, TXT, PNG, JPG, JPEG, GIF, WEBP
  - `GET /{id}/file` 파일 다운로드 엔드포인트 추가 (FileResponse)
  - 삭제 시 첨부파일도 함께 삭제
  - 응답에 `file_name` 필드 추가
- `backend/app/main.py`: startup 마이그레이션 추가 (file_path, file_name 컬럼 자동 추가)

**프론트엔드 파일 첨부 UI**
- `frontend/src/api/approvals.js`:
  - `createApproval` FormData 방식 전환 (`Content-Type: undefined`로 axios 자동 boundary 설정)
  - `downloadApprovalFile()`, `getApprovalFileBlobUrl()` 헬퍼 추가 (JWT 인증 포함 blob 다운로드)
- `frontend/src/pages/ApprovalsPage.jsx`:
  - 새 요청 모달에 파일 첨부 input + X 취소 버튼
  - 카드 클릭 → 상세보기 모달 (유형, 제목, 상태, 요청자, 상세 내용, 날짜)
  - 첨부파일: 미리보기 버튼(이미지/PDF) + 다운로드 버튼
  - 파일 미리보기 팝업 (이미지: img 렌더링, PDF: iframe)
  - Approve/Reject 버튼도 상세 모달 안에서 사용 가능
  - 에러 상세 메시지 표시 추가
- `frontend/src/components/dashboard/ApprovalQueueWidget.jsx`:
  - 위젯 모달에 파일 첨부 input + X 취소 버튼 (원격 디자인 유지)
  - 충돌 해결: 원격(createPortal + backdrop-blur 디자인) 기반으로 파일 첨부 기능 병합

### 이슈 및 해결

**이슈 1: FormData 업로드 실패**
- 원인: axios client 기본 `Content-Type: application/json`이 FormData boundary를 덮어씀
- 해결: `headers: { 'Content-Type': undefined }`로 설정하여 axios 자동 처리

**이슈 2: 파일 다운로드/미리보기 실패**
- 원인: `<a href>` 방식은 JWT 토큰을 보내지 못함
- 해결: axios blob 요청 기반 `downloadApprovalFile`, `getApprovalFileBlobUrl` 함수로 교체

**이슈 3: ApprovalsPage에서만 요청 생성 실패 (대시보드 위젯은 정상)**
- 상태: 디버깅 중 — catch에 에러 상세 로깅 추가, 원인 확인 필요

### 다음 할 일
- ApprovalsPage 요청 생성 실패 원인 확인 (브라우저 콘솔 에러 메시지 기반)
- EC2 서버 재배포
- Slack 연동 확장
- AI 연동 엔드포인트 (승언 문서 Agent 완성 대기)
- vLLM 백엔드 연동 + sLLM 교체 및 평가

---

## 2026-03-09 (세션 18) — RAG 검색 정확도 개선 + 문서 관리 UX

### 한 일

**문서 업로드 Scope 라벨링 + 팀 문서 접근 제어**
- `frontend/src/components/documents/ScopeSelector.jsx`: 회사/팀 선택 버튼에 설명 라벨 추가 ("전체 사용자가 열람 가능" / "OO 팀원만 열람 가능")
- `frontend/src/components/documents/DocumentList.jsx`: 공개범위(scope) 컬럼 추가 (회사/팀/개인 Badge)
- RAG 챗봇에 팀 문서 격리 적용:
  - `backend/app/api/v1/chat.py`: `user_team` 전달
  - `ai/agents/document_agent.py`: `user_team` 파라미터 추가, RAG retrieve에 전달
  - `ai/rag/hybrid_search.py`: BM25 검색에 team scope 필터 추가 (같은 팀만 팀 문서 열람)
  - `ai/rag/qdrant_pipeline.py`: `user_team` 전달

**스캔 PDF OCR Fallback 추가**
- `backend/app/services/document_service.py`: `_extract_pdf()`에서 텍스트 레이어 없는 PDF → PaddleOCR 자동 시도

**RAG 검색 점수 표시 개선**
- 문제: RRF min-max 정규화로 마지막 결과가 항상 0% 표시
- 해결: max 기반 정규화 + 40%~100% 바닥 보정 (`display_score = 0.4 + 0.6 * (score/max)`)
- `ai/rag/hybrid_search.py`: 점수 정규화 방식 변경

**태그/카테고리 기반 검색 부스트**
- `ai/rag/hybrid_search.py`: RRF 합산 후 쿼리 키워드가 문서 tags/category에 매칭되면 점수 부스트 (매칭 수 × 0.3)
- `backend/app/services/document_service.py`: 태그 프리픽스에서 대괄호 제거 → BM25 토크나이저 매칭 개선

**Query Refinement 개선**
- `ai/rag/query_refiner.py`: 문서 유형 동의어 추가 (보고서/회의록/제안서), 검색 동사 불용어 추가

**LLM 문서 검색 응답 개선**
- `ai/agents/document_agent.py`: "find" 프롬프트 강화 — Context의 모든 문서를 빠짐없이 나열하도록 지시

**서버 시작 시 자동 재인덱싱**
- `backend/app/main.py`: `startup_preload()`에서 기존 문서 Qdrant 자동 재인덱싱
- 프론트엔드: 재인덱싱 버튼 및 일괄 분석 버튼 제거

**커밋 및 배포**
- GitHub Actions CI/CD로 EC2 자동 배포
- EC2 서버 재시작 필요 (점수 개선 반영)

### 이슈 및 해결

**이슈 1: 검색 점수 0%/2% 표시**
- 원인: min-max 정규화에서 최저 점수가 항상 0
- 해결: max 기반 + 40% 바닥 보정

**이슈 2: 태그 프리픽스 BM25 매칭 실패**
- 원인: `[태그: ...]` 대괄호가 토크나이저에서 분리됨
- 해결: 대괄호/라벨 제거, 순수 키워드만 프리픽스

**이슈 3: LLM이 5개 중 3개만 답변**
- 해결: 프롬프트에 "모든 문서를 빠짐없이 나열" 명시

### 다음 할 일
- EC2 서버 수동 재시작 (점수 개선 반영 확인)
- AI 연동 엔드포인트 (승언 문서 Agent 완성 대기)
- vLLM 백엔드 연동 + sLLM 교체 및 평가
