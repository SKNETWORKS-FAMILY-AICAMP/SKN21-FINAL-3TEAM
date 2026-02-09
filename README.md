# WorkFlow Agent (듀듀)

> LangGraph 기반 멀티 Agent 업무 자동화 시스템

**팀원**: 신지용(PM) | 윤경은(AI리드) | 진승언(AI서브) | 안혜빈(Backend) | 문지영(Frontend)

---

## 프로젝트 개요

사내 규정 판단, 문서 분석, 일정 관리를 AI Agent가 자동화하는 시스템입니다.
사용자의 자연어 질문을 Intent 분류 후 적절한 Agent로 라우팅하여 처리합니다.

### 핵심 기능

| 기능 | 설명 |
|------|------|
| **규정 판단** | "인턴에게 AWS 접근 줘도 돼?" → 다중 규정 교차 판단 + 근거 + 대안 제시 |
| **회의록 생성** | 회의 내용 입력 → AI 요약 + 결정사항/Action Item 추출 → 회의록 양식 생성 |
| **문서 생성** | 템플릿 선택/업로드 → AI가 양식에 맞게 내용 채워서 생성 → 미리보기 + 다운로드 |
| **일정 관리** | Action Item → 일정 자동 등록 + Google Services 통합 (Calendar·Tasks·Gmail·Meet·Sheets) |

---

## 시스템 아키텍처

### 전체 구조 (담당자 표시)

