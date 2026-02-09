# WorkFlow Agent (듀듀) - 역할 분배 & 할 일 보드

---

## 팀원 매핑

| 이름 | 역할 | GitHub 라벨 |
|------|------|-------------|
| **신지용** | PM + Intent 분류 + Agent 오케스트레이션 | `팀원A:PM` |
| **윤경은** | AI 리드 (파인튜닝 v1 + 판단 Agent + RAG) | `팀원B:AI리드` |
| **진승언** | AI 서브 (파인튜닝 v2 + 문서 Agent) | `팀원C:AI서브` |
| **안혜빈** | Backend + DB + 인증 + 일정 Agent + Google Calendar | `팀원D:Backend` |
| **문지영** | Frontend 전담 (React) | `팀원E:Frontend` |

---

## 시스템 전체 흐름

```
사용자 질문
     │
     ▼
[지용] Intent Classification (klue/bert-base)
     │
     ▼
[지용] LangGraph Agent Orchestrator
     │ (조건부 라우팅)
     ├── judgment      → [경은] RAG + Reranker + sLLM (LoRA v1)
     │                        → 다중 규정 교차 판단 + confidence score
     │
     ├── doc_*         → [승언] Docling/PaddleOCR + sLLM (LoRA v2)
     │                        → 요약 / 생성 / 리스크 감지
     │
     └── schedule_*    → [혜빈] 일정 CRUD + Google Calendar 동기화
     │
     ▼
[지용] SSE 스트리밍 응답
     │
     ▼
[지영] 실시간 토큰 렌더링 → 완료 후 카드 UI
```

---

## 작업 의존성 (이거 먼저 봐주세요)

```
[지용] API 스키마 확정 (#2)
     ├──→ [지영] Mock API로 UI 개발 시작
     └──→ [혜빈] API 구현 시작

[지용] AgentState 확정 (#3)
     └──→ [경은][승언][혜빈] 각자 Agent 노드 개발 가능

[경은] 모델 벤치마크 (#7)
     ├──→ [경은] LoRA v1 파인튜닝 시작
     └──→ [승언] LoRA v2 파인튜닝 시작 (같은 모델 사용)

[혜빈] JWT 인증 (#20)
     └──→ [지영] 로그인 UI 연동
```

---

# 1단계: 설계 및 환경 세팅

> 이 단계가 끝나야 본격 개발이 시작됩니다

---

### 신지용 (PM)

| # | 이슈 | 할 일 | 우선순위 |
|---|------|-------|---------|
| #2 | **API 스키마 정의** | `backend/app/schemas/*.py` 검토 및 확정, 팀 전체 공유 | BLOCKER |
| #3 | **AgentState 필드 확정** | `ai/agents/state.py` 필드를 경은/승언/혜빈과 합의 | BLOCKER |

**체크리스트:**
- [ ] Chat API 스키마 (SSE 스트리밍 포함) 확정
- [ ] Documents / Meetings / Schedules CRUD 스키마 확정
- [ ] **문서 생성/다운로드 API 스키마 확정** (FR-DOC-008)
- [ ] **파싱 상태 조회 API 스키마 확정** (NF-PRF-002)
- [ ] Auth API 스키마 (혜빈과 협의) + **비밀번호 재설정 API**
- [ ] AgentState 필드 + 각 Agent 응답 형식 확정 (doc_generate 응답 포함)
- [ ] Docker + GitHub 세팅 완료 확인

---

### 윤경은 (AI 리드)

| # | 이슈 | 할 일 | 우선순위 |
|---|------|-------|---------|
| #7 | **모델 3개 베이스라인 비교** | Qwen3 / Kanana / EXAONE 동일 테스트셋 비교 | BLOCKER |

**체크리스트:**
- [ ] 테스트 데이터셋 50~100개 준비
- [ ] Qwen3-8B 벤치마크 (한국어, 규정해석, 판단형식, 속도)
- [ ] Kanana-8B 벤치마크
- [ ] EXAONE 3.5-7.8B 벤치마크
- [ ] 비교 리포트 작성 → **베이스 모델 확정** (승언에게 공유)

---

### 진승언 (AI 서브)

| # | 이슈 | 할 일 | 우선순위 |
|---|------|-------|---------|
| #15 | **Docling + PaddleOCR 테스트** | 실제 규정 PDF로 파싱 품질 확인 | 높음 |

