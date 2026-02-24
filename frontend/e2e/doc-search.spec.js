// @ts-check
import { test, expect } from '@playwright/test';

// ─── 설정 ───────────────────────────────────────────────
const LOGIN_EMAIL = 'jiyong1110@naver.com';
const LOGIN_PW = 'tlswldyd1!';
const SSE_WAIT = 40_000;

// ─── 헬퍼 ───────────────────────────────────────────────

async function login(page) {
  await page.goto('/');
  const emailInput = page.locator('input[type="email"]');
  if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
    await emailInput.fill(LOGIN_EMAIL);
    await page.locator('input[type="password"]').fill(LOGIN_PW);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL('**/dashboard', { timeout: 15_000 });
  }
}

async function goToChat(page) {
  await page.goto('/chat');
  await page.locator('textarea[placeholder*="질문"], input[placeholder*="질문"]')
    .waitFor({ state: 'visible', timeout: 10_000 });
}

async function loginAndGoToChat(page) {
  await login(page);
  await goToChat(page);
}

async function sendMessage(page, message) {
  const input = page.locator('textarea[placeholder*="질문"], input[placeholder*="질문"]');
  await input.fill(message);
  await input.press('Enter');
}

async function waitForBotResponse(page, timeoutMs = SSE_WAIT) {
  const botBubbles = page.locator('[class*="items-start"]').filter({ hasText: /.+/ });
  await botBubbles.first().waitFor({ state: 'visible', timeout: timeoutMs }).catch(() => {});

  const start = Date.now();
  let prevText = '';
  let stableCount = 0;

  while (Date.now() - start < timeoutMs) {
    await page.waitForTimeout(1500);
    const allText = await page.locator('main, [data-main-scroll]').first().textContent().catch(() => '');
    if (allText === prevText && allText.length > 0) {
      stableCount++;
      if (stableCount >= 2) break;
    } else {
      stableCount = 0;
    }
    prevText = allText;
  }
  return prevText;
}

// ─── doc_search 테스트 ─────────────────────────────────

test.describe('doc_search — 문서 검색 E2E 테스트', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(180_000);
  });

  // ── 1. 회의록 검색 (meeting_minutes) ──
  test('회의록 검색 — "스프린트 회의 내용 알려줘"', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '스프린트 킥오프 회의 내용 알려줘');

    const response = await waitForBotResponse(page, SSE_WAIT);
    console.log('[E2E] 회의록 검색 응답 길이:', response.length);
    console.log('[E2E] 응답 미리보기:', response.substring(0, 300));

    // 응답이 충분히 길어야 함
    expect(response.length).toBeGreaterThan(50);

    // 스크린샷
    await page.screenshot({ path: 'e2e/results/doc_search_01_meeting.png', fullPage: true });
  });

  // ── 2. 보고서 검색 (report) ──
  test('보고서 검색 — "서비스 성능 분석 보고서 찾아줘"', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '서비스 성능 분석 보고서 찾아줘');

    const response = await waitForBotResponse(page, SSE_WAIT);
    console.log('[E2E] 보고서 검색 응답 길이:', response.length);
    console.log('[E2E] 응답 미리보기:', response.substring(0, 300));

    expect(response.length).toBeGreaterThan(50);

    await page.screenshot({ path: 'e2e/results/doc_search_02_report.png', fullPage: true });
  });

  // ── 3. 제안서 검색 (proposal) ──
  test('제안서 검색 — "클라우드 마이그레이션 제안서"', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '클라우드 마이그레이션 제안서 내용 알려줘');

    const response = await waitForBotResponse(page, SSE_WAIT);
    console.log('[E2E] 제안서 검색 응답 길이:', response.length);
    console.log('[E2E] 응답 미리보기:', response.substring(0, 300));

    expect(response.length).toBeGreaterThan(50);

    await page.screenshot({ path: 'e2e/results/doc_search_03_proposal.png', fullPage: true });
  });

  // ── 4. 키워드 기반 검색 — DevOps ──
  test('키워드 검색 — "DevOps 관련 문서 찾아줘"', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, 'DevOps 파이프라인 관련 문서 찾아줘');

    const response = await waitForBotResponse(page, SSE_WAIT);
    console.log('[E2E] DevOps 검색 응답 길이:', response.length);
    console.log('[E2E] 응답 미리보기:', response.substring(0, 300));

    expect(response.length).toBeGreaterThan(50);

    await page.screenshot({ path: 'e2e/results/doc_search_04_devops.png', fullPage: true });
  });

  // ── 5. 보안 관련 문서 검색 ──
  test('보안 검색 — "보안 취약점 점검 결과 알려줘"', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '보안 취약점 점검 결과 알려줘');

    const response = await waitForBotResponse(page, SSE_WAIT);
    console.log('[E2E] 보안 검색 응답 길이:', response.length);
    console.log('[E2E] 응답 미리보기:', response.substring(0, 300));

    expect(response.length).toBeGreaterThan(50);

    await page.screenshot({ path: 'e2e/results/doc_search_05_security.png', fullPage: true });
  });
});
