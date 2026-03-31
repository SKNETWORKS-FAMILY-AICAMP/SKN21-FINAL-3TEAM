const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10" × 5.625"
pres.author = "3TEAM";
pres.title = "WorkFlow Agent DUDE";

// === Color Palette ===
const C = {
  pri900: "3D5164", pri700: "56728A", pri500: "6E87A0", pri300: "8FA3B4", pri100: "C8D5E2", pri50: "E8EEF3",
  acc700: "8B7D6E", acc500: "A89580", acc300: "C4B49A", acc100: "EDE5D0", acc50: "F7F3EB",
  sfcMain: "F4F5F7", sfcSub: "EBEDF0", sfcCard: "FFFFFF",
  success: "5B9A6F", successBg: "E8F4EC",
  warning: "C49A3C", warningBg: "F5EDD0",
  error: "C06060", errorBg: "F5E0E0",
  white: "FFFFFF", black: "2C3340", sub: "6B7280", muted: "9CA3AF", border: "D1D5DB", divider: "E5E7EB",
};

const FT = "Arial Black";
const FB = "Arial";

function addCard(s, x, y, w, h, fill, border) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, rectRadius: 0.08, line: border ? { color: border, width: 0.5 } : undefined });
}
function addTag(s, x, y, text, bg, tc) {
  addCard(s, x, y, 0.6, 0.28, bg);
  s.addText(text, { x, y, w: 0.6, h: 0.28, fontSize: 9, fontFace: FB, color: tc, align: "center", valign: "middle", margin: 0 });
}

// ========== 1. HERO ==========
{
  const s = pres.addSlide(); s.background = { color: C.pri900 };
  addCard(s, 3.2, 0.8, 3.6, 0.35, "FFFFFF");
  s.addText("SKN21 Final Project · 3TEAM", { x: 3.2, y: 0.8, w: 3.6, h: 0.35, fontSize: 11, fontFace: FB, color: C.pri900, align: "center", valign: "middle", margin: 0 });
  s.addText([
    { text: "WorkFlow Agent", options: { breakLine: true, fontSize: 40, bold: true, color: C.white } },
    { text: "DUDE", options: { fontSize: 40, bold: true, color: C.acc300 } },
  ], { x: 1, y: 1.5, w: 8, h: 1.8, fontFace: FT, align: "center", valign: "middle" });
  s.addText("LangGraph 기반 멀티 에이전트 업무 자동화 시스템", { x: 1.5, y: 3.4, w: 7, h: 0.4, fontSize: 16, fontFace: FB, color: C.pri100, align: "center" });
  s.addText("규정 판단 · 문서 생성/분석 · 일정 관리를 AI가 자연어로 처리합니다", { x: 1.5, y: 3.9, w: 7, h: 0.4, fontSize: 12, fontFace: FB, color: C.pri300, align: "center" });
}

// ========== 2. TOC ==========
{
  const s = pres.addSlide(); s.background = { color: C.white };
  s.addText("목차", { x: 0, y: 0.3, w: 10, h: 0.6, fontSize: 32, fontFace: FT, color: C.pri900, align: "center", bold: true });
  s.addText("Contents", { x: 0, y: 0.85, w: 10, h: 0.3, fontSize: 11, fontFace: FB, color: C.muted, align: "center" });
  function drawToc(items, sx) {
    let y = 1.4;
    for (const [cat, entries] of items) {
      s.addText(cat, { x: sx, y, w: 4, h: 0.25, fontSize: 8, fontFace: FB, color: C.pri500, bold: true, charSpacing: 2 });
      s.addShape(pres.shapes.LINE, { x: sx, y: y + 0.25, w: 3.8, h: 0, line: { color: C.pri100, width: 0.5 } });
      y += 0.4;
      for (const [n, t] of entries) {
        s.addText(n, { x: sx, y, w: 0.5, h: 0.35, fontSize: 18, fontFace: FT, color: C.pri300, align: "right", bold: true, margin: 0 });
        s.addText(t, { x: sx + 0.65, y, w: 3.3, h: 0.35, fontSize: 13, fontFace: FB, color: C.black, valign: "middle", margin: 0 });
        y += 0.4;
      }
      y += 0.15;
    }
  }
  drawToc([["OVERVIEW",[["01","개요"]]],["ARCHITECTURE",[["02","전체 시스템 아키텍처"],["03","Agent 구조와 역할"]]],["AI / DATA",[["04","데이터셋 구축 및 전처리"],["05","RAG Pipeline 최적화"],["06","LLM 파인튜닝 전략 및 수행"]]]], 0.8);
  drawToc([["ENGINEERING",[["07","트러블슈팅"]]],["RESULT",[["08","성능 평가"],["09","데모 시나리오"],["10","한계점 및 향후 발전 방향"]]],["CLOSING",[["11","팀 회고 및 Q&A"]]]], 5.2);
}

