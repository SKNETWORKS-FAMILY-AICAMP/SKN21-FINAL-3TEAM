# WorkFlow Agent (듀듀) - 역할 분배 & 할 일 보드

---

## 팀원 매핑

| 이름 | 역할 | GitHub 라벨 |
|------|------|-------------|
| **신지용** | PM + Intent 분류 + Agent 오케스트레이션 | `지용:PM` |
| **윤경은** | AI 서브 (파인튜닝 v1 + 판단 Agent + RAG) | `경은:AI서브` |
| **진승언** | AI 리드 (파인튜닝 v2 + 문서 Agent) | `승언:AI리드` |
| **안혜빈** | Backend + DB + 인증 + 일정 Agent + Google Services 통합 | `혜빈:Backend` |
| **문지영** | Frontend 전담 (React) | `지영:Frontend` |

---

## 개발 전략: LLM 먼저 → 파인튜닝은 나중에

```
1. LLM API (GPT/Claude)로 전체 기능 먼저 구현
2. 실제 동작 확인하면서 input/output 형태 확정
3. 확정된 형태에 맞춰 데이터 수집
4. 파인튜닝 → sLLM 교체 (모델만 갈아끼우면 됨)
```

**이미 확보된 데이터 (먼저 파인튜닝 가능):**

| 데이터 | 건수 | 파인튜닝 |
|--------|:----:|---------|
| 회의록 분석 | 800 | LoRA v2 → meeting_generate |
| 규정 판단 (Yes/No) | 1,000 | LoRA v1 → judgment |
| 규정 Q&A | 수집 중 | LoRA v1 → judgment |

**나머지 기능 (LLM API로 먼저 구현):**
- 문서 요약, 문서 생성, 문서 검색 답변, 리스크 감지 → GPT/Claude API로 동작
- 나중에 데이터 수집 후 sLLM으로 교체

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
     ├── judgment      → [경은] RAG + Reranker + sLLM (LoRA v1) 또는 LLM API
     │                        → 다중 규정 교차 판단 + confidence score
     │
     ├── doc_*         → [승언] 텍스트 추출 + sLLM (LoRA v2) 또는 LLM API
     │                        → 요약 / 생성 / 리스크 감지 (동적 템플릿 필드 방식)
     │
     └── schedule_*    → [혜빈] 일정 CRUD + Google 서비스 통합 (Calendar+Tasks+Gmail+Meet+Sheets)
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

