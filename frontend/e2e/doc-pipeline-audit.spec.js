// @ts-check
/**
 * 문서 Agent 파이프라인 감사 테스트
 *
 * 검색 / QA / 요약 각각의:
 *   - 출력 품질 (빈 응답, 에러 메시지, 이상한 출력)
 *   - 문서 연결 매핑 (sources/citations에 document_id가 있는지)
 *   - 하단 액션 버튼 존재 + 클릭 후 후속 응답
 */
import { test, expect } from '@playwright/test';
import { loginAndGoToChat, sendMessage } from './helpers.js';

const RESPONSE_TIMEOUT = 90_000;

/** SSE 스트리밍 완료 대기 (봇 메시지 텍스트 안정화) */
async function waitForStableResponse(page, msgIndex, timeoutMs = RESPONSE_TIMEOUT) {
  const botMessages = page.locator('[data-testid="bot-message"]');
  await botMessages.nth(msgIndex).waitFor({ state: 'visible', timeout: timeoutMs }).catch(() => {});

  const start = Date.now();
  let prevText = '';
  let stableCount = 0;

  while (Date.now() - start < timeoutMs) {
    await page.waitForTimeout(2000);
    const count = await botMessages.count();
    if (count <= msgIndex) continue;
    const currentText = await botMessages.nth(msgIndex).textContent().catch(() => '');
    if (currentText === prevText && currentText.length > 0) {
      stableCount++;
      if (stableCount >= 2) break;
    } else {
      stableCount = 0;
    }
    prevText = currentText;
  }
  return prevText;
}

/** 마지막 봇 메시지의 모든 버튼 텍스트 수집 */
async function getButtons(page) {
  const botMsg = page.locator('[data-testid="bot-message"]').last();
  const buttons = botMsg.locator('button');
  const count = await buttons.count();
  const texts = [];
  for (let i = 0; i < count; i++) {
    const t = await buttons.nth(i).textContent().catch(() => '');
    if (t.trim()) texts.push(t.trim());
  }
  return texts;
}

/** SSE result 이벤트를 캡처하는 네트워크 인터셉터 설정 */
async function captureSSEResult(page) {
  const results = [];
  page.on('response', async (response) => {
    if (response.url().includes('/chat/stream') && response.headers()['content-type']?.includes('event-stream')) {
      // SSE는 response.body()로 잡기 어려움 — console.log로 캡처
    }
  });
  // 대안: evaluate로 전역 변수에 저장
  await page.evaluate(() => {
    window.__sseResults = [];
    const origFetch = window.fetch;
    window.fetch = async function(...args) {
      const response = await origFetch.apply(this, args);
      if (args[0]?.toString().includes('/chat/stream') || (typeof args[0] === 'string' && args[0].includes('/chat/stream'))) {
        const clone = response.clone();
        const reader = clone.body.getReader();
        const decoder = new TextDecoder();
        (async () => {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const text = decoder.decode(value, { stream: true });
            const lines = text.split('\n');
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.type === 'result') {
                    window.__sseResults.push(data);
                  }
                } catch {}
              }
            }
          }
        })();
      }
      return response;
    };
  });
  return results;
}

/** 캡처된 SSE result 이벤트 가져오기 */
async function getSSEResults(page) {
  return await page.evaluate(() => window.__sseResults || []);
}

/** 새 채팅 세션 시작 */
async function startNewChat(page) {
  const newChatBtn = page.locator('button:has-text("새 대화"), [data-testid="new-chat"]').first();
  if (await newChatBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await newChatBtn.click();
    await page.waitForTimeout(1000);
  }
}

