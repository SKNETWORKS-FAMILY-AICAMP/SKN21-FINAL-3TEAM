const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "3TEAM";
pres.title = "WorkFlow Agent - DUDE";

// Color palette (matches presentation.html)
const C = {
  primary900: "3D5164",
  primary700: "56728A",
  primary500: "6E87A0",
  primary300: "8FA3B4",
  primary100: "C8D5E2",
  primary50: "E8EEF3",
  accent700: "8B7D6E",
  accent50: "F7F3EB",
  success: "5B9A6F",
  warning: "C49A3C",
  error: "C06060",
  dark: "2C3340",
  sub: "6B7280",
  muted: "9CA3AF",
  border: "D1D5DB",
  divider: "E5E7EB",
  surface: "F4F5F7",
  white: "FFFFFF",
};

const mkShadow = () => ({ type: "outer", blur: 4, offset: 2, angle: 135, color: "000000", opacity: 0.08 });

// ========== SLIDE 1: HERO ==========
let s = pres.addSlide();
s.background = { color: C.primary900 };
s.addText("SKN21 Final Project · 3TEAM", { x: 0.5, y: 1.2, w: 9, h: 0.4, fontSize: 12, color: C.primary100, align: "center", fontFace: "Arial" });
s.addText("WorkFlow Agent", { x: 0.5, y: 1.8, w: 9, h: 1.2, fontSize: 48, bold: true, color: C.white, align: "center", fontFace: "Arial" });
s.addText("DUDE (듀드)", { x: 0.5, y: 2.9, w: 9, h: 0.8, fontSize: 36, bold: true, color: C.accent50, align: "center", fontFace: "Arial" });
s.addText("LangGraph 기반 멀티 에이전트 업무 자동화 시스템", { x: 0.5, y: 3.9, w: 9, h: 0.4, fontSize: 14, color: C.primary100, align: "center" });
s.addText("규정 판단 · 문서 생성/분석 · 일정 관리를 AI가 자연어로 처리합니다", { x: 0.5, y: 4.4, w: 9, h: 0.4, fontSize: 11, color: C.primary300, align: "center" });

// ========== SLIDE 2: 문제 정의 ==========
s = pres.addSlide();
s.background = { color: C.surface };
s.addText("01", { x: 0.5, y: 0.3, w: 0.5, h: 0.3, fontSize: 10, bold: true, color: C.primary700, align: "center" });
s.addText("왜 필요한가?", { x: 0.5, y: 0.7, w: 9, h: 0.6, fontSize: 32, bold: true, color: C.primary900, align: "center", fontFace: "Arial" });

const problems = [
  { pct: "68%", title: "집중 시간 부족", desc: "핵심 업무에 집중할 시간이 부족", color: C.error },
  { pct: "62%", title: "정보 검색 낭비", desc: "사내 문서와 규정 검색에 과도한 시간", color: C.warning },
  { pct: "57%", title: "커뮤니케이션 부담", desc: "반복적 소통 업무에 시간 소요", color: C.primary700 },
];
problems.forEach((p, i) => {
  const x = 0.8 + i * 3;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.8, w: 2.8, h: 2.8, fill: { color: C.white }, shadow: mkShadow(), rectRadius: 0.15 });
  s.addText(p.pct, { x, y: 2.0, w: 2.8, h: 0.8, fontSize: 28, bold: true, color: p.color, align: "center", fontFace: "Arial" });
  s.addText(p.title, { x, y: 2.8, w: 2.8, h: 0.4, fontSize: 14, bold: true, color: C.primary900, align: "center" });
  s.addText(p.desc, { x, y: 3.3, w: 2.8, h: 0.4, fontSize: 10, color: C.sub, align: "center" });
});

// ========== SLIDE 3: 솔루션 & 핵심 효과 ==========
s = pres.addSlide();
s.background = { color: C.white };
s.addText("02", { x: 0.5, y: 0.3, w: 0.5, h: 0.3, fontSize: 10, bold: true, color: C.success });
s.addText("DUDE가 해결합니다", { x: 0.5, y: 0.6, w: 9, h: 0.6, fontSize: 28, bold: true, color: C.primary900, align: "center" });
s.addText("자연어 한 마디로 규정 확인, 문서 생성, 일정 등록까지", { x: 0.5, y: 1.1, w: 9, h: 0.3, fontSize: 11, color: C.sub, align: "center" });

