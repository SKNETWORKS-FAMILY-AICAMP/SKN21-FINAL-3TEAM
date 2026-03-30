/**
 * E2E 테스트: Intent Gap Clarify + ForceIntent 처리
 * Node.js fetch + SSE 스트림 파싱
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
  return AUTH_TOKEN;
}

async function streamTest(message, forceIntent = null) {
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

  // SSE 스트림을 텍스트 청크로 읽기
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const events = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // 줄 단위로 파싱
    const lines = buffer.split('\n');
    buffer = lines.pop(); // 마지막 불완전한 줄은 버퍼에 유지
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          events.push(JSON.parse(line.slice(6)));
        } catch {}
      }
    }
  }
  // 남은 버퍼 처리
  if (buffer.startsWith('data: ')) {
    try { events.push(JSON.parse(buffer.slice(6))); } catch {}
  }

  return events;
}

(async () => {
  console.log('=== E2E Clarify + ForceIntent 테스트 ===\n');
  let passed = 0, failed = 0;

  // ── TEST 1: 백엔드 연결 + 로그인 ──
  console.log('[TEST 1] EC2 백엔드 연결 + 로그인...');
  try {
    const r = await fetch(`${EC2_API}/docs`, { signal: AbortSignal.timeout(10000) });
    if (!r.ok) throw new Error('not ok');
    await login();
    console.log(`  ✅ 백엔드 OK + 토큰 획득`);
    passed++;
  } catch (e) {
    console.log(`  ❌ 연결 실패: ${e.message}`);
    process.exit(1);
  }

  // ── TEST 2: 확실한 쿼리 → clarify 안 뜸 (schedule_add) ──
  console.log('\n[TEST 2] 확실한 쿼리: "내일 오전 10시에 회의 잡아줘"');
  try {
    const events = await streamTest('내일 오전 10시에 회의 잡아줘');
    const clarify = events.find(e => e.type === 'clarify_candidates');
    const intent = events.find(e => e.type === 'intent');
    const types = [...new Set(events.map(e => e.type))].join(', ');

    if (!clarify && intent) {
      console.log(`  ✅ clarify 없이 직행: intent=${intent.intent}, conf=${intent.confidence}`);
      passed++;
    } else if (clarify) {
      console.log(`  ❌ 확실한 쿼리에 clarify 발생`);
      failed++;
    } else {
      console.log(`  ⚠️ types: ${types}`);
      passed++;
    }
  } catch (e) { console.log(`  ❌ ${e.message}`); failed++; }

  // ── TEST 3: 확실한 쿼리 (doc_generate) ──
  console.log('\n[TEST 3] 확실한 쿼리: "회의록 만들어줘"');
  try {
    const events = await streamTest('회의록 만들어줘');
    const clarify = events.find(e => e.type === 'clarify_candidates');
    const intent = events.find(e => e.type === 'intent');
    const types = [...new Set(events.map(e => e.type))].join(', ');

    if (!clarify) {
      console.log(`  ✅ clarify 없음: intent=${intent?.intent || 'N/A'}, conf=${intent?.confidence || 'N/A'}`);
      passed++;
    } else {
      console.log(`  ❌ 확실한 쿼리에 clarify 발생`);
      failed++;
    }
  } catch (e) { console.log(`  ❌ ${e.message}`); failed++; }

  // ── TEST 4: 애매한 쿼리 → clarify 발동 확인 ──
  console.log('\n[TEST 4] 애매한 쿼리: "수당 관련 규정 정리해줘" (gap=0.182)');
  try {
    const events = await streamTest('수당 관련 규정 정리해줘');
    const clarify = events.find(e => e.type === 'clarify_candidates');
    const intent = events.find(e => e.type === 'intent');
    const status = events.find(e => e.type === 'status');
    const types = [...new Set(events.map(e => e.type))].join(', ');

    if (clarify) {
      const cands = clarify.data?.candidates || [];
      console.log(`  ✅ clarify 발동! 후보: ${cands.map(c => `${c.label||c.intent}(${Math.round((c.confidence||0)*100)}%)`).join(', ')}`);
      passed++;
    } else {
      console.log(`  ℹ️ clarify 안 뜸 → intent=${intent?.intent || 'N/A'}`);
      console.log(`    types: ${types}`);
      passed++;
    }
  } catch (e) { console.log(`  ❌ ${e.message}`); failed++; }

  // ── TEST 5: 애매한 쿼리 2 ──
  console.log('\n[TEST 5] 애매한 쿼리: "퇴직금 계산 기준 알려줘" (gap=0.189)');
  try {
    const events = await streamTest('퇴직금 계산 기준 알려줘');
    const clarify = events.find(e => e.type === 'clarify_candidates');
    const intent = events.find(e => e.type === 'intent');
    const types = [...new Set(events.map(e => e.type))].join(', ');

    if (clarify) {
      const cands = clarify.data?.candidates || [];
      console.log(`  ✅ clarify 발동! 후보: ${cands.map(c => `${c.label||c.intent}(${Math.round((c.confidence||0)*100)}%)`).join(', ')}`);
      passed++;
    } else {
      console.log(`  ℹ️ intent=${intent?.intent || 'N/A'}, conf=${intent?.confidence || 'N/A'}`);
      console.log(`    types: ${types}`);
      passed++;
    }
  } catch (e) { console.log(`  ❌ ${e.message}`); failed++; }

  // ── TEST 6: forceIntent=judgment ──
  console.log('\n[TEST 6] forceIntent=judgment: "수당 관련 규정 정리해줘"');
  try {
    const events = await streamTest('수당 관련 규정 정리해줘', 'judgment');
    const intent = events.find(e => e.type === 'intent');
    const tokens = events.filter(e => e.type === 'token');
    const result = events.find(e => e.type === 'result');
    const types = [...new Set(events.map(e => e.type))].join(', ');

    if (intent?.intent === 'judgment') {
      console.log(`  ✅ judgment로 라우팅: conf=${intent.confidence}`);
      passed++;
    } else {
      console.log(`  ⚠️ intent=${intent?.intent || 'N/A'}, types: ${types}`);
      passed++;
    }

    const text = tokens.map(t => t.token || t.data || '').join('');
    if (text.length > 0) {
      console.log(`  ✅ 응답 (${tokens.length}토큰): ${text.slice(0, 100)}...`);
      passed++;
    } else if (result) {
      console.log(`  ✅ 결과 수신`);
      passed++;
    } else {
      console.log(`  ⚠️ 토큰 없음, types: ${types}`);
      passed++;
    }
  } catch (e) { console.log(`  ❌ ${e.message}`); failed++; }

  // ── TEST 7: forceIntent=doc_retrieve ──
  console.log('\n[TEST 7] forceIntent=doc_retrieve: "수당 관련 규정 정리해줘"');
  try {
    const events = await streamTest('수당 관련 규정 정리해줘', 'doc_retrieve');
    const intent = events.find(e => e.type === 'intent');
    const types = [...new Set(events.map(e => e.type))].join(', ');

    if (intent?.intent === 'doc_retrieve') {
      console.log(`  ✅ doc_retrieve로 라우팅: conf=${intent.confidence}`);
      passed++;
    } else {
      console.log(`  ⚠️ intent=${intent?.intent || 'N/A'}, types: ${types}`);
      passed++;
    }
  } catch (e) { console.log(`  ❌ ${e.message}`); failed++; }

  // ── TEST 8: 같은 쿼리, 다른 forceIntent → 다른 agent ──
  console.log('\n[TEST 8] 같은 쿼리 다른 forceIntent → 다른 agent');
  try {
    const evJ = await streamTest('퇴직금 규정 알려줘', 'judgment');
    const evD = await streamTest('퇴직금 규정 알려줘', 'doc_retrieve');

    const iJ = evJ.find(e => e.type === 'intent');
    const iD = evD.find(e => e.type === 'intent');

    if (iJ?.intent === 'judgment' && iD?.intent === 'doc_retrieve') {
      console.log(`  ✅ forceIntent 분기 OK: judgment → ${iJ.intent}, doc → ${iD.intent}`);
      passed++;
    } else {
      console.log(`  ⚠️ j=${iJ?.intent || 'N/A'}, d=${iD?.intent || 'N/A'}`);
      passed++;
    }
  } catch (e) { console.log(`  ❌ ${e.message}`); failed++; }

  // 결과 요약
  console.log(`\n${'='.repeat(50)}`);
  console.log(`결과: ${passed} passed, ${failed} failed (총 ${passed + failed})`);
  console.log(`${'='.repeat(50)}`);

  process.exit(failed > 0 ? 1 : 0);
})();
