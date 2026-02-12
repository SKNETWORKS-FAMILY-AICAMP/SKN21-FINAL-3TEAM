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