// Compact solution pills
const sols = [
  { name: "규정 판단", desc: "RAG + 4중 보조장치", color: C.primary700 },
  { name: "문서", desc: "생성/요약/검색/QA", color: C.accent700 },
  { name: "일정", desc: "Google 5종 연동", color: C.success },
];
sols.forEach((sol, i) => {
  const x = 1.2 + i * 2.8;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.6, w: 2.4, h: 0.45, fill: { color: C.surface }, line: { color: C.divider, width: 0.5 }, rectRadius: 0.2 });
  s.addText(sol.name + "  " + sol.desc, { x, y: 1.6, w: 2.4, h: 0.45, fontSize: 10, color: C.primary900, align: "center", margin: 0 });
});

// Effects - left
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 2.4, w: 4.3, h: 2.8, fill: { color: C.surface }, line: { color: C.divider, width: 0.5 }, rectRadius: 0.1 });
s.addText("핵심 효과", { x: 0.7, y: 2.5, w: 3, h: 0.4, fontSize: 14, bold: true, color: C.primary900 });
const effects = ["업무 시간 절감 — 규정 확인 30분→10초, 문서 작성 2시간→5분", "판단 정확도 향상 — RAG 4중 보조장치 + 신뢰도 점수", "복합 업무 자동 분해 — Task Planner 단계별 자동 실행", "sLLM 독립 운영 — Kanana-1.5-8B + LoRA 자체 서빙"];
s.addText(effects.map((e, i) => ({ text: e, options: { bullet: true, breakLine: i < effects.length - 1, fontSize: 9, color: C.sub } })), { x: 0.7, y: 3.0, w: 3.9, h: 2.0 });

// Effects - right
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.2, y: 2.4, w: 4.3, h: 2.8, fill: { color: C.surface }, line: { color: C.divider, width: 0.5 }, rectRadius: 0.1 });
s.addText("기대 효과", { x: 5.4, y: 2.5, w: 3, h: 0.4, fontSize: 14, bold: true, color: C.primary900 });
const expected = ["컴플라이언스 리스크 감소 — 규정 기반 판단 자동화", "조직 지식 자산화 — 사내 문서 벡터 DB 축적", "Google Workspace 통합 — 단일 OAuth", "확장 가능한 Agent 아키텍처 — LangGraph + LoRA 핫스왑"];
s.addText(expected.map((e, i) => ({ text: e, options: { bullet: true, breakLine: i < expected.length - 1, fontSize: 9, color: C.sub } })), { x: 5.4, y: 3.0, w: 3.9, h: 2.0 });

// ========== SLIDE 4: 팀 구성 ==========
s = pres.addSlide();
s.background = { color: C.surface };
s.addText("03", { x: 0.5, y: 0.3, w: 0.5, h: 0.3, fontSize: 10, bold: true, color: C.primary700 });
s.addText("팀 구성 및 역할 분담", { x: 0.5, y: 0.6, w: 9, h: 0.6, fontSize: 28, bold: true, color: C.primary900, align: "center" });
s.addText("멘토: 최민수", { x: 0.5, y: 1.1, w: 9, h: 0.3, fontSize: 10, color: C.muted, align: "center" });

const team = [
  { name: "신지용", role: "PM", desc: "프로젝트 관리 + 의도 분류 +\n오케스트레이터\n+ 문서 Agent", color: C.primary700, img: "assets/avatar-jiyong.png" },
  { name: "문지영", role: "FE / AI", desc: "React UI + SSE 실시간 채팅\n+ Intent 멀티라벨 분류 +\nPlanner LoRA 파인튜닝", color: C.success, img: "assets/avatar-jiyoung.png" },
  { name: "안혜빈", role: "BE", desc: "FastAPI + DB + 인증 +\nGoogle API 연동\n+ 멀티 Agent 기능 강화", color: C.warning, img: "assets/avatar-hyebin.png" },
  { name: "윤경은", role: "AI", desc: "판단 Agent + RAG\n+ LoRA 파인튜닝\n+ 팀스페이스 기능", color: C.accent700, img: "assets/avatar-gyeongeun.png" },
];
team.forEach((t, i) => {
  const x = 0.5 + i * 2.4;
  // Avatar
  try { s.addImage({ path: t.img, x: x + 0.6, y: 1.6, w: 1.1, h: 1.1, rounding: true }); } catch(e) {}
  // Name bar
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 2.9, w: 2.1, h: 0.4, fill: { color: C.primary700 }, rectRadius: 0.05 });
  s.addText(t.name, { x, y: 2.9, w: 2.1, h: 0.4, fontSize: 12, bold: true, color: C.white, align: "center", margin: 0 });
  // Role
  s.addText(t.role, { x, y: 3.4, w: 2.1, h: 0.3, fontSize: 11, bold: true, color: C.primary900, align: "center" });
  // Desc
  s.addText(t.desc, { x, y: 3.8, w: 2.1, h: 1.0, fontSize: 8, color: C.sub, align: "center" });
  // Bottom line
  s.addShape(pres.shapes.LINE, { x, y: 4.9, w: 2.1, h: 0, line: { color: C.primary700, width: 2 } });
});

