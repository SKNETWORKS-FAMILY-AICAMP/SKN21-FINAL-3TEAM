/** 산출물 5: 테스트 계획 및 결과 보고서 */
const C = require("./doc_common");

const children = [
  ...C.commonHeader("테스트 계획 및 결과 보고서"),

  ...C.overviewBlock({
    step: "모델링 및 평가",
    docName: "테스트 계획 및 결과 보고서",
    date: "2026.03.05",
    github: "https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM",
    members: "신지용, 윤경은, 안혜빈, 문지영",
  }),

  // ═══ 개요 (2단 테이블) ═══
  C.twoColRow("개요", [
    C.bullet("구현한 LLM 활용 어플리케이션의 전체 동작을 사용자의 어플리케이션 활용 흐름에 따라 테스트 하기 위한 계획서 및 결과 보고서."),
    C.bullet("다음의 과정에 따라 어플리케이션의 동작 검증"),
    C.bullet("규정 판단 질의 (Judgment Agent)", 1),
    C.bullet("문서 생성/검색/요약/QA (Document Agent)", 1),
    C.bullet("일정 관리 (Schedule Agent)", 1),
    C.bullet("Intent 분류 정확도", 1),
    C.bullet("RAG 검색 품질", 1),
    C.bullet("FastAPI로 구현된 LLM 어플리케이션 API Server를 구성하고 Swagger UI를 통해 검증"),
  ]),

  C.body(""),

  // ═══ 테스트 1: 규정 판단 ═══
  C.twoColRow("규정 판단\n(Judgment)", [
    C.bullet("사용자 질의에 따라 기업 내부 규정을 검색하고 판단 결과를 JSON으로 반환"),
    C.bullet("규정 검색 → RAG Hybrid Search → LLM 판단 생성"),
    C.bullet("판단 결과: result(yes/no/conditional/no_regulation), confidence, reasoning 포함"),
    C.body(""),
    C.body("요청:", { bold: true }),
    ...C.codeBlock([
      '{"question": "출장비 일비 지급 기준이 어떻게 되나요?"}',
    ]),
    C.body(""),
    C.body("결과:", { bold: true }),
    ...C.codeBlock([
      '{',
      '  "result": "yes",',
      '  "confidence": 0.92,',
      '  "reasoning": "출장규정 제8조에 따르면 출장 시 일비는',
      '    직급에 따라 차등 지급됩니다. 부장급 이상 50,000원,',
      '    과장급 40,000원, 대리급 이하 30,000원이 지급됩니다.",',
      '  "regulations": ["출장규정 제8조"]',
      '}',
    ]),
    C.body(""),
    C.bullet("정상적인 규정 검색 및 판단 결과 생성 확인"),
  ]),

  C.body(""),

  // ═══ 테스트 2: 문서 생성 ═══
  C.twoColRow("문서 생성\n(Document)", [
    C.bullet("사용자 요청에 따라 회의록, 보고서, 제안서 등의 문서를 생성"),
    C.bullet("문서 유형 설정 → 목차 생성 → 섹션별 내용 작성 → 전체 문서 반환"),
    C.body(""),
    C.body("요청:", { bold: true }),
    ...C.codeBlock([
      '{',
      '  "question": "2026년 1분기 프로젝트 진행 보고서 작성해줘",',
      '  "chat_option": "문서 생성"',
      '}',
    ]),
    C.body(""),
    C.body("결과:", { bold: true }),
    C.bullet("정상적인 목차 생성 및 섹션별 내용 작성"),
    C.bullet("문서 다운로드 기능 정상 동작 확인"),
  ]),

  C.body(""),

  // ═══ 테스트 3: 일정 관리 ═══
  C.twoColRow("일정 관리\n(Schedule)", [
    C.bullet("Google Calendar API와 연동하여 일정 추가/조회"),
    C.body(""),
    C.body("요청:", { bold: true }),
    ...C.codeBlock([
      '{"question": "다음 주 월요일 오후 2시에 팀 미팅 일정 추가해줘"}',
    ]),
    C.body(""),
    C.body("결과:", { bold: true }),
    C.bullet("Google Calendar에 일정 등록 완료"),
    C.bullet("일정 제목/시간/참석자 정보 정상 반환"),
  ]),

  C.pgBreak(),

  // ═══ 테스트 4: Intent 분류 ═══
  C.twoColRow("Intent\n분류 테스트", [
    C.bullet("BERT 기반 의도 분류기가 사용자 발화를 8개 카테고리로 분류"),
    C.bullet("카테고리: judgment, doc_search, doc_generate, doc_summary, doc_qa, schedule_add, schedule_view, general"),
    C.bullet("confidence threshold: 0.85 이상 시 해당 Agent로 라우팅"),
    C.body(""),
    C.body("테스트 결과:", { bold: true }),
    C.dataTable(
      ["입력", "예상", "실제", "confidence"],
      [
        ["연차 규정 알려줘", "judgment", "judgment", "0.94"],
        ["회의록 작성해줘", "doc_generate", "doc_generate", "0.91"],
        ["내일 일정 뭐 있어?", "schedule_view", "schedule_view", "0.89"],
        ["안녕하세요", "general", "general", "0.96"],
      ],
      [2000, 1600, 1600, 1172]
    ),
  ]),

  C.body(""),

  // ═══ 테스트 5: RAG 검색 ═══
  C.twoColRow("RAG 검색\n품질 테스트", [
    C.bullet("Hybrid Search (BM25 + Vector) + Reranker 파이프라인 평가"),
    C.body(""),
    C.body("검색 품질 지표:", { bold: true }),
    C.dataTable(
      ["지표", "값", "비고"],
      [
        ["Top-5 Recall", "87.3%", "상위 5개 결과 내 정답 포함률"],
        ["MRR", "0.82", "Mean Reciprocal Rank"],
        ["Reranker 적용 Top-3 정확도", "91.5%", "bge-reranker 적용 후"],
      ],
      [2500, 1300, 2572]
    ),
    C.body(""),
    C.bullet("BM25 단독 대비 Hybrid Search가 약 12% 성능 향상"),
  ]),

  C.body(""),

  // ═══ 테스트 6: LoRA 파인튜닝 평가 ═══
  C.twoColRow("LoRA v1\n파인튜닝 평가", [
    C.bullet("베이스 모델: Kanana-1.5-8B-Instruct (kakaocorp)"),
    C.bullet("파인튜닝: QLoRA 4-bit (r=16, alpha=32)"),
    C.bullet("학습 데이터: 2,949건 (train) / 328건 (eval)"),
    C.body(""),
    C.body("평가 결과 (328건):", { bold: true }),
    C.dataTable(
      ["카테고리", "정확도", "건수"],
      [
        ["no_regulation", "97.0%", "67건"],
        ["yes", "85.0%", "100건"],
        ["conditional", "84.0%", "100건"],
        ["no", "82.0%", "61건"],
        ["전체", "86.6%", "328건"],
      ],
      [2500, 1800, 2072]
    ),
    C.body(""),
    C.bullet("JSON 유효율: 98.2%"),
    C.bullet("v2 학습 준비 중 (r=32, alpha=64, epoch=5 → no/conditional 경계 개선 목표)"),
  ]),
];

const doc = C.buildDoc(children);
C.save(doc, "docs/산출물/5주차/3.모델링 및 평가_테스트 계획 및 결과 보고서.docx");
