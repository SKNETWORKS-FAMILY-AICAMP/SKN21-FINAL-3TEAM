
# 작업 로그 — 문지영 (Frontend)

## 2026-02-09 (일)

### 한 일
- **프로젝트 초기 세팅** (`01fd409`)
  - React + Vite + Tailwind CSS 프로젝트 구성
  - 디자인 시스템 컬러 토큰 적용 (primary, accent, surface, neutral 등)
  - 기본 디렉토리 구조 생성 (pages, components, store, hooks, api)
- **UI/UX 기반 구조 추가** (`20c5675`)
  - UI_UX.pdf 요구사항 대조 후 누락 컴포넌트 스켈레톤 추가
  - chat, dashboard, documents, common 등 컴포넌트 파일 생성
- **Google Services 확장 스켈레톤** (`a1c75e1`)
  - Google 서비스 관련 컴포넌트/API/스토어 스켈레톤 구조 생성
- **Mock 데이터 작성** (`3ddf7b6`)
  - 각 페이지별 Mock 데이터 구성 (대시보드, 채팅, 문서, 회의, 일정 등)

---

## 2026-02-10 (월)

### 한 일
- **로그인/회원가입 + 대시보드 + 챗봇 UI** (`d4ba311`)
  - LoginForm, RegisterForm, PasswordReset 구현
  - 대시보드: StatCard, RecentQueries, ActionItemList, ActivityTimeline, RiskAlert, TopQueries, QuickSearch, AutoScanBadge, CalendarWidget, TodayMeetings, RecentDocs
  - 챗봇: ChatWindow, MessageBubble, StreamingMessage, IntentBadge, JudgmentCard, DocumentCard, ScheduleCard, GenerateCard, MeetingSummaryCard, ErrorMessage, SuggestedQuestions, AgentIndicator, RegulationPanel
  - Layout, Sidebar, Header 공통 컴포넌트 완성
  - Zustand 스토어 4개 구현 (authStore, chatStore, googleStore, uiStore)
  - 커스텀 훅 4개 구현 (useAuth, useChat, useSSE, useGoogleServices)
  - API 클라이언트 8개 구현 (client, auth, chat, documents, meetings, schedules, google, admin)
  - React Router 라우팅 설정 (10개 페이지, 인증 보호 라우트)
- **문서 생성 시스템 구현** (`e1659fc`)
  - MeetingMinutesPage — 회의 내용 입력 → AI 요약 → 회의록 생성
  - DocumentGeneratePage — 템플릿 선택/업로드 → AI 내용 채움 → 문서 생성
  - MeetingInput, MeetingPreview 컴포넌트
  - TemplateSelector, TemplateUploadDialog, DocumentPreview 컴포넌트
  - 사이드바 메뉴에 "회의록 생성", "문서 생성" 추가

---

## 2026-02-11 (화)

### 한 일

#### 1) Google Services 확장 UI 구현 (`2795be7`)
- GoogleServicesConnect — 통합 OAuth 연결 UI (Calendar/Tasks/Gmail/Sheets/Meet 토글)
- TasksPanel — Google Tasks 할 일 관리 패널 (체크박스, Push/Pull 동기화)
- MeetLinkBadge — Google Meet 링크 뱃지
- EmailReminderButton — 알림 메일 발송 버튼
- SheetsDashboard — 스프레드시트 추적 대시보드
- ScheduleForm에 Meet 토글 + 참석자 이메일 입력 추가
- CalendarView에 Meet 링크 표시 추가
- google.js API 클라이언트 (17개 함수)
- googleStore.js Zustand 상태 관리

#### 2) 일정 관리 공휴일 버튼 구현 (`930a22f`)
- 캘린더에 공휴일 표시 기능 추가

#### 3) KeywordHighlight 공통 컴포넌트 구현 (`ffa6c4a`) — FR-DOC-006
> 문서 검색 시 검색어가 본문에서 노란색으로 하이라이트되는 기능

- `components/common/KeywordHighlight.jsx` 신규 생성
  - 검색어를 넣으면 텍스트 중 일치하는 부분을 노란 배경으로 표시해주는 공통 컴포넌트
  - 한글/영어 대소문자 구분 없이 매칭
  - 
- **적용한 곳:**
  - `DocumentsPage` — 검색창에 입력하면 문서 목록이 필터링되고, 문서명에 검색어가 하이라이트됨
  - `DocumentDetail` — 문서 상세의 문서명 + AI 분석 결과 텍스트에도 하이라이트 적용
  - `RegulationPanel` — 채팅 우측 규정 패널의 규정명, 조항, 내용에 하이라이트 적용

#### 4) 관리자 페이지 고도화 (`9ba9288`)
> 관리자 페이지의 "추가/수정/삭제" 버튼들이 동작하도록 구현

- **UserManagement (사용자 관리)**
  - "사용자 추가" 버튼 → 모달 팝업 (이름, 부서 선택, 권한 선택)
  - "수정" 버튼 → 기존 정보가 채워진 모달 → 수정 후 저장
  - 부서: 정보보안팀/개발팀/인사팀/기획팀/경영지원팀 중 선택
  - 권한: 관리자/일반 토글 버튼
- **RegulationManagement (규정 관리)**
  - "규정 추가" 버튼 → 모달 (규정명, 조항 수, 상태)
  - "수정" 버튼 → 기존 정보 수정 모달
  - "삭제" 버튼 → "정말 삭제하시겠습니까?" 확인 다이얼로그
  - 상태: 적용중/개정중/폐지 중 선택
- **SystemStats (시스템 통계)**
  - 일간/주간/월간 탭 클릭 시 실제로 다른 통계 데이터가 표시되도록 구현
  - 프로그레스 바 전환 시 애니메이션 효과 추가

#### 5) UI 품질 점검 및 버그 수정
> ESLint 돌려서 경고 0개로 만들고, 반응형/접근성/빈 핸들러 등 전반적 품질 개선

- **반응형 디자인** — 모바일/태블릿에서도 레이아웃이 깨지지 않도록 수정
  - `DashboardPage` — StatCard 그리드: 모바일 2열 → 데스크톱 4열
  - `DashboardPage` — 메인 콘텐츠: 모바일 1열 → 데스크톱 2열
  - `DocumentsPage` — 문서 목록 + 상세: 모바일 1열 → 데스크톱 2열
  - `MeetingsPage` — 회의 목록 + 상세: 모바일 1열 → 데스크톱 2열
  - `AdminPage` — 요약 카드: 모바일 1열 → 태블릿 3열, 메인 그리드 반응형 처리
- **빈 핸들러 수정** — 클릭해도 아무 반응 없던 버튼들 동작하도록 수정
  - `ActionItemList` — 대시보드의 Action Item 체크박스 클릭 시 완료 토글
  - `ActionItemPanel` — 회의 상세의 Action Item 체크박스 클릭 시 완료 토글
- **접근성 개선** — 스크린 리더가 버튼 용도를 읽을 수 있도록 aria-label 추가
  - `DashboardPage` 알림 버튼, `ActionItemList`/`ActionItemPanel` 체크박스, `RegulationPanel` 닫기 버튼
- **ESLint 설정 추가** — `eslint.config.js` 신규 생성
  - ESLint v9 flat config 형식, React + React Hooks 플러그인 적용
  - `eslint-plugin-react`, `@eslint/js`, `globals` 의존성 설치
  - 전체 코드 lint 실행 → 0 errors, 0 warnings 달성
- **미사용 변수 정리** — `Header.jsx`, `GoogleServicesConnect.jsx`의 사용되지 않는 변수 처리
- **Hook 경고 해소** — `useGoogleServices.js`의 의도적 의존성 생략에 eslint-disable 주석 추가

#### 6) 로그아웃 버튼 + DEV_BYPASS_AUTH 복원
- Sidebar 하단에 로그아웃 텍스트 버튼 추가
  - 클릭 시 토큰 삭제 → 로그인 페이지로 이동
  - 마우스 호버 시 "로그아웃 할래 말래" 툴팁 표시
- develop pull 후 사라진 `DEV_BYPASS_AUTH = true` 복원 (백엔드 로그인 개발 완료 전까지 인증 우회)

#### 7) 글씨 크기 조절 기능 구현 (`859a8c8`)
- 가-/가+ 버튼으로 전체 글씨 크기를 조절할 수 있는 기능

- **FontSizeControl 컴포넌트 신규 생성** (`components/common/FontSizeControl.jsx`)
  - 우측 하단 고정 위치에 가-/가+ 버튼 표시
  - 14px(하한) ~ 22px(상한), 2px 단위 조절 (총 5단계)
  - html root의 font-size를 변경하여 rem 기반 전체 UI 크기 조절
  - localStorage에 저장되어 새로고침해도 유지