// ========== 3. PROBLEM ==========
{
  const s = pres.addSlide(); s.background = { color: C.sfcMain };
  addTag(s, 4.7, 0.3, "01", C.errorBg, C.error);
  s.addText("Why?", { x: 0, y: 0.7, w: 10, h: 0.6, fontSize: 32, fontFace: FT, color: C.pri900, align: "center", bold: true });
  [{ p:"68%",t:"집중 시간 부족",d:"핵심 업무에 집중할 시간이 부족",c:C.error },
   { p:"62%",t:"정보 검색 낭비",d:"사내 문서와 규정 검색에 과도한 시간",c:C.warning },
   { p:"57%",t:"커뮤니케이션 부담",d:"반복적 소통 업무에 시간 소요",c:C.pri700 }
  ].forEach((v,i) => {
    const x = 1.2+i*2.8;
    addCard(s, x, 1.6, 2.4, 2.8, C.white, C.divider);
    s.addShape(pres.shapes.OVAL, { x:x+0.6,y:1.85,w:1.2,h:1.2, fill:{color:v.c,transparency:85}, line:{color:v.c,width:2,transparency:60} });
    s.addText(v.p, { x:x+0.6,y:1.85,w:1.2,h:1.2, fontSize:20, fontFace:FT, color:v.c, align:"center", valign:"middle", bold:true, margin:0 });
    s.addText(v.t, { x:x+0.1,y:3.2,w:2.2,h:0.35, fontSize:14, fontFace:FB, color:C.pri900, align:"center", bold:true });
    s.addText(v.d, { x:x+0.1,y:3.55,w:2.2,h:0.5, fontSize:10, fontFace:FB, color:C.sub, align:"center" });
  });
}

// ========== 4. SOLUTION ==========
{
  const s = pres.addSlide(); s.background = { color: C.white };
  addTag(s, 4.7, 0.2, "02", C.successBg, C.success);
  s.addText("DUDE가 처리합니다", { x:0,y:0.55,w:10,h:0.5, fontSize:28, fontFace:FT, color:C.pri900, align:"center", bold:true });
  s.addText("자연어 한 마디로 규정 확인, 문서 생성, 일정 등록까지", { x:0,y:1.0,w:10,h:0.3, fontSize:11, fontFace:FB, color:C.sub, align:"center" });
  [{ l:"규정 판단",s2:"RAG + 4중 보조장치",c:C.pri700 },{ l:"문서 생성/요약/검색/QA",s2:"LoRA 라우팅",c:C.acc700 },{ l:"일정 관리",s2:"Google 5종 연동",c:C.success }].forEach((p,i) => {
    const px = 0.8+i*3.1;
    addCard(s,px,1.45,2.7,0.55,p.c);
    s.addText([{text:p.l,options:{bold:true,fontSize:11,color:C.white,breakLine:true}},{text:p.s2,options:{fontSize:9,color:C.white}}], { x:px+0.15,y:1.45,w:2.4,h:0.55, fontFace:FB, align:"center", valign:"middle" });
  });
  [{ t:"업무 시간 절감",d:"규정 판단 30분→10초\n문서 작성 2시간→5분" },{ t:"판단 정확도 향상",d:"Base 37.2% → LoRA 85.4%\n(+48.2%p)" },
   { t:"복합 업무 자동 분해",d:"Intent 91.0% → Planner 87.0%\n멀티스텝 순차 실행" },{ t:"sLLM 독립 운영",d:"외부 API 의존 없이\n온프레미스 서빙" }
  ].forEach((e,i) => {
    const ex = 0.5+(i%2)*4.6, ey = 2.25+Math.floor(i/2)*1.55;
    addCard(s,ex,ey,4.3,1.35,C.sfcMain,C.divider);
    s.addText(e.t, { x:ex+0.2,y:ey+0.15,w:3.9,h:0.3, fontSize:13, fontFace:FB, color:C.pri900, bold:true, margin:0 });
    s.addText(e.d, { x:ex+0.2,y:ey+0.5,w:3.9,h:0.7, fontSize:10, fontFace:FB, color:C.sub, margin:0 });
  });
}