**체크리스트:**
- [ ] Docling 설치 + 디지털 PDF 파싱 테스트
- [ ] PaddleOCR 설치 + 스캔 문서 OCR 테스트
- [ ] 실제 규정 문서로 품질 확인 (테이블, 조항 구조)
- [ ] **문서 템플릿 구조 설계** (`ai/templates/` — 회의록/보고서/JD/제안서)
- [ ] **회의록 자동 감지 로직 설계** (FR-DOC-002)
- [ ] 학습 데이터 구축 계획 수립 (1,500개)

---

### 안혜빈 (Backend)

| # | 이슈 | 할 일 | 우선순위 |
|---|------|-------|---------|
| #19 | **DB 스키마 확정 + Alembic 마이그레이션** | 9개 테이블 ERD, 첫 마이그레이션 | BLOCKER |

**체크리스트:**
- [ ] `docker-compose up -d db redis`로 PostgreSQL 실행
- [ ] `backend/app/models/*.py` 9개 모델 필드 검토/수정
- [ ] ERD 다이어그램 작성
- [ ] `alembic revision --autogenerate -m "Initial tables"`
- [ ] `alembic upgrade head`
- [ ] Google Cloud Console OAuth 설정 시작

---

### 문지영 (Frontend)

| # | 이슈 | 할 일 | 우선순위 |
|---|------|-------|---------|
| #24 | **Figma 디자인 + 디자인 시스템** | 7개 화면 디자인 | 높음 |

