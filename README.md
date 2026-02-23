# WorkFlow Agent (듀듀)

> LangGraph 기반 멀티 Agent 업무 자동화 시스템

**팀원**: 신지용(PM) | 윤경은(AI서브) | 진승언(AI리드) | 안혜빈(Backend) | 문지영(Frontend)

---

## 프로젝트 개요

사내 규정 판단, 문서 분석, 일정 관리를 AI Agent가 자동화하는 시스템입니다.
사용자의 자연어 질문을 Intent 분류 후 적절한 Agent로 라우팅하여 처리합니다.

### 핵심 기능

| 기능 | 설명 |
|------|------|
| **규정 판단** | "인턴에게 AWS 접근 줘도 돼?" → 다중 규정 교차 판단 + 근거 + 대안 제시 |
| **문서 생성** | 등록된 템플릿(template_id)에 맞춰 초안 생성 → 초안 + 추가 입력 항목 반환 (챗봇/문서생성 페이지 공용) |
| **문서 요약** | 사용자가 선택한 문서(document_id)를 회사 요약 포맷으로 요약 (챗봇/페이지 공용) |
| **문서 검색** | query(+필터)로 문서 검색. 챗봇: 질문→쿼리 변환 후 추천 / 페이지: 키워드/목록/필터 탐색 |
| **문서 QA** | 질문에 대해 RAG로 근거를 찾아 답변+인용 반환 (주 사용처: 챗봇) |
| **일정 관리** | 자연어 → 일정 자동 등록/조회 + Google Calendar 통합 |

---

## 개발 전략: LLM API 먼저 → sLLM은 나중에

```
1단계  설계 · 환경 세팅                                    ✅ 완료
2단계  LLM API(GPT/Claude)로 전체 기능 먼저 구현            ✅ 대부분 완료
3단계  Agent 개발 — LLM API 기반으로 실제 동작 확인          ← 지금 여기
4단계  확정된 input/output에 맞춰 데이터 수집 → LoRA 파인튜닝
5단계  sLLM(vLLM) 교체 — 모델만 갈아끼우면 됨
6단계  통합 테스트 → 배포
```