test.describe('문서 Agent 파이프라인 감사', () => {

  // ═══════════════════════════════════════════
  // 1. 검색 테스트
  // ═══════════════════════════════════════════

  test('검색: 출력 품질 + 문서매핑 + 버튼', async ({ page }) => {
    test.setTimeout(180_000);
    await loginAndGoToChat(page);
    await captureSSEResult(page);

    await sendMessage(page, '보고서 문서 찾아줘');
    const msg = await waitForStableResponse(page, 0);
    console.log(`\n[검색] 응답 (${msg.length}자):\n${msg.slice(0, 500)}`);
    await page.screenshot({ path: 'e2e/results/audit-search.png' });

    // 출력 품질 검사
    expect(msg.length).toBeGreaterThan(20);
    expect(msg).not.toContain('처리 중 오류');
    expect(msg).not.toContain('undefined');
    expect(msg).not.toContain('null');
    expect(msg).toContain('건'); // "N건의 관련 문서"

    // SSE result에서 sources 확인
    const sseResults = await getSSEResults(page);
    console.log(`[검색] SSE result 이벤트: ${sseResults.length}개`);
    if (sseResults.length > 0) {
      const data = sseResults[sseResults.length - 1].data || {};
      const sources = data.sources || [];
      console.log(`[검색] sources 수: ${sources.length}`);
      // 문서 매핑 검사: 각 source에 document_id가 있는지
      const missingIds = sources.filter(s => !s.document_id);
      if (missingIds.length > 0) {
        console.log(`[검색] ⚠️ document_id 없는 source: ${missingIds.length}개`);
        missingIds.forEach(s => console.log(`  - title: "${s.title}", score: ${s.score}`));
      }
      // search_info 확인
      if (data.search_info) {
        console.log(`[검색] search_info: ${JSON.stringify(data.search_info)}`);
      }
    }

    // 버튼 확인
    const buttons = await getButtons(page);
    console.log(`[검색] 버튼: ${JSON.stringify(buttons)}`);
  });

  // ═══════════════════════════════════════════
  // 2. QA 테스트
  // ═══════════════════════════════════════════

  test('QA: 출력 품질 + citations + 버튼', async ({ page }) => {
    test.setTimeout(180_000);
    await loginAndGoToChat(page);
    await captureSSEResult(page);

    await sendMessage(page, '출장비 정산은 어떻게 하나요?');
    const msg = await waitForStableResponse(page, 0);
    console.log(`\n[QA] 응답 (${msg.length}자):\n${msg.slice(0, 500)}`);
    await page.screenshot({ path: 'e2e/results/audit-qa-1.png' });

    // 출력 품질 검사
    expect(msg.length).toBeGreaterThan(10);
    expect(msg).not.toContain('처리 중 오류');
    expect(msg).not.toContain('Mock');

    // SSE result 검사
    const sseResults = await getSSEResults(page);
    console.log(`[QA] SSE result 이벤트: ${sseResults.length}개`);
    if (sseResults.length > 0) {
      const data = sseResults[sseResults.length - 1].data || {};
      console.log(`[QA] intent: ${sseResults[sseResults.length - 1].intent}`);
      console.log(`[QA] sub_type: ${data.sub_type || 'N/A'}`);
      console.log(`[QA] confidence: ${data.confidence}`);
      console.log(`[QA] sources 수: ${(data.sources || []).length}`);
      console.log(`[QA] citations 수: ${(data.citations || []).length}`);

      // citations 검사
      const citations = data.citations || [];
      if (citations.length === 0) {
        console.log(`[QA] ⚠️ citations 비어있음`);
      } else {
        citations.forEach((c, i) => {
          console.log(`[QA] citation[${i}]: source="${c.source}", relevance=${c.relevance}`);
        });
      }

      // sources에 document_id 있는지
      const sources = data.sources || [];
      const missingIds = sources.filter(s => !s.document_id);
      if (missingIds.length > 0) {
        console.log(`[QA] ⚠️ document_id 없는 source: ${missingIds.length}개`);
      }
    }

    // 버튼 확인
    const buttons = await getButtons(page);
    console.log(`[QA] 버튼: ${JSON.stringify(buttons)}`);
  });

  test('QA: 문서 컨텍스트 있을 때 (force doc_retrieve:qa)', async ({ page }) => {
    test.setTimeout(180_000);
    await loginAndGoToChat(page);
    await captureSSEResult(page);

    // 먼저 검색해서 문서를 찾고
    await sendMessage(page, '클라우드 계약서 찾아줘');
    await waitForStableResponse(page, 0);

    // "질문하기" 버튼 클릭 (있으면)
    const btn = page.locator('button:has-text("질문")').last();
    const hasBtn = await btn.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasBtn) {
      await btn.click();
      await page.waitForTimeout(2000);

      const msg2 = await waitForStableResponse(page, 1);
      console.log(`\n[QA-doc] 후속 QA 응답 (${msg2.length}자):\n${msg2.slice(0, 500)}`);
      await page.screenshot({ path: 'e2e/results/audit-qa-doc.png' });

      expect(msg2.length).toBeGreaterThan(10);
      expect(msg2).not.toContain('처리 중 오류');
      expect(msg2).not.toContain('시간이 초과');

      const sseResults = await getSSEResults(page);
      if (sseResults.length > 1) {
        const data = sseResults[sseResults.length - 1].data || {};
        console.log(`[QA-doc] sub_type: ${data.sub_type}`);
        console.log(`[QA-doc] confidence: ${data.confidence}`);
      }
    } else {
      console.log('[QA-doc] "질문하기" 버튼 없음 — 스킵');
    }
  });

  // ═══════════════════════════════════════════
  // 3. 요약 테스트
  // ═══════════════════════════════════════════

  test('요약: 출력 품질 + 태그 + 버튼', async ({ page }) => {
    test.setTimeout(180_000);
    await loginAndGoToChat(page);
    await captureSSEResult(page);

    await sendMessage(page, '클라우드 계약서 요약해줘');
    const msg = await waitForStableResponse(page, 0);
    console.log(`\n[요약] 응답 (${msg.length}자):\n${msg.slice(0, 500)}`);
    await page.screenshot({ path: 'e2e/results/audit-summary.png' });

    // 출력 품질 검사
    expect(msg.length).toBeGreaterThan(10);
    expect(msg).not.toContain('처리 중 오류');
    expect(msg).not.toContain('Mock');

    // SSE result 검사
    const sseResults = await getSSEResults(page);
    console.log(`[요약] SSE result 이벤트: ${sseResults.length}개`);
    if (sseResults.length > 0) {
      const data = sseResults[sseResults.length - 1].data || {};
      console.log(`[요약] sub_type: ${data.sub_type || 'N/A'}`);
      console.log(`[요약] tags: ${JSON.stringify(data.tags)}`);
      console.log(`[요약] summary 길이: ${(data.summary || '').length}`);
      console.log(`[요약] document_id: ${data.document_id}`);

      if (!data.tags || data.tags.length === 0) {
        console.log('[요약] ⚠️ tags 비어있음');
      }
      if (!data.document_id) {
        console.log('[요약] ⚠️ document_id 없음 — DB 연결 안 됨');
      }
    }

    // 버튼 확인
    const buttons = await getButtons(page);
    console.log(`[요약] 버튼: ${JSON.stringify(buttons)}`);
  });

  // ═══════════════════════════════════════════
  // 4. 검색 → 요약 → QA 3단계 체인
  // ═══════════════════════════════════════════

  test('3단계 체인: 검색 → 요약 → QA', async ({ page }) => {
    test.setTimeout(300_000);
    await loginAndGoToChat(page);
    await captureSSEResult(page);

    // Step 1: 검색
    await sendMessage(page, '회의록 찾아줘');
    const msg1 = await waitForStableResponse(page, 0);
    console.log(`\n[체인1:검색] ${msg1.length}자`);
    const btns1 = await getButtons(page);
    console.log(`[체인1:검색] 버튼: ${JSON.stringify(btns1)}`);
    await page.screenshot({ path: 'e2e/results/audit-chain-1-search.png' });

    // Step 2: "요약" 버튼 클릭
    const summaryBtn = page.locator('button:has-text("요약")').last();
    const hasSummary = await summaryBtn.isVisible({ timeout: 5000 }).catch(() => false);
    if (!hasSummary) {
      console.log('[체인] ⚠️ "요약" 버튼 없음 — 체인 중단');
      return;
    }
    await summaryBtn.click();
    await page.waitForTimeout(2000);
    const botCount = await page.locator('[data-testid="bot-message"]').count();
    const msg2 = await waitForStableResponse(page, botCount - 1);
    console.log(`\n[체인2:요약] ${msg2.length}자:\n${msg2.slice(0, 300)}`);
    const btns2 = await getButtons(page);
    console.log(`[체인2:요약] 버튼: ${JSON.stringify(btns2)}`);
    await page.screenshot({ path: 'e2e/results/audit-chain-2-summary.png' });

    // Step 3: "질문하기" 버튼 클릭
    const qaBtn = page.locator('button:has-text("질문")').last();
    const hasQa = await qaBtn.isVisible({ timeout: 5000 }).catch(() => false);
    if (!hasQa) {
      console.log('[체인] ⚠️ "질문하기" 버튼 없음 — 체인 중단');
      return;
    }
    await qaBtn.click();
    await page.waitForTimeout(2000);
    const botCount3 = await page.locator('[data-testid="bot-message"]').count();
    const msg3 = await waitForStableResponse(page, botCount3 - 1);
    console.log(`\n[체인3:QA] ${msg3.length}자:\n${msg3.slice(0, 300)}`);
    await page.screenshot({ path: 'e2e/results/audit-chain-3-qa.png' });

    // 최종 SSE 확인
    const sseResults = await getSSEResults(page);
    console.log(`[체인] 총 SSE result: ${sseResults.length}개`);
    sseResults.forEach((r, i) => {
      console.log(`  [${i}] intent=${r.intent}, sub_type=${r.data?.sub_type || 'N/A'}`);
    });
  });

});