```
╔══════════════════════════════════════════════════════════════════════════╗
║  🖥️ Frontend — 지영                                                    ║
║                                                                        ║
║  React (Vite) + Zustand + TanStack Query + Tailwind + shadcn/ui       ║
║                                                                        ║
║  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐          ║
║  │ 대시보드    │ │  AI 챗봇   │ │ 회의록생성  │ │  문서생성   │          ║
║  │            │ │            │ │            │ │            │          ║
║  │ StatCard   │ │ ChatWindow │ │ MeetInput  │ │ TemplSel   │          ║
║  │ TopQueries │ │ Streaming  │ │ MeetPreview│ │ TemplUpload│          ║
║  │ RiskAlert  │ │ JudgmentCd │ │            │ │ DocPreview │          ║
║  │ QuickSearch│ │ GenerateCd │ │            │ │            │          ║
║  │ AutoScan   │ │ MeetingSumm│ │            │ │            │          ║
║  │ Timeline   │ │ ErrorMsg   │ │            │ │            │          ║
║  │            │ │ SuggestQ   │ │            │ │            │          ║
║  │            │ │ RegPanel   │ │            │ │            │          ║
║  │            │ │ AgentIndic │ │            │ │            │          ║
║  └────────────┘ └────────────┘ └────────────┘ └────────────┘          ║
║                                                                        ║
║  ┌────────────┐ ┌────────────┐                                        ║
║  │  문서관리   │ │  일정관리   │                                        ║
║  │ DocList    │ │ FullCal    │                                        ║
║  │ Upload     │ │ GoogleSync │                                        ║
║  │ Highlight  │ │ EventForm  │                                        ║
║  │ Parsing    │ │            │                                        ║
║  │ ScopeSelect│ │            │                                        ║
║  └────────────┘ └────────────┘                                        ║
║                                                                        ║
║  ┌────────────┐ ┌────────────┐ ┌────────────┐                         ║
║  │  로그인     │ │  관리자     │ │  SSE 수신   │                         ║
║  │ LoginForm  │ │ UserMgmt   │ │ EventSource│                         ║
║  │ Register   │ │ QueryLogs  │ │ useSSE hook│                         ║
║  │ PwdReset   │ │ Statistics │ │            │                         ║
║  └────────────┘ └────────────┘ └────────────┘                         ║
╚═══════════════════════════╤════════════════════════════════════════════╝
                            │ REST API + SSE Stream
╔═══════════════════════════╧════════════════════════════════════════════╗
║  ⚙️ Backend API — 혜빈 (+ 지용: chat/stream SSE)                       ║
║                                                                        ║
║  FastAPI                                                               ║
║  ┌──────────────────────────────────────────────────────────┐          ║
║  │  /api/v1/chat/stream ─── SSE 스트리밍 ──────── [지용]    │          ║
║  │  /api/v1/auth/*      ─── JWT + 비밀번호 재설정 ─ [혜빈]  │          ║
║  │  /api/v1/documents/* ─── CRUD + 생성/다운로드 ── [혜빈]  │          ║
║  │  /api/v1/meetings/*  ─── 회의 관리 ───────────── [혜빈]  │          ║
║  │  /api/v1/schedules/* ─── 일정 CRUD ──────────── [혜빈]  │          ║
║  │  /api/v1/calendar/*  ─── Google Calendar+Meet ─ [혜빈]  │          ║
║  │  /api/v1/google/*    ─── 통합 OAuth ────────── [혜빈]  │          ║
║  │  /api/v1/tasks/*     ─── Google Tasks ──────── [혜빈]  │          ║
║  │  /api/v1/gmail/*     ─── Gmail 발송 ────────── [혜빈]  │          ║
║  │  /api/v1/sheets/*    ─── Google Sheets ─────── [혜빈]  │          ║
║  │  /api/v1/admin/*     ─── 통계 + 로그 + 권한 ─── [혜빈]  │          ║
║  └──────────────────────────────────────────────────────────┘          ║
║                                                                        ║
║  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        ║
║  │ JWT 인증/권한    │  │ PostgreSQL      │  │ Redis           │        ║
║  │ [혜빈]          │  │ 11 tables[혜빈] │  │ Cache + Queue   │        ║
║  └─────────────────┘  └─────────────────┘  └─────────────────┘        ║
║                                                                        ║
║  Services [혜빈]                                                       ║
║  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        ║
║  │ template_service│  │ statistics_svc  │  │ parsing_service │        ║
║  │ 문서 생성/다운   │  │ Top 질의/로그    │  │ 파싱 상태 관리  │        ║
║  └─────────────────┘  └─────────────────┘  └─────────────────┘        ║
║                                                                        ║
║  Google Services [혜빈] — GoogleBaseService 상속 구조                   ║
║  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  ║
║  │ calendar_svc │ │ tasks_svc    │ │ gmail_svc    │ │ sheets_svc   │  ║
║  │ +Meet 링크   │ │ Action Item  │ │ 알림/초대    │ │ 추적 시트    │  ║
║  │              │ │ ↔ Task 동기화│ │ 메일 발송    │ │ 생성/동기화  │  ║
║  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘  ║
║  ┌──────────────────────────────────────────────────────────────┐      ║
║  │ schedule_service — 4개 Google 서비스 오케스트레이션 통합      │      ║
║  └──────────────────────────────────────────────────────────────┘      ║
╚═══════════════════════════╤════════════════════════════════════════════╝
                            │
╔═══════════════════════════╧════════════════════════════════════════════╗
║  🤖 AI Engine                                                          ║
║                                                                        ║
║  ┌──────────────────────────────────────────────────────┐              ║
║  │  Intent Classifier (klue/bert-base)        [지용]    │              ║
║  │  7개: judgment, doc_search, doc_generate,            │              ║
║  │       meeting_generate, schedule_*, general           │              ║
║  └──────────┬───────────────────────────────────────────┘              ║
║             │                                                          ║
║  ┌──────────▼───────────────────────────────────────────┐              ║
║  │  LangGraph Orchestrator (StateGraph)       [지용]    │              ║
║  │  조건부 라우팅 + 멀티턴 컨텍스트 + SSE 스트리밍       │              ║
║  └──────┬──────────────┬──────────────┬─────────────────┘              ║
║         │              │              │                                ║
║         ▼              ▼              ▼                                ║
║  ┌──────────────┐┌──────────────┐┌──────────────┐                     ║
║  │ 판단 Agent   ││ 문서 Agent   ││ 일정 Agent   │                     ║
║  │    [경은]    ││    [승언]    ││    [혜빈]    │                     ║
║  │              ││              ││              │                     ║
║  │ · 다중규정   ││ · 회의록생성 ││ · CRUD       │                     ║
║  │   교차판단   ││ · 문서생성   ││ · 우선순위   │                     ║
║  │ · confidence ││ · 템플릿관리 ││ · 담당자배정 │                     ║
║  │ · 조건부판단 ││ · 리스크감지 ││ · Google 통합│                     ║
║  │ · 이력참조   ││ · 자동스캔   ││              │                     ║
║  └──────┬───────┘└──────┬───────┘└──────┬───────┘                     ║
║         │              │              │                                ║
║         ▼              │              │                                ║
║  ┌──────────────────┐  │              │                                ║
║  │ RAG Pipeline     │  │              │                                ║
║  │ [경은]           │  │              │                                ║
║  │                  │  │              │                                ║
║  │ BM25 (Top 15)   │  │              │                                ║
║  │   + Vector Search│  │              │                                ║
║  │   (ChromaDB)    │  │              │                                ║
║  │ → 합산 (Top 20) │  │              │                                ║
║  │ → Reranker      │  │              │                                ║
║  │   (bge-v2-m3)   │  │              │                                ║
║  │ → Top 5 전달    │  │              │                                ║
║  └──────┬───────────┘  │              │                                ║
║         │              │              │                                ║
║         ▼              ▼              │                                ║
║  ┌─────────────────────────────────┐  │                                ║
║  │ vLLM 모델 서빙 [경은]           │  │                                ║
║  │ OpenAI 호환 API + 스트리밍      │  │                                ║
║  │                                 │  │                                ║
║  │  ┌───────────┐  ┌───────────┐  │  │                                ║
║  │  │ LoRA v1   │  │ LoRA v2   │  │  │                                ║
║  │  │ 판단 특화  │  │ 문서 특화  │  │  │                                ║
║  │  │ 2,000개   │  │ 1,800개   │  │  │                                ║
║  │  │ [경은]    │  │ [승언]    │  │  │                                ║
║  │  └───────────┘  └───────────┘  │  │                                ║
║  │                                 │  │                                ║
║  │  Base: Qwen3/Kanana/EXAONE     │  │                                ║
║  │        (7~8B, 벤치마크 후 확정) │  │                                ║
║  └─────────────────────────────────┘  │                                ║
║                                       │                                ║
║  ┌────────────────────────────────┐   │                                ║
║  │ Document Parser [승언]         │   │                                ║
║  │                                │   │                                ║
║  │ Docling (디지털 PDF 구조화)    │   │                                ║
║  │ PaddleOCR (스캔/이미지 OCR)    │   │                                ║
║  │ python-docx (DOCX 파싱)        │   │                                ║
║  └────────────────────────────────┘   │                                ║
║                                       │                                ║
║  ┌────────────────────────────────┐   │                                ║
║  │ Template Engine [승언]         │   │                                ║
║  │                                │   │                                ║
║  │ 회의록 / 보고서 / JD / 제안서  │   │                                ║
║  │ render() → to_docx() / to_pdf()│   │                                ║
║  └────────────────────────────────┘   │                                ║
╚═══════════════════════════╤═══════════╧════════════════════════════════╝
                            │
╔═══════════════════════════╧════════════════════════════════════════════╗
║  ☁️ External Services                                                   ║
║                                                                        ║
║  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        ║
║  │ Google OAuth 2.0│  │ Google APIs     │  │ RunPod (A100)   │        ║
║  │ (통합 scope)    │  │ Calendar+Tasks  │  │ GPU 학습 [경은] │        ║
║  │ [혜빈]          │  │ Gmail+Sheets    │  │                 │        ║
║  │                 │  │ +Meet [혜빈]    │  │                 │        ║
║  └─────────────────┘  └─────────────────┘  └─────────────────┘        ║
╚════════════════════════════════════════════════════════════════════════╝
```