// ========== SLIDE 5: 기술 스택 ==========
s = pres.addSlide();
s.background = { color: C.white };
s.addText("04", { x: 0.5, y: 0.3, w: 0.5, h: 0.3, fontSize: 10, bold: true, color: C.primary700 });
s.addText("기술 스택", { x: 0.5, y: 0.6, w: 9, h: 0.6, fontSize: 28, bold: true, color: C.primary900, align: "center" });

const stacks = [
  { title: "AI / ML", color: C.primary700, items: ["LangGraph", "Kanana-1.5-8B + LoRA", "vLLM (RunPod A100)", "KoELECTRA (Intent)", "Qdrant + BM25 + BGE Reranker"] },
  { title: "Backend", color: C.accent700, items: ["FastAPI + SSE", "PostgreSQL 16 (RDS)", "SQLAlchemy + Alembic", "JWT + Google OAuth 2.0"] },
  { title: "Frontend", color: C.success, items: ["React 18 (Vite)", "Zustand + TanStack Query", "Tailwind + shadcn/ui", "FullCalendar"] },
  { title: "Infra", color: C.warning, items: ["AWS EC2 + RDS", "Docker Compose", "GitHub Actions CI/CD", "RunPod A100 + Qdrant Cloud"] },
];
stacks.forEach((st, i) => {
  const x = 0.4 + i * 2.4;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.5, w: 2.2, h: 3.5, fill: { color: C.surface }, shadow: mkShadow(), rectRadius: 0.1 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.3, y: 1.7, w: 0.5, h: 0.5, fill: { color: st.color }, rectRadius: 0.08 });
  s.addText(st.title, { x, y: 2.4, w: 2.2, h: 0.35, fontSize: 13, bold: true, color: C.primary900, align: "left", margin: [0, 0, 0, 10] });
  s.addText(st.items.map((item, j) => ({ text: item, options: { bullet: true, breakLine: j < st.items.length - 1, fontSize: 9, color: C.sub } })), { x: x + 0.15, y: 2.8, w: 1.9, h: 2.0 });
});

// ========== SLIDE 6: 아키텍처 ==========
s = pres.addSlide();
s.background = { color: C.white };
s.addText("05", { x: 0.5, y: 0.2, w: 0.5, h: 0.3, fontSize: 10, bold: true, color: C.primary700 });
s.addText("전체 시스템 아키텍처", { x: 0.5, y: 0.4, w: 9, h: 0.5, fontSize: 24, bold: true, color: C.primary900, align: "center" });

// Ingress
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1.5, y: 1.0, w: 7, h: 0.6, fill: { color: C.surface }, line: { color: C.divider, width: 0.5 }, rectRadius: 0.08 });
s.addText("User Query  →  React  →  FastAPI", { x: 1.5, y: 1.0, w: 7, h: 0.6, fontSize: 11, color: C.primary900, align: "center", margin: 0 });

// Arrow
s.addText("↓", { x: 4.5, y: 1.6, w: 1, h: 0.3, fontSize: 14, color: C.muted, align: "center" });

// AI Core box
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1, y: 1.9, w: 8, h: 2.2, fill: { color: C.primary50 }, line: { color: C.primary100, width: 0.5 }, rectRadius: 0.1 });
s.addText("AI CORE (LangGraph)", { x: 1, y: 1.95, w: 8, h: 0.3, fontSize: 9, color: C.primary500, align: "center" });

