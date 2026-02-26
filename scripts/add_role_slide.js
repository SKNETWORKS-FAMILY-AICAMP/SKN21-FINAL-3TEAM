const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3" x 7.5"
pres.author = "Team DueDue";
pres.title = "역할별 업무 현황";

// ── Colors (matching existing Tailwind slate palette) ──
const BG = "F3F3F3";
const CARD_BG = "F8FAFC";       // slate-50
const DARK = "0F172A";           // slate-900
const TEXT_PRIMARY = "1E293B";   // slate-800
const TEXT_SEC = "334155";       // slate-700
const TEXT_MUTED = "5C7188";     // custom gray from existing slides
const HEADER_GRAY = "999999";
const BORDER = "E2E8F0";        // slate-200

// Accent colors (from existing slides)
const ORANGE = "ED561B";
const BLUE = "2D58B8";
const CYAN = "058DC7";
const GREEN = "50B432";
const RED = "E04B4B";

// ── Helpers (fresh objects each call to avoid pptxgenjs mutation bug) ──
const makeShadow = () => ({
  type: "outer", color: "000000", blur: 6, offset: 2, angle: 135, opacity: 0.06
});

const slide = pres.addSlide();
slide.background = { color: BG };

// ── "WorkFlow Agent" header ──
slide.addText("WorkFlow Agent", {
  x: 0.6, y: 0.2, w: 3, h: 0.35,
  fontSize: 13, fontFace: "Malgun Gothic",
  color: HEADER_GRAY, margin: 0,
});

// ── Title ──
slide.addText("역할별 업무 현황", {
  x: 0.6, y: 0.55, w: 6, h: 0.6,
  fontSize: 32, fontFace: "Roboto",
  color: DARK, bold: true, margin: 0,
});

// ── Subtitle line ──
slide.addText("5명의 팀원이 AI · Backend · Frontend 전 영역을 커버합니다", {
  x: 0.6, y: 1.1, w: 8, h: 0.3,
  fontSize: 12, fontFace: "Malgun Gothic",
  color: TEXT_MUTED, margin: 0,
});

// ── 5 Member Cards ──
const members = [
  {
    name: "신지용",
    role: "PM + Intent 분류",
    color: ORANGE,
    stat: "87.8%",
    statLabel: "Adv F1",
    items: [
      "Intent 7-Stage 실험 설계·수행",
      "LangGraph 오케스트레이터 + SSE",
      "판단/문서/일정 Agent 공동 개발",
      "GitHub 이슈/마일스톤 전면 정비",
    ],
  },
  {
    name: "진승언",
    role: "AI 리드 — 문서 Agent",
    color: BLUE,
    stat: "4",
    statLabel: "Doc 기능",
    items: [
      "Document Agent (생성/요약/검색/QA)",
      "PDF·DOCX 파서 + 템플릿 시스템",
      "CI/CD 파이프라인 (GitHub Actions)",
      "Qdrant 문서 관리 API 구현",
    ],
  },
  {
    name: "윤경은",
    role: "AI 서브 — 판단 Agent",
    color: CYAN,
    stat: "270",
    statLabel: "규정 청크",
    items: [
      "RAG (Qdrant + BM25 + Reranker)",
      "다중 규정 교차 판단 + 4층 환각 방지",
      "규정 문서 270개 청크 구축",
      "파인튜닝 데이터 1,500건 준비",
    ],
  },
  {
    name: "안혜빈",
    role: "Backend + Google",
    color: GREEN,
    stat: "51",
    statLabel: "REST API",
    items: [
      "DB 11테이블 + Alembic + JWT 인증",
      "Google 5대 서비스 통합 (OAuth)",
      "Schedule Agent + REST API 구현",
      "AWS EC2 배포 + CI/CD 운영",
    ],
  },
  {
    name: "문지영",
    role: "Frontend 전담",
    color: RED,
    stat: "63",
    statLabel: "컴포넌트",
    items: [
      "12페이지 + 63 컴포넌트 전체 UI",
      "대시보드·챗봇·문서·일정 관리",
      "다크모드 + Zustand + SSE 실시간",
      "Google Calendar + 관리자 페이지",
    ],
  },
];

