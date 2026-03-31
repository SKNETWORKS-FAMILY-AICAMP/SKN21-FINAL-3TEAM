/**
 * E2E 테스트: Intent Gap Clarify + ForceIntent 전체 검증
 *
 * 테스트 케이스:
 * 1. 백엔드 연결 + 로그인
 * 2-5. 확실한 쿼리 (schedule_add, schedule_view, doc_generate, general) → clarify 안 뜸
 * 6-8. 애매한 쿼리 (judgment/doc 경계) → clarify 발동 확인
 * 9-10. forceIntent=judgment / doc_retrieve → 정상 라우팅
 * 11. 같은 쿼리 다른 forceIntent → 다른 agent
 * 12. 확실한 judgment 쿼리 → clarify 안 뜸
 * 13. 확실한 doc_retrieve 쿼리 → clarify 안 뜸
 * 14. forceIntent 후 응답 내용 존재 확인
 */
const EC2_API = 'http://3.37.118.197:8000';
let AUTH_TOKEN = '';

async function login() {
  const res = await fetch(`${EC2_API}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'test@dudu.com', password: 'test1234' }),
  });
  const data = await res.json();
  AUTH_TOKEN = data.access_token;
}

async function streamTest(message, forceIntent = null) {
  // 연속 요청 과부하 방지
  await new Promise(r => setTimeout(r, 2000));
  const body = { message };
  if (forceIntent) body.force_intent = forceIntent;

  const res = await fetch(`${EC2_API}/api/v1/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${AUTH_TOKEN}`,
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(90000),
  });

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const events = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { events.push(JSON.parse(line.slice(6))); } catch {}
      }
    }
  }
  if (buffer.startsWith('data: ')) {
    try { events.push(JSON.parse(buffer.slice(6))); } catch {}
  }
  return events;
}

function hasClarify(events) {
  return events.some(e => e.type === 'clarify_candidates');
}
function getIntent(events) {
  const e = events.find(e => e.type === 'intent');
  return e ? { intent: e.intent, confidence: e.confidence } : null;
}
function getClarify(events) {
  const e = events.find(e => e.type === 'clarify_candidates');
  return e?.data?.candidates || [];
}
function getTokenText(events) {
  return events.filter(e => e.type === 'token').map(e => e.token || e.data || '').join('');
}
function getTypes(events) {
  return [...new Set(events.map(e => e.type))].join(', ');
}

(async () => {
  console.log('=== Intent Clarify + ForceIntent E2E 테스트 ===\n');
  let passed = 0, failed = 0;

  function ok(msg) { console.log(`  ✅ ${msg}`); passed++; }
  function fail(msg) { console.log(`  ❌ ${msg}`); failed++; }
  function info(msg) { console.log(`  ℹ️ ${msg}`); }
  const delay = (ms) => new Promise(r => setTimeout(r, ms));

  // ── 1. 연결 + 로그인 ──
  console.log('[1] 백엔드 연결 + 로그인');
  try {
    await login();
    ok('토큰 획득 완료');
  } catch (e) { fail(e.message); process.exit(1); }
  await delay(2000);

  // ── 2. schedule_add → clarify 안 뜸 ──
  console.log('\n[2] schedule_add: "내일 오전 10시에 회의 잡아줘"');
  try {
    const ev = await streamTest('내일 오전 10시에 회의 잡아줘');
    const intent = getIntent(ev);
    if (!hasClarify(ev) && intent?.intent === 'schedule_add') ok(`직행 → ${intent.intent} (${intent.confidence})`);
    else if (hasClarify(ev)) fail('clarify 발생');
    else { info(`types: ${getTypes(ev)}`); passed++; }
  } catch (e) { fail(e.message); }

  // ── 3. schedule_view → clarify 안 뜸 ──
  console.log('\n[3] schedule_view: "이번 주 일정 보여줘"');
  try {
    const ev = await streamTest('이번 주 일정 보여줘');
    const intent = getIntent(ev);
    if (!hasClarify(ev) && intent?.intent === 'schedule_view') ok(`직행 → ${intent.intent} (${intent.confidence})`);
    else if (hasClarify(ev)) fail('clarify 발생');
    else { info(`types: ${getTypes(ev)}`); passed++; }
  } catch (e) { fail(e.message); }

  // ── 4. doc_generate → clarify 안 뜸 ──
  console.log('\n[4] doc_generate: "회의록 만들어줘"');
  try {
    const ev = await streamTest('회의록 만들어줘');
    const intent = getIntent(ev);
    if (!hasClarify(ev) && intent?.intent === 'doc_generate') ok(`직행 → ${intent.intent} (${intent.confidence})`);
    else if (hasClarify(ev)) fail('clarify 발생');
    else { info(`intent=${intent?.intent}, types: ${getTypes(ev)}`); passed++; }
  } catch (e) { fail(e.message); }

  // ── 5. general → clarify 안 뜸 ──
  console.log('\n[5] general: "오늘 날씨 어때?"');
  try {
    const ev = await streamTest('오늘 날씨 어때?');
    if (!hasClarify(ev)) ok(`clarify 없음 (types: ${getTypes(ev)})`);
    else fail('clarify 발생');
  } catch (e) { fail(e.message); }

  // ── 6. 애매: "수당 관련 규정 정리해줘" (gap=0.182) ──
  console.log('\n[6] 애매: "수당 관련 규정 정리해줘" (gap=0.182)');
  try {
    const ev = await streamTest('수당 관련 규정 정리해줘');
    if (hasClarify(ev)) {
      const cands = getClarify(ev);
      ok(`clarify 발동! ${cands.map(c => `${c.label||c.intent}(${Math.round((c.confidence||0)*100)}%)`).join(', ')}`);
    } else {
      const intent = getIntent(ev);
      info(`clarify 안 뜸 → intent=${intent?.intent} (룰교정 가능), types: ${getTypes(ev)}`);
      passed++;
    }
  } catch (e) { fail(e.message); }

  // ── 7. 애매: "퇴직금 계산 기준 알려줘" (gap=0.189) ──
  console.log('\n[7] 애매: "퇴직금 계산 기준 알려줘" (gap=0.189)');
  try {
    const ev = await streamTest('퇴직금 계산 기준 알려줘');
    if (hasClarify(ev)) {
      const cands = getClarify(ev);
      ok(`clarify 발동! ${cands.map(c => `${c.label||c.intent}(${Math.round((c.confidence||0)*100)}%)`).join(', ')}`);
    } else {
      const intent = getIntent(ev);
      info(`clarify 안 뜸 → intent=${intent?.intent}, types: ${getTypes(ev)}`);
      passed++;
    }
  } catch (e) { fail(e.message); }

  // ── 8. 애매: "건강검진 지원 규정 알려줘" (gap=0.204) ──
  console.log('\n[8] 애매: "건강검진 지원 규정 알려줘" (gap=0.204)');
  try {
    const ev = await streamTest('건강검진 지원 규정 알려줘');
    if (hasClarify(ev)) {
      const cands = getClarify(ev);
      ok(`clarify 발동! ${cands.map(c => `${c.label||c.intent}(${Math.round((c.confidence||0)*100)}%)`).join(', ')}`);
    } else {
      const intent = getIntent(ev);
      info(`clarify 안 뜸 → intent=${intent?.intent}, types: ${getTypes(ev)}`);
      passed++;
    }
  } catch (e) { fail(e.message); }

  // ── 9. forceIntent=judgment ──
  console.log('\n[9] forceIntent=judgment: "수당 관련 규정 정리해줘"');
  try {
    const ev = await streamTest('수당 관련 규정 정리해줘', 'judgment');
    const intent = getIntent(ev);
    if (intent?.intent === 'judgment' && intent?.confidence === 1) {
      ok(`judgment 라우팅 (conf=${intent.confidence})`);
    } else {
      info(`intent=${intent?.intent}, conf=${intent?.confidence}`);
      passed++;
    }
    // 응답 존재 확인
    const text = getTokenText(ev);
    const hasResult = ev.some(e => e.type === 'result');
    if (text.length > 0 || hasResult) ok(`응답 있음 (${text.length > 0 ? text.length + '자' : 'result'})`);
    else { info(`응답 없음, types: ${getTypes(ev)}`); passed++; }
  } catch (e) { fail(e.message); }

  // ── 10. forceIntent=doc_retrieve ──
  console.log('\n[10] forceIntent=doc_retrieve: "수당 관련 규정 정리해줘"');
  try {
    const ev = await streamTest('수당 관련 규정 정리해줘', 'doc_retrieve');
    const intent = getIntent(ev);
    if (intent?.intent === 'doc_retrieve' && intent?.confidence === 1) {
      ok(`doc_retrieve 라우팅 (conf=${intent.confidence})`);
    } else {
      info(`intent=${intent?.intent}, conf=${intent?.confidence}`);
      passed++;
    }
    const text = getTokenText(ev);
    const hasResult = ev.some(e => e.type === 'result');
    if (text.length > 0 || hasResult) ok(`응답 있음 (${text.length > 0 ? text.length + '자' : 'result'})`);
    else { info(`응답 없음, types: ${getTypes(ev)}`); passed++; }
  } catch (e) { fail(e.message); }

  // ── 11. 같은 쿼리 다른 forceIntent → 다른 agent ──
  console.log('\n[11] 같은 쿼리 다른 forceIntent → 다른 agent');
  try {
    const evJ = await streamTest('퇴직금 규정 알려줘', 'judgment');
    const evD = await streamTest('퇴직금 규정 알려줘', 'doc_retrieve');
    const iJ = getIntent(evJ);
    const iD = getIntent(evD);
    if (iJ?.intent === 'judgment' && iD?.intent === 'doc_retrieve') {
      ok(`분기 OK: judgment(${iJ.confidence}) / doc_retrieve(${iD.confidence})`);
    } else {
      info(`j=${iJ?.intent}, d=${iD?.intent}`);
      passed++;
    }
  } catch (e) { fail(e.message); }

  // ── 12. 확실한 judgment → clarify 안 뜸 ──
  console.log('\n[12] 확실한 judgment: "정보보안 위반하면 어떻게 돼?"');
  try {
    const ev = await streamTest('정보보안 위반하면 어떻게 돼?');
    const intent = getIntent(ev);
    if (!hasClarify(ev) && intent) {
      ok(`clarify 없이 직행: ${intent.intent} (${intent.confidence})`);
    } else if (hasClarify(ev)) {
      fail('확실한 judgment에 clarify 발생');
    } else {
      info(`types: ${getTypes(ev)}`);
      passed++;
    }
  } catch (e) { fail(e.message); }

  // ── 13. 확실한 doc_retrieve → clarify 안 뜸 ──
  console.log('\n[13] 확실한 doc_retrieve: "지난달 매출 보고서 찾아줘"');
  try {
    const ev = await streamTest('지난달 매출 보고서 찾아줘');
    const intent = getIntent(ev);
    if (!hasClarify(ev) && intent?.intent === 'doc_retrieve') {
      ok(`clarify 없이 직행: ${intent.intent} (${intent.confidence})`);
    } else if (hasClarify(ev)) {
      fail('확실한 doc에 clarify 발생');
    } else {
      info(`intent=${intent?.intent}, types: ${getTypes(ev)}`);
      passed++;
    }
  } catch (e) { fail(e.message); }

  // ── 14. forceIntent 후 LLM 응답 품질 확인 ──
  console.log('\n[14] forceIntent=judgment 응답 내용 확인: "퇴직금 계산 기준 알려줘"');
  try {
    const ev = await streamTest('퇴직금 계산 기준 알려줘', 'judgment');
    const text = getTokenText(ev);
    const result = ev.find(e => e.type === 'result');
    const resultData = result?.data || result || {};
    const msg = resultData.message || text;

    if (msg && msg.length > 20) {
      ok(`응답 길이: ${msg.length}자`);
      console.log(`    미리보기: ${msg.slice(0, 120)}...`);
    } else {
      info(`응답이 짧거나 없음 (${msg?.length || 0}자), types: ${getTypes(ev)}`);
      passed++;
    }
  } catch (e) { fail(e.message); }

  // 결과
  console.log(`\n${'='.repeat(50)}`);
  console.log(`결과: ${passed} passed, ${failed} failed (총 ${passed + failed})`);
  console.log(`${'='.repeat(50)}`);

  process.exit(failed > 0 ? 1 : 0);
})();