// Intent → Planner → Orchestrator
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1.5, y: 2.3, w: 2, h: 0.6, fill: { color: C.white }, line: { color: C.primary100, width: 0.5 }, rectRadius: 0.05 });
s.addText("Intent Classifier\nroberta-large · 93.3%", { x: 1.5, y: 2.3, w: 2, h: 0.6, fontSize: 8, color: C.primary900, align: "center", margin: 0 });
s.addText("→", { x: 3.55, y: 2.4, w: 0.4, h: 0.4, fontSize: 12, color: C.primary300, align: "center" });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 4, y: 2.3, w: 2, h: 0.6, fill: { color: C.white }, line: { color: C.primary100, width: 0.5 }, rectRadius: 0.05 });
s.addText("Task Planner\nKanana LoRA · 87.0%", { x: 4, y: 2.3, w: 2, h: 0.6, fontSize: 8, color: C.primary900, align: "center", margin: 0 });
s.addText("→", { x: 6.05, y: 2.4, w: 0.4, h: 0.4, fontSize: 12, color: C.primary300, align: "center" });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.5, y: 2.3, w: 2, h: 0.6, fill: { color: C.primary700 }, rectRadius: 0.05 });
s.addText("Orchestrator\n조건부 라우팅", { x: 6.5, y: 2.3, w: 2, h: 0.6, fontSize: 8, color: C.white, align: "center", margin: 0 });

// 4 Agents
const agents = [
  { name: "Judgment", desc: "4중 보조장치 + 신뢰도", color: C.primary700 },
  { name: "Document", desc: "생성/요약/검색/QA", color: C.accent700 },
  { name: "Schedule", desc: "Google 5종 연동", color: C.success },
  { name: "General", desc: "대화/인사", color: C.muted },
];
agents.forEach((a, i) => {
  const x = 1.3 + i * 1.9;
  s.addShape(pres.shapes.RECTANGLE, { x, y: 3.2, w: 1.7, h: 0.7, fill: { color: C.white }, line: { color: C.divider, width: 0.5 } });
  s.addShape(pres.shapes.RECTANGLE, { x, y: 3.2, w: 0.04, h: 0.7, fill: { color: a.color } });
  s.addText(a.name, { x: x + 0.1, y: 3.22, w: 1.5, h: 0.3, fontSize: 9, bold: true, color: a.color, margin: 0 });
  s.addText(a.desc, { x: x + 0.1, y: 3.5, w: 1.5, h: 0.25, fontSize: 7, color: C.muted, margin: 0 });
});

// Arrow
s.addText("↓", { x: 4.5, y: 4.1, w: 1, h: 0.3, fontSize: 14, color: C.muted, align: "center" });

// Infrastructure
const infra = ["PostgreSQL\nRDS · 17 tables", "Qdrant Cloud\nVector + BM25", "vLLM\nRunPod A100 · LoRA", "Google APIs\nCalendar/Tasks/Gmail/Sheets"];
infra.forEach((inf, i) => {
  const x = 1.3 + i * 1.9;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 4.4, w: 1.7, h: 0.6, fill: { color: C.accent50 }, line: { color: C.divider, width: 0.5 }, rectRadius: 0.05 });
  s.addText(inf, { x, y: 4.4, w: 1.7, h: 0.6, fontSize: 7, color: C.accent700, align: "center", margin: 0 });
});

// SSE
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1.5, y: 5.1, w: 7, h: 0.4, fill: { color: C.surface }, line: { color: C.divider, width: 0.5 }, rectRadius: 0.08 });
s.addText("SSE Streaming Response · E2E 2~4s", { x: 1.5, y: 5.1, w: 7, h: 0.4, fontSize: 10, color: C.primary900, align: "center", margin: 0 });

// ========== SLIDE 7: Agent 구조 ==========
s = pres.addSlide();
s.background = { color: C.surface };
s.addText("06", { x: 0.5, y: 0.2, w: 0.5, h: 0.3, fontSize: 10, bold: true, color: C.primary700 });
s.addText("Agent 구조", { x: 0.5, y: 0.5, w: 9, h: 0.5, fontSize: 24, bold: true, color: C.primary900, align: "center" });

