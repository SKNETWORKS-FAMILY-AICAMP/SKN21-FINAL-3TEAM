# WorkFlow Agent (듀듀)

> LangGraph 기반 멀티 Agent 업무 자동화 시스템

**팀원**: 신지용 문지영 윤경은 안혜빈 진승언

---

## 프로젝트 개요

사내 규정 판단, 문서 분석, 일정 관리를 AI Agent가 자동화하는 시스템입니다.
사용자의 자연어 질문을 Intent 분류 후 적절한 Agent로 라우팅하여 처리합니다.

```
[사용자 입력]
     ↓
[Intent 분류] → klue/bert-base (7개 카테고리)
     ↓
[LangGraph 오케스트레이터] → 조건부 라우팅
     ├── 판단 Agent  → RAG + Reranker + sLLM (LoRA v1)
     ├── 문서 Agent  → Docling/PaddleOCR + sLLM (LoRA v2)
     └── 일정 Agent  → CRUD + Google Calendar
     ↓
[SSE 스트리밍 응답] → 실시간 토큰 렌더링
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| **AI/ML** | LangGraph, vLLM, LoRA (PEFT), ChromaDB, BM25, bge-reranker-v2-m3 |
| **Base LLM** | Qwen3 / Kanana / EXAONE 3.5 (7~8B, 벤치마크 후 확정) |
| **Backend** | FastAPI, PostgreSQL, SQLAlchemy, Alembic, JWT, Celery + Redis |
| **Frontend** | React (Vite), Zustand, TanStack Query, Tailwind CSS, FullCalendar |
| **Infra** | Docker, AWS (EC2/S3/RDS), RunPod (A100), GitHub Actions |

---

## 프로젝트 구조

```
C:\SKN21-FINAL-3TEAM/
│
├── backend/                    # FastAPI 백엔드
│   ├── app/
│   │   ├── main.py             # FastAPI 앱 진입점
│   │   ├── config.py           # 환경변수 설정
│   │   ├── api/
│   │   │   ├── deps.py         # 공통 의존성 (인증, DB 세션)
│   │   │   └── v1/
│   │   │       ├── router.py   # 라우터 통합
│   │   │       ├── chat.py     # 챗봇 + SSE 스트리밍
│   │   │       ├── auth.py     # JWT 인증/회원가입
│   │   │       ├── documents.py # 문서 CRUD
│   │   │       ├── meetings.py  # 회의 관리
│   │   │       ├── schedules.py # 일정 CRUD
│   │   │       ├── calendar.py  # Google Calendar 연동
│   │   │       └── admin.py     # 관리자 API
│   │   ├── core/
│   │   │   ├── security.py     # JWT, 암호화 (AES-256)
│   │   │   └── middleware.py   # CORS, 에러 핸들링
│   │   ├── db/
│   │   │   ├── base.py         # SQLAlchemy Base
│   │   │   └── session.py      # DB 세션 관리
│   │   ├── models/             # ORM 모델 (9개 테이블)
│   │   │   ├── user.py
│   │   │   ├── document.py     # scope: company/personal
│   │   │   ├── regulation.py
│   │   │   ├── meeting.py
│   │   │   ├── action_item.py
│   │   │   ├── schedule.py
│   │   │   ├── judgment.py     # 판단 이력
│   │   │   ├── chat_log.py
│   │   │   └── oauth_token.py
│   │   ├── schemas/            # Pydantic 요청/응답 스키마
│   │   └── services/           # 비즈니스 로직
│   ├── alembic/                # DB 마이그레이션
│   ├── tests/
│   └── requirements.txt
│
├── ai/                         # AI/ML 모듈
│   ├── agents/                 # LangGraph Agent 노드
│   │   ├── state.py            # AgentState (공유 상태 정의)
│   │   ├── orchestrator.py     # LangGraph StateGraph
│   │   ├── intent_classifier.py # Intent 분류 (klue/bert-base)
│   │   ├── judgment_agent.py   # 판단 Agent (다중규정, confidence)
│   │   ├── document_agent.py   # 문서 Agent (요약/생성/리스크)
│   │   └── schedule_agent.py   # 일정 Agent (CRUD + GCal)
│   ├── rag/                    # RAG 파이프라인
│   │   ├── pipeline.py         # 메인 파이프라인
│   │   ├── hybrid_search.py    # BM25 + Vector Search
│   │   ├── reranker.py         # bge-reranker-v2-m3
│   │   ├── embeddings.py       # ko-sbert-nli
│   │   └── vectorstore.py      # ChromaDB
│   ├── finetuning/             # LoRA 파인튜닝
│   │   ├── train_v1_judgment.py # v1: 판단 특화 (1,300개)
│   │   ├── train_v2_document.py # v2: 문서 특화 (700개)
│   │   ├── evaluate.py         # 평가 모듈
│   │   └── configs/            # 학습 설정 YAML
│   ├── document_parser/        # 문서 전처리
│   │   ├── parser.py           # 파일 형식별 라우터
│   │   ├── docling_parser.py   # PDF 구조화 파싱
│   │   ├── ocr_parser.py       # PaddleOCR 한국어 OCR
│   │   └── docx_parser.py      # DOCX 파싱
│   ├── serving/
│   │   └── vllm_client.py      # vLLM API 클라이언트
│   └── requirements.txt
│
├── frontend/                   # React (Vite) 프론트엔드
│   ├── src/
│   │   ├── main.jsx            # 앱 진입점
│   │   ├── App.jsx             # 라우팅 설정
│   │   ├── api/                # Axios API 모듈 (7개)
│   │   ├── components/
│   │   │   ├── common/         # Layout, Sidebar, Header
│   │   │   ├── chat/           # ChatWindow, StreamingMessage, 카드 UI
│   │   │   ├── dashboard/      # StatCard, 타임라인, 리스크 알림
│   │   │   ├── documents/      # 문서 목록, 업로드, ScopeSelector
│   │   │   ├── meetings/       # 회의 목록, AI 분석 패널
│   │   │   ├── schedules/      # FullCalendar, Google 연동
│   │   │   ├── auth/           # 로그인, 회원가입 폼
│   │   │   └── admin/          # 사용자/규정 관리, 시스템 통계
│   │   ├── pages/              # 페이지 컴포넌트 (8개)
│   │   ├── hooks/              # useAuth, useSSE, useChat
│   │   ├── store/              # Zustand (auth, chat, ui)
│   │   ├── styles/             # Tailwind globals
│   │   └── utils/              # 상수, 헬퍼 함수
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
│
├── docker/
│   ├── docker-compose.yml      # DB + Redis + Backend + Frontend
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── Dockerfile.vllm         # vLLM 모델 서빙
│
├── data/
│   ├── training/
│   │   ├── v1_judgment/        # 판단 학습 데이터 (1,300개)
│   │   └── v2_document/        # 문서 학습 데이터 (700개)
│   ├── evaluation/             # 평가 데이터셋
│   └── regulations/            # 규정 원본 문서
│
├── scripts/
│   ├── setup_db.py             # DB 초기 설정
│   ├── seed_data.py            # 시드 데이터
│   └── run_benchmark.py        # 모델 벤치마크
│
├── .github/workflows/ci.yml   # CI 파이프라인
├── .env.example                # 환경변수 템플릿
└── .gitignore
```

---

## 팀원별 담당 영역

| 팀원 | 역할 | 주요 담당 파일 |
|------|------|---------------|
| **A (PM)** | Intent 분류 + 오케스트레이션 | `ai/agents/state.py`, `orchestrator.py`, `intent_classifier.py`, `backend/app/api/v1/chat.py`, `main.py` |
| **B (AI 리드)** | 파인튜닝 v1 + 판단 Agent + RAG | `ai/agents/judgment_agent.py`, `ai/rag/*`, `ai/finetuning/train_v1*`, `ai/serving/vllm_client.py` |
| **C (AI 서브)** | 파인튜닝 v2 + 문서 Agent | `ai/agents/document_agent.py`, `ai/document_parser/*`, `ai/finetuning/train_v2*` |
| **D (Backend)** | DB + 인증 + 일정 Agent + GCal | `backend/app/models/*`, `core/security.py`, `api/v1/{auth,schedules,calendar,admin}.py` |
| **E (Frontend)** | React UI 전담 | `frontend/src/` 전체 |

---

## Git 브랜치 전략

```
main (배포용)
 └── develop (통합 개발)
      ├── feature/intent-classification    (팀원 A)
      ├── feature/agent-orchestrator       (팀원 A)
      ├── feature/judgment-agent           (팀원 B)
      ├── feature/rag-pipeline             (팀원 B)
      ├── feature/reranker                 (팀원 B)
      ├── feature/finetuning-judgment      (팀원 B)
      ├── feature/document-agent           (팀원 C)
      ├── feature/document-parser          (팀원 C)
      ├── feature/finetuning-document      (팀원 C)
      ├── feature/schedule-agent           (팀원 D)
      ├── feature/google-calendar          (팀원 D)
      ├── feature/auth-system              (팀원 D)
      ├── feature/database                 (팀원 D)
      ├── feature/dashboard-ui             (팀원 E)
      ├── feature/chatbot-ui               (팀원 E)
      ├── feature/calendar-ui              (팀원 E)
      └── feature/streaming-ui             (팀원 E)
```

### 커밋 컨벤션

```
feat: 새 기능 추가        fix: 버그 수정
docs: 문서 수정           refactor: 리팩토링
test: 테스트 추가         chore: 설정/환경 변경
```

---

## 빠른 시작

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일에 실제 값 입력

# 2. Docker로 실행 (DB + Redis + Backend + Frontend)
cd docker
docker-compose up -d

# 3. 또는 로컬 개발
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

---

## API 문서

서버 실행 후:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