### 담당자별 색상 요약

```
[지용] Intent 분류 + LangGraph 오케스트레이터 + SSE 스트리밍 + 배포
[경은] 판단 Agent + RAG Pipeline + Reranker + vLLM 서빙 + LoRA v1
[승언] 문서 Agent + Document Parser + Template Engine + LoRA v2
[혜빈] Backend API 전체 + DB + 인증 + 일정 Agent + Google Services 통합
[지영] Frontend 전체 (7개 화면 + 30+ 컴포넌트 + SSE 수신)
```

### Agent 처리 흐름 (예: 규정 판단)

```
사용자: "인턴에게 AWS 콘솔 접근 권한을 줘도 되나요?"
         │
         ▼
┌─────────────────────────────────────┐
│ 1. Intent Classification   [지용]   │
│    klue/bert-base                   │
│    → intent: "judgment"             │
│    → confidence: 0.92               │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 2. LangGraph Orchestrator  [지용]   │
│    AgentState에 intent 저장         │
│    → 조건부 엣지: judgment          │
│    → SSE: "판단 Agent 호출 중..."    │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 3. RAG Pipeline            [경은]   │
│    ① BM25 검색 (Top 15)            │
│    ② Vector 검색 (Top 15)          │
│    ③ 합산 (Top 20)                 │
│    ④ Reranker (Top 5)              │
│    → 정보보안 규정 3.2조            │
│    → 개발 가이드라인 5.1조          │
│    → 인사 규정 2.3조                │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 4. 판단 Agent + sLLM       [경은]   │
│    LoRA v1 (판단 특화)              │
│    다중 규정 교차 판단:              │
│    → 종합: 조건부 가능               │
│    → 근거: 3개 조항                  │
│    → 대안: 테스트 환경 한정          │
│    → confidence: 0.85                │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 5. SSE 스트리밍 응답       [지용]   │
│    → type: "token" (실시간 전송)    │
│    → type: "done"  (완료 신호)      │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 6. 카드 UI 렌더링          [지영]   │
│    JudgmentCard: 판단 결과 표시     │
│    → 결과 뱃지 (조건부 가능)        │
│    → 근거 조항 목록                  │
│    → confidence 게이지               │
│    → 대안 제시                       │
└─────────────────────────────────────┘
```

