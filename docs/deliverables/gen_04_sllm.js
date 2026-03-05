/** 산출물 4: 자체 LLM 인공지능 (2단 테이블 레이아웃) */
const C = require("./doc_common");

const children = [
  // ── 타이틀 (좌측 정렬, 2단 테이블 스타일과 다름) ──
  C.para([C.t("자체 LLM 인공지능", { bold: true, size: 40, color: "1A1A1A" })], { after: 40 }),
  C.para([C.t("SKN Family AI Camp 21기 : 최종 프로젝트 3조", { size: 20, color: "555555" })], { after: 200 }),

  // ═══ 프로젝트 주제 ═══
  C.twoColRow("프로젝트 주제", [
    C.body("기업 내부 규정 기반 업무 지원 AI 어시스턴트 — WorkFlow Agent (듀듀)"),
  ]),

  // ═══ LLM Fine-Tuning 적용 원본 데이터 ═══
  C.twoColRow("LLM\nFine-Tuning\n적용 원본 데이터", [
    C.para([C.t("[ 기업 내부 규정 원본 10종 ]", { bold: true, size: 20 })], { after: 80 }),
    C.dash("인사규정, 급여규정, 출장규정, 교육훈련규정, 복리후생규정"),
    C.dash("징계규정, 윤리강령, 개인정보처리규정, IT보안규정, 종합규정(PDF)"),
    C.body(""),
    C.body("+) AIHub 공개 데이터(문서 요약, MRC, 보고서 QA)도 Document Agent 학습에 활용하였습니다."),
    C.body("+) 한국경제 PDF 자료는 프롬프트 엔지니어링만 적용했으므로 제외했습니다."),
  ]),

  // ═══ LLM 아웃풋 구조 ═══
  C.twoColRow("Judgment\nAgent\nLLM 아웃풋\n구조", [
    C.para([C.t("[ Judgment Agent 아웃풋 구조 ]", { bold: true, size: 20 })], { after: 80 }),
    C.body("1) result: 판단 결과 (yes / no / conditional / no_regulation)"),
    C.body("2) confidence: 판단 신뢰도 (0.0~1.0)"),
    C.body("3) reasoning: 판단 근거 설명"),
    C.body("4) regulations: 참조한 규정 목록"),
    C.body("5) cross_references: 교차 참조 규정"),
    C.body("6) alternatives: 대안/조건부 허용 시 안내"),
    C.body(""),
    C.body("아웃풋은 위와 같은 JSON 구조로 출력합니다."),
    C.body("따라서 Fine-Tuning 데이터도 위 형태를 참고하여 가공하였습니다."),
    C.body("참고로 해당 Fine-Tuning 단계는 AI 인플루언서의 말투가 아닌 '아웃풋 형태의 일관성 부여'에 초점을 두고 진행했습니다."),
  ]),

  // ═══ Document / Intent 아웃풋 구조 ═══
  C.twoColRow("Document\nAgent /\nIntent 분류\n아웃풋 구조", [
    C.para([C.t("[ Document Agent 아웃풋 구조 ]", { bold: true, size: 20 })], { after: 80 }),
    C.body("intent에 따라 4가지 분기로 동작합니다:"),
    C.dash("doc_search: 문서 검색 결과 반환 (관련 문서 목록 + 핵심 내용)"),
    C.dash("doc_generate: 문서 생성 (보고서/회의록/JD/제안서 — 목차 + 섹션별 내용)"),
    C.dash("doc_summary: 문서 요약 (원문 핵심 요약 텍스트)"),
    C.dash("doc_qa: 문서 기반 질의응답 (질문에 대한 답변 + 근거 문서)"),
    C.body(""),
    C.para([C.t("[ Intent 분류 아웃풋 구조 ]", { bold: true, size: 20 })], { after: 80 }),
    C.body("BERT 기반 분류기가 사용자 발화를 8개 카테고리로 분류:"),
    C.body("judgment, doc_search, doc_generate, doc_summary, doc_qa, schedule_add, schedule_view, general"),
    C.body("confidence > 0.85 시 해당 Agent로 라우팅, 미만 시 clarification 요청"),
  ]),

  // ═══ Fine-Tuning 데이터 구조 ═══
  C.twoColRow("Fine-Tuning\n데이터 구조", [
    C.para([C.t("[ Fine-Tuning 데이터 구조 ]", { bold: true, size: 20 })], { after: 80 }),
    C.body("Fine-Tuning 데이터는 JSONL 파일 형태로 구성되어 있으며, 총 3가지 role(system, user, assistant)을 부여했습니다."),
    C.body("첫 번째로 'system'에서는 프롬프트 지시 사항을 입력하였습니다."),
    C.body("두 번째로 'user'에서는 규정 내용 + 사용자 질문을 입력했습니다."),
    C.body("세 번째로 'assistant'에서는 프롬프트 지시 사항을 반영하여 판단 결과 JSON을 입력했습니다."),
    C.body(""),
    C.body("각 role에 부여한 예시는 아래와 같습니다."),
    C.body(""),
    C.para([C.t("[ system ]", { bold: true, size: 20 })], { after: 60 }),
    C.body("당신은 기업 내부 규정 판단 전문가입니다. 주어진 규정과 질문을 분석하여 JSON 형식으로 판단 결과를 제공하세요. result는 yes/no/conditional/no_regulation 중 하나여야 합니다."),
    C.body(""),
    C.para([C.t("[ user ]", { bold: true, size: 20 })], { after: 60 }),
    C.body("[규정 내용]"),
    C.body("인사규정 제12조(연차휴가)"),
    C.body("① 1년간 80퍼센트 이상 출근한 근로자에게 15일의 유급휴가를 준다..."),
    C.body(""),
    C.body("[질문]"),
    C.body("입사 6개월 된 직원이 연차를 사용할 수 있나요?"),
    C.body(""),
    C.para([C.t("[ assistant ]", { bold: true, size: 20 })], { after: 60 }),
    ...C.codeBlock([
      '{',
      '  "result": "conditional",',
      '  "confidence": 0.88,',
      '  "reasoning": "인사규정 제12조에 따르면 1년 80% 이상 출근시 15일',
      '    유급휴가를 부여하나, 1년 미만인 경우 1개월 개근시 1일의',
      '    유급휴가가 발생합니다.",',
      '  "regulations": ["인사규정 제12조"],',
      '  "cross_references": [],',
      '  "alternatives": ["1년 미만 근로자는 월 1일씩 발생하는 연차 사용 가능"]',
      '}',
    ]),
  ]),

  // ═══ Fine-Tuning 데이터 예시 / 현황 ═══
  C.twoColRow("Fine-Tuning\n데이터 현황", [
    C.body("이와 같은 형식으로 총 11,258건의 학습 데이터를 마련한 후, JSONL 형태로 정리했습니다."),
    C.body(""),
    C.dataTable(
      ["담당자", "데이터셋", "건수", "형식", "용도"],
      [
        ["신지용", "Intent v1", "1,916건", "JSONL", "의도 분류 모델 학습"],
        ["신지용", "Intent v2", "2,898건", "JSONL", "의도 분류 개선 (증강)"],
        ["윤경은", "Judgment v1", "3,277건", "JSONL", "규정 판단 LoRA 파인튜닝"],
        ["진승언", "Doc Generate", "1,262건", "JSONL", "문서 생성 모델 학습"],
        ["진승언", "Doc QA", "1,203건", "JSONL", "문서 질의응답 모델"],
        ["진승언", "Doc Summary", "702건", "JSONL", "문서 요약 모델 학습"],
      ],
      [900, 1200, 800, 700, 2400]
    ),
    C.body(""),
    C.body("파인튜닝 모델: Kanana-1.5-8B-Instruct (kakaocorp)", { bold: true }),
    C.body("파인튜닝 방식: QLoRA 4-bit (r=32, alpha=64, epoch=5, lr=1.5e-4)"),
    C.body("학습 환경: RunPod A100 40GB"),
  ]),
];

const doc = C.buildDoc(children);
C.save(doc, "docs/산출물/5주차/3.모델링 및 평가_자체 LLM 인공지능.docx");
