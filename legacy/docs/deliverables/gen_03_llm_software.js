/** 산출물 3: LLM 활용 소프트웨어 */
const C = require("./doc_common");

const children = [
  ...C.commonHeader("LLM 활용 소프트웨어"),

  // 정보 테이블
  C.infoTable([
    ["산출물 단계", "모델링 및 평가"],
    ["평가 산출물", "LLM 활용 소프트웨어"],
    ["제출 일자", "2026.03.05"],
    ["깃허브 경로", "https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM"],
    ["작성 팀원", "신지용, 윤경은, 안혜빈, 문지영"],
  ]),
  C.body(""),
  C.body("*활용한 LLM 모델: GPT-4o (OpenAI), Claude 3.5 Sonnet (Anthropic), Kanana-1.5-8B-Instruct (vLLM/LoRA)"),

  // ═══ 1. 시스템 개요 ═══
  C.h1("1. 시스템 개요"),
  C.body("본 소프트웨어는 기업 내부 규정 문서를 벡터 데이터베이스(Qdrant)에 저장하고 LLM(GPT-4o / Claude / vLLM)과 연동하여 사용자 질문에 규정 기반 답변을 제공하는 RAG(Retrieval-Augmented Generation) + Multi-Agent 구조를 사용합니다."),
  C.body("LLM API Key 등 민감 정보는 환경 변수로 관리되며, 프롬프트 최적화를 통해 빠른 응답 속도와 품질을 보장합니다."),

  // ═══ 2. 시스템 구성 요소 ═══
  C.h1("2. 시스템 구성 요소"),
  ...C.codeBlockLight([
    "User",
    "  |",
    "  v",
    "[React Frontend (Vite + Tailwind)]",
    "  |",
    "  v",
    "[FastAPI Backend + JWT Auth]",
    "  |",
    "  v",
    "[LangGraph Orchestrator]",
    "  |-- 1. Intent Classification    <-- (BERT 분류기, 8개 카테고리)",
    "  |-- 2. Judgment Agent           <-- (RAG: Qdrant + BM25 + ko-sbert-nli)",
    "  |-- 3. Document Agent           <-- (생성/검색/요약/QA)",
    "  |-- 4. Schedule Agent           <-- (Google Calendar API)",
    "  +-- 5. LLM Provider            <-- (OpenAI/Anthropic/vLLM Factory)",
  ]),
  C.body(""),
  C.body("구성 요소 설명:", { bold: true }),
  C.bullet("Intent Classification: BERT 기반 분류기로 사용자 발화를 8개 카테고리로 분류 (confidence > 0.85 시 라우팅)"),
  C.bullet("Judgment Agent: Qdrant 하이브리드 검색(BM25 + Vector) → bge-reranker 재순위화 → LLM 판단 생성"),
  C.bullet("Document Agent: 문서 검색(doc_search), 생성(doc_generate), 요약(doc_summary), QA(doc_qa)"),
  C.bullet("Schedule Agent: Google Calendar API 연동으로 일정 추가/조회"),
  C.bullet("LLM Provider: Factory 패턴으로 OpenAI/Anthropic/vLLM 간 전환 (BaseLLM 추상 클래스)"),

  C.pgBreak(),

  // ═══ 3. 코드 구조 ═══
  C.h1("3. 코드 구조 (모듈화, 주석 포함)"),
  ...C.treeBlock([
    "SKN21-FINAL-3TEAM/",
    "|-- ai/",
    "|   |-- agents/",
    "|   |   |-- orchestrator.py       # LangGraph 라우터 + Intent 분류",
    "|   |   |-- judgment_agent.py     # 규정 판단 Agent (RAG+LLM)",
    "|   |   |-- document_agent.py     # 문서 처리 Agent",
    "|   |   +-- schedule_agent.py     # 일정 관리 Agent",
    "|   |-- llm/",
    "|   |   |-- factory.py            # LLM Provider Factory",
    "|   |   |-- base.py               # BaseLLM 추상 클래스",
    "|   |   |-- openai_provider.py    # OpenAI GPT-4o",
    "|   |   |-- anthropic_provider.py # Claude 3.5 Sonnet",
    "|   |   +-- vllm_provider.py      # vLLM (LoRA 모델)",
    "|   |-- rag/",
    "|   |   |-- hybrid_search.py      # BM25 + Vector 하이브리드",
    "|   |   |-- vectorstore.py        # Qdrant 벡터 저장소",
    "|   |   +-- reranker.py           # bge-reranker-v2",
    "|   |-- finetuning/               # LoRA 파인튜닝 스크립트",
    "|   +-- serving/                  # vLLM 서빙 클라이언트",
    "|-- backend/app/",
    "|   |-- api/v1/                   # REST API 엔드포인트",
    "|   |-- models/                   # SQLAlchemy ORM 모델",
    "|   |-- services/                 # 비즈니스 로직",
    "|   +-- schemas/                  # Pydantic 스키마",
    "|-- frontend/src/",
    "|   |-- components/               # React 컴포넌트",
    "|   |-- pages/                    # 11개 페이지",
    "|   +-- store/                    # Zustand 상태관리",
    "+-- .env                          # 환경 변수 (gitignore)",
  ]),

  // ═══ 4. 주요 코드 ═══
  C.h1("4. 주요 코드 (요약 + 평가요소 적용)"),

  C.h2("4.1 예외 처리 포함"),
  C.body("LLM 호출 시 try/except로 오류를 처리하여 서비스 안정성을 보장합니다:"),
  ...C.codeBlock([
    "async def call_llm(self, messages, **kwargs):",
    "    try:",
    "        response = await self.client.chat.completions.create(",
    "            model=self.model_name,",
    "            messages=messages,",
    "            **kwargs",
    "        )",
    "        return response.choices[0].message.content",
    "    except Exception as e:",
    '        logger.error(f"LLM 호출 실패: {e}")',
    '        raise LLMError(f"LLM 응답 생성 실패: {str(e)}")',
  ]),

  C.h2("4.2 LLM Provider Factory (모듈 전환)"),
  C.body("Factory 패턴으로 환경변수 하나만 변경하면 OpenAI/Anthropic/vLLM 간 전환이 가능합니다:"),
  ...C.codeBlock([
    "def create_llm(provider=None, config=None) -> BaseLLM:",
    '    provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()',
    '    if provider == "openai":',
    "        from ai.llm.openai_provider import OpenAIProvider",
    "        return OpenAIProvider(config)",
    '    elif provider == "anthropic":',
    "        from ai.llm.anthropic_provider import AnthropicProvider",
    "        return AnthropicProvider(config)",
    '    elif provider == "vllm":',
    "        from ai.serving.vllm_client import VLLMProvider",
    "        return VLLMProvider(config)",
    "    else:",
    '        raise ValueError(f"지원하지 않는 Provider: {provider}")',
  ]),

  C.h2("4.3 Judgment Agent — RAG 규정 그룹핑"),
  C.body("RAG 검색 결과를 규정 출처별로 그룹핑하여 교차 규정 판단의 정확도를 높입니다:"),
  ...C.codeBlock([
    "def _group_regulations(context: list[dict]) -> dict[str, list[dict]]:",
    '    """RAG 검색 결과를 규정 출처별로 그룹핑"""',
    "    groups: dict[str, list[dict]] = defaultdict(list)",
    "    for doc in context:",
    '        chapter = doc.get("chapter", "")',
    "        if chapter:",
    "            groups[chapter].append(doc)",
    "            continue",
    '        source = doc.get("source", "출처 불명")',
    '        reg_name = re.sub(r"\\.(pdf|md|txt)$", "", source).strip()',
    "        groups[reg_name].append(doc)",
    "    return dict(groups)",
  ]),

  C.h2("4.4 .env & 환경변수 설정"),
  ...C.codeBlock([
    "OPENAI_API_KEY=sk-...",
    "ANTHROPIC_API_KEY=sk-ant-...",
    "VLLM_BASE_URL=http://runpod-url:8000",
    "QDRANT_URL=http://localhost:6333",
    "DATABASE_URL=postgresql://...",
    "JWT_SECRET_KEY=...",
    "GOOGLE_CLIENT_ID=...",
  ]),

  C.pgBreak(),

  // ═══ 5. 프롬프트 최적화 ═══
  C.h1("5. 프롬프트 최적화"),
  C.body("질문과 검색된 문서를 바탕으로 프롬프트를 생성합니다. 문서 내용을 요약하고 중복을 제거하여 프롬프트 길이를 최적화합니다:"),
  ...C.codeBlock([
    "def build_judgment_prompt(question: str, context_docs: list[str]) -> str:",
    '    """질문과 검색된 문서를 바탕으로 프롬프트를 생성"""',
    "    docs = \"\\n\".join(set(context_docs))[:3000]  # 토큰 수 제한",
    "    return (",
    '        "당신은 기업 내부 규정 전문가입니다.\\n"',
    '        f"관련 규정:\\n{docs}\\n\\n"',
    '        f"질문: {question}\\n"',
    '        "JSON 형식으로 답변: {result, confidence, reasoning, regulations}"',
    "    )",
  ]),

  // ═══ 6. 보안 고려 사항 ═══
  C.h1("6. 보안 고려 사항"),
  C.body("API Key는 절대 코드에 하드코딩하지 않고, .env 파일 또는 시스템 환경 변수에서 로드합니다."),
  C.body(".env는 반드시 .gitignore에 추가합니다."),
  C.body("JWT 토큰 기반 인증으로 API 접근을 제어합니다."),
  C.body("Google OAuth 2.0으로 외부 서비스(Calendar, Gmail, Sheets) 연동 시 안전한 인증을 수행합니다."),

  // ═══ 7. 테스트 시나리오 ═══
  C.h1("7. 테스트 시나리오"),
  C.bullet('질문: "연차 사용 규정이 어떻게 되나요?"'),
  C.bullet('응답: RAG 검색 → 인사규정 제12조 기반 → JSON 판단 결과 반환'),
  C.body(""),
  C.body("→ 벡터 검색 + LLM 연동 + 예외 처리 + 최적화된 응답 확인"),

  C.body(""),

  // ═══ 평가요소표 ═══
  C.h2("평가요소표"),
  C.dataTable(
    ["평가 항목", "대응 내용"],
    [
      ["벡터 DB와 LLM이 목적에 맞는\n프롬프트로 효율적 연동", "프롬프트 생성 함수 + 검색된 문서 기반"],
      ["예상치 못한 상황 예외 처리 포함", "try/except로 LLM 호출 오류 처리"],
      ["코드 모듈화 및 주석 작성", "각 기능별 파일 분리 + 설명 포함"],
      ["보안 정보 노출 방지", ".env 파일 + 환경변수 활용"],
      ["빠른 응답을 위한 프롬프트 최적화", "중복 제거 및 길이 제한 전략"],
    ],
    [4536, 4536]
  ),
];

const doc = C.buildDoc(children);
C.save(doc, "docs/산출물/5주차/3.모델링 및 평가_LLM 활용 소프트웨어.docx");