### 회의록 생성 흐름

```
[회의록 생성 페이지 — 지영]
  사용자: 회의 내용 텍스트 입력 + (선택) 제목/날짜/참석자
     │
     ▼
  POST /api/v1/meetings/generate  [혜빈]
     │
     ▼
  [문서 Agent — meeting_generate — 승언]
     ├── sLLM으로 요약 (결정사항, Action Item 추출)
     ├── MeetingMinutesTemplate 양식에 데이터 채움
     ├── 규정 리스크 자동 스캔 (RAG)
     ├── meetings + documents + action_items 테이블 저장
     │
     ▼
  [MeetingPreview — 지영]
  응답: 요약 + 결정사항 + Action Items + 미리보기(MD) + 다운로드 URL + 리스크
```

### 문서 생성 흐름

```
[문서 생성 페이지 — 지영]
  사용자: 템플릿 업로드 OR 기존 템플릿 선택 → 내용/지시사항 입력
     │
     ▼
  POST /api/v1/documents/generate { template_id, user_input }  [혜빈]
     │
     ▼
  [문서 Agent — doc_generate — 승언]
     ├── document_templates에서 parsed_structure 로딩
     ├── sLLM으로 양식에 맞는 내용 생성
     ├── BaseTemplate.render_from_structure()로 렌더링
     ├── documents 테이블 저장
     │
     ▼
  [DocumentPreview — 지영]
  응답: 미리보기(MD) + 다운로드 URL (DOCX/PDF)
```