// ========== 5. WHY sLLM ==========
{
  const s = pres.addSlide(); s.background = { color: C.sfcMain };
  addTag(s, 4.7, 0.2, "03", C.pri50, C.pri700);
  s.addText("왜 온프레미스 sLLM인가?", { x:0,y:0.55,w:10,h:0.5, fontSize:28, fontFace:FT, color:C.pri900, align:"center", bold:true });
  s.addText("GPT/Claude API 대신 자체 파인튜닝 모델을 운영하는 이유", { x:0,y:1.0,w:10,h:0.3, fontSize:11, fontFace:FB, color:C.sub, align:"center" });
  [{t:"보안",d:"데이터 외부 전송 X\n컴플라이언스 충족",c:C.error},{t:"비용",d:"무제한 추론\n비용 절감 극대화",c:C.success},{t:"도메인 특화",d:"LoRA 파인튜닝\n정밀 최적화 + 정확도 향상",c:C.pri700}].forEach((r,i) => {
    const rx = 0.7+i*3.1;
    addCard(s,rx,1.5,2.7,1.6,C.white,C.divider);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:rx+0.85,y:1.7,w:1.0,h:0.7, fill:{color:r.c,transparency:85}, rectRadius:0.1 });
    s.addText(r.t, { x:rx+0.1,y:2.5,w:2.5,h:0.3, fontSize:14, fontFace:FB, color:C.pri900, align:"center", bold:true });
    s.addText(r.d, { x:rx+0.1,y:2.8,w:2.5,h:0.5, fontSize:10, fontFace:FB, color:C.sub, align:"center" });
  });
  addCard(s, 0.7, 3.35, 8.6, 0.5, C.pri700);
  s.addText("Kanana-1.5-8B  ·  4종 LoRA 어댑터 (판단/생성/요약/플래너)  ·  vLLM A100 핫스왑  ·  80~120 tok/s", { x:0.7,y:3.35,w:8.6,h:0.5, fontSize:11, fontFace:FB, color:C.white, align:"center", valign:"middle" });
  [{v:"80~120",u:"tok/s"},{v:"~100ms",u:"LoRA 핫스왑"},{v:"4-bit",u:"QLoRA"},{v:"6~10초",u:"E2E 응답"}].forEach((m,i) => {
    const mx = 0.7+i*2.15;
    addCard(s,mx,4.05,2.0,0.8,C.white,C.divider);
    s.addText(m.v, { x:mx,y:4.1,w:2.0,h:0.4, fontSize:16, fontFace:FT, color:C.pri700, align:"center", bold:true, margin:0 });
    s.addText(m.u, { x:mx,y:4.5,w:2.0,h:0.25, fontSize:9, fontFace:FB, color:C.sub, align:"center", margin:0 });
  });
}