[경은] LLM API 연동 (#39)
     └──→ [승언] document_agent에서 LLM API 사용 가능 (#40)

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
- [ ] **텍스트 추출기 구현** (PDF/DOCX → 텍스트, PyMuPDF + python-docx)

---

### 안혜빈 (Backend)

| # | 이슈 | 할 일 | 우선순위 |
|---|------|-------|---------|
| #19 | **DB 스키마 확정 + Alembic 마이그레이션** | 11개 테이블 ERD, 첫 마이그레이션 | BLOCKER |

**체크리스트:**
- [v] `docker-compose up -d db redis`로 PostgreSQL 실행
- [v] `backend/app/models/*.py` 11개 모델 필드 검토/수정 (google_sheet_trackers 포함)
- [v] ERD 다이어그램 작성
- [v] `alembic revision --autogenerate -m "Initial tables"`
- [v] `alembic upgrade head`
- [v] Google Cloud Console OAuth 설정 시작 (Calendar + Tasks + Gmail + Sheets scope)

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

# 2단계: 기반 개발 + LLM API 연동

> 데이터 수집을 기다리지 않고 LLM API로 기능 먼저 구현

---

### 신지용

| # | 이슈 | 할 일 |
|---|------|-------|
| #4 | **Intent 학습 데이터 구축** | 7개 카테고리 × 200문장, Claude/GPT-4 증강 |

**체크리스트:**
- [ ] 카테고리별 시드 문장 30개씩 직접 작성
- [ ] Claude/GPT-4로 증강 → 카테고리별 200개
- [ ] 품질 검증 (중복 제거, 라벨 정확성)
- [ ] train/eval 분할 (85:15)

---

### 윤경은

| # | 이슈 | 할 일 |
|---|------|-------|
| #39 | **[B-8] LLM API 연동 모듈** | GPT/Claude API 호출 공통 모듈 작성 |
| #8 | **[B-2] RAG 파이프라인 구축** | ChromaDB + BM25 + Vector + Reranker |

**체크리스트:**
- [ ] LLM API 공통 모듈 작성 (나중에 sLLM으로 교체 가능한 구조)
- [ ] judgment_agent LLM API 연동 (규정 판단 + Q&A)
- [ ] ChromaDB 세팅 + 규정 문서 임베딩
- [ ] BM25 + Vector 하이브리드 검색 구현
- [ ] Reranker 연동

---

### 진승언

| # | 이슈 | 할 일 |
|---|------|-------|
| #40 | **[C-7] document_agent LLM API 연동** | 문서 요약/생성/검색/리스크 감지 LLM 연동 |

**체크리스트:**
- [ ] document_agent LLM API 연동 (동적 템플릿 필드 방식)
- [ ] 문서 요약: 텍스트 추출 → 필드 목록 삽입 → LLM → JSON 파싱
- [ ] 문서 생성: 템플릿 필드 조회 → LLM → JSON 파싱 → Template 렌더링
- [ ] 문서 검색: RAG 검색결과 + 질문 → LLM → 정리된 답변
- [ ] 리스크 감지: 분석 내용 + 규정 → LLM → 위반 여부 판단
- [ ] **Template 코드 수정** (REQUIRED_FIELDS를 데이터 스키마에 맞게)
- [ ] 긴 문서 청크 분할 로직

---

### 안혜빈

| # | 이슈 | 할 일 |
|---|------|-------|
| #20 | **JWT 인증 시스템** | 로그인/회원가입/토큰 관리 |

**체크리스트:**
- [v] 비밀번호 해싱 (bcrypt)
- [v] JWT 토큰 생성/검증
- [v] 회원가입 API (`/api/v1/auth/register`)
- [v] 로그인 API (`/api/v1/auth/login`)
- [v] **비밀번호 찾기/변경 API** (`/api/v1/auth/password-reset/*`)
- [v] `get_current_user` 의존성 완성
- [v] Google OAuth 연결 시작
- [v] **문서 업로드 API + 텍스트 추출 연동**

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

# 3단계: Agent 개발 + 핵심 기능

---

### 신지용

| # | 이슈 | 할 일 |
|---|------|-------|
| #5 | **Intent 분류 모델 학습** | klue/bert-base 파인튜닝, 목표 F1 90%+ |
| #6 | **LangGraph 오케스트레이터 + SSE** | StateGraph 빌드, 조건부 라우팅, 스트리밍 엔드포인트 |

---

### 윤경은

| # | 이슈 | 할 일 |
|---|------|-------|
| #12 | **판단 Agent 구현** | 다중규정 교차판단, confidence, 조건부 판단, 이력 참조 |

---

### 진승언

| # | 이슈 | 할 일 |
|---|------|-------|
| #17 | **문서 Agent 구현** | 요약, **템플릿 기반 생성 (동적 필드 방식)**, 회의록 분석, 리스크 감지, **규정 위반 자동 스캔** |

---

### 안혜빈

| # | 이슈 | 할 일 |
|---|------|-------|
| #21 | **Google Calendar 연동** | OAuth 플로우, Push/Pull, 토큰 자동 갱신 |
| #33 | **Google Services 확장 (Tasks+Gmail+Meet+Sheets)** | GoogleBaseService, 4개 서비스 백엔드, 통합 OAuth, 17개 API |

---

### 문지영

| # | 이슈 | 할 일 |
|---|------|-------|
| #27 | **챗봇 UI + SSE 스트리밍** | ChatWindow, 토큰 렌더링, 판단/문서/일정 카드, GenerateCard, MeetingSummaryCard, AgentIndicator, ErrorMessage, SuggestedQuestions, RegulationPanel |

---

# 4단계: 데이터 수집 + 파인튜닝 (LLM 구현 후 진행)

> 기능이 LLM으로 동작하는 것을 확인한 후, 확정된 input/output에 맞춰 데이터 수집

---

### 윤경은

| # | 이슈 | 할 일 |
|---|------|-------|
| #9 | **판단 데이터 변환** | Excel → JSONL + 규정 원문 추가 |
| #10 | **LoRA v1 파인튜닝** | 판단 1,000건 + Q&A, QLoRA 4-bit |
| #11 | **vLLM 서빙 환경** | OpenAI 호환 API + LoRA 핫스왑 + 스트리밍 |

---

### 진승언

| # | 이슈 | 할 일 |
|---|------|-------|
| #14 | **회의록 JSONL 변환** | proceedings/*.json → meeting_train.jsonl |
| #16 | **LoRA v2 파인튜닝** | 회의록 800건, 경은과 동일 베이스 모델 |
| #41 | **[C-8] 추가 데이터 수집** | 문서 요약 300건 + 문서 생성 200건 + 검색 답변 200건 + 리스크 200건 |

---

### 추가 데이터 수집 역할 분담 (5명)

| 담당자 | 데이터 | 건수 |
|--------|--------|:----:|
| **지용** | Intent 분류 문장 (7개 카테고리) | 1,400 |
| **경은** | 규정 해석 Q&A | 500 |
| **승언** | 문서 요약 300건 + 문서 검색 답변 200건 | 500 |
| **혜빈** | 문서 생성 200건 | 200 |
| **지영** | 리스크 감지 200건 | 200 |

> 상세 양식 및 수집 방법: `data/DATA_GUIDE.md` 참고

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

## 파인튜닝 데이터 현황

### 확보 완료

| 데이터 | 건수 | 어댑터 | 상태 |
|--------|:----:|--------|:----:|
| 규정 판단 (Yes/No) | 1,000 | LoRA v1 | ✅ Excel → JSONL 변환 필요 |
| 회의록 분석 | 800 | LoRA v2 | ✅ JSON → JSONL 변환 필요 |
| 규정 Q&A | ?건 | LoRA v1 | 🔄 수집 중 |

### 추후 수집 (LLM 구현 후)

| 데이터 | 건수 | 어댑터 |
|--------|:----:|--------|
| Intent 분류 문장 | 1,400 | BERT |
| 문서 검색 답변 | 200 | LoRA v2 |
| 문서 요약 (동적 필드) | 300 | LoRA v2 |
| 문서 생성 (동적 필드) | 200 | LoRA v2 |
| 리스크 감지 | 200 | LoRA v2 |

### 어댑터별 학습 데이터

| 어댑터 | 데이터 | 합계 |
|--------|-------|:----:|
| **LoRA v1** (판단 특화) | 판단 1,000 + Q&A 500 | **1,500** |
| **LoRA v2** (문서 특화) | 회의록 800 + 검색 200 + 요약 300 + 생성 200 + 리스크 200 | **1,700** |

> 검증용 15% 별도 분리 (학습에 사용하지 않음)

---

## Git 브랜치 전략

> 1인 1브랜치 원칙 — 브랜치 5개로 충돌 최소화

```
main (배포용 - PM 지용만 머지)
 └── develop (통합 개발 - PR 머지 대상)
      ├── feat/pm-지용          스키마, Intent, 오케스트레이터, SSE
      ├── feat/ai-경은          LLM API, RAG, 판단 Agent, 파인튜닝
      ├── feat/ai-승언          문서 Agent, 파서, 템플릿, 파인튜닝
      ├── feat/backend-혜빈     DB, 인증, API, Google Services
      └── feat/frontend-지영    전체 UI
```

### 브랜치 규칙

| 규칙 | 설명 |
|------|------|
| **develop 직접 커밋 금지** | 반드시 자기 브랜치에서 작업 후 PR로 머지 |
| **main 직접 커밋 금지** | develop → main은 PM(지용)만 머지 |
| **작업 전 최신화** | `git pull origin develop` → 자기 브랜치에 rebase 후 작업 시작 |
| **충돌은 자기 브랜치에서** | develop에 머지할 때 충돌 나면 자기 브랜치에서 해결 후 다시 PR |
| **공유 파일 수정 시 사전 공유** | `state.py`, `schemas/*.py`, `constants.js` 등은 슬랙에 먼저 알리기 |

### 일상 작업 흐름

```bash
# 1. 작업 시작 전 — develop 최신 가져오기
git checkout feat/ai-경은
git pull origin develop --rebase

# 2. 작업 + 커밋
git add 파일명
git commit -m "feat: 판단 Agent LLM API 연동 #12"

# 3. push
git push origin feat/ai-경은

# 4. GitHub에서 PR 생성 (develop ← feat/ai-경은)

# 5. 리뷰 후 머지
```

### 커밋 규칙

```bash
# 형식
<type>: <설명> #이슈번호

# 예시
feat: 판단 Agent LLM API 연동 #12
fix: Intent 분류 confidence 임계값 조정 #5
docs: API 스키마 문서 업데이트 #2
hotfix: SSE 연결 끊김 수정 #30

# type 종류
feat:     새 기능
fix:      버그 수정
hotfix:   긴급 수정 (develop에 직접 커밋 허용)
docs:     문서 수정
refactor: 리팩토링
test:     테스트
chore:    설정/환경
```

### PR 규칙

```
1. 자기 브랜치에서 작업 완료 후 push
2. GitHub에서 PR 생성 (develop ← feat/xxx-이름)
3. PR 제목: 커밋 메시지와 동일 형식 (예: "feat: 판단 Agent LLM API 연동 #12")
4. PR 본문 필수 항목:
   - 무엇을 했는지 (변경사항 요약)
   - 테스트 방법 (어떻게 확인하는지)
   - 관련 이슈: "Closes #이슈번호"
5. 리뷰어: 같은 영역 담당자 1명 이상 지정
   - AI 코드 → 경은 ↔ 승언 상호 리뷰
   - 백엔드 ↔ AI 연동 → 혜빈 + 경은/승언
   - 프론트 ↔ 백엔드 연동 → 지영 + 혜빈
   - 스키마/설계 변경 → PM 지용 필수 리뷰
6. 리뷰 승인 후 머지 → Squash and merge 사용
7. 머지 후 자기 브랜치 삭제하지 않음 (계속 사용)
```

### 긴급 수정 (hotfix)

```
- develop이 깨졌을 때만 사용
- 커밋 타입: hotfix
- develop에 직접 커밋 허용 (단, 슬랙에 먼저 공유)
- 예: hotfix: DB 마이그레이션 오류 수정 #99
```

### 금지 사항

```
- git push --force (본인 브랜치 포함 금지)
- git reset --hard (커밋 날아감)
- develop/main에 직접 push
- .env, credentials.json 등 시크릿 파일 커밋
- node_modules/, __pycache__/, .venv/ 커밋
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
| `ai/templates/base.py` | 템플릿 베이스 클래스 (render, to_docx, to_pdf, from_parsed_structure, render_from_structure) |
| `ai/templates/__init__.py` | SYSTEM_TEMPLATES 레지스트리 |
| `ai/templates/meeting_minutes.py` | 회의록 템플릿 |
| `ai/templates/report.py` | 보고서 템플릿 |
| `ai/templates/jd.py` | 채용 공고 템플릿 |
| `ai/templates/proposal.py` | 제안서 템플릿 |

### 추가된 백엔드 서비스/API (혜빈 담당)

| 파일 | 기능 |
|------|------|
| `models/document_template.py` | 커스텀/시스템 템플릿 저장 DB 모델 |
| `services/template_service.py` | 문서 생성 + 다운로드 + 템플릿 업로드 + 감지 |
| `services/statistics_service.py` | Top 질의 통계 + 질의 로그 |
| `services/parsing_service.py` | 파싱 상태 관리 |
| `api/v1/documents.py` | 추가: `/generate`, `/{id}/download`, `/{id}/parsing-status`, `/search/highlight`, `/templates/*` (업로드/목록/상세/삭제) |
| `api/v1/meetings.py` | 추가: `/generate`, `/{id}/download` |
| `api/v1/admin.py` | 추가: `/query-logs`, `/top-queries`, `/users/{id}/permissions` |
| `api/v1/auth.py` | 추가: `/password-reset/request`, `/password-reset/confirm` |

---

## Google Services 확장 설계 (2026-02-09 추가)

> PM 요청: Google Calendar 외 4개 Google 서비스 추가 연동
> Intent 7개 유지, `schedule_add`/`schedule_view` 내부에서 자동 연동

### 추가 Google 서비스 (4개)

| 서비스 | 기능 | scope |
|--------|------|-------|
| **Google Tasks** | Action Item → 할 일 등록 (완료 체크, 미완료 추적) | `tasks` |
| **Gmail** | 담당자 기한 알림 메일 + 회의 초대 메일 자동 발송 | `gmail_send` |
| **Google Meet** | 캘린더 일정 등록 시 자동 Meet 링크 생성 | `calendar` (확장) |
| **Google Sheets** | Action Item 현황 스프레드시트 자동 생성 → 팀 추적 대시보드 | `sheets` |

### DB 변경 사항

| 변경 대상 | 추가 필드 |
|-----------|----------|
| `oauth_tokens` | `scopes: Text` (연결된 서비스 범위, 콤마 구분) |
| `action_items` | `google_task_id`, `sheet_row_id`, `email_sent_at` |
| `schedules` | `google_meet_link` |
| **신규** `google_sheet_trackers` | `spreadsheet_id`, `spreadsheet_url`, `sheet_name`, `meeting_id` |

### 신규 백엔드 파일 (혜빈 담당)

| 파일 | 설명 |
|------|------|
| `services/google_base_service.py` | Google API 공통 (인증, 토큰 갱신, scope 확인) — 5개 서비스 베이스 |
| `services/tasks_service.py` | Google Tasks CRUD + 상태 동기화 |
| `services/gmail_service.py` | 알림 메일 + 회의 초대 메일 발송 |
| `services/sheets_service.py` | 스프레드시트 생성 + Action Item 추적 |
| `models/google_sheet_tracker.py` | 스프레드시트 추적 DB 모델 |
| `api/v1/google_connect.py` | 통합 OAuth (status/connect/callback/disconnect) |
| `api/v1/tasks.py` | Tasks 동기화 엔드포인트 (5개) |
| `api/v1/gmail.py` | 메일 발송 엔드포인트 (3개) |
| `api/v1/sheets.py` | Sheets 생성/동기화 엔드포인트 (4개) |
| `schemas/google_services.py` | 모든 Google 서비스 요청/응답 스키마 |

### 수정된 백엔드 파일 (혜빈 담당)

| 파일 | 변경 내용 |
|------|----------|
| `services/calendar_service.py` | `GoogleBaseService` 상속, `create_event_with_meet()` 추가 |
| `services/schedule_service.py` | 4개 Google 서비스 오케스트레이션 통합 |
| `api/v1/calendar.py` | `/event-with-meet` 엔드포인트 추가 |
| `api/v1/router.py` | 4개 신규 라우터 등록 (google, tasks, gmail, sheets) |
| `schemas/schedule.py` | `google_meet_link`, `include_meet`, `attendee_emails` 추가 |
| `schemas/meeting.py` | ActionItemResponse에 `google_task_id`, `email_sent_at` 추가 |

### 수정된 AI 파일 (지용 담당)

| 파일 | 변경 내용 |
|------|----------|
| `ai/agents/state.py` | `google_services_result: Optional[dict]` 추가 |
| `ai/agents/schedule_agent.py` | Google 서비스 통합 응답 구조 (`google_services` 필드) |

### 신규 프론트엔드 파일 (지영 담당)

| 파일 | 기능 |
|------|------|
| `api/google.js` | Google 서비스 통합 API 클라이언트 (17개 함수) |
| `store/googleStore.js` | Zustand 상태 관리 (연결/Tasks/Sheets) |
| `hooks/useGoogleServices.js` | Google 서비스 커스텀 훅 |
| `components/schedules/GoogleServicesConnect.jsx` | 통합 연결 UI (4개 서비스 토글) |
| `components/schedules/TasksPanel.jsx` | 할 일 관리 패널 (체크박스, Push/Pull) |
| `components/schedules/MeetLinkBadge.jsx` | Meet 링크 뱃지 |
| `components/schedules/EmailReminderButton.jsx` | 알림 메일 발송 버튼 |
| `components/schedules/SheetsDashboard.jsx` | 스프레드시트 추적 대시보드 |

### 수정된 프론트엔드 파일 (지영 담당)

| 파일 | 변경 내용 |
|------|----------|
| `utils/constants.js` | `GOOGLE_SCOPES`, `GOOGLE_SCOPE_LABELS`, `TASK_STATUS` 추가 |
| `pages/SchedulesPage.jsx` | 전체 리빌드 (Google 서비스 컴포넌트 통합) |
| `components/schedules/CalendarView.jsx` | Meet 링크 뱃지 표시 |
| `components/schedules/ScheduleForm.jsx` | Meet 토글 + 참석자 이메일 입력 |
| `api/schedules.js` | `createScheduleWithMeet` 추가 |

### API 엔드포인트 (17개 신규)

| Prefix | 엔드포인트 수 | 설명 |
|--------|-------------|------|
| `/api/v1/google` | 4 | 통합 OAuth (status/connect/callback/disconnect) |
| `/api/v1/tasks` | 5 | sync, sync-all, list, status update, pull |
| `/api/v1/gmail` | 3 | send-reminder, send-meeting-invite, send-bulk-reminders |
| `/api/v1/sheets` | 4 | create, sync, list, get-url |
| `/api/v1/calendar` | 1 (추가) | event-with-meet |

---

## 문서 생성 시스템 구조 변경 (2026-02-09 추가)

> PM 요청: 문서 Agent 담당 전용 페이지 2개 신설

### Intent 변경 사항

| 기존 | 변경 후 | 비고 |
|------|---------|------|
| `doc_summary` | 삭제 | `doc_generate`에 통합 (요약 및 생성 = 한 흐름) |
| `meeting_analysis` | `meeting_generate` | 분석→생성으로 목적 변경 |
| (없음) | `general` | 일반 질문 처리 추가 |

### 신규 페이지 (지영 담당)

| 페이지 | 경로 | 설명 |
|--------|------|------|
| 회의록 생성 | `/meeting-minutes` | 회의 내용 입력 → AI 요약 → 회의록 양식 생성 |
| 문서 생성 | `/document-generate` | 템플릿 선택/업로드 → AI 내용 채움 → 문서 생성 |

### 신규 프론트엔드 컴포넌트 (지영 담당)

| 파일 | 기능 |
|------|------|
| `pages/MeetingMinutesPage.jsx` | 회의록 요약 및 생성 페이지 |
| `pages/DocumentGeneratePage.jsx` | 문서 요약 및 생성 페이지 |
| `components/meetings/MeetingInput.jsx` | 회의 내용 텍스트 입력 폼 |
| `components/meetings/MeetingPreview.jsx` | 회의록 미리보기 + 다운로드 |
| `components/documents/TemplateSelector.jsx` | 템플릿 선택 그리드 |
| `components/documents/TemplateUploadDialog.jsx` | 템플릿 파일 업로드 다이얼로그 |
| `components/documents/DocumentPreview.jsx` | 생성 문서 미리보기 + 다운로드 |

### 사이드바 메뉴 변경

```
대시보드
AI 챗봇
회의록 생성     ← NEW
문서 생성       ← NEW
문서 관리       ← 기존
일정 관리
관리자
```
