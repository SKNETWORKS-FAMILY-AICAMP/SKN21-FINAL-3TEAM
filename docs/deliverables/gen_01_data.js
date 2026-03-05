/** 산출물 1: 수집된 데이터 및 전처리 문서 */
const C = require("./doc_common");

const children = [
  ...C.commonHeader("수집된 데이터 및 전처리 문서"),

  ...C.overviewBlock({
    step: "모델링 및 평가",
    docName: "수집된 데이터 및 전처리 문서",
    date: "2026.03.05",
    github: "https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM",
    members: "신지용, 윤경은",
  }),

  // ═══ 1. 개요 ═══
  C.h1("1. 개요"),

  C.h2("1.1 데이터 설명"),
  C.body("본 문서는 WorkFlow Agent(듀듀) 프로젝트에서 기업 내부 규정 기반 업무 지원 AI 어시스턴트의 sLLM(smaller Large Language Model) 파인튜닝을 위한 데이터 수집 및 전처리 과정을 정리한 문서입니다."),
  C.body("데이터의 출처, 수집 방법, 전처리 단계, 품질 관리 및 저장 방식에 대한 내용을 포함합니다."),
  C.body(""),
  C.body("본 프로젝트는 가상 기업(듀듀테크)의 내부 규정 10종을 기반으로, 사용자 질의에 대한 규정 판단(Judgment), 의도 분류(Intent), 문서 처리(Document) 기능을 제공하며, 각 기능에 특화된 파인튜닝 데이터를 수집/생성하였습니다."),

  C.h2("1.2 데이터 수집 목적"),
  C.body("WorkFlow Agent는 기업 내부 규정을 기반으로 질의에 답변하는 AI 어시스턴트로, 정교한 규정 해석과 판단 능력이 요구됩니다. 이에 따라:"),
  C.bullet("규정 판단(Judgment): yes/no/conditional/no_regulation 4가지 판단을 정확히 생성"),
  C.bullet("의도 분류(Intent): 사용자 발화를 8개 카테고리로 정확히 분류"),
  C.bullet("문서 처리(Document): 회의록/보고서/제안서 생성, 요약, QA 기능 지원"),
  C.body("이러한 요구를 충족하기 위해 도메인 특화 데이터를 수집하고 가공하였습니다."),

  // ═══ 2. 데이터 수집 ═══
  C.h1("2. 데이터 수집"),

  C.h2("2.1 데이터 출처"),
  C.bullet("기업 내부 규정 원본: 자체 제작 가상 기업(듀듀테크) 규정 10종 (PDF/TXT)"),
  C.bullet("LLM API 생성: GPT-4 / Claude API로 규정 기반 질의-판단 쌍 자동 생성"),
  C.bullet("AIHub 공개 데이터: 문서 요약, MRC, 보고서 QA 데이터셋 활용"),
  C.bullet("데이터 증강: 경계 케이스, 적대적 패턴, 교차 규정 시나리오 추가"),

  C.h2("2.2 수집 기간"),
  C.body("2026.02.17 ~ 03.05 (약 17일)"),
  C.dash("규정 문서 수집: 02.17 ~ 02.21"),
  C.dash("Intent/Judgment/Document 데이터 생성: 02.21 ~ 03.04"),
  C.dash("전처리 및 정제: 03.04 ~ 03.05"),

  C.h2("2.3 데이터 유형"),
  C.bullet("텍스트 데이터 (JSONL — JSON Lines 형식)"),
  C.bullet("규정 원본 문서 (PDF / TXT)"),

  // ═══ 전체 데이터셋 현황 ═══
  C.h2("2.4 전체 데이터셋 현황"),
  C.body("학습 데이터 총 11,258건:", { bold: true }),
  C.dataTable(
    ["담당자", "데이터셋", "건수", "형식", "용도"],
    [
      ["신지용", "Intent v1", "1,916건", "JSONL", "의도 분류 모델 학습"],
      ["신지용", "Intent v2", "2,898건", "JSONL", "의도 분류 개선 (증강)"],
      ["윤경은", "Judgment v1", "3,277건", "JSONL", "규정 판단 LoRA 파인튜닝"],
      ["진승언", "Document Generate", "1,262건", "JSONL", "문서 생성 모델 학습"],
      ["진승언", "Document QA", "1,203건", "JSONL", "문서 질의응답 모델"],
      ["진승언", "Document Summary", "702건", "JSONL", "문서 요약 모델 학습"],
    ],
    [1100, 1600, 900, 800, 2672]
  ),
  C.body(""),
  C.body("규정 원본 문서 (10종):", { bold: true }),
  C.body("인사규정, 급여규정, 출장규정, 교육훈련규정, 복리후생규정, 징계규정, 윤리강령, 개인정보처리규정, IT보안규정, 종합규정(PDF)"),

  C.pgBreak(),

  // ═══ 3. 데이터 전처리 ═══
  C.h1("3. 데이터 전처리"),

  C.h2("3.1 전처리 개요"),
  C.bullet("데이터 정제 (JSON 파싱 오류, 중복, 결측치 처리)"),
  C.bullet("파인튜닝 형식 변환 (JSONL Chat Completion 포맷)"),
  C.bullet("프롬프트 엔지니어링 (conditional 판단 기준 명시)"),
  C.bullet("학습/평가 데이터 분할"),

  C.h2("3.2 데이터 정제"),
  C.h3("Intent 데이터 (신지용)"),
  C.bullet("중복 발화 제거"),
  C.bullet("레이블 불일치 수정"),
  C.bullet("v2 증강 기법: 경계 케이스, 적대적 패턴, 다중 의도, 초단문, 격식체"),
  C.body(""),
  C.dataTable(
    ["버전", "Train", "Val", "Test", "증강 기법"],
    [
      ["v1", "1,916건", "-", "-", "기본 카테고리별 생성"],
      ["v2", "2,327건", "285건", "286건", "경계/적대/다중의도/초단문/격식체"],
    ],
    [800, 1100, 900, 900, 3372]
  ),

  C.body(""),
  C.h3("Judgment 데이터 (윤경은)"),
  C.bullet("JSON 파싱 실패 샘플 제거 (약 1.8%)"),
  C.bullet("confidence 값 범위 보정 (0.0~1.0)"),
  C.bullet("reasoning 필드 비어있는 샘플 제거"),
  C.bullet("cross_references, alternatives 누락 시 빈 배열([])로 기본값"),
  C.bullet("conditions 필드: conditional 아닌 경우 null 통일"),
  C.body(""),
  C.dataTable(
    ["레이블", "Train", "Eval", "설명"],
    [
      ["yes", "~740건", "~82건", "규정상 무조건 허용/가능"],
      ["no", "~700건", "~78건", "규정상 명확히 금지/불가"],
      ["conditional", "~880건", "~98건", "조건부 허용 (승인/조건 필요)"],
      ["no_regulation", "~629건", "~70건", "관련 규정 없음"],
    ],
    [1500, 1200, 1000, 3372]
  ),
  C.body(""),
  C.body("교차 규정 데이터: cross_regulation v1~v4 포함 (3개+ 규정 교차 분석 시나리오)"),

  C.body(""),
  C.h3("Document 데이터 (진승언)"),
  C.dataTable(
    ["데이터셋", "건수", "출처", "설명"],
    [
      ["v2_generate", "1,262건", "AIHub + 자체", "회의록/보고서/제안서 생성"],
      ["v2_qa", "1,203건", "AIHub MRC", "문서 기반 질의응답"],
      ["v2_summary", "702건", "AIHub", "문서 요약"],
    ],
    [1500, 1000, 1200, 3372]
  ),

  C.pgBreak(),

  C.h2("3.3 프롬프트 엔지니어링 (Judgment v2)"),
  C.body("시스템 프롬프트에 conditional 판단 기준 5가지를 명시적으로 추가하여 판단 정확도를 개선하였습니다:"),
  C.numbered(1, "사전 승인/허가/신청이 필요한 경우"),
  C.numbered(2, "특정 조건 충족 시에만 허용 (기간, 금액, 자격 등)"),
  C.numbered(3, "여러 규정이 적용되어 상황에 따라 결과가 다른 경우"),
  C.numbered(4, "규정 간 충돌이 있어 상위 규정 확인 필요한 경우"),
  C.numbered(5, '재량 표현("~할 수 있다")이 있는 경우'),
  C.body(""),
  C.body("→ scripts/upgrade_prompts.py로 3,277건 전체 일괄 업데이트 완료"),

  C.h2("3.4 파인튜닝 형식 변환"),
  C.body("JSONL 형식 (OpenAI Chat Completion):", { bold: true }),
  C.body("하나의 샘플은 3개 role의 messages 배열로 구성됩니다."),
  ...C.codeBlock([
    '{"messages": [',
    '  {"role": "system", "content": "...판단 전문가 시스템 프롬프트..."},',
    '  {"role": "user", "content": "[규정 내용]\\n\\n[사용자 질문]"},',
    '  {"role": "assistant", "content": "{\\"result\\":\\"conditional\\",...}"}',
    ']}',
  ]),

  C.h2("3.5 학습/평가 데이터 분할"),
  C.dataTable(
    ["데이터셋", "Train", "Eval/Val", "Test", "비율"],
    [
      ["Intent v2", "2,327건", "285건", "286건", "80/10/10"],
      ["Judgment v1", "2,949건", "328건", "-", "90/10"],
      ["Document (3종)", "3,167건 합계", "-", "-", "전체 학습용"],
    ],
    [1600, 1200, 1200, 1000, 2072]
  ),

  // ═══ 4. 데이터 저장 및 검증 ═══
  C.h1("4. 데이터 저장 및 검증"),

  C.h2("4.1 저장 방식"),
  C.bullet("파일 형식: JSONL (JSON Lines) / 인코딩: UTF-8"),
  C.bullet("디렉토리: data/training/{intent, intent_v2, v1_judgment, v2_generate, v2_qa, v2_summary}/"),
  C.bullet("버전 관리: Git (GitHub) / 백업: *.jsonl.bak"),

  C.h2("4.2 정합성 검증 결과"),
  C.dataTable(
    ["검증 항목", "Judgment", "Intent", "Document"],
    [
      ["JSON 유효성", "98.2%", "100%", "100%"],
      ["필수 필드 존재", "100%", "100%", "100%"],
      ["레이블 값 유효", "100%", "100%", "100%"],
      ["프롬프트 일치", "100% (v2)", "-", "-"],
    ],
    [2000, 1690, 1690, 1692]
  ),

  C.body(""),
  C.h2("4.3 향후 계획"),
  C.body("현재 sLLM 파인튜닝(LoRA v2)이 진행 중이며, 학습 완료 후 성능 평가를 통해 추가 데이터 수집 여부를 결정할 예정입니다."),
  C.bullet("Judgment v2 학습 완료 후 conditional 정확도 개선 확인 (v1: 75% → 목표 85%+)"),
  C.bullet("Intent v2 데이터로 의도 분류 모델 재학습 예정"),
  C.bullet("Document Agent 데이터 품질 검증 후 LoRA v2 학습 진행"),
];

const doc = C.buildDoc(children);
C.save(doc, "docs/산출물/5주차/3.모델링 및 평가_수집된 데이터 및 전처리 문서.docx");