// ========== 6. TEAM ==========
{
  const s = pres.addSlide(); s.background = { color: C.sfcMain };
  addTag(s, 4.7, 0.2, "04", C.pri50, C.pri700);
  s.addText("팀 구성 및 역할 분담", { x:0,y:0.55,w:10,h:0.5, fontSize:28, fontFace:FT, color:C.pri900, align:"center", bold:true });
  s.addText("멘토: 최민수", { x:0,y:1.0,w:10,h:0.25, fontSize:10, fontFace:FB, color:C.muted, align:"center" });
  [{n:"신지용",r:"PM",d:"프로젝트 관리 +\n의도 분류 +\n오케스트레이터\n+ 문서 Agent"},{n:"문지영",r:"FE / AI",d:"React UI +\nSSE 실시간 채팅 +\nIntent 멀티라벨 분류 +\nPlanner LoRA 파인튜닝"},{n:"안혜빈",r:"BE",d:"FastAPI + DB +\nGoogle API 연동"},{n:"윤경은",r:"AI",d:"판단 Agent + RAG\n+ LoRA 파인튜닝\n+ 팀스페이스 기능"}].forEach((m,i) => {
    const mx = 0.5+i*2.35;
    s.addShape(pres.shapes.OVAL, { x:mx+0.45,y:1.5,w:1.2,h:1.2, fill:{color:C.pri100}, line:{color:C.pri300,width:1} });
    s.addText(m.n[0], { x:mx+0.45,y:1.5,w:1.2,h:1.2, fontSize:24, fontFace:FT, color:C.pri700, align:"center", valign:"middle", bold:true, margin:0 });
    addCard(s,mx+0.1,2.85,1.9,0.35,C.pri700);
    s.addText(m.n, { x:mx+0.1,y:2.85,w:1.9,h:0.35, fontSize:12, fontFace:FB, color:C.white, align:"center", valign:"middle", bold:true, margin:0 });
    s.addText(m.r, { x:mx+0.1,y:3.3,w:1.9,h:0.3, fontSize:12, fontFace:FB, color:C.pri900, align:"center", bold:true, margin:0 });
    s.addShape(pres.shapes.LINE, { x:mx+0.7,y:3.65,w:0.7,h:0, line:{color:C.pri300,width:0.5} });
    s.addText(m.d, { x:mx+0.05,y:3.75,w:2.0,h:1.2, fontSize:10, fontFace:FB, color:C.sub, align:"center", valign:"top" });
    s.addShape(pres.shapes.LINE, { x:mx+0.1,y:5.1,w:1.9,h:0, line:{color:C.pri700,width:2} });
  });
}

// ========== 7. TECH STACK ==========
{
  const s = pres.addSlide(); s.background = { color: C.white };
  addTag(s, 4.7, 0.2, "06", C.pri50, C.pri700);
  s.addText("기술 스택", { x:0,y:0.55,w:10,h:0.5, fontSize:28, fontFace:FT, color:C.pri900, align:"center", bold:true });
  [{t:"AI / ML",items:["LangGraph","Kanana-1.5-8B + LoRA","vLLM (RunPod A100)","roberta-large (Intent)","Qdrant + BM25 + Reranker"],c:C.pri700},
   {t:"Backend",items:["FastAPI + SSE","PostgreSQL 16 (RDS)","SQLAlchemy + Alembic","JWT + Google OAuth 2.0"],c:C.acc700},
   {t:"Frontend",items:["React 18 (Vite)","Zustand + TanStack Query","Tailwind + shadcn/ui","FullCalendar"],c:C.success},
   {t:"Infra",items:["AWS EC2 + RDS","Docker Compose","GitHub Actions CI/CD","RunPod A100 + Qdrant Cloud"],c:C.warning}
  ].forEach((st,i) => {
    const sx = 0.5+i*2.35;
    addCard(s,sx,1.3,2.15,3.5,C.sfcMain,C.divider);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:sx+0.65,y:1.5,w:0.85,h:0.7, fill:{color:st.c}, rectRadius:0.08 });
    s.addText(st.t, { x:sx+0.1,y:2.35,w:1.95,h:0.35, fontSize:14, fontFace:FB, color:C.pri900, bold:true, align:"center", margin:0 });
    s.addText(st.items.map((item,idx) => ({text:item, options:{bullet:true, breakLine:idx<st.items.length-1, fontSize:10, color:C.sub}})), { x:sx+0.15,y:2.8,w:1.85,h:1.8, fontFace:FB, valign:"top" });
  });
}

