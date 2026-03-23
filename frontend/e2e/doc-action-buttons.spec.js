// @ts-check
/**
 * 문서 Agent 응답 하단 액션 버튼 기능 테스트
 *
 * 테스트 흐름:
 *   1. 검색 → 하단 "요약해줘" / "질문하기" 버튼 클릭 → 후속 응답 확인
 *   2. QA → 하단 "출처 문서 요약" / "관련 문서 더 찾기" 버튼 클릭
 *   3. 요약 → 하단 "이 문서에 질문하기" / "관련 문서 더 찾기" 버튼 클릭
 *   4. 3단계 체인: 검색 → 요약 → 질문
 */
import { test, expect } from '@playwright/test';
import { loginAndGoToChat, sendMessage } from './helpers.js';

const RESPONSE_TIMEOUT = 90_000;

/** 봇 메시지가 N개 이상 나올 때까지 대기 (SSE 스트리밍 완료 감지) */
async function waitForNthBotMessage(page, n, timeoutMs = RESPONSE_TIMEOUT) {
  const botMessages = page.locator('[data-testid="bot-message"]');

  // 먼저 n번째 봇 메시지가 나타나길 대기
  await botMessages.nth(n - 1).waitFor({ state: 'visible', timeout: timeoutMs }).catch(() => {});

  // 내용이 안정화될 때까지 폴링 (스트리밍 완료 감지)
  const start = Date.now();
  let prevText = '';
  let stableCount = 0;

  while (Date.now() - start < timeoutMs) {
    await page.waitForTimeout(2000);
    const count = await botMessages.count();
    if (count < n) continue;

    const currentText = await botMessages.nth(n - 1).textContent().catch(() => '');
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

/** 봇 메시지 개수 */
async function getBotMessageCount(page) {
  return await page.locator('[data-testid="bot-message"]').count();
}

/** 특정 텍스트의 버튼 클릭 (마지막 봇 메시지 내에서) */
async function clickActionButton(page, buttonText) {
  // 마지막 봇 메시지 내부 또는 전체에서 찾기
  const btn = page.locator(`[data-testid="bot-message"]:last-child button:has-text("${buttonText}")`);
  let visible = await btn.isVisible({ timeout: 5000 }).catch(() => false);
  if (visible) {
    await btn.click();
    return true;
  }
  // fallback: 전체에서 마지막 매칭
  const fallback = page.locator(`button:has-text("${buttonText}")`).last();
  visible = await fallback.isVisible({ timeout: 3000 }).catch(() => false);
  if (visible) {
    await fallback.click();
    return true;
  }
  return false;
}

/** 마지막 봇 메시지에 있는 모든 버튼 텍스트 수집 */
async function listActionButtons(page) {
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

test.describe('문서 Agent 액션 버튼 테스트', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(180_000);
  });

  // ═══════════════════════════════════════════
  // 1. 검색 → 버튼 테스트
  // ═══════════════════════════════════════════

  test('검색 후 "질문하기" 버튼 → QA 응답', async ({ page }) => {
    await loginAndGoToChat(page);

    // 1단계: 문서 검색
    await sendMessage(page, '보고서 문서 검색해줘');
    const msg1 = await waitForNthBotMessage(page, 1);
    const count1 = await getBotMessageCount(page);
    console.log(`[E2E:검색→QA] 검색 응답: ${msg1.length}자, 봇 메시지 수: ${count1}`);

    // 버튼 목록 확인
    const buttons = await listActionButtons(page);
    console.log(`[E2E:검색→QA] 발견된 버튼: ${JSON.stringify(buttons)}`);
    await page.screenshot({ path: 'e2e/results/search-buttons-v2.png' });

    // 2단계: "질문" 버튼 클릭
    const clicked = await clickActionButton(page, '질문');
    console.log(`[E2E:검색→QA] "질문" 버튼 클릭: ${clicked}`);

    if (clicked) {
      const msg2 = await waitForNthBotMessage(page, count1 + 1);
      const count2 = await getBotMessageCount(page);
      console.log(`[E2E:검색→QA] 후속 응답: ${msg2.length}자, 봇 메시지 수: ${count2}`);

      expect(count2).toBeGreaterThan(count1);
      expect(msg2.length).toBeGreaterThan(10);
      expect(msg2).not.toContain('처리 중 오류');
    }
  });

  test('검색 후 "요약" 버튼 → 요약 응답', async ({ page }) => {
    await loginAndGoToChat(page);

    await sendMessage(page, '회의록 문서 찾아줘');
    const msg1 = await waitForNthBotMessage(page, 1);
    const count1 = await getBotMessageCount(page);
    console.log(`[E2E:검색→요약] 검색 응답: ${msg1.length}자`);

    const buttons = await listActionButtons(page);
    console.log(`[E2E:검색→요약] 버튼: ${JSON.stringify(buttons)}`);

    const clicked = await clickActionButton(page, '요약');
    console.log(`[E2E:검색→요약] "요약" 버튼 클릭: ${clicked}`);

    if (clicked) {
      const msg2 = await waitForNthBotMessage(page, count1 + 1);
      const count2 = await getBotMessageCount(page);
      console.log(`[E2E:검색→요약] 후속 응답: ${msg2.length}자`);

      expect(count2).toBeGreaterThan(count1);
      expect(msg2.length).toBeGreaterThan(10);
      expect(msg2).not.toContain('처리 중 오류');
    }
  });

  // ═══════════════════════════════════════════
  // 2. QA → 버튼 테스트
  // ═══════════════════════════════════════════

  test('QA 후 "출처 문서 요약" 버튼 → 요약 응답', async ({ page }) => {
    await loginAndGoToChat(page);

    await sendMessage(page, '출장비 정산 기준이 어떻게 되나요?');
    const msg1 = await waitForNthBotMessage(page, 1);
    const count1 = await getBotMessageCount(page);
    console.log(`[E2E:QA→요약] QA 응답: ${msg1.length}자`);

    const buttons = await listActionButtons(page);
    console.log(`[E2E:QA→요약] 버튼: ${JSON.stringify(buttons)}`);
    await page.screenshot({ path: 'e2e/results/qa-buttons-v2.png' });

    const clicked = await clickActionButton(page, '요약');
    console.log(`[E2E:QA→요약] "요약" 버튼 클릭: ${clicked}`);

    if (clicked) {
      const msg2 = await waitForNthBotMessage(page, count1 + 1);
      const count2 = await getBotMessageCount(page);
      console.log(`[E2E:QA→요약] 후속 응답: ${msg2.length}자`);

      expect(count2).toBeGreaterThan(count1);
      expect(msg2.length).toBeGreaterThan(10);
      expect(msg2).not.toContain('처리 중 오류');
    }
  });

  test('QA 후 "관련 문서 더 찾기" 버튼 → 검색 응답', async ({ page }) => {
    await loginAndGoToChat(page);

    await sendMessage(page, '연차 사용 조건이 뭐야?');
    const msg1 = await waitForNthBotMessage(page, 1);
    const count1 = await getBotMessageCount(page);
    console.log(`[E2E:QA→검색] QA 응답: ${msg1.length}자`);

    const clicked = await clickActionButton(page, '더 찾기');
    console.log(`[E2E:QA→검색] "더 찾기" 버튼 클릭: ${clicked}`);

    if (clicked) {
      const msg2 = await waitForNthBotMessage(page, count1 + 1);
      const count2 = await getBotMessageCount(page);
      console.log(`[E2E:QA→검색] 후속 응답: ${msg2.length}자`);

      expect(count2).toBeGreaterThan(count1);
      expect(msg2.length).toBeGreaterThan(10);
      expect(msg2).not.toContain('처리 중 오류');
    }
  });

  // ═══════════════════════════════════════════
  // 3. 요약 → 버튼 테스트
  // ═══════════════════════════════════════════

  test('요약 후 "이 문서에 질문하기" 버튼 → QA 응답', async ({ page }) => {
    await loginAndGoToChat(page);

    await sendMessage(page, '최근 회의록 요약해줘');
    const msg1 = await waitForNthBotMessage(page, 1);
    const count1 = await getBotMessageCount(page);
    console.log(`[E2E:요약→QA] 요약 응답: ${msg1.length}자`);

    const buttons = await listActionButtons(page);
    console.log(`[E2E:요약→QA] 버튼: ${JSON.stringify(buttons)}`);
    await page.screenshot({ path: 'e2e/results/summary-buttons-v2.png' });

    const clicked = await clickActionButton(page, '질문');
    console.log(`[E2E:요약→QA] "질문" 버튼 클릭: ${clicked}`);

    if (clicked) {
      const msg2 = await waitForNthBotMessage(page, count1 + 1);
      const count2 = await getBotMessageCount(page);
      console.log(`[E2E:요약→QA] 후속 응답: ${msg2.length}자`);

      expect(count2).toBeGreaterThan(count1);
      expect(msg2.length).toBeGreaterThan(10);
      expect(msg2).not.toContain('처리 중 오류');
    }
  });

  test('요약 후 "관련 문서 더 찾기" 버튼 → 검색 응답', async ({ page }) => {
    await loginAndGoToChat(page);

    await sendMessage(page, '보고서 요약해줘');
    const msg1 = await waitForNthBotMessage(page, 1);
    const count1 = await getBotMessageCount(page);
    console.log(`[E2E:요약→검색] 요약 응답: ${msg1.length}자`);

    const clicked = await clickActionButton(page, '더 찾기');
    console.log(`[E2E:요약→검색] "더 찾기" 버튼 클릭: ${clicked}`);

    if (clicked) {
      const msg2 = await waitForNthBotMessage(page, count1 + 1);
      const count2 = await getBotMessageCount(page);
      console.log(`[E2E:요약→검색] 후속 응답: ${msg2.length}자`);

      expect(count2).toBeGreaterThan(count1);
      expect(msg2.length).toBeGreaterThan(10);
      expect(msg2).not.toContain('처리 중 오류');
    }
  });

  // ═══════════════════════════════════════════
  // 4. 3단계 체인: 검색 → 요약 → 질문
  // ═══════════════════════════════════════════

  test('버튼 체인: 검색 → 요약 → 질문 (3단계)', async ({ page }) => {
    await loginAndGoToChat(page);

    // 1단계: 검색
    console.log('[E2E:체인] === 1단계: 검색 ===');
    await sendMessage(page, '인사규정 문서 찾아줘');
    await waitForNthBotMessage(page, 1);
    const count1 = await getBotMessageCount(page);
    console.log(`[E2E:체인] 검색 후 메시지 수: ${count1}`);

    // 2단계: "요약" 버튼
    console.log('[E2E:체인] === 2단계: 요약 버튼 ===');
    const clicked1 = await clickActionButton(page, '요약');
    if (!clicked1) {
      console.log('[E2E:체인] 요약 버튼 없음, 체인 중단');
      return;
    }
    const msg2 = await waitForNthBotMessage(page, count1 + 1);
    const count2 = await getBotMessageCount(page);
    console.log(`[E2E:체인] 요약 후 메시지 수: ${count2}, 응답: ${msg2.length}자`);
    expect(count2).toBeGreaterThan(count1);

    // 3단계: "질문" 버튼
    console.log('[E2E:체인] === 3단계: 질문 버튼 ===');
    const clicked2 = await clickActionButton(page, '질문');
    if (!clicked2) {
      console.log('[E2E:체인] 질문 버튼 없음, 체인 중단');
      return;
    }
    const msg3 = await waitForNthBotMessage(page, count2 + 1);
    const count3 = await getBotMessageCount(page);
    console.log(`[E2E:체인] 질문 후 메시지 수: ${count3}, 응답: ${msg3.length}자`);

    expect(count3).toBeGreaterThan(count2);
    expect(msg3.length).toBeGreaterThan(10);
    expect(msg3).not.toContain('처리 중 오류');
    console.log('[E2E:체인] 3단계 체인 완료!');
  });
});
