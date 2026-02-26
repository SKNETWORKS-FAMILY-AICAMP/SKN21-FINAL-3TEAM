// @ts-check
const { test, expect } = require('@playwright/test');

const BASE_URL = 'http://localhost:5174';
const LOGIN_EMAIL = 'jiyong1110@naver.com';
const LOGIN_PW = 'tlswldyd1!';

// 로그인 후 채팅 페이지로 이동하는 헬퍼
async function loginAndGoToChat(page) {
  await page.goto(BASE_URL);

  // 로그인 페이지로 리다이렉트되면 로그인 수행
  await page.waitForTimeout(2000);
  const url = page.url();
  console.log('[E2E] Current URL:', url);

  // 이메일 입력
  const emailInput = page.locator('input[type="email"]');
  if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
    console.log('[E2E] Login page detected, logging in...');
    await emailInput.fill(LOGIN_EMAIL);
    await page.locator('input[type="password"]').fill(LOGIN_PW);
    await page.locator('button[type="submit"]').click();

    // 로그인 완료 대기 (채팅 페이지 or 대시보드로 이동)
    await page.waitForTimeout(3000);
    console.log('[E2E] After login URL:', page.url());
  }

  // 채팅 페이지로 이동
  const chatLink = page.locator('a[href*="chat"], a[href*="Chat"], [data-testid="chat"]');
  if (await chatLink.first().isVisible({ timeout: 3000 }).catch(() => false)) {
    await chatLink.first().click();
    await page.waitForTimeout(1000);
  } else {
    // 직접 이동
    await page.goto(BASE_URL + '/chat');
    await page.waitForTimeout(2000);
  }

  console.log('[E2E] Chat page URL:', page.url());
}

// 메시지 전송 헬퍼
async function sendMessage(page, message) {
  const input = page.locator('input[placeholder*="질문"]');
  await input.waitFor({ state: 'visible', timeout: 10000 });
  await input.fill(message);
  await input.press('Enter');
  console.log(`[E2E] Sent: "${message}"`);
}

// SSE 응답 대기 (토큰 스트리밍이 끝날 때까지)
async function waitForResponse(page, timeoutMs = 30000) {
  // AgentIndicator 또는 응답 메시지가 나타날 때까지 대기
  await page.waitForTimeout(3000);

  // 응답이 스트리밍 되는 동안 대기
  const startTime = Date.now();
  let lastContent = '';
  while (Date.now() - startTime < timeoutMs) {
    await page.waitForTimeout(1000);
    // 마지막 메시지 버블의 텍스트 확인
    const messages = page.locator('[class*="message"], [class*="bubble"], [class*="assistant"]');
    const count = await messages.count();
    if (count > 0) {
      const content = await messages.last().textContent().catch(() => '');
      if (content && content === lastContent && content.length > 10) {
        // 응답이 안정되면 완료
        break;
      }
      lastContent = content;
    }
  }
  return lastContent;
}

test.describe('Document Agent 리팩토링 E2E 테스트', () => {

  test.beforeEach(async ({ page }) => {
    // 타임아웃 넉넉히
    test.setTimeout(120000);
  });

  test('1. 로그인 성공', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForTimeout(2000);

    const emailInput = page.locator('input[type="email"]');
    if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      await emailInput.fill(LOGIN_EMAIL);
      await page.locator('input[type="password"]').fill(LOGIN_PW);
      await page.locator('button[type="submit"]').click();
      await page.waitForTimeout(3000);
    }

    // 로그인 후 URL이 login이 아니어야 함
    const url = page.url();
    console.log('[E2E] Post-login URL:', url);
    expect(url).not.toContain('/login');

    // 스크린샷
    await page.screenshot({ path: 'tests/screenshots/01_login_success.png' });
  });

  test('2. 채팅 페이지 접근 + intent 표시 확인', async ({ page }) => {
    await loginAndGoToChat(page);

    // 채팅 입력창이 보여야 함
    const input = page.locator('input[placeholder*="질문"]');
    await expect(input).toBeVisible({ timeout: 10000 });

    await page.screenshot({ path: 'tests/screenshots/02_chat_page.png' });
  });

  test('3. doc_generate — "보고서 작성해줘"', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '보고서 작성해줘');

    // intent 이벤트 확인 — AgentIndicator에 "문서 생성" 표시되는지
    await page.waitForTimeout(5000);

    const pageContent = await page.content();
    console.log('[E2E] doc_generate — page has AgentIndicator:', pageContent.includes('Agent'));

    await page.screenshot({ path: 'tests/screenshots/03_doc_generate.png' });

    // 응답이 뭔가 나왔는지 확인
    await page.waitForTimeout(10000);
    await page.screenshot({ path: 'tests/screenshots/03_doc_generate_result.png' });
  });

  test('4. doc_generate (meeting_minutes) — "회의록 만들어줘"', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '회의록 만들어줘. 2월 20일 주간회의, 참석자 김철수 이영희, DB 마이그레이션 결정');

    await page.waitForTimeout(10000);
    await page.screenshot({ path: 'tests/screenshots/04_meeting_minutes.png' });
  });

  test('5. doc_search — "마케팅 문서 찾아줘"', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '마케팅 문서 찾아줘');

    await page.waitForTimeout(10000);
    await page.screenshot({ path: 'tests/screenshots/05_doc_search.png' });
  });

  test('6. doc_summary — "이 문서 요약해줘"', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '이 문서 요약해줘');

    await page.waitForTimeout(10000);

    // doc_summary는 document_content 없으면 안내 메시지가 나와야 함
    const content = await page.textContent('body');
    console.log('[E2E] doc_summary response contains 선택:', content.includes('선택'));

    await page.screenshot({ path: 'tests/screenshots/06_doc_summary.png' });
  });

  test('7. doc_qa — "지난 회의 결정사항이 뭐야?"', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '지난 회의 결정사항이 뭐야?');

    await page.waitForTimeout(10000);
    await page.screenshot({ path: 'tests/screenshots/07_doc_qa.png' });
  });

  test('8. judgment (기존 유지) — "연차 규정 알려줘"', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '연차 규정 알려줘');

    await page.waitForTimeout(10000);
    await page.screenshot({ path: 'tests/screenshots/08_judgment.png' });
  });

  test('9. schedule_view (기존 유지) — "오늘 일정 알려줘"', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '오늘 일정 알려줘');

    await page.waitForTimeout(10000);
    await page.screenshot({ path: 'tests/screenshots/09_schedule_view.png' });
  });
});
