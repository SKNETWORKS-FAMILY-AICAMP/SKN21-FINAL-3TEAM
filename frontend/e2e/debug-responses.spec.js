// @ts-check
import { test, expect } from '@playwright/test';

const LOGIN_EMAIL = 'jiyong1110@naver.com';
const LOGIN_PW = 'tlswldyd1!';

async function loginAndGoToChat(page) {
  await page.goto('/');
  const emailInput = page.locator('input[type="email"]');
  if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
    await emailInput.fill(LOGIN_EMAIL);
    await page.locator('input[type="password"]').fill(LOGIN_PW);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL('**/dashboard', { timeout: 15_000 });
  }
  await page.goto('/chat');
  await page.locator('input[placeholder*="질문"]').waitFor({ state: 'visible', timeout: 10_000 });
}

async function sendAndCapture(page, message, label) {
  const input = page.locator('input[placeholder*="질문"]');
  await input.fill(message);
  await input.press('Enter');

  // SSE 응답 완료 대기
  const start = Date.now();
  let prevText = '';
  let stableCount = 0;
  const timeout = 40_000;

  while (Date.now() - start < timeout) {
    await page.waitForTimeout(2000);
    const allText = await page.locator('[data-main-scroll]').first().textContent().catch(() => '');
    if (allText === prevText && allText.length > 0) {
      stableCount++;
      if (stableCount >= 2) break;
    } else {
      stableCount = 0;
    }
    prevText = allText;
  }

  // 봇 응답만 추출 (마지막 assistant 메시지)
  // items-start = bot bubble 기준
  const botMessages = page.locator('[class*="items-start"]');
  const count = await botMessages.count();
  let botText = '';
  if (count > 0) {
    botText = await botMessages.last().textContent().catch(() => '(추출 실패)');
  }

  console.log(`\n${'='.repeat(60)}`);
  console.log(`[${label}] 질문: "${message}"`);
  console.log(`${'─'.repeat(60)}`);
  console.log(`[${label}] 응답 (${botText.length}자):`);
  console.log(botText);
  console.log(`${'='.repeat(60)}\n`);

  return botText;
}

test.describe('챗봇 응답 디버그', () => {
  test.setTimeout(300_000);

  test('모든 인텐트 응답 내용 캡처', async ({ page }) => {
    await loginAndGoToChat(page);

    // 1. judgment
    const r1 = await sendAndCapture(page, '연차 사용 가능한가요?', 'judgment');
    await page.screenshot({ path: 'e2e/results/debug_01_judgment.png', fullPage: true });

    // 새 세션 (페이지 새로고침)
    await page.goto('/chat');
    await page.locator('input[placeholder*="질문"]').waitFor({ state: 'visible', timeout: 10_000 });

    // 2. doc_search
    const r2 = await sendAndCapture(page, '마케팅 관련 문서 찾아줘', 'doc_search');
    await page.screenshot({ path: 'e2e/results/debug_02_doc_search.png', fullPage: true });

    await page.goto('/chat');
    await page.locator('input[placeholder*="질문"]').waitFor({ state: 'visible', timeout: 10_000 });

    // 3. doc_generate
    const r3 = await sendAndCapture(page, '보고서 작성해줘', 'doc_generate');
    await page.screenshot({ path: 'e2e/results/debug_03_doc_generate.png', fullPage: true });

    await page.goto('/chat');
    await page.locator('input[placeholder*="질문"]').waitFor({ state: 'visible', timeout: 10_000 });

    // 4. schedule_view
    const r4 = await sendAndCapture(page, '오늘 일정 알려줘', 'schedule_view');
    await page.screenshot({ path: 'e2e/results/debug_04_schedule_view.png', fullPage: true });

    await page.goto('/chat');
    await page.locator('input[placeholder*="질문"]').waitFor({ state: 'visible', timeout: 10_000 });

    // 5. general
    const r5 = await sendAndCapture(page, '안녕하세요', 'general');
    await page.screenshot({ path: 'e2e/results/debug_05_general.png', fullPage: true });

    await page.goto('/chat');
    await page.locator('input[placeholder*="질문"]').waitFor({ state: 'visible', timeout: 10_000 });

    // 6. 재택근무 규정 (문제의 질문)
    const r6 = await sendAndCapture(page, '재택근무 규정 알려줘', 'judgment_재택');
    await page.screenshot({ path: 'e2e/results/debug_06_재택근무.png', fullPage: true });

    // 요약 출력
    console.log('\n\n' + '🔍'.repeat(30));
    console.log('===== 응답 요약 =====');
    console.log(`judgment (연차):     ${r1.length}자`);
    console.log(`doc_search (마케팅): ${r2.length}자`);
    console.log(`doc_generate (보고서): ${r3.length}자`);
    console.log(`schedule_view (일정): ${r4.length}자`);
    console.log(`general (안녕):      ${r5.length}자`);
    console.log(`judgment (재택근무): ${r6.length}자`);
  });
});
