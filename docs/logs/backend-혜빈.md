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