const agentDetails = [
  { name: "Judgment AGENT", desc: "사내규정 기반\nyes/no/conditional 판단\n+ 근거 조항 + 대안", flow: ["사용자 질의", "↓", "RAG (top-k)", "↓", "sLLM 판단 (LoRA v1)", "↓", "4중 보조장치 + confidence", "↓", "응답"], color: C.primary700 },
  { name: "Document AGENT", desc: "문서 생성/요약/검색/QA\n4가지 오퍼레이션", flow: ["사용자 질의", "↓", "서브타입 판단", "↓", "sLLM ← LoRA 라우팅", "↓", "응답"], color: C.accent700 },
  { name: "Schedule AGENT", desc: "자연어 → 일정 등록/조회\n+ Google 5종 연동", flow: ["사용자 질의", "↓", "LLM 자연어 파싱", "↓", "Google API 호출", "↓", "결과 반환"], color: C.success },
];
agentDetails.forEach((ag, i) => {
  const x = 0.3 + i * 3.3;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.2, w: 3, h: 4.0, fill: { color: C.white }, line: { color: C.divider, width: 0.5 }, shadow: mkShadow(), rectRadius: 0.1 });
  s.addText(ag.name, { x, y: 1.4, w: 3, h: 0.35, fontSize: 13, bold: true, color: C.primary900, align: "center", margin: 0 });
  s.addText(ag.desc, { x, y: 1.8, w: 3, h: 0.6, fontSize: 8, color: C.sub, align: "center" });
  ag.flow.forEach((step, j) => {
    const isArrow = step === "↓";
    const yPos = 2.5 + j * 0.2;
    if (!isArrow) {
      const isFirst = j === 0;
      const isLast = j === ag.flow.length - 1;
      const bgColor = (isFirst || isLast) ? ag.color : C.surface;
      const txtColor = (isFirst || isLast) ? C.white : C.sub;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.3, y: yPos - 0.02, w: 2.4, h: 0.22, fill: { color: bgColor }, rectRadius: 0.03 });
      s.addText(step, { x: x + 0.3, y: yPos - 0.02, w: 2.4, h: 0.22, fontSize: 7, color: txtColor, align: "center", margin: 0 });
    } else {
      s.addText("↓", { x: x + 0.3, y: yPos - 0.05, w: 2.4, h: 0.2, fontSize: 8, color: C.muted, align: "center" });
    }
  });
});

s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 5.35, w: 9, h: 0.3, fill: { color: C.primary700 }, rectRadius: 0.05 });
s.addText("Planner Agent: 3개 Agent를 하나의 LangGraph 오케스트레이터로 융합", { x: 0.5, y: 5.35, w: 9, h: 0.3, fontSize: 9, color: C.white, align: "center", margin: 0 });

// ========== SLIDE 8: 데이터셋 현황 ==========
s = pres.addSlide();
s.background = { color: C.white };
s.addText("07", { x: 0.5, y: 0.2, w: 0.5, h: 0.3, fontSize: 10, bold: true, color: C.primary700 });
s.addText("데이터셋 현황", { x: 0.5, y: 0.5, w: 9, h: 0.5, fontSize: 24, bold: true, color: C.primary900, align: "center" });

// Bar chart
s.addChart(pres.charts.BAR, [
  { name: "train", labels: ["Intent 분류", "Planner", "판단", "문서 요약", "문서 생성"], values: [3954, 1471, 3468, 900, 1350] },
  { name: "eval", labels: ["Intent 분류", "Planner", "판단", "문서 요약", "문서 생성"], values: [610, 150, 328, 100, 150] },
], {
  x: 0.3, y: 1.2, w: 5, h: 3.5, barDir: "col",
  chartColors: [C.primary300, C.error],
  chartArea: { fill: { color: C.white }, roundedCorners: true },
  catAxisLabelColor: C.sub, valAxisLabelColor: C.sub,
  valGridLine: { color: C.divider, size: 0.5 }, catGridLine: { style: "none" },
  showValue: true, dataLabelPosition: "outEnd", dataLabelColor: C.dark, dataLabelFontSize: 7,
  showLegend: true, legendPos: "t",
});