const cardW = 2.28;
const cardH = 5.15;
const gap = 0.22;
const startX = 0.55;
const cardY = 1.55;

members.forEach((m, i) => {
  const x = startX + i * (cardW + gap);

  // Card background with shadow
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y: cardY, w: cardW, h: cardH,
    fill: { color: CARD_BG },
    line: { color: BORDER, width: 0.5 },
    shadow: makeShadow(),
  });

  // ── Color header strip ──
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y: cardY, w: cardW, h: 0.08,
    fill: { color: m.color },
    line: { width: 0 },
  });

  // ── Colored circle with initial ──
  slide.addShape(pres.shapes.OVAL, {
    x: x + 0.15, y: cardY + 0.25, w: 0.5, h: 0.5,
    fill: { color: m.color },
    line: { width: 0 },
  });
  slide.addText(m.name.charAt(0), {
    x: x + 0.15, y: cardY + 0.25, w: 0.5, h: 0.5,
    fontSize: 18, fontFace: "Roboto",
    color: "FFFFFF", bold: true,
    align: "center", valign: "middle", margin: 0,
  });

  // ── Name ──
  slide.addText(m.name, {
    x: x + 0.75, y: cardY + 0.22, w: cardW - 0.9, h: 0.3,
    fontSize: 16, fontFace: "Malgun Gothic",
    color: TEXT_PRIMARY, bold: true, margin: 0,
  });

  // ── Role label ──
  slide.addText(m.role, {
    x: x + 0.75, y: cardY + 0.5, w: cardW - 0.9, h: 0.25,
    fontSize: 9, fontFace: "Malgun Gothic",
    color: TEXT_MUTED, margin: 0,
  });

  // ── Stat callout ──
  slide.addShape(pres.shapes.RECTANGLE, {
    x: x + 0.15, y: cardY + 0.95, w: cardW - 0.3, h: 0.75,
    fill: { color: m.color, transparency: 92 },
    line: { width: 0 },
  });
  slide.addText(m.stat, {
    x: x + 0.15, y: cardY + 0.92, w: cardW - 0.3, h: 0.5,
    fontSize: 30, fontFace: "Roboto",
    color: m.color, bold: true,
    align: "center", valign: "middle", margin: 0,
  });
  slide.addText(m.statLabel, {
    x: x + 0.15, y: cardY + 1.35, w: cardW - 0.3, h: 0.25,
    fontSize: 10, fontFace: "Malgun Gothic",
    color: TEXT_MUTED,
    align: "center", margin: 0,
  });

  // ── Separator ──
  slide.addShape(pres.shapes.LINE, {
    x: x + 0.15, y: cardY + 1.85, w: cardW - 0.3, h: 0,
    line: { color: BORDER, width: 0.75 },
  });

  // ── Bullet items ──
  const bulletTexts = m.items.map((item, j) => ({
    text: item,
    options: {
      bullet: { code: "2022", color: m.color },
      breakLine: j < m.items.length - 1,
      fontSize: 9.5,
      fontFace: "Malgun Gothic",
      color: TEXT_SEC,
      paraSpaceBefore: 6,
      paraSpaceAfter: 4,
    },
  }));

  slide.addText(bulletTexts, {
    x: x + 0.1, y: cardY + 1.95, w: cardW - 0.2, h: cardH - 2.1,
    valign: "top",
    margin: [0, 4, 0, 4],
  });
});

// ── Bottom bar ──
slide.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 7.05, w: 13.34, h: 0.45,
  fill: { color: "0F172A" },
  line: { width: 0 },
  shadow: { type: "outer", color: "000000", blur: 4, offset: 2, angle: 270, opacity: 0.1 },
});
slide.addText("SK networks Family AI Camp 21기  |  최종 프로젝트 3팀  |  WorkFlow Agent (듀듀)", {
  x: 0, y: 7.05, w: 13.34, h: 0.45,
  fontSize: 11, fontFace: "Malgun Gothic",
  color: "94A3B8", align: "center", valign: "middle", margin: 0,
});

// Save
pres.writeFile({ fileName: "scripts/role_slide_standalone.pptx" })
  .then(() => console.log("role_slide_standalone.pptx created!"))
  .catch(err => console.error(err));
