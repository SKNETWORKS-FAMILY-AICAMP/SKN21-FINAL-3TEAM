/** 산출물 2: 시스템 아키텍처 문서 */
const C = require("./doc_common");

const children = [
  ...C.commonHeader("시스템 아키텍처"),

  ...C.overviewBlock({
    step: "모델링 및 평가",
    docName: "시스템 아키텍처",
    date: "2026.03.05",
    github: "https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM",
    members: "신지용, 윤경은, 안혜빈, 문지영",
  }),

  // TOC 테이블
  C.dataTable(
    ["항목", "하위 항목 1", "하위 항목 2"],
    [
      ["컴포넌트 다이어그램", "구성 요소", "설명"],
      ["시퀀스 다이어그램", "참여자 (Actors)", "주요 흐름"],
      ["액티비티 다이어그램", "구성", "주요 액션 노드"],
    ],
    [3200, 2936, 2936]
  ),

  C.pgBreak(),

  // ═══ 1. 컴포넌트 다이어그램 ═══
  C.h1("1. 컴포넌트 다이어그램"),
  C.imagePlaceholder("컴포넌트 다이어그램 이미지 — 별도 첨부"),

  C.h2("구성 요소"),
  C.numbered(1, "클라이언트 (Client):"),
  C.dash("React (Vite) + Tailwind + shadcn/ui", 1),
  C.dash("FullCalendar (일정 UI)", 1),
  C.dash("인터페이스: JWT 인증, REST API (HTTPS)", 1),

  C.numbered(2, "AWS Cloud:"),
  C.dash("EC2 인스턴스: Nginx (리버스 프록시), Gunicorn (WSGI), FastAPI (백엔드)", 1),
  C.dash("LangGraph Multi-Agent: Orchestrator, Judgment Agent, Document Agent, Schedule Agent", 1),
  C.dash("RAG Pipeline: Qdrant Vector DB, BM25 + ko-sbert-nli embeddings, bge-reranker", 1),

  C.numbered(3, "데이터베이스:"),
  C.dash("PostgreSQL (RDS) + SQLAlchemy / Alembic", 1),

  C.numbered(4, "외부 서비스:"),
  C.dash("RunPod (sLLM / vLLM 실행 환경)", 1),
  C.dash("OpenAI / Anthropic API (LLM)", 1),
  C.dash("Google Services (Calendar, Gmail, Sheets, Drive)", 1),

  C.h2("설명"),
  C.body("- 클라이언트는 React 프론트엔드에서 JWT 인증을 수행하고, REST API로 FastAPI 백엔드와 통신합니다."),
  C.body("- AWS Cloud의 EC2에서 Nginx + Gunicorn + FastAPI가 요청을 처리하며, LangGraph 기반 Multi-Agent 시스템이 의도 분류 결과에 따라 적절한 Agent로 라우팅합니다."),
  C.body("- 판단 Agent는 Qdrant RAG + Hybrid Search(BM25 + ko-sbert-nli)로 관련 규정을 검색한 후, bge-reranker로 재순위화하고 LLM으로 최종 판단을 생성합니다."),
  C.body("- 최종 응답은 SSE(Server-Sent Events)를 통해 실시간으로 스트리밍됩니다."),

  C.pgBreak(),

  // ═══ 2. 시퀀스 다이어그램 ═══
  C.h1("2. 시퀀스 다이어그램"),
  C.imagePlaceholder("시퀀스 다이어그램 이미지 — 별도 첨부"),

  C.h2("참여자 (Actors)"),
  C.numbered(1, "User: React Frontend를 통해 요청을 시작하는 사용자"),
  C.numbered(2, "Frontend: React (Vite) 기반 SPA 클라이언트"),
  C.numbered(3, "FastAPI: 백엔드 API 서버 (JWT 인증 처리)"),
  C.numbered(4, "LangGraph Orchestrator: 의도 분류 + Agent 라우팅"),
  C.numbered(5, "Judgment Agent: RAG + LLM 기반 규정 판단"),
  C.numbered(6, "Document Agent: 문서 생성/검색/요약/QA"),
  C.numbered(7, "Schedule Agent: Google Calendar API 연동"),
  C.numbered(8, "LLM Provider: OpenAI(GPT-4o) / Anthropic(Claude) / vLLM(Kanana)"),

  C.h2("주요 흐름"),
  C.numbered(1, "사용자가 채팅 메시지를 입력하면 React Frontend가 FastAPI로 HTTP 요청을 전송합니다."),
  C.numbered(2, "FastAPI는 JWT 토큰을 검증하고, 유효한 요청을 LangGraph Orchestrator로 전달합니다."),
  C.numbered(3, "Orchestrator는 BERT Intent Classifier를 호출하여 8개 카테고리 중 하나로 의도를 분류합니다 (confidence > 0.85)."),
  C.numbered(4, "분류된 의도에 따라 해당 Agent(Judgment / Document / Schedule)로 라우팅합니다."),
  C.numbered(5, "각 Agent는 필요 시 LLM Provider를 호출하여 응답을 생성합니다."),
  C.numbered(6, "생성된 응답은 SSE를 통해 실시간으로 Frontend에 스트리밍됩니다."),

  C.pgBreak(),

  // ═══ 3. 액티비티 다이어그램 ═══
  C.h1("3. 액티비티 다이어그램"),
  C.imagePlaceholder("액티비티 다이어그램 이미지 — 별도 첨부"),

  C.h2("구성"),
  C.numbered(1, "시작 지점: 사용자가 채팅 메시지를 입력합니다."),
  C.numbered(2, "Intent 분류: BERT 모델이 8개 카테고리로 분류"),
  C.body("   카테고리: judgment, doc_search, doc_generate, doc_summary, doc_qa, schedule_add, schedule_view, general", { indent: 400 }),
  C.numbered(3, "분기 (Decision Node):"),
  C.dash("judgment → RAG 검색 + 규정 판단 생성 (Judgment Agent)", 1),
  C.dash("doc_* → 문서 처리 (Document Agent: 검색/생성/요약/QA)", 1),
  C.dash("schedule_* → 일정 관리 (Schedule Agent: 추가/조회)", 1),
  C.dash("general → 일반 대화 (직접 LLM 응답)", 1),
  C.numbered(4, "각 Agent 처리 후 응답을 SSE로 스트리밍"),
  C.numbered(5, "종료 지점: 사용자에게 결과 반환"),

  C.h2("주요 액션 노드"),
  C.dash("메시지 수신: FastAPI 엔드포인트에서 사용자 입력 수신 및 인증 검증"),
  C.dash("의도 분류: BERT 기반 Intent Classifier가 사용자 발화의 의도를 판별"),
  C.dash("Judgment Agent: Qdrant 하이브리드 검색(BM25 + Dense) → bge-reranker → LLM 판단 생성"),
  C.dash("Document Agent: 문서 검색, 생성(회의록/보고서/제안서), 요약, 질의응답 처리"),
  C.dash("Schedule Agent: Google Calendar 연동을 통한 일정 추가/조회/관리"),
  C.dash("응답 스트리밍: SSE를 통해 생성된 토큰을 실시간으로 클라이언트에 전송"),
];

const doc = C.buildDoc(children);
C.save(doc, "docs/산출물/5주차/3.모델링 및 평가_시스템 아키텍처.docx");