### DB ERD (11 테이블) — [혜빈]

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  users   │────▶│  documents   │     │ regulations  │
│          │     │ (scope:      │     │              │
│          │     │  company/    │     │              │
│          │     │  personal)   │     │              │
└────┬─────┘     └──────────────┘     └──────────────┘
     │
     ├──────────▶┌──────────────────┐
     │           │ document_templates│  (커스텀/시스템 템플릿)
     │           │ parsed_structure  │
     │           └──────────────────┘
     │
     ├──────────▶┌──────────────┐     ┌──────────────┐
     │           │  meetings    │────▶│ action_items │
     │           └──────────────┘     └──────┬───────┘
     │                                        │
     ├──────────▶┌──────────────┐◀────────────┘
     │           │  schedules   │
     │           └──────────────┘
     │
     ├──────────▶┌──────────────┐
     │           │  judgments   │  (판단 이력)
     │           └──────────────┘
     │
     ├──────────▶┌──────────────┐
     │           │  chat_logs   │
     │           └──────────────┘
     │
     ├──────────▶┌──────────────┐
     │           │ oauth_tokens │  (Google OAuth + scopes)
     │           └──────────────┘
     │
     └──────────▶┌────────────────────┐
                 │ google_sheet_      │
                 │ trackers           │  (스프레드시트 추적)
                 └────────────────────┘