// ========== 8. ARCHITECTURE ==========
{
  const s = pres.addSlide(); s.background = { color: C.white };
  addTag(s, 4.55, 0.15, "07", C.pri50, C.pri700);
  s.addText("전체 시스템 아키텍처", { x:0,y:0.45,w:10,h:0.45, fontSize:26, fontFace:FT, color:C.pri900, align:"center", bold:true });
  // Left
  [{l:"User Query",s2:""},{l:"React",s2:"SSE Client"},{l:"FastAPI",s2:"JWT / OAuth"}].forEach((item,i) => {
    const iy = 1.2+i*1.15;
    addCard(s,0.3,iy,1.3,0.8,C.sfcMain,C.divider);
    s.addText(item.l, { x:0.3,y:iy+(item.s2?0.08:0.15),w:1.3,h:0.35, fontSize:11, fontFace:FB, color:C.pri900, align:"center", bold:true, margin:0 });
    if(item.s2) s.addText(item.s2, { x:0.3,y:iy+0.42,w:1.3,h:0.25, fontSize:8, fontFace:FB, color:C.muted, align:"center", margin:0 });
  });
  s.addText("→", { x:1.6,y:2.1,w:0.4,h:0.4, fontSize:18, color:C.pri300, align:"center", valign:"middle" });
  // Center
  addCard(s,2.1,1.0,5.4,3.8,C.pri50,C.pri100);
  s.addText("AI CORE — LANGGRAPH ORCHESTRATOR", { x:2.1,y:1.1,w:5.4,h:0.25, fontSize:8, fontFace:FB, color:C.pri500, align:"center", bold:true, charSpacing:2, margin:0 });
  addCard(s,2.8,1.45,4.1,0.65,C.white,C.pri100);
  s.addText("classify_intent", { x:2.8,y:1.48,w:4.1,h:0.3, fontSize:13, fontFace:FB, color:C.pri900, align:"center", bold:true, margin:0 });
  s.addText("roberta-large ONNX 멀티라벨 · 91.0% · 19ms", { x:2.8,y:1.78,w:4.1,h:0.25, fontSize:9, fontFace:FB, color:C.muted, align:"center", margin:0 });
  // Branches
  [{t:"compound",tc:C.warning,bg:"FFF8EE",bd:C.warning,items:[["decompose_query","Planner LoRA"],["compound_pending","순차 스트리밍"]]},
   {t:"단일 (conf ≥ 0.85)",tc:C.success,bg:"EEFBF0",bd:C.success,items:[["Judgment",""],["Document",""],["Schedule",""],["General",""]]},
   {t:"low conf (< 0.85)",tc:C.error,bg:"FFF0F0",bd:C.error,items:[["clarify_with_candidates","top-2 후보 제시"]]}
  ].forEach((b,i) => {
    const bx = 2.3+i*1.75;
    addCard(s,bx,2.3,1.55,1.8,b.bg,b.bd);
    s.addText(b.t, { x:bx,y:2.35,w:1.55,h:0.25, fontSize:9, fontFace:FB, color:b.tc, align:"center", bold:true, margin:0 });
    if(i===1) {
      b.items.forEach((a,ai) => {
        const ax=bx+0.08+(ai%2)*0.72, ay=2.7+Math.floor(ai/2)*0.55;
        addCard(s,ax,ay,0.67,0.45,C.white,C.divider);
        s.addText(a[0], { x:ax,y:ay+0.05,w:0.67,h:0.35, fontSize:8, fontFace:FB, color:C.pri700, align:"center", bold:true, margin:0 });
      });
    } else {
      b.items.forEach((item,ii) => {
        const iy=2.7+ii*0.6;
        addCard(s,bx+0.1,iy,1.35,0.5,C.white,C.divider);
        s.addText(item[0], { x:bx+0.1,y:iy+0.02,w:1.35,h:0.25, fontSize:8, fontFace:FB, color:C.pri900, align:"center", bold:true, margin:0 });
        if(item[1]) s.addText(item[1], { x:bx+0.1,y:iy+0.25,w:1.35,h:0.2, fontSize:7, fontFace:FB, color:C.muted, align:"center", margin:0 });
      });
    }
  });
  addCard(s,2.3,4.25,5.0,0.35,C.pri700);
  s.addText("format_response → SSE Streaming → END", { x:2.3,y:4.25,w:5.0,h:0.35, fontSize:10, fontFace:FB, color:C.white, align:"center", valign:"middle", bold:true, margin:0 });
  s.addText("→", { x:7.5,y:2.1,w:0.4,h:0.4, fontSize:18, color:C.pri300, align:"center", valign:"middle" });
  // Right
  [{l:"Qdrant Cloud",s2:"벡터+BM25"},{l:"vLLM (RunPod)",s2:"Kanana+LoRA"},{l:"Google APIs",s2:"Cal/Tasks/Gmail/Sheets"},{l:"PostgreSQL",s2:"RDS 16 테이블"}].forEach((inf,i) => {
    const iy=1.2+i*0.9;
    addCard(s,8.0,iy,1.7,0.7,C.acc50,C.acc300);
    s.addText(inf.l, { x:8.0,y:iy+0.05,w:1.7,h:0.3, fontSize:10, fontFace:FB, color:C.acc700, align:"center", bold:true, margin:0 });
    s.addText(inf.s2, { x:8.0,y:iy+0.35,w:1.7,h:0.25, fontSize:8, fontFace:FB, color:C.muted, align:"center", margin:0 });
  });
}