- **왜?** 파인튜닝 먼저 하면 input/output이 바뀔 때마다 데이터를 다시 만들어야 함
- LLM API로 기능을 완성하면서 실제 형태를 확정한 뒤, 그에 맞는 데이터를 수집하는 게 효율적
- Agent 코드는 LLM 호출 인터페이스만 바꾸면 되는 구조 (공통 모듈 #39)

---

## 시스템 아키텍처

### 전체 파이프라인

```
사용자 입력 (챗봇 / 회의록 페이지 / 문서 페이지)
       │
       ▼
 Frontend (React) ── POST /api/v1/chat/stream ──→ Backend (FastAPI)
                                                       │
                                                  JWT 인증 → AgentState 초기화
                                                       │
                                                       ▼
                                          ┌─── Orchestrator (LangGraph) ───┐
                                          │                                │
                                          │  [classify_intent]             │
                                          │   BERT → Solar LLM → Embedding │
                                          │   (3단계 fallback)              │
                                          │         │                      │
                                          │   confidence < 0.7?            │
                                          │    ├─ Yes → clarify (top-3)    │
                                          │    └─ No  → Agent 라우팅        │
                                          │         │                      │
                                          │    ┌────┼────┬──────┐         │
                                          │    ▼    ▼    ▼      ▼         │
                                          │  Judge Doc  Sched  General    │
                                          │    │    │    │      │         │
                                          │    └────┴────┴──────┘         │
                                          │         │                      │
                                          │  [format_response]             │
                                          └─────────┼──────────────────────┘
                                                    │
                                                    ▼
                                          chat_logs DB 저장
                                                    │
       ┌────────────────────────────────────────────┘
       │  SSE (text/event-stream)
       ▼
 Frontend 렌더링
  intent → 처리중 표시 / token → 스트리밍 / result → 최종 응답 / done → 종료
```

### 각 Agent 워크플로우

```
┌─ Judgment Agent (경은) ─────────────────────────────────────────────────────┐
│                                                                             │
│  user_input ──→ RAG 하이브리드 검색 (규정문서, top_k=7) ──→ LLM 판단 (JSON)  │
│                    │                                          │             │
│                    │  Qdrant + BM25                            │             │
│                    │  bge-reranker                             ▼             │
│                                                   3중 보조장치 검증           │
│                                                   ├─ 환각 탐지 (인용 cross-check)
│                                                   ├─ 조항 존재 검증          │
│                                                   └─ confidence 보정        │
│                                                          │                  │
│                                                          ▼                  │
│  Output: { result: yes/no/conditional, confidence, reasoning, regulations } │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ Document Agent (승언) ─────────────────────────────────────────────────────┐
│                                                                             │
│  intent에 따라 4가지 분기 (챗봇/페이지 공용):                                  │
│                                                                             │
│  doc_generate ──→ 템플릿 로드(template_id) ──→ LLM 초안 생성 (JSON)          │
│                  → { data, preview, additional_fields }                      │
│                                                                             │
│  doc_summary ──→ 문서 로드(document_id) ──→ LLM 회사 요약 포맷 생성          │
│                  → { title, core_summary, key_points, keywords }            │
│                                                                             │
│  doc_search ──→ query(+필터) ──→ RAG 하이브리드 검색 (전체문서)               │
│                  챗봇: 질문→쿼리 변환 후 추천 / 페이지: 키워드/필터 탐색       │
│                  → { results[], message }                                    │
│                                                                             │
│  doc_qa ──→ RAG 검색 (비규정 문서) ──→ LLM 답변 + 인용 (주 사용처: 챗봇)     │
│                  → { answer, citations[] }                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ Schedule Agent (혜빈) ─────────────────────────────────────────────────────┐
│                                                                             │
│  schedule_add ──→ LLM 파싱 (자연어→구조화) ──→ Google Calendar API 등록      │
│                  → { schedule{title,start,end}, google_services{event_id} }  │
│                                                                             │
│  schedule_view ──→ LLM 기간 추출 ──→ Google Calendar API 조회               │
│                  → { schedules[], message }                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ General Response ──────────────────────────────────────────────────────────┐
│                                                                             │
│  user_input ──→ LLM 일반 응답 (업무 관련 친절 답변)                           │
│                  → { message }                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Intent 분류 체계 (8개)

```
judgment       → Judgment Agent    (규정 판단/정보)
doc_search     → Document Agent    (문서 검색)
doc_generate   → Document Agent    (문서 생성, 회의록 포함)
doc_summary    → Document Agent    (문서 요약)
doc_qa         → Document Agent    (문서 QA)
schedule_add   → Schedule Agent    (일정 추가)
schedule_view  → Schedule Agent    (일정 조회)
general        → General Response  (일반 대화)
```

### 전체 구조 (담당자 표시)

```
╔══════════════════════════════════════════════════════════════════════════╗
║  Frontend — 지영                                                        ║
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
║  Backend API — 혜빈 (+ 지용: chat/stream SSE)                          ║
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
║  AI Engine                                                             ║
║                                                                        ║
║  ┌──────────────────────────────────────────────────────┐              ║
║  │  Intent Classifier (klue/bert-base)        [지용]    │              ║
║  │  8개: judgment, doc_search, doc_generate,            │              ║
║  │       doc_summary, doc_qa, schedule_*, general        │              ║
║  └──────────┬───────────────────────────────────────────┘              ║
║             │                                                          ║
║  ┌──────────▼───────────────────────────────────────────┐              ║
║  │  LangGraph Orchestrator (StateGraph)       [지용]    │              ║
║  │  단일질문 분류 → 조건부 라우팅 + SSE 스트리밍          │              ║
║  └──────┬──────────────┬──────────────┬─────────────────┘              ║
║         │              │              │                                ║
║         ▼              ▼              ▼                                ║
║  ┌──────────────┐┌──────────────┐┌──────────────┐                     ║
║  │ 판단 Agent   ││ 문서 Agent   ││ 일정 Agent   │                     ║
║  │    [경은]    ││    [승언]    ││    [혜빈]    │                     ║
║  │              ││              ││              │                     ║
║  │ · 다중규정   ││ · 문서검색   ││ · CRUD       │                     ║
║  │   교차판단   ││ · 문서생성   ││ · 우선순위   │                     ║
║  │ · confidence ││ · 문서요약   ││ · 담당자배정 │                     ║
║  │ · 조건부판단 ││ · 문서QA     ││ · Google 통합│                     ║
║  │ · 이력참조   ││ · 템플릿관리 ││              │                     ║
║  └──────┬───────┘└──────┬───────┘└──────┬───────┘                     ║
║         │              │              │                                ║
║         ▼              │              │                                ║
║  ┌──────────────────┐  │              │                                ║
║  │ RAG Pipeline     │  │              │                                ║
║  │ [경은]           │  │              │                                ║
║  │                  │  │              │                                ║
║  │ BM25 (Top 15)   │  │              │                                ║
║  │   + Vector Search│  │              │                                ║
║  │   (Qdrant)    │  │              │                                ║
║  │ → 합산 (Top 20) │  │              │                                ║
║  │ → Reranker      │  │              │                                ║
║  │   (bge-v2-m3)   │  │              │                                ║
║  │ → Top 5 전달    │  │              │                                ║
║  └──────┬───────────┘  │              │                                ║
║         │              │              │                                ║
║         ▼              ▼              │                                ║
║  ┌─────────────────────────────────┐  │                                ║
║  │ LLM 모듈 [경은] #39             │  │                                ║
║  │                                 │  │                                ║
║  │  현재: GPT/Claude API           │  │                                ║
║  │  ──────────────────────────     │  │                                ║
║  │  추후(4단계): vLLM + LoRA      │  │                                ║
║  │  ┌───────────┐  ┌───────────┐  │  │                                ║
║  │  │ LoRA v1   │  │ LoRA v2   │  │  │                                ║
║  │  │ 판단 특화  │  │ 문서 특화  │  │  │                                ║
║  │  │ 1,500개   │  │ 1,700개   │  │  │                                ║
║  │  │ [경은]    │  │ [승언]    │  │  │                                ║
║  │  └───────────┘  └───────────┘  │  │                                ║
║  │                                 │  │                                ║
║  │  Base: Kanana-1.5-8B            │  │                                ║
║  │        (벤치마크 선정, 종합 0.652)│  │                               ║
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
║  External Services                                                     ║
║                                                                        ║
║  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        ║
║  │ Google OAuth 2.0│  │ Google APIs     │  │ RunPod (A100)   │        ║
║  │ (통합 scope)    │  │ Calendar+Tasks  │  │ GPU 학습 [경은] │        ║
║  │ [혜빈]          │  │ Gmail+Sheets    │  │                 │        ║
║  │                 │  │ +Meet [혜빈]    │  │                 │        ║
║  └─────────────────┘  └─────────────────┘  └─────────────────┘        ║
╚════════════════════════════════════════════════════════════════════════╝
```

### RAG 검색 대상

| Agent/기능 | RAG | 검색 대상 | 비고 |
|-----------|-----|----------|------|
| Judgment | O | 규정/규칙 문서 | 문서 카테고리 필터 |
| doc_search | O | 모든 문서 | 필터 없음 |
| doc_qa | O | 비규정 업무 문서 | 문서 카테고리 필터 |
| doc_generate | X | - | 사용자 입력 기반 생성 |
| doc_summary | X | - | 대상 문서가 명시적으로 주어짐 |
| Schedule | X | - | |
| General | X | - | |

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
│    1) BM25 검색 (Top 15)            │
│    2) Vector 검색 (Top 15)          │
│    3) 합산 (Top 20)                 │
│    4) Reranker (Top 5)              │
│    → 정보보안 규정 3.2조            │
│    → 개발 가이드라인 5.1조          │
│    → 인사 규정 2.3조                │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 4. 판단 Agent + LLM        [경은]   │
│    현재: GPT/Claude API             │
│    추후: LoRA v1 (판단 특화)        │
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
| LLM API (현재) | **GPT-4 / Claude** | 기능 구현 단계에서 사용, 추후 sLLM 교체 |
| Base sLLM (추후) | **Kanana-1.5-8B** | 벤치마크 선정 (종합 0.652) |
| Fine-tuning (추후) | **LoRA (PEFT)** + QLoRA 4-bit | 판단 v1 (1,500개) + 문서 v2 (1,700개) |
| 모델 서빙 | **vLLM** | OpenAI 호환 API + LoRA 핫스왑 + 스트리밍 |
| Vector DB | **Qdrant** | 문서 임베딩 저장 + 유사도 검색 |
| Embedding | **jhgan/ko-sbert-nli** | 한국어 문장 임베딩 |
| Reranker | **BAAI/bge-reranker-v2-m3** | 검색 결과 재정렬 (Top 5) |
| 키워드 검색 | **BM25 (rank_bm25)** | Hybrid Search의 키워드 매칭 |
| Intent 분류 | **klue/bert-base** | 8개 카테고리: judgment, doc_search, doc_generate, doc_summary, doc_qa, schedule_add, schedule_view, general |
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
| 애니메이션 | framer-motion |
| 차트 | Recharts |

### Infra

| 구분 | 기술 |
|------|------|
| Cloud | AWS (EC2 + S3 + RDS) |
| GPU (학습) | RunPod (A100 40GB) |
| Container | Docker + Docker Compose |
| CI/CD | GitHub Actions |

---

## 파인튜닝 데이터 (4단계에서 진행)

> LLM API로 기능을 완성한 뒤, 확정된 input/output 형태에 맞춰 데이터 수집 → sLLM 교체

| 어댑터 | 데이터 구성 | 합계 | 담당 |
|--------|-----------|------|------|
| **LoRA v1** (판단) | 판단 1,000 + Q&A 500 | **1,500개** | 경은 |
| **LoRA v2** (문서) | 회의록 800 + 검색 200 + 요약 300 + 생성 200 + 리스크 200 | **1,700개** | 승언 |

### Intent 분류 데이터 (완료)

| 구분 | 건수 | 모델 |
|------|------|------|
| 원본 학습 데이터 | 1,405개 (7개 JSONL) | klue/bert-base |
| 증강 데이터 | 463개 (13개 증강 파일) | — |
| **학습 합계** | **1,868개** | — |
| Adversarial 테스트셋 | 120개 | Eval F1 98.2%, Adv F1 90.2% |

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
│       ├── models/              # ORM 모델 (11개 테이블)
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
│   │   ├── config.py            # 분류 임계값 설정
│   │   ├── orchestrator.py      # StateGraph 오케스트레이터
│   │   ├── intent_classifier.py # Intent 분류 (klue/bert-base)
│   │   ├── judgment_agent.py    # 판단 Agent (경은)
│   │   ├── document_agent.py    # 문서 Agent (승언)
│   │   └── schedule_agent.py    # 일정 Agent (혜빈)
│   ├── llm/                     # LLM 공통 모듈 (경은)
│   │   ├── base.py              # BaseLLMProvider 인터페이스
│   │   ├── factory.py           # LLM 팩토리
│   │   ├── openai_provider.py   # OpenAI (GPT)
│   │   ├── anthropic_provider.py # Anthropic (Claude)
│   │   └── prompts.py           # 프롬프트 관리
│   ├── rag/                     # RAG 파이프라인 (경은)
│   │   ├── hybrid_search.py     # BM25 + Vector
│   │   ├── reranker.py          # bge-reranker-v2-m3
│   │   ├── vectorstore.py       # Qdrant
│   │   ├── qdrant_pipeline.py   # Qdrant 파이프라인
│   │   └── qdrant_store.py      # Qdrant 벡터스토어
│   ├── templates/               # 문서 템플릿 (승언)
│   │   ├── base.py              # BaseTemplate
│   │   ├── meeting_minutes.py   # 회의록
│   │   ├── report.py            # 보고서
│   │   ├── jd.py                # 채용 공고
│   │   └── proposal.py          # 제안서
│   ├── tests/                   # AI 테스트
│   ├── experiments/             # ML 실험 (전처리, 학습, 평가)
│   ├── finetuning/              # LoRA 학습 (경은/승언)
│   ├── document_parser/         # 문서 파싱 (승언)
│   └── serving/vllm_client.py   # vLLM 클라이언트
│
├── frontend/                    # React 프론트엔드 (지영)
│   └── src/
│       ├── components/
│       │   ├── chat/            # 챗봇 UI + 응답 카드
│       │   ├── dashboard/       # 대시보드 위젯
│       │   ├── documents/       # 문서 관리
│       │   ├── meetings/        # 회의 관리
│       │   ├── schedules/       # 일정 (FullCalendar)
│       │   ├── auth/            # 로그인/회원가입
│       │   └── admin/           # 관리자
│       ├── hooks/               # useAuth, useSSE, useChat
│       ├── store/               # Zustand (auth, chat, ui, google)
│       └── pages/               # 페이지 라우팅
│
├── data/                        # 학습/평가 데이터
│   ├── training/
│   │   ├── intent/              # Intent 데이터 (원본 1,405 + 증강 463)
│   │   ├── v1_judgment/         # 판단 데이터 (1,500개)
│   │   └── v2_document/         # 문서 데이터 (1,700개)
│   ├── evaluation/              # 벤치마크 리포트 + 결과
│   └── regulations/             # 규정 원본 문서
│
├── docs/                        # 기획/설계 문서
│   ├── agent/architecture.md    # 아키텍처 설계
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
| **윤경은** (AI서브) | 파인튜닝 v1 + 판단 + RAG | `judgment_agent.py`, `ai/rag/*`, LoRA v1, vLLM 서빙 |
| **진승언** (AI리드) | 파인튜닝 v2 + 문서 Agent | `document_agent.py`, `ai/templates/*`, `document_parser/*`, LoRA v2 |
| **안혜빈** (Backend) | DB + 인증 + 일정 Agent | `models/*`, `services/*`, JWT, Google Services 통합, 관리자 API |
| **문지영** (Frontend) | React UI 전담 | `frontend/src/` 전체, SSE 수신, 카드 UI, 반응형 |

---

## Git 브랜치 전략

> 1인 1브랜치 원칙 — 브랜치 5개로 충돌 최소화

```
main (배포용 - PM 지용만 머지)
 └── develop (통합 개발 - PR 머지 대상)
      ├── feat/jiyong            Intent, 오케스트레이터, SSE, 스키마
      ├── feat/ai-경은          LLM API, RAG, 판단 Agent, 파인튜닝
      ├── feat/ai-승언          문서 Agent, 파서, 템플릿, 파인튜닝
      ├── feat/backend-혜빈     DB, 인증, API, Google Services
      └── feat/frontend-지영    전체 UI
```

### 커밋 컨벤션

```
<type>: <설명> #이슈번호

feat: 판단 Agent LLM API 연동 #12
fix: Intent 분류 confidence 임계값 조정 #5
docs: API 스키마 문서 업데이트 #2
```

### PR 규칙

```
1. 자기 브랜치에서 작업 후 push
2. GitHub PR 생성 (develop ← feat/xxx-이름)
3. PR 본문에 "Closes #이슈번호"
4. 리뷰 승인 후 Squash and merge
5. develop → main은 PM(지용)만 머지
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
| `docs/agent/architecture.md` | 아키텍처 설계 (Agent 워크플로우, RAG 대상, 파인튜닝 전략) |
| `docs/TASK_BOARD.md` | 일일 작업 참고 (체크리스트, 이슈 매핑) |
| `docs/역할분배_기술스택_v5_final.md` | 기술 결정 배경, 멘토 피드백, 아키텍처 상세 |
| Swagger UI (`/docs`) | API 스펙 확인 (서버 실행 후) |

---

## API 문서

서버 실행 후:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