```

---

## 기술 스택

### AI / ML

| 구분 | 기술 | 용도 |
|------|------|------|
| Agent Framework | **LangGraph** | StateGraph 기반 Agent 오케스트레이션 |
| Base LLM | **Qwen3 / Kanana / EXAONE 3.5** (7~8B) | 벤치마크 후 확정 |
| Fine-tuning | **LoRA (PEFT)** + QLoRA 4-bit | 판단 v1 (2,000개) + 문서 v2 (1,800개) |
| 모델 서빙 | **vLLM** | OpenAI 호환 API + LoRA 핫스왑 + 스트리밍 |
| Vector DB | **ChromaDB** | 문서 임베딩 저장 + 유사도 검색 |
| Embedding | **jhgan/ko-sbert-nli** | 한국어 문장 임베딩 |
| Reranker | **BAAI/bge-reranker-v2-m3** | 검색 결과 재정렬 (Top 5) |
| 키워드 검색 | **BM25 (rank_bm25)** | Hybrid Search의 키워드 매칭 |
| Intent 분류 | **klue/bert-base** | 7개 카테고리: judgment, doc_search, doc_generate, meeting_generate, schedule_add, schedule_view, general |
| 문서 파싱 | **Docling + PaddleOCR** | PDF 구조화 + 스캔 OCR |

### Backend

| 구분 | 기술 |
|------|------|
| Framework | FastAPI + SSE (StreamingResponse) |
| Database | PostgreSQL (11 tables) |
| ORM | SQLAlchemy + Alembic |
| 인증 | JWT (PyJWT) + Google OAuth 2.0 |
| Task Queue | Celery + Redis |
| 암호화 | AES-256 (cryptography) |

### Frontend

| 구분 | 기술 |
|------|------|
| Framework | React (Vite) |
| 상태관리 | Zustand + TanStack Query |
| 스트리밍 | EventSource (SSE) |
| 스타일 | Tailwind CSS + shadcn/ui |
| 캘린더 | FullCalendar |
| 차트 | Recharts |

### Infra

| 구분 | 기술 |
|------|------|
| Cloud | AWS (EC2 + S3 + RDS) |
| GPU (학습) | RunPod (A100 40GB) |
| Container | Docker + Docker Compose |
| CI/CD | GitHub Actions |

---

## 파인튜닝 데이터 (총 3,800개)

| 어댑터 | 데이터 구성 | 합계 | 담당 |
|--------|-----------|------|------|
| **LoRA v1** (판단) | 판단 1,000 + Q&A 1,000 | **2,000개** | 경은 |
| **LoRA v2** (문서) | 회의록 700 + 요약 500 + 생성 400 + 리스크 200 | **1,800개** | 승언 |

> 검증용 15% 별도 분리 / Claude·GPT-4 초안 → 사람 검증

---

## 프로젝트 구조

```
SKN21-FINAL-3TEAM/
│
├── backend/                     # FastAPI 백엔드 (혜빈)
│   └── app/
│       ├── main.py              # 앱 진입점
│       ├── config.py            # 환경변수
│       ├── api/v1/              # REST API 엔드포인트
│       │   ├── chat.py          # 챗봇 + SSE 스트리밍
│       │   ├── auth.py          # JWT + 비밀번호 재설정
│       │   ├── documents.py     # 문서 CRUD + 생성/다운로드
│       │   ├── meetings.py      # 회의 관리
│       │   ├── schedules.py     # 일정 CRUD
│       │   ├── calendar.py      # Google Calendar + Meet
│       │   ├── google_connect.py # 통합 OAuth
│       │   ├── tasks.py         # Google Tasks API
│       │   ├── gmail.py         # Gmail 발송 API
│       │   ├── sheets.py        # Google Sheets API
│       │   └── admin.py         # 관리자 + 통계 + 로그
│       ├── models/              # ORM 모델 (11개 테이블, google_sheet_trackers 포함)
│       ├── schemas/             # Pydantic 스키마
│       └── services/            # 비즈니스 로직
│           ├── template_service.py   # 문서 생성/다운로드
│           ├── statistics_service.py # 통계/로그
│           ├── parsing_service.py    # 파싱 상태 관리
│           ├── google_base_service.py # Google API 공통 베이스
│           ├── calendar_service.py   # Calendar + Meet 연동
│           ├── tasks_service.py      # Google Tasks 동기화
│           ├── gmail_service.py      # 알림/초대 메일 발송
│           ├── sheets_service.py     # Sheets 추적 시트
│           └── schedule_service.py   # 4개 서비스 오케스트레이션
│
├── ai/                          # AI/ML 모듈
│   ├── agents/                  # LangGraph Agent (지용/경은/승언)
│   │   ├── state.py             # AgentState 공유 상태
│   │   ├── orchestrator.py      # StateGraph 오케스트레이터
│   │   ├── intent_classifier.py # Intent 분류 (klue/bert-base)
│   │   ├── judgment_agent.py    # 판단 Agent (경은)
│   │   ├── document_agent.py    # 문서 Agent (승언)
│   │   └── schedule_agent.py    # 일정 Agent (혜빈)
│   ├── rag/                     # RAG 파이프라인 (경은)
│   │   ├── hybrid_search.py     # BM25 + Vector
│   │   ├── reranker.py          # bge-reranker-v2-m3
│   │   └── vectorstore.py       # ChromaDB
│   ├── templates/               # 문서 템플릿 (승언)
│   │   ├── base.py              # BaseTemplate
│   │   ├── meeting_minutes.py   # 회의록
│   │   ├── report.py            # 보고서
│   │   ├── jd.py                # 채용 공고
│   │   └── proposal.py          # 제안서
│   ├── finetuning/              # LoRA 학습 (경은/승언)
│   ├── document_parser/         # 문서 파싱 (승언)
│   └── serving/vllm_client.py   # vLLM 클라이언트
│
├── frontend/                    # React 프론트엔드 (지영)
│   └── src/
│       ├── components/
│       │   ├── chat/            # 챗봇 UI + 응답 카드 7종
│       │   ├── dashboard/       # 대시보드 위젯
│       │   ├── documents/       # 문서 관리
│       │   ├── meetings/        # 회의 관리
│       │   ├── schedules/       # 일정 (FullCalendar)
│       │   ├── auth/            # 로그인/회원가입
│       │   └── admin/           # 관리자
│       ├── hooks/               # useAuth, useSSE, useChat
│       ├── store/               # Zustand (auth, chat, ui, google)
│       └── pages/               # 페이지 라우팅 (10개, MeetingMinutesPage/DocumentGeneratePage 추가)
│
├── data/                        # 학습/평가 데이터
│   ├── training/
│   │   ├── v1_judgment/         # 판단 데이터 (2,000개)
│   │   └── v2_document/         # 문서 데이터 (1,800개)
│   └── regulations/             # 규정 원본 문서
│
├── docker/                      # Docker 설정
│   ├── docker-compose.yml
│   └── Dockerfile.*
│
├── docs/                        # 기획/설계 문서
│   ├── TASK_BOARD.md            # 작업 보드 (일일 참고)
│   └── 역할분배_기술스택_v5_final.md # 기술 참고서
│
└── .github/workflows/ci.yml    # CI 파이프라인
```

---

## 팀원별 담당

| 팀원 | 역할 | 핵심 담당 |
|------|------|----------|
| **신지용** (PM) | Intent + 오케스트레이션 | `ai/agents/orchestrator.py`, SSE 스트리밍, API 스키마, 배포 |
| **윤경은** (AI리드) | 파인튜닝 v1 + 판단 + RAG | `judgment_agent.py`, `ai/rag/*`, LoRA v1, vLLM 서빙 |
| **진승언** (AI서브) | 파인튜닝 v2 + 문서 Agent | `document_agent.py`, `ai/templates/*`, `document_parser/*`, LoRA v2, 회의록 생성 + 문서 생성 |
| **안혜빈** (Backend) | DB + 인증 + 일정 Agent | `models/*`, `services/*`, JWT, Google Services 통합 (Calendar·Tasks·Gmail·Meet·Sheets), 관리자 API |
| **문지영** (Frontend) | React UI 전담 | `frontend/src/` 전체, SSE 수신, 카드 UI, 회의록 생성 페이지, 문서 생성 페이지, 반응형 |

---

## Git 브랜치 전략

```
main (배포용 - PM만 머지)
 └── develop (통합 개발)
      ├── feature/intent-classification    (지용)
      ├── feature/agent-orchestrator       (지용)
      ├── feature/judgment-agent           (경은)
      ├── feature/rag-pipeline             (경은)
      ├── feature/finetuning-judgment      (경은)
      ├── feature/document-agent           (승언)
      ├── feature/document-parser          (승언)
      ├── feature/finetuning-document      (승언)
      ├── feature/auth-system              (혜빈)
      ├── feature/database                 (혜빈)
      ├── feature/google-calendar          (혜빈)
      ├── feature/google-services          (혜빈)
      ├── feature/dashboard-ui             (지영)
      ├── feature/chatbot-ui               (지영)
      ├── feature/google-services-ui       (지영)
      └── feature/streaming-ui             (지영)
```

### 커밋 컨벤션

```
feat: 새 기능 추가        fix: 버그 수정
docs: 문서 수정           refactor: 리팩토링
test: 테스트 추가         chore: 설정/환경 변경

예시: feat: 판단 Agent Yes/No 판단 로직 구현 #12
```

### PR 규칙

```
1. feature 브랜치에서 작업
2. push → GitHub PR 생성 (develop ← feature/xxx)
3. PR 본문에 "Closes #이슈번호"
4. 리뷰 후 머지 → 이슈 자동 닫힘
```

---

## 빠른 시작

```bash
# 1. 환경변수 설정
cp .env.example .env

# 2. Docker로 실행
cd docker && docker-compose up -d

# 3. 또는 로컬 개발
# Backend
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

---

## 문서 참고

| 문서 | 용도 |
|------|------|
| `docs/TASK_BOARD.md` | 일일 작업 참고 (체크리스트, 이슈 매핑) |
| `docs/역할분배_기술스택_v5_final.md` | 기술 결정 배경, 멘토 피드백, 아키텍처 상세 |
| Swagger UI (`/docs`) | API 스펙 확인 (서버 실행 후) |

---

## API 문서

서버 실행 후:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