// ========== 9. AGENT STRUCTURE ==========
{
  const s = pres.addSlide(); s.background = { color: C.sfcMain };
  addTag(s,4.7,0.2,"08",C.pri50,C.pri700);
  s.addText("Agent 구조", { x:0,y:0.55,w:10,h:0.5, fontSize:28, fontFace:FT, color:C.pri900, align:"center", bold:true });
  [{n:"문서 AGENT",r:"문서 생성/요약/검색/QA\n4가지 오퍼레이션",c:C.acc700,bg:C.acc50,f:"사용자 질의 → 서브타입 판단\n→ sLLM ← LoRA 라우팅 → 응답"},
   {n:"판단 AGENT",r:"사내규정 기반\nyes/no/conditional 판단\n+ 근거 조항 + 대안",c:C.pri700,bg:C.pri50,f:"사용자 질의 → RAG (top-k)\n→ sLLM 판단 (LoRA v1)\n→ 4중 보조장치 + confidence → 응답"},
   {n:"일정 AGENT",r:"자연어 → 일정 등록/조회\n+ Google 5종 연동",c:C.success,bg:C.successBg,f:"사용자 질의 → LLM 자연어 파싱\n→ Google API 호출\n→ 결과 반환"}
  ].forEach((a,i) => {
    const ax=0.5+i*3.15;
    addCard(s,ax,1.3,2.85,3.4,C.white,C.divider);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:ax+0.85,y:1.5,w:1.15,h:0.8, fill:{color:a.bg}, rectRadius:0.1 });
    s.addText(a.n, { x:ax+0.1,y:2.45,w:2.65,h:0.35, fontSize:14, fontFace:FT, color:C.pri900, align:"center", bold:true, margin:0 });
    s.addText(a.r, { x:ax+0.1,y:2.8,w:2.65,h:0.65, fontSize:9, fontFace:FB, color:C.sub, align:"center" });
    s.addText(a.f, { x:ax+0.15,y:3.55,w:2.55,h:1.0, fontSize:9, fontFace:FB, color:C.sub, align:"center", valign:"top" });
  });
  addCard(s,0.5,4.85,9.0,0.4,C.pri700);
  s.addText("LangGraph Orchestrator: classify_intent → 조건부 라우팅 (단일 / 복합 / 저신뢰)", { x:0.5,y:4.85,w:9.0,h:0.4, fontSize:10, fontFace:FB, color:C.white, align:"center", valign:"middle", margin:0 });
}

