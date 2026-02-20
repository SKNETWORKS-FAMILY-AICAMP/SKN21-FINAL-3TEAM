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

### 다음 할 일
- 나머지 Mock → 실제 API 교체
- 관리자 API 연동 (#29)

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

### 다음 할 일
- 나머지 Mock → 실제 API 교체
- 관리자 API 연동 (#29)

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

### 다음 할 일
- 관리자 API 연동 (#29)
- 나머지 Mock → 실제 API 교체 (대시보드, 채팅, 문서, 회의)

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
| 로그아웃 기능 | ✅ 완료 | Sidebar 하단 텍스트 버튼 + DEV_BYPASS_AUTH 복원 |
| 글씨 크기 조절 | ✅ 완료 | FontSizeControl (가-/가+), 전체 54파일 px→rem 변환 |
| 다크 모드 | ✅ 완료 | CSS 변수 방식, OS 감지, localStorage 유지, ThemeToggle |
| 인쇄 기능 | ✅ 완료 | `.print-area` 선택적 인쇄, 문서/회의 프리뷰+상세 |
| 페이지 전환 애니메이션 | ✅ 완료 | framer-motion, fade+slide 200ms |
| 파일 드래그&드롭 | ✅ 완료 | 채팅 파일 첨부, 검증(형식/크기), FileChip |
| 대화 세션 관리 | ✅ 완료 | localStorage 세션 목록, 자동 생성/전환/삭제 |
| **백엔드 실제 연동** | 🔄 진행중 | 일정 관리 완료, 나머지 페이지 교체 필요 |

### 파일 현황
- **페이지**: 10개 전체 구현
- **컴포넌트**: 63개 (chat 15, dashboard 11, documents 7, meetings 5, schedules 8, auth 3, admin 3, common 12)
- **스토어**: 4개 (auth, chat, google, ui)
- **훅**: 4개 (useAuth, useChat, useSSE, useGoogleServices)
- **API**: 8개 (client, auth, chat, documents, meetings, schedules, google, admin)
- **npm 패키지 추가**: framer-motion