// Table
s.addText("전체 데이터 현황", { x: 5.5, y: 1.2, w: 4.2, h: 0.35, fontSize: 12, bold: true, color: C.primary900 });
const dataRows = [
  [{ text: "구분", options: { fill: { color: C.primary700 }, color: C.white, bold: true, fontSize: 9 } }, { text: "출처", options: { fill: { color: C.primary700 }, color: C.white, bold: true, fontSize: 9 } }],
  [{ text: "Intent 분류", options: { fontSize: 8 } }, { text: "자체 제작 + Adversarial 463", options: { fontSize: 8 } }],
  [{ text: "Planner", options: { fontSize: 8 } }, { text: "자체 제작 + GPT 증강", options: { fontSize: 8 } }],
  [{ text: "판단 LoRA", options: { fontSize: 8 } }, { text: "수동 제작(Excel) + 규정DB", options: { fontSize: 8 } }],
  [{ text: "문서요약 LoRA", options: { fontSize: 8 } }, { text: "AI Hub SN 582 + GPT 증강", options: { fontSize: 8 } }],
  [{ text: "문서생성 LoRA", options: { fontSize: 8 } }, { text: "AI Hub + 합성(회의록/보고서/제안서)", options: { fontSize: 8 } }],
];
s.addTable(dataRows, { x: 5.5, y: 1.6, w: 4.2, colW: [1.4, 2.8], border: { pt: 0.5, color: C.divider } });

// ========== SLIDE 9: 성능 평가 ==========
s = pres.addSlide();
s.background = { color: C.white };
s.addText("성능 평가", { x: 0.5, y: 0.3, w: 9, h: 0.5, fontSize: 24, bold: true, color: C.primary900, align: "center" });

// Key metrics
const metrics = [
  { val: "97.9%", label: "Intent Test F1", sub: "KoELECTRA · 7.9ms", color: C.primary700 },
  { val: "85.4%", label: "Judgment 정확도", sub: "LoRA v3 · JSON 97.6%", color: C.accent700 },
  { val: "0.926", label: "Doc Gen BERTScore", sub: "LoRA v3", color: C.success },
  { val: "0.952", label: "RAG MRR", sub: "Hybrid+Reranker+HyDE", color: C.warning },
];
metrics.forEach((m, i) => {
  const x = 0.4 + i * 2.4;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.0, w: 2.2, h: 1.2, fill: { color: C.surface }, shadow: mkShadow(), rectRadius: 0.1 });
  s.addText(m.val, { x, y: 1.05, w: 2.2, h: 0.5, fontSize: 22, bold: true, color: m.color, align: "center", fontFace: "Arial", margin: 0 });
  s.addText(m.label, { x, y: 1.5, w: 2.2, h: 0.3, fontSize: 9, color: C.sub, align: "center", margin: 0 });
  s.addText(m.sub, { x, y: 1.75, w: 2.2, h: 0.2, fontSize: 7, color: C.muted, align: "center", margin: 0 });
});

// Base vs LoRA table
s.addText("Kanana Base vs LoRA 파인튜닝", { x: 0.5, y: 2.5, w: 4.5, h: 0.35, fontSize: 12, bold: true, color: C.primary900 });
const compRows = [
  [{ text: "항목", options: { fill: { color: C.primary700 }, color: C.white, bold: true, fontSize: 8 } }, { text: "Base", options: { fill: { color: C.primary700 }, color: C.white, bold: true, fontSize: 8 } }, { text: "LoRA", options: { fill: { color: C.primary700 }, color: C.white, bold: true, fontSize: 8 } }, { text: "개선", options: { fill: { color: C.primary700 }, color: C.white, bold: true, fontSize: 8 } }],
  [{ text: "판단 정확도", options: { fontSize: 8 } }, { text: "83.5%", options: { fontSize: 8, align: "center" } }, { text: "85.4%", options: { fontSize: 8, bold: true, align: "center" } }, { text: "+1.9%p", options: { fontSize: 8, color: C.success, align: "center" } }],
  [{ text: "요약 BERTScore", options: { fontSize: 8 } }, { text: "0.828", options: { fontSize: 8, align: "center" } }, { text: "0.859", options: { fontSize: 8, bold: true, align: "center" } }, { text: "+0.031", options: { fontSize: 8, color: C.success, align: "center" } }],
  [{ text: "생성 BERTScore", options: { fontSize: 8 } }, { text: "0.896", options: { fontSize: 8, align: "center" } }, { text: "0.926", options: { fontSize: 8, bold: true, align: "center" } }, { text: "+0.030", options: { fontSize: 8, color: C.success, align: "center" } }],
  [{ text: "생성 JSON 유효율", options: { fontSize: 8 } }, { text: "77.3%", options: { fontSize: 8, align: "center" } }, { text: "87.3%", options: { fontSize: 8, bold: true, align: "center" } }, { text: "+10%p", options: { fontSize: 8, color: C.success, align: "center" } }],
  [{ text: "생성 False Fill", options: { fontSize: 8 } }, { text: "44.3%", options: { fontSize: 8, align: "center" } }, { text: "17.9%", options: { fontSize: 8, bold: true, align: "center" } }, { text: "-26.4%p", options: { fontSize: 8, color: C.success, align: "center" } }],
];
s.addTable(compRows, { x: 0.5, y: 2.9, w: 4.5, colW: [1.3, 0.9, 0.9, 1.0], border: { pt: 0.5, color: C.divider } });