**체크리스트:**
- [ ] `cd frontend && npm install && npm run dev` 확인
- [ ] 디자인 시스템 정의 (컬러: #FFFEF5, #3B82F6, #8B5CF6)
- [ ] 7개 화면 Figma 디자인
- [ ] 컴포넌트 디자인 (카드, 뱃지, 버튼, 인풋)

---

# 2단계: 데이터 구축 + 기반 개발

---

### 신지용

| # | 이슈 | 할 일 |
|---|------|-------|
| #4 | **Intent 학습 데이터 구축** | 7개 카테고리 × 150~200문장, Claude/GPT-4 증강 |

**체크리스트:**
- [ ] 카테고리별 시드 문장 30개씩 직접 작성
- [ ] Claude/GPT-4로 증강 → 카테고리별 150~200개
- [ ] 품질 검증 (중복 제거, 라벨 정확성)
- [ ] train/eval 분할 (85:15)

---

### 윤경은

| # | 이슈 | 할 일 |
|---|------|-------|
| #9 | **판단 학습 데이터 구축 (1,300개)** | 판단 예시 500개 + 규정 해석 Q&A 800개 (승언과 공동) |

**체크리스트:**
- [ ] 규정 기반 Yes/No 판단 500개 구축
- [ ] 규정 해석 Q&A 800개 검증 (승언이 작성 → 경은이 검증)
- [ ] 검증용 10~15% 분리
- [ ] JSONL 형식 저장

---

### 진승언

| # | 이슈 | 할 일 |
|---|------|-------|
| #14 | **학습 데이터셋 구축 (1,500개)** | 규정 Q&A 800개 작성 + 회의록 400개 + 요약 300개 |

**체크리스트:**
- [ ] 규정 해석 Q&A 800개 작성 (Claude/GPT-4 → 검증)
- [ ] 회의록 → 결정사항/Action Item 추출 400개
- [ ] 문서 요약 + 생성 300개
- [ ] 검증용 15% 분리
- [ ] JSONL 형식 저장

---

### 안혜빈

| # | 이슈 | 할 일 |
|---|------|-------|
| #20 | **JWT 인증 시스템** | 로그인/회원가입/토큰 관리 |

**체크리스트:**
- [ ] 비밀번호 해싱 (bcrypt)
- [ ] JWT 토큰 생성/검증
- [ ] 회원가입 API (`/api/v1/auth/register`)
- [ ] 로그인 API (`/api/v1/auth/login`)
- [ ] **비밀번호 찾기/변경 API** (`/api/v1/auth/password-reset/*`)
- [ ] `get_current_user` 의존성 완성
- [ ] Google OAuth 연결 시작

---

### 문지영

| # | 이슈 | 할 일 |
|---|------|-------|
| #25 | **공통 컴포넌트 + 대시보드** | Layout, Sidebar, Header + 대시보드 5개 컴포넌트 |
| #26 | **로그인/회원가입 UI** | LoginForm, RegisterForm + Auth 연동 |

**체크리스트:**
- [ ] Layout / Sidebar / Header 완성
- [ ] 대시보드: StatCard, RecentQueries, ActionItemList, ActivityTimeline, RiskAlert
- [ ] **대시보드 추가: TopQueries (월/주/일), QuickSearch, AutoScanBadge**
- [ ] LoginForm / RegisterForm / **PasswordReset**
- [ ] Zustand authStore + useAuth 훅 연동
- [ ] Mock 데이터로 UI 확인

---

# 3단계: 핵심 AI 개발

---

### 신지용

| # | 이슈 | 할 일 |
|---|------|-------|
| #5 | **Intent 분류 모델 학습** | klue/bert-base 파인튜닝, 목표 F1 90%+ |

---

### 윤경은

| # | 이슈 | 할 일 |
|---|------|-------|
| #10 | **LoRA v1 파인튜닝** | 판단 특화 (1,300개), QLoRA 4-bit, RunPod A100 |
| #8 | **RAG 파이프라인 구축** | ChromaDB + BM25 + Vector + Reranker |
| #11 | **vLLM 서빙 환경** | OpenAI 호환 API + LoRA 핫스왑 + 스트리밍 |

---

### 진승언

| # | 이슈 | 할 일 |
|---|------|-------|
| #16 | **LoRA v2 파인튜닝** | 문서 분석 특화 (700개), 경은과 동일 모델 사용 |

---

### 안혜빈

| # | 이슈 | 할 일 |
|---|------|-------|
| #21 | **Google Calendar 연동** | OAuth 플로우, Push/Pull, 토큰 자동 갱신 |

---

### 문지영

| # | 이슈 | 할 일 |
|---|------|-------|
| #27 | **챗봇 UI + SSE 스트리밍** | ChatWindow, 토큰 렌더링, 판단/문서/일정 카드, **GenerateCard, MeetingSummaryCard, AgentIndicator, ErrorMessage, SuggestedQuestions, RegulationPanel** |

---

# 4단계: Agent 개발

---

### 신지용

| # | 이슈 | 할 일 |
|---|------|-------|
| #6 | **LangGraph 오케스트레이터 + SSE** | StateGraph 빌드, 조건부 라우팅, 스트리밍 엔드포인트 |

---

### 윤경은

| # | 이슈 | 할 일 |
|---|------|-------|
| #12 | **판단 Agent 확장** | 다중규정 교차판단, confidence, 조건부 판단, 이력 참조 |

---

### 진승언

| # | 이슈 | 할 일 |
|---|------|-------|
| #17 | **문서 Agent 구현** | 요약, **템플릿 기반 생성 (회의록/보고서/JD/제안서)**, 회의록 분석, 리스크 감지, scope 반영, **규정 위반 자동 스캔** |

---

### 안혜빈

| # | 이슈 | 할 일 |
|---|------|-------|
| #22 | **일정 Agent API** | CRUD + 우선순위 자동설정 + 담당자 + GCal 동기화 |
| #23 | **관리자 API + 로그** | 사용자 CRUD, 통계, **질의 로그 탭**, **Top 질의 통계**, **권한별 접근 설정**, AES-256 암호화 |

---

### 문지영

| # | 이슈 | 할 일 |
|---|------|-------|
| #28 | **문서/회의/일정 관리 UI** | 3개 페이지 전체 구현, **KeywordHighlight, ParsingStatus, JsonViewer** 포함 |

---

# 5단계: 통합 및 테스트

---

| 담당 | # | 할 일 |
|------|---|-------|
| **지용** | #30 | 전체 파이프라인 E2E 연결 테스트 |
| **경은** | #13 | 성능 평가 리포트 (판단 정확도, RAG MRR, 응답속도) |
| **승언** | #18 | 성능 평가 리포트 (ROUGE-L, BERTScore, F1) |
| **지영** | #29 | 관리자 UI + 전체 API 연동 + 반응형 |

---

# 6단계: 배포 및 마무리

---

| 담당 | # | 할 일 |
|------|---|-------|
| **지용** | #31 | AWS 배포 + Docker + CI/CD + 최종 테스트 + 발표 준비 |

---

## 파인튜닝 데이터 분배 (총 2,000개)

| 카테고리 | 수량 | 담당 |
|---------|------|------|
| 규정 기반 Yes/No 판단 | 500개 | **경은** |
| 규정 해석 Q&A | 800개 | **승언**(작성) + **경은**(검증) |
| 회의록 → 결정사항/Action Item | 400개 | **승언** |
| 문서 요약 + 문서 생성 | 300개 | **승언** |
| **합계** | **2,000개** | |

---

## Git 브랜치 전략

```
main (배포용 - 지용만 머지)
 └── develop (통합 개발)
      ├── feature/intent-classification    (지용)
      ├── feature/agent-orchestrator       (지용)
      ├── feature/judgment-agent           (경은)
      ├── feature/rag-pipeline             (경은)
      ├── feature/reranker                 (경은)
      ├── feature/finetuning-judgment      (경은)
      ├── feature/document-agent           (승언)
      ├── feature/document-parser          (승언)
      ├── feature/finetuning-document      (승언)
      ├── feature/schedule-agent           (혜빈)
      ├── feature/google-calendar          (혜빈)
      ├── feature/auth-system              (혜빈)
      ├── feature/database                 (혜빈)
      ├── feature/dashboard-ui             (지영)
      ├── feature/chatbot-ui               (지영)
      ├── feature/calendar-ui              (지영)
      └── feature/streaming-ui             (지영)
```

### 커밋 규칙

```bash
# 형식
<type>: <설명> #이슈번호

# 예시
feat: 판단 Agent Yes/No 판단 로직 구현 #12
fix: Intent 분류 confidence 임계값 조정 #5
docs: API 스키마 문서 업데이트 #2

# type 종류
feat:     새 기능
fix:      버그 수정
docs:     문서 수정
refactor: 리팩토링
test:     테스트
chore:    설정/환경
```

### PR 규칙

```
1. feature 브랜치에서 작업
2. push 후 GitHub에서 PR 생성 (develop ← feature/xxx)
3. PR 본문에 "Closes #이슈번호" 작성
4. 리뷰 후 머지 → 이슈 자동 닫힘
```

---

## UI_UX.pdf 기반 추가 파일 (2026-02-09 추가)

> `docs/UI_UX.pdf` 요구사항 대조 후 누락분을 추가했습니다.

### 추가된 프론트엔드 컴포넌트 (지영 담당)

| 파일 | 기능 | 요구사항 |
|------|------|---------|
| `components/chat/GenerateCard.jsx` | 문서 생성 응답 (미리보기 + 다운로드) | FR-DOC-008 |
| `components/chat/MeetingSummaryCard.jsx` | 회의 요약 응답 (결정사항 + Action Items) | - |
| `components/chat/ErrorMessage.jsx` | 에러/폴백 메시지 + 재시도 | NF-ST-001 |
| `components/chat/SuggestedQuestions.jsx` | 추천 질문 칩 | - |
| `components/chat/RegulationPanel.jsx` | 관련 규정 패널 (우측) | - |
| `components/chat/AgentIndicator.jsx` | Agent 호출 인디케이터 | - |
| `components/common/KeywordHighlight.jsx` | 검색 키워드 하이라이트 | FR-DOC-006 |
| `components/common/ParsingStatus.jsx` | 파싱 상태 표시 | NF-PRF-002 |
| `components/common/JsonViewer.jsx` | 원본 JSON 보기 | FR-DOC-004 |
| `components/dashboard/TopQueries.jsx` | Top 질의 응답 (월/주/일) | - |
| `components/dashboard/QuickSearch.jsx` | 빠른 규정 검색 바 | - |
| `components/dashboard/AutoScanBadge.jsx` | 자동 스캔 뱃지 | FR-DOC-010 |
| `components/auth/PasswordReset.jsx` | 비밀번호 찾기/변경 | - |

### 추가된 AI 템플릿 시스템 (승언 담당)

| 파일 | 기능 |
|------|------|
| `ai/templates/base.py` | 템플릿 베이스 클래스 (render, to_docx, to_pdf) |
| `ai/templates/meeting_minutes.py` | 회의록 템플릿 |
| `ai/templates/report.py` | 보고서 템플릿 |
| `ai/templates/jd.py` | 채용 공고 템플릿 |
| `ai/templates/proposal.py` | 제안서 템플릿 |

### 추가된 백엔드 서비스/API (혜빈 담당)

| 파일 | 기능 |
|------|------|
| `services/template_service.py` | 문서 생성 + 다운로드 + 템플릿 감지 |
| `services/statistics_service.py` | Top 질의 통계 + 질의 로그 |
| `services/parsing_service.py` | 파싱 상태 관리 |
| `api/v1/documents.py` | 추가: `/generate`, `/{id}/download`, `/{id}/parsing-status`, `/search/highlight` |
| `api/v1/admin.py` | 추가: `/query-logs`, `/top-queries`, `/users/{id}/permissions` |
| `api/v1/auth.py` | 추가: `/password-reset/request`, `/password-reset/confirm` |
