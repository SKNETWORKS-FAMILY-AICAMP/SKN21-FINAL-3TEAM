// @ts-check
// ─── E2E 공통 헬퍼 ──────────────────────────────────────────

export const LOGIN_EMAIL = 'jiyong1110@naver.com';
export const LOGIN_PW = 'tlswldyd1!';
export const SSE_WAIT = 40_000;

/** 로그인 수행 */
export async function login(page) {
  await page.goto('/');
  if (!page.url().includes('/login') && !page.url().endsWith('/')) return;

  const emailInput = page.locator('input[type="email"]');
  if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
    await emailInput.fill(LOGIN_EMAIL);
    await page.locator('input[type="password"]').fill(LOGIN_PW);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL('**/dashboard', { timeout: 15_000 });
  }
}

/** 채팅 페이지 이동 */
export async function goToChat(page) {
  await page.goto('/chat');
  await page.locator('[data-testid="chat-input"]')
    .waitFor({ state: 'visible', timeout: 10_000 });
}

/** 로그인 + 채팅 페이지 이동 */
export async function loginAndGoToChat(page) {
  await login(page);
  await goToChat(page);
}

/** 메시지 전송 */
export async function sendMessage(page, message) {
  const input = page.locator('[data-testid="chat-input"]');
  await input.fill(message);
  await input.press('Enter');
}

/** AI 응답 완료 대기 (SSE 스트리밍이 안정화될 때까지 폴링) */
export async function waitForBotResponse(page, timeoutMs = SSE_WAIT) {
  // 봇 버블이 하나 이상 나타나길 기다림
  const botBubbles = page.locator('[data-testid="bot-message"]');
  await botBubbles.first().waitFor({ state: 'visible', timeout: timeoutMs }).catch(() => {});

  // 내용이 안정화될 때까지 폴링
  const start = Date.now();
  let prevText = '';
  let stableCount = 0;

  while (Date.now() - start < timeoutMs) {
    await page.waitForTimeout(1500);
    const allText = await page.locator('[data-main-scroll]').first().textContent().catch(() => '');
    if (allText === prevText && allText.length > 0) {
      stableCount++;
      if (stableCount >= 2) break; // 3초간 변화 없으면 완료
    } else {
      stableCount = 0;
    }
    prevText = allText;
  }
  return prevText;
}

/** 메시지 전송 + 응답 캡처 (디버그용) */
export async function sendAndCapture(page, message, label, timeoutMs = SSE_WAIT) {
  const input = page.locator('[data-testid="chat-input"]');
  await input.fill(message);
  await input.press('Enter');

  // SSE 응답 완료 대기
  const start = Date.now();
  let prevText = '';
  let stableCount = 0;

  while (Date.now() - start < timeoutMs) {
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

  // 봇 응답만 추출 (마지막 bot-message)
  const botMessages = page.locator('[data-testid="bot-message"]');
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