// Model summary table
s.addText("모델별 최종 성능 요약", { x: 5.3, y: 2.5, w: 4.5, h: 0.35, fontSize: 12, bold: true, color: C.primary900 });
const modelRows = [
  [{ text: "모듈", options: { fill: { color: C.primary700 }, color: C.white, bold: true, fontSize: 8 } }, { text: "지표", options: { fill: { color: C.primary700 }, color: C.white, bold: true, fontSize: 8 } }, { text: "결과", options: { fill: { color: C.primary700 }, color: C.white, bold: true, fontSize: 8 } }],
  [{ text: "Intent (KoELECTRA)", options: { fontSize: 8, color: C.primary700, bold: true } }, { text: "Test F1 / Adversarial F1", options: { fontSize: 8 } }, { text: "97.9% / 87.8%", options: { fontSize: 8, bold: true } }],
  [{ text: "Planner (Kanana)", options: { fontSize: 8, color: C.primary700, bold: true } }, { text: "Held-out 정확도", options: { fontSize: 8 } }, { text: "87.0%", options: { fontSize: 8, bold: true } }],
  [{ text: "Judgment (LoRA v3)", options: { fontSize: 8, color: C.accent700, bold: true } }, { text: "정확도 / JSON 유효", options: { fontSize: 8 } }, { text: "85.4% / 97.6%", options: { fontSize: 8, bold: true } }],
  [{ text: "Doc Summary (v3)", options: { fontSize: 8, color: C.accent700, bold: true } }, { text: "BERTScore / 포맷", options: { fontSize: 8 } }, { text: "0.859 / 100%", options: { fontSize: 8, bold: true } }],
  [{ text: "Doc Generate (v3)", options: { fontSize: 8, color: C.accent700, bold: true } }, { text: "BERTScore / JSON", options: { fontSize: 8 } }, { text: "0.926 / 87.3%", options: { fontSize: 8, bold: true } }],
  [{ text: "RAG 검색", options: { fontSize: 8, color: C.success, bold: true } }, { text: "MRR / Hit Rate", options: { fontSize: 8 } }, { text: "0.952 / 95.2%", options: { fontSize: 8, bold: true } }],
];
s.addTable(modelRows, { x: 5.3, y: 2.9, w: 4.5, colW: [1.6, 1.5, 1.4], border: { pt: 0.5, color: C.divider } });

// ========== SLIDE 10: Q&A ==========
s = pres.addSlide();
s.background = { color: C.primary900 };
s.addText("WorkFlow Agent — DUDE", { x: 0.5, y: 1.2, w: 9, h: 0.4, fontSize: 12, color: C.primary100, align: "center" });
s.addText("Q & A", { x: 0.5, y: 2.0, w: 9, h: 1.5, fontSize: 60, bold: true, color: C.white, align: "center", fontFace: "Arial" });
s.addText("감사합니다", { x: 0.5, y: 3.5, w: 9, h: 0.5, fontSize: 16, color: C.primary100, align: "center" });
s.addText("SKN21 Final Project · 3TEAM", { x: 0.5, y: 4.2, w: 9, h: 0.3, fontSize: 10, color: C.primary300, align: "center" });

// Save
pres.writeFile({ fileName: "/Users/moonjiyoung/Desktop/SKN21-FINAL-3TEAM/DUDE_Presentation.pptx" })
  .then(() => console.log("PPTX created successfully!"))
  .catch(err => console.error(err));