- **App.jsx에 통합** — BrowserRouter 안에 배치하여 로그인 포함 모든 페이지에서 사용 가능
- **로그인 카드 너비 rem 변환** — `w-[400px]` → `w-[28rem]`으로 변경하여 글씨 크기에 따라 카드도 유연하게 확대/축소

#### 8) 전체 text-[px] → text-[rem] 일괄 변환 (`859a8c8`)
> 가-/가+ 기능이 모든 글씨에 적용되도록 px 고정값을 rem으로 변환

- **변환 대상 54개 파일**, 총 6종류 px 값 변환:
  - `text-[10px]` → `text-[0.625rem]`
  - `text-[11px]` → `text-[0.6875rem]`
  - `text-[13px]` → `text-[0.8125rem]`
  - `text-[15px]` → `text-[0.9375rem]`
  - `text-[22px]` → `text-[1.375rem]`, `text-[28px]` → `text-[1.75rem]`, `text-[32px]` → `text-[2rem]`
- **적용 영역**: pages, dashboard, chat, documents, meetings, schedules, admin, auth, common 컴포넌트 + globals.css
- 변환 후 `text-[Npx]` 잔여 0건 확인 완료

### 다음 할 일
- 백엔드 연동 준비 (Mock → 실제 API 교체)
- JWT 인증 실제 연동 (#26) — 혜빈 JWT 구현 완료 후
- 챗봇 SSE 실제 연동 (#27) — 백엔드 SSE 엔드포인트 완성 후
- 관리자 API 연동 (#29) — 5단계

---

## 2026-02-12 (수)

### 한 일

#### 1) GitHub 이슈 정리 — 완료된 Frontend 이슈 5개 Close
> 작업 로그와 이슈 체크리스트를 대조하여 완전히 완료된 이슈를 정리

- **#24 [E-1] Figma 디자인 + 디자인 시스템 정의** — 이미 Closed (이전)
- **#25 [E-2] 공통 컴포넌트 + 대시보드 UI** → ✅ Closed
- **#26 [E-3] 로그인/회원가입/비밀번호 재설정 UI + Auth 연동** → ✅ Closed (JWT 연동 커밋 `2739696` 포함)
- **#27 [E-4] AI 챗봇 UI + SSE 스트리밍 + 전체 응답 카드** → ✅ Closed
- **#28 [E-5] 문서/회의/일정 관리 UI + 하이라이트/파싱/JSON뷰어** → ✅ Closed
- **#34 [E-7] Google Services 프론트엔드 UI** → ✅ Closed

**남은 열린 이슈:**
- **#29 [E-6] 관리자 페이지 UI + API 통합 연동 + 반응형** — UI/반응형 완료, API 연동 + 최종 QA 미완

#### 2) 프론트엔드 고도화 5개 기능 구현
> 백엔드 없이 Mock 모드에서 동작하는 프론트엔드 단독 기능 5개 일괄 구현

##### (a) 다크 모드
- **CSS 변수 방식**: 57개+ 컴포넌트에 `dark:` 클래스를 일일이 추가하지 않고, 색상값을 CSS 변수로 참조하여 `.dark` 클래스 하나로 전체 전환
- `tailwind.config.js` — `darkMode: 'class'` 추가, 모든 색상값을 CSS 변수 참조로 교체, `sidebar` 전용 토큰 추가
- `globals.css` — `:root`(라이트)와 `.dark`(다크) CSS 변수 정의, 다크 스크롤바 스타일
- `store/uiStore.js` — `theme` 상태 + `toggleTheme()` + localStorage 저장 + OS 기본 테마 감지
- `App.jsx` — `useEffect`로 `<html>`에 dark 클래스 동기화
- `Sidebar.jsx` — `bg-primary-700` → `bg-sidebar-bg`로 변경 (양쪽 모드에서 어두운 사이드바 유지), ThemeToggle 배치
- **NEW** `components/common/ThemeToggle.jsx` — 해/달 아이콘 토글 버튼
- `ChatPage.jsx` — 확인 다이얼로그 `bg-white` → `bg-surface-card`로 변경

##### (b) 인쇄 기능
- **`.print-area` 클래스 기반 선택적 인쇄**: 인쇄 버튼 클릭 시 해당 카드에 `.print-area` 추가 → `window.print()` → `afterprint`로 제거
- `globals.css` — `@media print` 규칙 (`.print-area` 외 숨김, A4 마진, 인쇄용 레이아웃)
- `DocumentPreview.jsx`, `MeetingPreview.jsx` — `useRef` + 인쇄 핸들러 + 프린터 아이콘 인쇄 버튼
- `DocumentDetail.jsx`, `MeetingDetail.jsx` — 인쇄 버튼 추가

##### (c) 페이지 전환 애니메이션
- `framer-motion` 패키지 설치
- `Layout.jsx` — `AnimatePresence` + `motion.div` 래핑, fade+slide 효과(200ms), 페이지 전환 시 스크롤 리셋

##### (d) 파일 드래그&드롭
- `ChatWindow.jsx` — 드래그 오버레이, 파일 검증(PDF/DOCX/TXT/이미지, 10MB 제한), `FileChip` 컴포넌트, 클립 아이콘 파일 첨부 버튼, 전송 시 `[첨부: 파일명]` 텍스트 포함

##### (e) 대화 세션 관리
- `chatStore.js` — `sessions[]`, `activeSessionId`, `createSession()`, `switchSession()`, `deleteSession()`, `saveCurrentSession()`, `initSession()` + localStorage 연동, 첫 메시지 시 세션 자동 생성
- `useSSE.js` — 스트리밍 완료 시 `saveCurrentSession()` 호출
- `ChatPage.jsx` — ChatSessionSidebar 통합, "대화 목록" 토글 버튼, 마운트 시 `initSession()`
- **NEW** `components/chat/ChatSessionSidebar.jsx` — 세션 목록(이름, 메시지 수, 시간), 삭제 버튼, "새 대화" 버튼, 활성 세션 하이라이트

**변경 요약**: 수정 14개 파일, 신규 2개 파일, npm 패키지 1개(framer-motion)
**빌드 확인**: `npm run build` 성공

#### 3) 다크모드 색상 튜닝
- 초기 다크모드가 너무 어두움 → 진회색/연회색 조합으로 2차례 밝기 조정
- 최종 배경: `#363B44`, 카드: `#3E444D`, 사이드바: `#30353C`

#### 4) 인증 우회 해제
- `App.jsx` — `DEV_BYPASS_AUTH = true` → `false` 변경
- 로그인하지 않으면 대시보드 등 보호 페이지 접근 불가, `/login`으로 리다이렉트

#### 5) Google 로그인 시 서비스 자동 연동 (백엔드 수정)
> Google 로그인과 Google 서비스 연동이 별도 OAuth 플로우로 분리되어 사용자가 두 번 인증해야 하는 문제 해결
> 로그인 한 번으로 Calendar/Tasks/Gmail/Sheets까지 자동 연동되도록 변경

- **`backend/app/api/v1/auth.py` 수정**:
  - `GET /auth/google` — scope에 서비스 스코프 4개 추가 (calendar, tasks, gmail.send, spreadsheets)
    - `access_type`: `online` → `offline` (refresh_token 받기 위해)
    - `prompt`: `select_account` → `consent` (모든 스코프 동의 + refresh_token 보장)
  - `GET /auth/google/callback` — 로그인 후 OAuthToken 자동 저장
    - code → access_token + refresh_token 교환
    - OAuthToken 테이블에 저장 (access_token, refresh_token, expires_at, scopes 4개 전부)
    - 기존 토큰 있으면 scope 병합
  - imports 추가: `OAuthToken`, `encrypt_data`, `GOOGLE_SCOPES`, `datetime`, `timedelta`, `timezone`

- **`backend/app/api/v1/google_connect.py` 수정**:
  - `POST /google/connect` — OAuth URL에 `login_hint` 파라미터 추가 (`current_user.email`)
  - 여러 Google 계정 있어도 로그인에 사용한 계정이 자동 선택되어 다른 계정으로 연결 방지

- **동작 흐름 (변경 후)**:
  1. 사용자가 "Google로 로그인" 클릭
  2. Google 동의 화면 (로그인 + Calendar/Tasks/Gmail/Sheets 권한 한번에 요청)
  3. 승인 → 백엔드에서 access_token + refresh_token 교환 + OAuthToken 저장
  4. JWT 발급 → 프론트엔드 리다이렉트
  5. 일정 관리 페이지 접속 시 `/google/status` 호출 → "Google 서비스 연결됨" 표시 (추가 연동 불필요)

#### 6) Google Calendar 실제 연동 (Mock → 실제 API)
> 일정 관리 페이지의 Mock 데이터를 제거하고 실제 Google Calendar 이벤트를 표시하도록 연동

- **`SchedulesPage.jsx`** — mockEvents/mockActions 전체 삭제, 실제 Google Calendar 데이터로 교체
  - 연결 시 이벤트 자동 로드 (백엔드 기본값 ±3개월)
  - 수동 새로고침 버튼 추가
  - backend 응답 형식(`{title, start, end, meet_link}`)을 CalendarView 형식으로 변환
- **`googleStore.js`** — Calendar 상태/액션 추가
  - `calendarEvents`, `calendarLoading`, `calendarError` 상태
  - `fetchCalendarEvents()`, `createEventWithMeet()`, `syncEventToGoogle()` 액션
- **`google.js`** — `listCalendarEvents(timeMin, timeMax)`, `syncEventToGoogle(eventData)` API 추가
- **`useGoogleServices.js`** — Calendar 자동 로드 제거 (페이지에서 시간 범위 지정하여 직접 호출)
- **Backend `calendar_service.py` 수정**:
  - `primary` 캘린더만 → **모든 캘린더 조회**로 변경 (Family 등 서브 캘린더 포함)
  - 기본 시간 범위 ±3개월 설정
  - maxResults 50 → 250 확대
  - 공휴일 캘린더(`#holiday@group.v.calendar.google.com`) 제외 (프론트엔드 하드코딩 공휴일과 중복 방지)
- **일괄 알림 버튼(`EmailReminderButton`) 제거** — SchedulesPage 헤더에서 삭제
- **디버그 코드 정리** — googleStore.js, SchedulesPage.jsx의 console.log/디버그 패널 제거

### 다음 할 일
- 나머지 Mock → 실제 API 교체 (대시보드, 채팅, 문서, 회의 등)
- 전체 E2E 테스트 지원

---

## 2026-02-12 (수) — 오후

### 한 일
- 일정 추가 버그 수정 (`SchedulesPage.jsx`)
  - `useGoogleServices.getState()` 호출 오류 → 훅에서 직접 구조분해로 변경
  - `create_meet`/`attendees` 필드명 불일치 수정
  - 종일 이벤트 시 Invalid Date 발생 수정
- 캘린더 토/일 색상 적용 (`CalendarView.jsx`)
  - 토요일 헤더+날짜 파란색, 일요일 헤더+날짜 빨간색, 공휴일 날짜도 빨간색 표시
  - 월간/주간/연간 뷰 전부 적용
- 대체공휴일 데이터 추가 (`CalendarView.jsx`)
  - 2025~2027년 대체공휴일 전체 추가 

---

## 2026-02-15 (일)

### 한 일

#### 1) 이모지 → Lucide React 아이콘 전면 교체
- `lucide-react` 패키지 설치
- 38개+ 파일에서 50개+ 이모지를 Lucide SVG 아이콘으로 교체
- `constants.js` — INTENT_ICONS / SUGGESTED_QUESTION_CATEGORIES 이모지 → Lucide 이름 문자열로 변환
- `SuggestedQuestions.jsx` — ICON_MAP 매핑으로 Lucide 컴포넌트 렌더링

#### 2) 회의록 생성 페이지 → 문서 생성 페이지에 통합
- MeetingMinutesPage 삭제 (App.jsx 라우트 + Sidebar 메뉴 제거)
- DocumentGeneratePage에서 `meeting_minutes` 템플릿 선택 시 MeetingInput + MeetingPreview 표시

#### 3) 화면 빈 화면 버그 수정
- **원인 1**: `client.js` 응답 인터셉터의 `window.location.href = '/login'`이 React 렌더링 중 DOM 충돌 → 리다이렉트 제거, React Router 상태 기반으로 변경
- **원인 2**: Lucide 아이콘이 `forwardRef` 객체라 `typeof icon === 'function'` 체크 실패 → IIFE 패턴으로 수정 (`ActivityTimeline.jsx`)

### 다음 할 일
- alert() → toast 알림 컴포넌트 교체 (6곳)
- window.confirm() → 모달 다이얼로그 교체
- 로딩 스켈레톤 추가
- 나머지 Mock → 실제 API 교체
- 관리자 API 연동 (#29)

---

## 2026-02-17 (화)

### 한 일

#### 1) 대시보드 편집 모드 구현
- `uiStore.js` — 대시보드 레이아웃 상태 추가 (leftColumn/rightColumn/hidden, localStorage 저장)
- `DashboardPage.jsx` — WIDGET_REGISTRY 기반 동적 렌더링, framer-motion Reorder로 드래그 순서 변경, X 버튼으로 위젯 숨기기, 점선 카드로 숨긴 위젯 복원, 편집/완료 토글 + 초기화 버튼

#### 2) AI 챗봇 프로필 변경
- `MessageBubble.jsx` — AI 프로필을 "AI" 텍스트 → accent-500 배경 + Brain 아이콘으로 변경


---

## 2026-02-19 (목)

### 한 일

#### 1) Docker 환경 구성
- `Dockerfile.backend` — `ai/requirements.txt` 설치 추가, PYTHONPATH/CMD 경로 수정, bitsandbytes 제외
- `.env` — DATABASE_URL/REDIS_URL 호스트 `localhost` → `db`/`redis`로 변경
- `vite.config.js` — 프록시 타겟 `process.env.BACKEND_URL || 'http://localhost:8000'`으로 변경
- `docker-compose.yml` — frontend에 `BACKEND_URL=http://backend:8000` 추가 (Google 로그인 500 에러 해결)

#### 2) 챗봇 버그 수정
- `useChat.js` — `createSession()` 중복 호출 제거, `isStreaming` 스테일 클로저 버그 수정
- `useSSE.js` — SSE 에러 시 Mock 폴백 제거 → `setLastAssistantError()`로 UI에 직접 표시
- `chatStore.js` — 빈 세션 자동 정리, `initSession()` 수정 (in-memory 메시지 있으면 덮어쓰지 않음)
- `ChatPage.jsx` — judgment 카드 텍스트 이중 렌더링 수정

#### 3) DocumentsPage Mock 데이터 제거
- `mockDocs` 삭제, 실제 업로드 문서만 표시

#### 4) 대시보드 예시 질문 → 챗봇 자동 전송
- `chatStore.js` — `pendingQuestion` 상태 추가
- `AIChatWidget.jsx` — 질문 클릭 시 `setPendingQuestion(q)` 후 `/chat` 이동
- `ChatPage.jsx` — 마운트 시 `pendingQuestion` 감지 → 새 세션 생성 + 자동 전송
- React StrictMode 이중 실행 + Auth 리마운트 문제 → `mountedRef`로 해결

#### 5) 대시보드 위젯 자유 배치 (컬럼 간 드래그)
- `framer-motion Reorder` → HTML5 드래그 앤 드롭으로 교체
- `uiStore.js` — `moveWidget()` 추가
- `DashboardPage.jsx` — 좌↔우 컬럼 자유 이동, 드롭 위치 파란 선 표시

#### 6) 일정 유형 커스터마이즈 기능 구현

- **`store/scheduleTypeStore.js`** 신규 생성
  - 기본 유형 3개 (회의/마감일/개인 일정) + 커스텀 유형 localStorage 저장
  - `addType(label, color)`, `removeType(id)` 액션
- **`components/schedules/ScheduleTypeManager.jsx`** 신규 생성
  - 기본 유형 목록 (삭제 불가) + 커스텀 유형 목록 (삭제 가능)
  - 이름 입력 + 색상 스와치 12개 선택 → `+ 추가` 버튼 배경색이 선택 색상으로 실시간 변경
- **`ScheduleForm.jsx`** 수정 — 스토어에서 동적으로 유형 목록 불러와 버튼 렌더링 (커스텀 유형 자동 반영)

### 다음 할 일
- 관리자 API 연동 (#29)
- 나머지 Mock → 실제 API 교체 (대시보드, 채팅, 문서, 회의)

---

## 2026-02-20 (금)

### 한 일

#### 1) 회원가입 성공 팝업 + 로그인 자동 입력 구현

- **문제**: 회원가입 후 팝업 없이 바로 동작하거나, 대시보드로 튕기는 버그
- **원인 분석**: `PublicOnlyRoute`가 `isAuthenticated = true` 감지 시 즉시 대시보드로 리다이렉트하여 팝업이 렌더링되지 못함

- **`useAuth.js`** 수정
  - `register()` 성공 후 자동 `/login` 이동 제거 → 이동 제어권을 `LoginPage`로 위임

- **`LoginPage.jsx`** 수정
  - `showRegisterSuccess` 상태 추가 — 성공 팝업 표시 여부 관리
  - `registeredCredentials` 상태 추가 — 회원가입한 이메일/비밀번호 임시 보관
  - `handleRegister` — 회원가입 성공 시 자동 로그인 없이 팝업만 표시 (토큰 저장 안 함 → PublicOnlyRoute 리다이렉트 방지)
  - `handleRegisterSuccessConfirm` — 팝업 확인 시 `switchTab('login')`으로 로그인 탭 전환
  - 성공 팝업 UI 추가 (체크 아이콘 + "회원가입 완료!" + "확인" 버튼)
  - `LoginForm`에 `defaultEmail`, `defaultPassword` prop 전달

- **`LoginForm.jsx`** 수정
  - `defaultEmail`, `defaultPassword` prop 추가
  - `useState` 초기값을 prop 값으로 설정 → 로그인 탭 전환 시 이메일/비밀번호 자동 입력

- **최종 흐름**: 회원가입 제출 → 성공 팝업 → "확인" 클릭 → 로그인 탭 (이메일·비밀번호 자동 입력)

#### 2) 사이드바 접기/펼치기 기능 구현 (`Sidebar.jsx`, `Layout.jsx`)

- **토글 버튼 추가**: 사이드바 상단 W 로고 아래에 햄버거 아이콘(`Menu`) 버튼 배치
  - 펼쳐진 상태에서 커서 올리면 → `메뉴 접기` 툴팁
  - 접힌 상태에서 커서 올리면 → `메뉴 펼치기` 툴팁
- **접힌 상태 (`w-16`)**: 아이콘만 중앙 정렬 표시
  - 섹션 레이블(`메인`, `관리` 등) → 얇은 구분선으로 대체
  - 각 메뉴 아이템 → 아이콘만, `title` 속성으로 마우스 오버 시 메뉴명 표시
  - 유저 프로필 → 아바타만, ThemeToggle + LogOut 아이콘 버튼으로 대체
- **펼친 상태 (`w-60`)**: 기존과 동일
- **애니메이션**: `transition-[width] duration-300 ease-in-out` 부드러운 전환
- **버튼 클리핑 버그 수정**: `aside`의 `overflow-y-auto`를 내부 `<div>`로 이동하여 절대 위치 버튼이 잘리지 않도록 수정

#### 3) 사이드바 메모 기능 구현 (`Sidebar.jsx`, `uiStore.js`)

- **다중 메모 지원**: 단일 textarea → 메모 리스트 방식으로 구현
  - `uiStore.js` — `memos` 배열 상태 (`{ id, text, createdAt }`), localStorage 자동 저장
  - `addMemo()`, `updateMemo()`, `deleteMemo()`, `selectMemo()` 액션
  - 기존 단일 메모(`sidebar-memo`) 있으면 새 형식(`sidebar-memos`)으로 자동 마이그레이션
- **목록 보기**: 메모 제목(첫 줄) 리스트 표시, `+` 버튼으로 새 메모 추가, 휴지통 아이콘으로 삭제 (hover 시 표시)
- **편집 보기**: 메모 클릭 시 textarea 표시, "목록으로" 버튼으로 리스트 복귀
- **사이드바 접힌 상태**: StickyNote 아이콘 + 메모 개수 뱃지 표시
- **자동 저장 표시**: 타이핑 멈추고 0.5초 후 `✓ 자동 저장됨` accent 색상 텍스트 페이드인 → 2초 후 페이드아웃

---

## 2026-02-23 (월)

### 한 일

#### 1) 네비게이션 사이드바 → Topbar 전환
- **기존 Sidebar 제거**, 상단 Topbar 방식으로 네비게이션 변경
- `components/common/Topbar.jsx` 신규 생성
  - 로고 + 7개 메뉴 가로 나열 + 우측(테마토글, 메모, 알림, 유저, 로그아웃)
- `Layout.jsx` 수정 — `flex-row` → `flex-col`, Sidebar → Topbar 교체
- 메모 기능을 Topbar에 **플로팅 패널**로 이전
  - StickyNote 아이콘 + 메모 개수 뱃지
  - 패널 외부 클릭 시 닫힘
- `NavPreviewPage.jsx` 생성 — Topbar/CommandPalette/TabBar 3종 비교 프리뷰 페이지 (`/nav-preview`)

#### 3) doc_summary 프론트엔드 연동 (6개 파일)
- `api/chat.js` — `sendMessage`에 `documentId` 파라미터 추가
- `store/chatStore.js` — `selectedDocumentId`, `selectedDocumentName`, `setSelectedDocument`, `clearSelectedDocument` 상태 추가
- `hooks/useSSE.js` — `startStream`에 `documentId` 받아서 `body.document_id` 포함
- `hooks/useChat.js` — `selectedDocumentId` 꺼내서 `startStream`에 전달, 전송 후 자동 해제
- `components/chat/ChatWindow.jsx` — 입력창 위에 선택 문서 칩 표시 (X로 해제)
- `pages/ChatPage.jsx` — "문서 선택" 버튼 + 검색 가능한 문서 피커 모달 추가, `listDocuments()` API 연동

#### 5) 챗봇 좌측 아이콘 레일 추가
- 헤더 우측 "대화 목록" 버튼 제거 → 좌측에 얇은 아이콘 레일(w-11) 배치
- 햄버거(`Menu`) 아이콘으로 대화 목록 토글 (최상단)
- `MessageSquarePlus` 아이콘으로 새 대화 생성

#### 6) Agent 표시 방식 변경 — iOS 스타일 Agent 바
- 메시지 위 AgentIndicator 제거 (ChatPage 3곳)
- 입력창 위에 4개 둥근 pill로 Agent 그룹 표시: `규정 판단` / `문서` / `일정` / `일반`
- 활성 Agent 진한 색 하이라이트 + 스트리밍 중 아이콘 pulse 애니메이션

#### 7) 상단바 및 챗봇 페이지 레이아웃 전면 개편 (`Layout.jsx`, `ChatPage.jsx`, `ChatWindow.jsx`)
- 상하 패딩 30px 통일 (`py-[30px]`)
- 하단 구분선(`border-b`) 제거
- 수직 정렬 `items-end` → `items-center` 변경
- 활성 메뉴 밑줄 위치 조정 (`pb-3` 추가)
- `/chat` 경로 감지 → `Layout.jsx`에서 패딩/오버플로 조건 분기 (overflow 클리핑 문제 해결)
- AgentBar(입력창 위 4개 Agent pill) 제거 → AI 답변 위 `AgentIndicator`로 대체 (`MessageBubble.jsx`)
- `RegulationPanel` 우측 여백(`-mr-8`) 제거 (`RegulationPanel.jsx`)
- `ChatSessionSidebar` 폭 `w-64` → `w-[320px]` (RegulationPanel과 통일)
- 채팅 입력 영역 우측 패딩 분기: 패널 열림 `pr-[3px]`, 닫힘 `pr-32` (글씨 크기 조절 버튼 겹침 방지)

#### 8) 문서 관리 페이지 UI 개선 (`DocumentsPage.jsx`, `DocumentList.jsx`, `DocumentUpload.jsx`, `ScopeSelector.jsx`)
- `FilterBar` 전체 제거 (전체/규정/회의록/보고서 탭, 상태/구분 드롭다운)
- 검색창 좌측에 검색 타입 선택 추가: 제목 / 제목+내용 / 날짜
- 문서 업로드 영역 높이 `min-h-[280px]`, `flex flex-col items-center justify-center` 중앙 정렬
- '개인 문서' → '팀 문서' 변경 (`ScopeSelector.jsx`)
- 문서 목록 헤더에 scope 필터 추가: 전체 / 회사 / 팀

#### 9) CustomSelect 커스텀 드롭다운 컴포넌트 신규 생성 (`components/common/CustomSelect.jsx`)
- 브라우저 기본 select 대신 사이트 테마(blue-grey 팔레트)에 맞는 커스텀 드롭다운
- ChevronDown 아이콘 회전 애니메이션, 외부 클릭 시 자동 닫힘
- 선택 항목: `bg-primary-100`(진함), 호버: `bg-primary-50`(연함)
- `buttonClassName` prop으로 컨텍스트별 높이 조정 가능
- `whitespace-nowrap` 적용으로 텍스트 줄바꿈 방지
- 검색 타입 선택 / 문서 목록 scope 필터 두 곳에 적용

#### 10) 문서 생성 페이지 템플릿 축소 (`constants.js`, `TemplateSelector.jsx`)
- 템플릿 5개 → 3개로 축소: 회의록 / 보고서 / 제안서 (채용 공고, 사용자 정의 제거)
- `grid-cols-2` → `grid-cols-3`으로 한 줄에 3개 표시

#### 11) UI 개선 및 기능 추가
- 회의 관리 페이지 전체 제거 (라우트, AIDock, Topbar 메뉴)
- 글씨 크기 버튼 로그인/회원가입에서만 표시
- 사용자 관리에 팀 컬럼/드롭다운 추가
- 문서 관리 검색 버튼 추가
- 비밀번호 변경 모달 추가 (유저 드롭다운)
- 일정 캘린더 유형별 필터 버튼 (전체/회의/마감일/개인일정/공휴일)

### 다음 할 일
- 나머지 Mock → 실제 API 교체 (대시보드, 문서 생성)
- 관리자 API 연동 (#29)
- 비밀번호 변경 백엔드 엔드포인트 구현 요청 (혜빈)

---

## 2026-02-24 (화) — 오후

### 한 일

#### 1) 관리자 페이지 UI 개선 (`AdminPage.jsx`, `SystemStats.jsx`)

- 최근 질의 로그 · 인기 질의 카드 가로 사이즈 고정 (`overflow-hidden`, `min-w-0`) — 질의가 길어져도 카드가 늘어나지 않음
- '처리된 회의' 요약 카드 제거, 3열 그리드로 조정

#### 2) 대화 목록 세션 이름 변경 기능 (`ChatSessionSidebar.jsx`, `chatStore.js`)

- hover 시 연필 아이콘 표시 → 클릭하면 인라인 input 전환
- **Enter** 또는 blur → 저장, **Esc** → 취소
- `chatStore.js`에 `renameSessionById` 액션 추가 (API 호출 + 상태 업데이트)

#### 3) 문서 관리 날짜 달력 검색 (`DocumentsPage.jsx`, `components/common/DatePicker.jsx`)

- 검색 타입 '날짜' 선택 시 텍스트 input 대신 달력 팝업 표시
- `DatePicker.jsx` 신규 생성 — 외부 라이브러리 없이 순수 React+Tailwind로 구현
  - 월/연도 네비게이션, 일/토 색상 구분, 오늘 선택 버튼
  - 날짜 선택 즉시 자동 검색, `right-0` 정렬로 화면 잘림 방지
  - 검색 타입 '날짜' 선택 시 달력 자동 오픈 (`autoOpen` prop)

#### 4) 검색 UI 크기 안정화 (`DocumentsPage.jsx`)

- 검색칸 너비 `w-[280px]` 고정 — 검색 타입 전환/검색 실행 시 크기 변동 없음
- 검색 버튼: 너비 `w-[68px]` · 높이 `h-[38px]` · `!py-0` · `!rounded-md` 고정
- 날짜 선택 시 검색 버튼 `invisible` 처리로 레이아웃 유지
- 검색칸 · 검색 버튼 높이(`h-[38px]`) · 모서리(`rounded-md`) 통일

### 다음 할 일
- 나머지 Mock → 실제 API 교체 (대시보드, 문서 생성)
- 관리자 API 연동 (#29)

---

## 2026-02-24 (화)

### 한 일

#### 1) 문서 생성 페이지 입력 폼 개선 (`MeetingInput.jsx`, `DocumentGeneratePage.jsx`)


- **공통 (회의록 · 보고서 · 제안서 3개 폼)**
  - 담당자 초기값: 로그인 유저 이름 자동 입력
  - 회의내용 textarea 자동 높이 조절 (`onInput` + `scrollHeight`)
  - 최대 130px에서 크기 고정 후 스크롤 (`max-h-[130px]`, `overflow-y-auto`)

#### 2) 문서 관리 날짜 검색 버그 수정 (`DocumentsPage.jsx`)

- DatePicker `key`를 고정 문자열 → 동적 `datePickerKey`로 변경
- 검색 타입을 '날짜'로 전환할 때 key 갱신하여 DatePicker 상태 리셋 (이전 날짜가 남아있던 버그 해결)

### 다음 할 일
- 나머지 Mock → 실제 API 교체 (대시보드, 문서 생성)
- 관리자 API 연동 (#29)

---

## 2026-02-25 (수)

### 한 일

#### 1) 대시보드 Mock 데이터 → 실제 API 연동 (`DashboardPage.jsx`)

- Mock 데이터 4개(`mockActivities`, `mockActions`, `mockMeetings`, `mockDocs`, `calEvents`) 전부 삭제
- `useDashboardData()` 커스텀 훅 신규 작성
  - `listSchedules()` → 오늘 일정 필터링 + 마감 임박(D-7 이내) 산출 + 캘린더 날짜별 점 표시
  - `listDocuments()` → 최근 문서 5개
  - `listSessions()` → 최근 채팅 세션
- 3개 API를 `Promise.allSettled`로 병렬 호출 (하나 실패해도 나머지 정상 표시)
- `GreetingBanner` 카운트(`meetingCount`, `actionCount`)를 실제 데이터에서 산출
- 위젯 props를 WIDGET_REGISTRY 외부에서 주입하는 방식으로 리팩토링
- 로딩 상태 표시 추가 ("데이터를 불러오는 중...")

#### 2) RecentDocs 위젯 개선 (`RecentDocs.jsx`)

- 빈 상태 메시지 추가 ("업로드된 문서가 없습니다.")
- Badge variant에 실제 API 상태값(`완료`, `처리중`) 대응 추가

#### 3) 일정 삭제 기능 구현 (PR #75)

> 일정 관리 페이지 날짜 팝업에서 일정을 삭제할 수 있는 기능 추가

- **`CalendarView.jsx`** — `DayDetailPopup` 각 일정 우측에 Trash2 쓰레기통 버튼 추가
  - Google Calendar 이벤트(`event_id` 있는 항목)에만 버튼 표시 (공휴일 제외)
  - 클릭 시 스피너 표시 → 삭제 완료 즉시 목록에서 제거
  - hover 시 빨간색 전환
- **`SchedulesPage.jsx`** — 이벤트 매핑에 `id: event.event_id`, `calendarId: event.calendar_id` 추가
  - 기존 `event.id` → `event.event_id` 필드명 수정 (버튼 미표시 버그 원인)
- **`api/google.js`** — `deleteCalendarEvent(eventId, calendarId)` 추가
- **`googleStore.js`** — `deleteCalendarEvent` 액션 추가 (삭제 후 스토어에서 즉시 제거)
- **`backend/app/api/v1/calendar.py`** — `DELETE /calendar/events/{event_id}` 엔드포인트 추가
- **`backend/app/services/calendar_service.py`** — `delete_event()` 메서드 추가
  - 전달받은 `calendar_id`로 1차 시도 → 실패 시 전체 캘린더 순회 탐색 (Not Found 완전 해결)
  - sub-캘린더(Family 등) 이벤트도 정상 삭제 가능

#### 4) Tasks 탭 UI 개선 (PR #76, `TasksPanel.jsx`, `SchedulesPage.jsx`)

- **Push/Pull 버튼 → 새로고침 버튼 하나로 통합** — RefreshCw 아이콘 + 로딩 중 스피너 회전
- **헤더 "Google Tasks" → "Tasks"** 로 변경 (미연결 안내 메시지 포함)
- **탭 전환 시 헤더 버튼 숨김** — Tasks/Sheets 탭에서 새로고침·유형 관리·일정 추가 버튼 미표시
- **전체 탭 정렬** — 미완료 항목이 완료 항목보다 상단에 표시 (`sort((a,b) => a.completed - b.completed)`)

#### 5) 일정 유형 → Google Calendar 연동 (PR #76)

> 앱에서 커스텀 유형 추가 시 Google Calendar에 동일한 이름의 캘린더 자동 생성

- **`backend/app/services/calendar_service.py`** — `create_calendar(name, color)` 메서드 추가
  - `calendars().insert()` 로 캘린더 생성 → `calendarList().patch()` 로 색상 지정
  - `push_event` / `create_event_with_meet` — `event_data.calendar_id` 지원 (지정 캘린더에 이벤트 저장)
- **`backend/app/api/v1/calendar.py`** — `POST /calendar/calendars` 엔드포인트 추가
- **`frontend/src/api/google.js`** — `createGoogleCalendar(name, color)` 추가
- **`frontend/src/store/scheduleTypeStore.js`** — `addType(label, color, calendarId)` — calendarId 저장
- **`frontend/src/components/schedules/ScheduleTypeManager.jsx`** — 유형 추가 시 Google 연결되어 있으면 캘린더 자동 생성, 실패 시 로컬만 저장 (graceful fallback)
- **`frontend/src/pages/SchedulesPage.jsx`** — 이벤트 생성 시 type의 calendarId 조회 후 전달, pull 시 `calendarId → typeId` 역매핑 추가

#### 6) 일정 유형 표시 버그 수정

- 등록 유형(회의/마감일 등)이 항상 "개인 일정"으로 표시되는 버그 수정
- 원인: Google Calendar에 type 개념 없어 pull 시 type 정보 소실
- 수정: `extendedProperties.private.workflow_type`에 유형 저장 → pull 시 복원
- 우선순위: extendedProperties → calendarId 역매핑 → 기본값('google')

#### 7) ScheduleTypeManager 버튼 텍스트 수정

- 유형 추가 중 "추가 중..." → "추가 중" (말줄임표 제거로 버튼 잘림 현상 해결)

#### 8) 일정 유형 삭제 시 Google Calendar 연동 (PR #77)

- **`backend/app/services/calendar_service.py`** — `delete_calendar(calendar_id)` 메서드 추가
- **`backend/app/api/v1/calendar.py`** — `DELETE /calendar/calendars?calendar_id=xxx` 엔드포인트 추가
- **`frontend/src/api/google.js`** — `deleteGoogleCalendar(calendarId)` 추가
- **`frontend/src/components/schedules/ScheduleTypeManager.jsx`** — 삭제 버튼 클릭 시 Google Calendar도 함께 삭제
  - Google 연결 + calendarId 있는 유형만 API 호출
  - API 실패해도 앱 내 유형은 정상 삭제 (graceful fallback)
  - Google 미연결 또는 calendarId 없는 유형은 로컬만 삭제
### 다음 할 일
- vite 프록시 설정 로컬/EC2 분리 (.env.local)
- 판단 Agent 스트리밍 디버깅
- 문서 생성 AI 연동 (501 엔드포인트 해소)

---

## 2026-02-26 (목)

### 한 일

#### 1) README.md Agent 워크플로우 Mermaid 다이어그램으로 교체
- 각 Agent 워크플로우 섹션의 ASCII art → Mermaid `graph TD` 형식으로 전환
  - Judgment Agent, Document Agent, Schedule Agent, General Response 4개 서브그래프 구성
  - 전체 구조도 (`전체 구조 2`) 섹션도 Mermaid로 변환

#### 2) 카드 글라스모피즘(반투명) 효과 적용 (`globals.css`)
- `.card` 클래스: `bg-white/60 backdrop-blur-md border-white/60 shadow-md` 적용
- 팝업/모달은 `bg-surface-card` 변수 사용 → 불투명 유지 (`#FFFFFF`)
- 다크 모드 카드: `rgba(48, 52, 62, 0.6)`

#### 3) 대시보드 오늘 일정 버그 수정 (`DashboardPage.jsx`)
- **원인**: 일정 관리 페이지에서 추가한 일정은 Google Calendar에만 저장되는데, 대시보드는 백엔드 DB(`/api/v1/schedules/`)만 조회해서 표시 안 됨
- **수정**: `googleStore`의 `calendarEvents`를 대시보드에서도 읽어와 백엔드 DB 일정과 병합
  - 오늘 날짜 Google Calendar 이벤트 필터링 후 schedule 형식으로 변환
  - 제목+날짜 기준 중복 제거
  - `todayMeetings`, `upcomingActions`, `calEvents` 모두 병합된 데이터 사용

#### 4) 문서 생성 AI 연동 확인 (`DocumentGeneratePage.jsx`)
- `handleGenerate`, `handleMeetingSubmit`, `handleDownload` 모두 실제 API 호출 확인
  - `generateDocument()` → `/api/v1/documents/generate` 실제 연동 ✅
  - `downloadDocument()` → `/api/v1/documents/{id}/download` 실제 연동 ✅
- 파일 상단 `mockMeetingResult`, `mockResults` 변수는 미사용 dead code (실제로는 쓰이지 않음)

#### 5) 일정 등록/팀 공유 버그 수정 (`SchedulesPage.jsx`, `ScheduleForm.jsx`)

**문제 1: 일정 등록 버튼 눌러도 반응 없음 (사원 계정)**
- **원인**: 제목/날짜 미입력 시 `if (!data.date || !data.title) return;`으로 아무 피드백 없이 무시됨
- **원인 2**: API 에러(500)도 `console.error`로만 찍히고 사용자에게 안 보임 + 에러 시에도 폼이 닫힘
- **수정 (ScheduleForm.jsx)**:
  - 폼 유효성 검사 추가 — 제목 비면 "제목을 입력하세요", 날짜 미선택이면 "날짜를 선택하세요" 빨간 에러 표시
  - 로딩 상태 추가 — 등록 버튼 "등록 중..." + `disabled` 중복 클릭 방지
- **수정 (SchedulesPage.jsx)**:
  - API 실패 시 빨간 에러 배너 표시 ("일정 저장에 실패했습니다")
  - DB 저장 실패하면 `throw error`로 폼이 닫히지 않음

**문제 2: 500 Internal Server Error (타임존)**
- **원인**: `toISOString()`이 `2026-03-03T00:00:00.000Z` (UTC+Z) 형태로 보내는데, DB 컬럼이 `TIMESTAMP WITHOUT TIME ZONE`이라 `offset-naive/aware` 충돌
- **수정**: `toISOString()` 대신 `2026-03-03T09:00:00` 형태(타임존 없음)로 직접 전송

**문제 3: 회의 유형으로 등록했는데 "개인 일정"으로 표시됨**
- **원인**: Google Calendar에는 type 개념이 없어서 pull 시 `event_type`이 null → 기본값 `'google'`(개인 일정)으로 표시. 중복 제거에서 DB 일정(정확한 type) 대신 Google Calendar 버전(잘못된 type)이 남음
- **수정**: 중복 제거 방향 역전 — DB 일정을 우선하고 Google Calendar에서 meetLink만 보강
  - 이전: Google Calendar 우선, DB 필터링 → type 소실
  - 이후: DB 우선, Google Calendar 필터링 → type 보존

**문제 4: 팀 일정 공유 안 됨 (영업팀 관리자 → 사원)**
- **원인**: AWS RDS에 `team_name`/`is_team_visible` 컬럼 누락 (Alembic 마이그레이션 미실행)
- **수정**: EC2 SSH 접속 → `alembic stamp` + `alembic upgrade head` 실행 → 컬럼 추가 완료
- **수정 2**: EC2 백엔드 `git pull` + uvicorn 재시작


#### 6) 일정 삭제 권한 제어 — 본인 + 관리자만 삭제 가능

**백엔드 수정 (3개 파일)**
- **`backend/app/schemas/schedule.py`** — `ScheduleResponse`에 `user_id` 필드 추가 (프론트에서 소유자 판별용)
- **`backend/app/services/schedule_service.py`** — `get_schedule()`, `delete_schedule()`에 `is_admin` 파라미터 추가, 관리자는 소유권 체크 스킵
- **`backend/app/api/v1/schedules.py`** — DELETE 엔드포인트에서 `user.is_admin` 전달, 목록/생성 응답에 `user_id` 포함

**프론트엔드 수정 (2개 파일)**
- **`frontend/src/pages/SchedulesPage.jsx`**
  - DB 일정/팀원 일정에 `scheduleId`, `userId` 필드 추가
  - `canDelete()` — DB 일정은 `userId === user.id`일 때만 삭제 허용 (관리자는 전체 삭제 가능, 공휴일은 항상 X)
  - `handleDeleteEvent()` — DB 일정은 `DELETE /schedules/{id}` (백엔드에서 Google Calendar도 삭제), Google 전용 이벤트는 기존 방식
- **`frontend/src/components/schedules/CalendarView.jsx`** — `onCanDelete` prop 추가, 삭제 아이콘 표시 조건을 `onCanDelete?.(e)` 결과로 제어

**삭제 아이콘 표시 규칙:**
| 이벤트 | 일반 사원 | 관리자 |
|--------|----------|--------|
| 내가 등록한 일정 | O | O |
| 타인이 등록한 일정 | X | O |
| 공휴일 | X | X |



### 다음 할 일
- 판단 Agent 스트리밍 디버깅

---

## 2026-03-04 (수)

### 한 일

#### 1) 판단 Agent 응답 카드 UI 개선 (`JudgmentCard.jsx`, `ChatPage.jsx`)

- **규정 팝업 기능 추가** — 관련 규정 클릭 시 전체 내용을 모달 팝업으로 표시
  - `RegulationPopup` 컴포넌트 신규 생성 (ESC/외부 클릭으로 닫기)
  - 규정 항목을 `<div>` → `<button>`으로 변경, hover 시 색상 전환 + "전체 보기 →" 링크
- **레이아웃 변경** — summary(줄글)를 규정+신뢰도 아래로 이동 (border-t 구분선 추가)
- **ChatPage 판단 응답 렌더링 리팩토링**
  - JudgmentCard는 `summary=null`로 규정+신뢰도만 표시
  - 기존 content/reasoning 중복 렌더링 로직 정리

#### 2) 스트리밍 메시지 UX 개선 (`StreamingMessage.jsx`)

- status(에이전트 상태) 표시 제거
- 빈 텍스트 상태: 점 3개만 → "답변을 생성하고 있어요" 텍스트 + bounce 도트(w-2 h-2)로 변경

#### 3) 채팅 스크롤/대기 표시 버그 수정 (`ChatWindow.jsx`, `ChatPage.jsx`)

- **ChatWindow** — `useEffect` 의존성에 `isStreaming` 추가 (스트리밍 시작/종료 시 자동 스크롤)
- **ChatPage** — `isWaitingForResponse` 로직 추가
  - `isStreaming` 설정 전 빈 어시스턴트 메시지에도 타이핑 인디케이터 표시
  - 전송 직후 빈 화면 → 즉시 "답변을 생성하고 있어요" 표시로 개선

#### 4) alert/window.confirm → 커스텀 Toast + ConfirmModal 교체

- **`store/toastStore.js`** 신규 생성 — Zustand 기반 toast 상태 관리
  - `toast.success/error/info/warning(message)` 명령형 API
  - `confirm(message)` — Promise 반환, 사용자 응답(확인/취소) 대기
  - 토스트 3.5초 후 자동 제거
- **`components/common/Toast.jsx`** 신규 생성
  - 우측 상단 고정 토스트 (success/error/info/warning 타입별 색상)
  - 좌측 컬러 바로 타입 시각화, X 버튼으로 수동 닫기
  - 커스텀 확인 모달 (ESC/외부 클릭 닫기, 취소/확인 버튼)
- **`App.jsx`** — `<Toast />` 전역 마운트
- **6개 파일 교체** (총 alert 18개, window.confirm 2개 → 0개)
  - `DocumentsPage.jsx` — 업로드 성공/실패, 삭제 confirm
  - `DocumentGeneratePage.jsx` — 생성/다운로드/템플릿 실패
  - `ChatPage.jsx` — 문서 다운로드
  - `UserManagement.jsx` — 사용자 추가/상태/권한/삭제 실패
  - `RegulationManagement.jsx` — 저장/삭제 실패
  - `TasksPanel.jsx` — Task 삭제 confirm

#### 5) Slack 알림 연동 UI 구현 (#85)

> 일정 관리 페이지에서 Slack 알림을 활성화/비활성화할 수 있는 토글 UI 추가

- **`frontend/src/components/schedules/SlackConnect.jsx`** 신규 생성
  - Slack 보라색 아이콘(#4A154B) + 토글 스위치 카드
  - 연결 시 CheckCircle 아이콘 + "일정 등록 시 채널로 알림이 전송됩니다" 안내
  - 미연결 시 "활성화하면 일정 등록 시 Slack 채널로 알림을 보냅니다" 안내
  - 토글 클릭 → `connect()`/`disconnect()` + toast 알림 (성공/실패)

- **`frontend/src/api/slack.js`** 신규 생성
  - `getSlackStatus()` — 연결 상태 조회
  - `connectSlack()` — 알림 활성화
  - `disconnectSlack()` — 연결 해제
  - `sendSlackNotification(payload)` — 알림 전송

- **`frontend/src/store/slackStore.js`** 신규 생성
  - Zustand + persist (localStorage `slack-store`)
  - `connected`, `loading` 상태
  - `fetchStatus()` — 백엔드 상태 동기화
  - `connect()` / `disconnect()` 액션

- **`frontend/src/pages/SchedulesPage.jsx`** 수정
  - `SlackConnect` 컴포넌트를 Google 서비스 연결 카드 아래에 배치

#### 6) 일정 수정 기능 구현

- **`CalendarView.jsx`** — `DayDetailPopup`에 Pencil 수정 아이콘 추가
  - 삭제 아이콘 왼쪽에 배치, hover 시 파란색 전환
  - `onEditEvent`, `onCanEdit` prop 추가 — 수정/삭제 권한 독립 분리
  - 수정 권한: 본인 DB 일정만 (관리자도 남의 일정 수정 불가)
  - 삭제 권한: 기존 유지 (본인 + 관리자)
- **`ScheduleForm.jsx`** — `initialData` prop 추가로 편집 모드 지원
  - 전달 시 기존 값(제목, 날짜, 시간, 유형, 종일, 팀공유)으로 폼 프리필
  - 헤더: "일정 추가" / "일정 수정", 버튼: "등록" / "수정"
- **`SchedulesPage.jsx`** — 수정 흐름 연결
  - `editingSchedule` 상태 + `handleEditEvent` / `handleUpdateSchedule` 함수 추가
  - 기존 `updateSchedule` API (`PUT /schedules/{id}`) 연동
  - DB 일정에 `rawStartTime`/`rawEndTime` (HH:mm 형식) 저장 — 한국어 로케일 시간("오후 02:00") 대신 원본 시간 사용
  - DB 일정에 `year`, `isTeamVisible` 필드 추가
  - 수정 완료 시 목록 새로고침 + 폼 닫기
- **에러 처리 안전장치 추가**
  - Pydantic 422 에러의 `detail`이 객체 배열일 때 React 크래시 방지 (`typeof detail === 'string'` 체크)
  - `handleAddSchedule`에도 동일 적용

**수정 아이콘 표시 규칙:**
| 이벤트 | 수정 | 삭제 |
|--------|------|------|
| 내가 등록한 일정 | O | O |
| 타인이 등록한 일정 | X | X (관리자만 O) |
| 공휴일 | X | X |

#### 7) '팀 일정' 토글 버튼 제거

- 헤더 우측 '팀 일정' 버튼 제거 — 팀 소속이면 팀원 일정 항상 표시
- `showTeamSchedules` 상태 + useEffect 제거, `hasTeam`으로 직접 판단
- 미사용 `Users` import 제거

#### 8) 챗봇 대화목록 빈 세션 개선

**문제**: 챗봇 페이지 진입 시마다 서버에 새 세션이 생성되어, 메시지 없이 페이지를 떠나면 빈 "새 대화" 세션이 계속 쌓이는 현상

**수정 — `chatStore.js`**
- `initSession`: `createSession()` 호출 제거 → 세션 목록만 로드 후 `activeSessionId: null` 상태로 초기화
  - 페이지 진입 시 기존 세션 목록을 사이드바에 표시하되 서버 세션은 생성하지 않음
- `initSession` 내 빈 세션 정리 로직 추가:
  - "새 대화" 이름의 세션들에 대해 `getSessionMessages` 병렬 조회
  - 메시지 0개인 세션을 `deleteSessionAPI`로 서버에서 일괄 삭제 (Promise.allSettled)
  - 삭제된 세션 제외한 목록으로 상태 갱신
- `startNewSession` 액션 신규 추가: 서버 세션 생성 없이 `activeSessionId: null, messages: []` 로컬 상태만 초기화

**수정 — `ChatPage.jsx`**
- 좌측 레일 "새 대화" 버튼: `createSession` → `startNewSession`
- 대시보드 질문 자동 전송 시 중복 `createSession()` 호출 제거 (sendMessage 내부에서 처리)

**결과**: 세션은 실제로 메시지를 보낼 때만 생성 / 페이지 로드 시 기존 빈 "새 대화" 세션 자동 정리

#### 9) Sheets 삭제 기능 구현 + UX 개선

- **`backend/app/services/sheets_service.py`** — `delete_sheet()` 메서드 추가 (DB 레코드 삭제)
- **`backend/app/api/v1/sheets.py`** — `DELETE /sheets/{spreadsheet_id}` 엔드포인트 추가 (404 처리 포함)
- **`frontend/src/api/google.js`** — `deleteSheet(spreadsheetId)` API 함수 추가
- **`frontend/src/store/googleStore.js`** — `deleteSheet` 액션 추가 (API 호출 후 스토어 즉시 반영)
- **`frontend/src/components/schedules/SheetsDashboard.jsx`** — 각 시트 우측에 빨간 "삭제" 텍스트 버튼 추가 (동기화/열기와 통일감), 삭제 전 커스텀 confirm 모달("이 시트를 삭제하시겠습니까?"), 성공/실패 toast 알림, 삭제 중 로딩 상태 처리

### 다음 할 일
- Slack 백엔드 엔드포인트 연동 확인
- 전체 E2E 테스트
- 팀서비스 확장 UI 최종 대응 (#87)

---

## 2026-03-05 (목)

### 한 일

#### 1) 다크모드 UI 가시성 전반 개선

- **`globals.css`** — 다크모드 surface/border 색상 전체 밝기 상향 조정
  - body 배경 그라디언트 및 sidebar 배경도 동일 밝기로 조정

- **`MyPage.jsx`** — 다크모드에서 안 보이던 요소 전면 수정
  - AI 스타일 토글 선택 버튼: `bg-white` → `bg-surface-card`

- **`TaskPipelineWidget.jsx`** — 하드코딩된 `bg-white`/`bg-white/60` 전면 제거
  - 팀 아바타 pill, 유틸리티 버튼, Stage 헤더, 카드 컨테이너, 태스크 카드, Empty 상태, 진행률 바 영역 모두 CSS 변수 색상으로 교체

- **`AIChatWidget.jsx`, `CalendarWidget.jsx`** — `border border-white/60` → `border border-neutral-border`, 배경 `dark:bg-surface-card`로 교체

- **`GreetingBanner.jsx`** — 인라인 스타일(`rgba(255,255,255,0.45)`) 제거 → `bg-white/50 dark:bg-surface-card border-neutral-border` Tailwind 클래스로 교체

#### 2) 마이페이지 프로필 사진 업로드 기능 구현

- **`backend/app/api/v1/auth.py`** — `POST /auth/me/avatar` 엔드포인트 신규 추가
  - `UploadFile` 수신 → jpg/png/webp/gif 형식 검증
  - `backend/uploads/avatars/{uuid}.ext` 절대 경로로 저장 (추후 S3 교체 용이한 구조)
  - `users.avatar` 필드 URL로 즉시 업데이트 후 반환

- **`backend/app/main.py`** — `StaticFiles` 마운트 추가 (`/uploads` → `backend/uploads/`)
  - 절대 경로 `Path(__file__).resolve().parent.parent / "uploads"` 사용 (CWD 의존 제거)

- **`frontend/src/api/auth.js`** — `uploadAvatar(file)`, `updateProfile(payload)` 함수 추가
  - `uploadAvatar`: `FormData`로 multipart 업로드 (Content-Type 헤더 수동 지정 제거 → axios 자동 boundary 설정)
  - `updateProfile`: 기존 `client` 미import 버그 해결 (저장 버튼이 아예 동작하지 않던 문제)

- **`frontend/src/pages/MyPage.jsx`** — 프로필 사진 업로드 UI 구현
  - 카메라(`Camera`) 아이콘 버튼 추가 (아바타 우측 하단, 파란색)
  - 클릭 → 숨겨진 `<input type="file" accept="image/*">` 트리거
  - 파일 선택 즉시 `createObjectURL`로 미리보기 → 백엔드 업로드 → 영구 URL로 교체
  - 업로드 중 스피너 표시 + 버튼 비활성화, 실패 시 이전 아바타로 복원
  - URL 입력칸 제거, 안내 텍스트로 대체

#### 3) 마이페이지 프로필 저장 버그 수정

- **문제**: 프로필 수정 모달에서 "저장하기" 버튼 클릭 시 500 에러 발생, 사진 미리보기는 되나 저장 안 됨
- **원인 분석**:
  - `a1b2c3d4e5f6_avatar_column_to_text.py` 마이그레이션의 `down_revision`이 존재하지 않는 `8c278366604b`를 참조 → 마이그레이션이 DB에 실제 적용되지 않은 상태
  - DB의 `avatar` 컬럼이 `VARCHAR(255)`로 남아 있어 base64 문자열 저장 시 overflow → 500
- **수정 (백엔드)**:
  - `backend/alembic/versions/a1b2c3d4e5f6_avatar_column_to_text.py` — `down_revision` 수정 (`8c278366604b` → `7939e09c25f2`)
  - develop push로 자동 배포
- **수정 (프론트엔드)**:
  - `handleAvatarFileChange` — canvas 리사이즈 방식 복구 (최대 200px, JPEG 75%)
  - `saveError` state 추가, 모달 열기/닫기 시 에러 초기화

#### 4) 마이페이지 개인화 설정 → 3개 신규 섹션으로 교체 (`MyPage.jsx`)

- **개인화 설정 섹션 제거** — AI 답변 스타일 토글, 시스템 알림 토글, 단축키 관리 버튼 삭제
- **다가오는 일정 미리보기** 섹션 추가
  - 오늘 이후 일정을 날짜순 정렬 후 최대 4개 표시
  - 일정 타입(회의/업무/마감) 뱃지 + 우선순위 컬러 도트(high=빨강, medium=노랑, low=초록)
  - "전체 보기" 링크 → `/schedules`
- **AI 활용 통계** 섹션 추가
  - AI 대화 / 생성 문서 / 등록 일정 수를 프로그레스 바로 시각화
  - 가입 이후 전체 누적 사용량 표시
- **계정 보안** 섹션 추가
  - 이메일, 계정 권한, 가입일 표시
  - 비밀번호 변경 버튼 → 모달 오픈 (현재/새/확인 입력, 눈 아이콘 토글, 8자 미만·불일치 유효성 검사, 성공 시 1.5초 후 자동 닫힘)

#### 5) 상단바 드롭다운 "비밀번호 변경" 항목 제거 (`Topbar.jsx`, `Header.jsx`)

- `Topbar.jsx` — 드롭다운 메뉴에서 "비밀번호 변경" 버튼 제거
- `Header.jsx` — 동일하게 제거 (기존에 수정됨), `Key` import 정리
- 비밀번호 변경은 마이페이지 → 계정 보안 섹션에서 일원화

#### 6) 대시보드 Today Schedule 타임라인 시간 범위 자동 맞춤 (`ScheduleTimelineWidget.jsx`)

- **기존**: 08~18 하드코딩
- **변경**: 기본 09~18 표시, 범위 밖 일정이 있을 때만 자동 확장
  - 가장 이른 시작보다 1시간 앞 / 가장 늦은 종료보다 1시간 뒤로 범위 조정
  - 현재 시간 바도 표시 범위 기준으로 재계산, 범위 밖이면 숨김

#### 7) Header.jsx Today Schedule 날짜 필터 수정 (`Header.jsx`)

- 기존: `start_time_gte`/`start_time_lt` 쿼리 파라미터로 필터 시도 → 백엔드가 해당 파라미터를 지원하지 않아 무시됨
- 변경: 전체 일정 수신 후 프론트에서 오늘 날짜(`YYYY-MM-DD`) 기준으로 직접 필터링

#### 8) 일정 추가 시 종료 시간 자동 설정 + 유효성 검사 (`ScheduleForm.jsx`)

- 시작 시간 선택 시 종료 시간을 자동으로 +1시간으로 설정
- 23:10 이후는 23:50으로 고정 (범위 초과 방지)
- 이후 종료 시간 드롭다운에서 수동 수정 가능
- 종료 시간이 시작 시간 이하면 등록 차단 — "종료 시간은 시작 시간보다 늦어야 합니다" 에러 표시
- 종일 일정은 시간 검사 제외

### 다음 할 일
- 전체 E2E 테스트
- 판단 Agent 스트리밍 디버깅

---

## 현재 구현 현황 요약

| 항목 | 상태 | 비고 |
|------|------|------|
| 디자인 시스템 (#24) | ✅ 완료 | 컬러 토큰, Tailwind 테마 적용 |
| 공통 컴포넌트 + 대시보드 (#25) | ✅ 완료 | Layout, Sidebar, Header + 대시보드 11개 컴포넌트 |
| 로그인/회원가입 UI (#26) | ✅ UI 완료 | Mock 상태, 백엔드 연동 대기 |
| 챗봇 UI + SSE (#27) | ✅ UI 완료 | SSE Mock 모드, 백엔드 연동 대기 |
| 문서 생성 페이지 | ✅ 완료 | MeetingMinutesPage, DocumentGeneratePage |
| Google Services UI | ✅ 완료 | 5개 서비스 통합 UI |
| 일정 관리 | ✅ 완료 | Google Calendar 실제 연동, 공휴일 중복 제거, 자동 갱신 |
| KeywordHighlight (FR-DOC-006) | ✅ 완료 | 문서 검색 + 규정 패널 키워드 하이라이트 |
| 글씨 크기 조절 | ✅ 완료 | FontSizeControl (가-/가+), 전체 54파일 px→rem 변환 |
| 다크 모드 | ✅ 완료 | CSS 변수 방식, OS 감지, localStorage 유지, ThemeToggle |
| 파일 드래그&드롭 | ✅ 완료 | 채팅 파일 첨부, 검증(형식/크기), FileChip |
| 대화 세션 관리 | ✅ 완료 | localStorage 세션 목록, 자동 생성/전환/삭제 |
| **백엔드 실제 연동** | 🔄 진행중 | 일정 관리 + 대시보드 완료, 문서 생성/관리자 교체 필요 |

### 파일 현황
- **페이지**: 10개 전체 구현
- **컴포넌트**: 63개 (chat 15, dashboard 11, documents 7, meetings 5, schedules 8, auth 3, admin 3, common 12)
- **스토어**: 4개 (auth, chat, google, ui)
- **훅**: 4개 (useAuth, useChat, useSSE, useGoogleServices)
- **API**: 8개 (client, auth, chat, documents, meetings, schedules, google, admin)
- **npm 패키지 추가**: framer-motion