// ========== 10. JUDGMENT AGENT DETAIL ==========
{
  const s = pres.addSlide(); s.background = { color: C.white };
  addTag(s,4.55,0.15,"08-1",C.pri50,C.pri700);
  s.addText("Judgment Agent 상세", { x:0,y:0.45,w:10,h:0.45, fontSize:26, fontFace:FT, color:C.pri900, align:"center", bold:true });
  s.addText("사내규정 기반 판단 · RAG 검색 → sLLM 판단 → 4중 보조장치 → Confidence 보정", { x:0,y:0.85,w:10,h:0.25, fontSize:10, fontFace:FB, color:C.sub, align:"center" });
  // Top 4 flow
  [{t:"사용자 질의",d:"+ 이전 대화 컨텍스트\n(최근 3턴)",bg:C.sfcMain,bd:C.divider,tc:C.pri900},
   {t:"RAG 하이브리드 검색",d:"Qdrant + BM25 + Reranker\ntop_k=5 · 규정 전용 필터",bg:C.pri50,bd:C.pri100,tc:C.pri700},
   {t:"규정 그룹핑 + 프롬프트",d:"출처별 규정 분류\n이전 판단 이력 3건 포함",bg:C.pri50,bd:C.pri100,tc:C.pri700},
   {t:"sLLM 판단",d:"LoRA v1_judgment\nKanana-1.5-8B · JSON mode",bg:C.pri700,bd:undefined,tc:C.white}
  ].forEach((tf,i) => {
    const tx=0.35+i*2.4;
    addCard(s,tx,1.25,2.15,1.1,tf.bg,tf.bd);
    s.addText(tf.t, { x:tx+0.1,y:1.3,w:1.95,h:0.35, fontSize:11, fontFace:FB, color:tf.tc, align:"center", bold:true, margin:0 });
    s.addText(tf.d, { x:tx+0.1,y:1.65,w:1.95,h:0.55, fontSize:9, fontFace:FB, color:tf.bg===C.pri700?C.pri100:C.muted, align:"center", margin:0 });
  });
  // Bottom 3
  addCard(s,0.35,2.6,3.7,2.3,C.successBg,C.success);
  s.addText("4중 보조장치", { x:0.35,y:2.7,w:3.7,h:0.3, fontSize:12, fontFace:FB, color:C.success, align:"center", bold:true, margin:0 });
  [["1. 카테고리 제한","yes / no / conditional"],["2. 키워드 매칭","인용 조항 환각 탐지"],["3. 조항 존재 검증","Qdrant 실존 여부 확인"],["4. 일관성 모니터링","동일 쿼리 캐싱+비교"]].forEach((sg,i) => {
    const gx=0.5+(i%2)*1.8, gy=3.1+Math.floor(i/2)*0.85;
    addCard(s,gx,gy,1.65,0.7,C.white,C.divider);
    s.addText(sg[0], { x:gx+0.05,y:gy+0.05,w:1.55,h:0.3, fontSize:10, fontFace:FB, color:C.pri900, align:"center", bold:true, margin:0 });
    s.addText(sg[1], { x:gx+0.05,y:gy+0.35,w:1.55,h:0.25, fontSize:8, fontFace:FB, color:C.muted, align:"center", margin:0 });
  });
  addCard(s,4.25,2.6,2.9,2.3,C.acc50,C.acc300);
  s.addText("Confidence 보정", { x:4.25,y:2.7,w:2.9,h:0.3, fontSize:12, fontFace:FB, color:C.acc700, align:"center", bold:true, margin:0 });
  s.addText("calibrated =\nLLM×0.6 + RAG×0.25\n+ coverage×0.15\n- penalties", { x:4.4,y:3.1,w:2.6,h:0.9, fontSize:10, fontFace:FB, color:C.sub, align:"center" });
  ["충돌 패널티","환각 패널티","미존재 조항"].forEach((p,i) => {
    addCard(s,4.4+i*0.88,4.15,0.82,0.3,C.white,C.divider);
    s.addText(p, { x:4.4+i*0.88,y:4.15,w:0.82,h:0.3, fontSize:7, fontFace:FB, color:C.sub, align:"center", valign:"middle", margin:0 });
  });
  addCard(s,7.35,2.6,2.3,2.3,C.sfcMain,C.divider);
  s.addText("최종 응답", { x:7.35,y:2.7,w:2.3,h:0.3, fontSize:12, fontFace:FB, color:C.pri900, align:"center", bold:true, margin:0 });
  s.addText("result + confidence\n+ reasoning\n+ 근거 조항\n+ 교차참조\n+ 대안", { x:7.35,y:3.15,w:2.3,h:1.3, fontSize:10, fontFace:FB, color:C.sub, align:"center" });
}

// ========== 11. LIMITATIONS ==========
{
  const s = pres.addSlide(); s.background = { color: C.sfcMain };
  addTag(s,4.7,0.2,"10",C.warningBg,C.warning);
  s.addText("한계점 및 향후 계획", { x:0,y:0.55,w:10,h:0.5, fontSize:28, fontFace:FT, color:C.pri900, align:"center", bold:true });
  s.addText("현재 한계점", { x:0.5,y:1.2,w:4.3,h:0.35, fontSize:14, fontFace:FB, color:C.pri900, bold:true });
  [["Conditional 정확도 78%","목표 85% -7%p\n조건부 가능 경계 모호"],["3-step 복합 요청 66.7%","1-step 91.3% 대비 낮음\n8B 모델 멀티스텝 추론 한계"],
   ["Reranker 지연 +5.7초","정확도 vs 속도 트레이드오프\nMRR 0.636→0.952"],["vLLM LoRA 전환 이슈","v3_summary 한글 깨짐\npeft 버전 호환"]
  ].forEach((l,i) => {
    const ly=1.65+i*0.9;
    addCard(s,0.5,ly,4.3,0.75,C.white,C.divider);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:0.55,y:ly+0.05,w:0.12,h:0.65, fill:{color:C.error}, rectRadius:0.04 });
    s.addText(l[0], { x:0.8,y:ly+0.05,w:3.9,h:0.3, fontSize:11, fontFace:FB, color:C.pri900, bold:true, margin:0 });
    s.addText(l[1], { x:0.8,y:ly+0.35,w:3.9,h:0.35, fontSize:8, fontFace:FB, color:C.sub, margin:0 });
  });
  s.addText("향후 발전 방향", { x:5.2,y:1.2,w:4.3,h:0.35, fontSize:14, fontFace:FB, color:C.pri900, bold:true });
  [["Conditional 데이터 정밀 보강","레이블 표준 재정의 + 경계 사례\n추가 수집 → 목표 85%"],["빈출 규정 판단 캐싱","자주 묻는 규정 질문 캐싱으로\nReranker 지연 우회"],
   ["모델 경량화 & 최적화","4-bit 양자화 적용 · ONNX 변환\n추론 속도 개선"],["복합 질문 연쇄 처리","규정 판단+문서 생성 연쇄\n3-step 이상 분해 성능 강화"]
  ].forEach((f,i) => {
    const fy=1.65+i*0.9;
    addCard(s,5.2,fy,4.3,0.75,C.white,C.divider);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:5.25,y:fy+0.05,w:0.12,h:0.65, fill:{color:C.success}, rectRadius:0.04 });
    s.addText(f[0], { x:5.5,y:fy+0.05,w:3.9,h:0.3, fontSize:11, fontFace:FB, color:C.pri900, bold:true, margin:0 });
    s.addText(f[1], { x:5.5,y:fy+0.35,w:3.9,h:0.35, fontSize:8, fontFace:FB, color:C.sub, margin:0 });
  });
}

// ========== 12. Q&A ==========
{
  const s = pres.addSlide(); s.background = { color: C.pri900 };
  s.addText("WorkFlow Agent — DUDE", { x:0,y:1.3,w:10,h:0.4, fontSize:12, fontFace:FB, color:C.pri300, align:"center", charSpacing:3 });
  s.addText("Q & A", { x:0,y:1.8,w:10,h:1.2, fontSize:54, fontFace:FT, color:C.white, align:"center", valign:"middle", bold:true });
  s.addText("감사합니다", { x:0,y:3.2,w:10,h:0.5, fontSize:16, fontFace:FB, color:C.pri100, align:"center" });
  s.addText("SKN21 Final Project · 3TEAM", { x:0,y:3.8,w:10,h:0.4, fontSize:11, fontFace:FB, color:C.pri300, align:"center" });
}

// === SAVE ===
pres.writeFile({ fileName: "/Users/moonjiyoung/Desktop/SKN21-FINAL-3TEAM/DUDE_Presentation.pptx" }).then(() => {
  console.log("PPT 생성 완료: DUDE_Presentation.pptx");
}).catch(err => console.error("오류:", err));
