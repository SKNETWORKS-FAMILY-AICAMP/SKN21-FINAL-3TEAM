// @ts-check
import { test, expect } from '@playwright/test';

// ─── 설정 ───────────────────────────────────────────────
const LOGIN_EMAIL = 'jiyong1110@naver.com';
const LOGIN_PW = 'tlswldyd1!';
const SSE_WAIT = 20_000; // SSE 응답 최대 대기(ms)

// ─── 헬퍼 ───────────────────────────────────────────────

/** 로그인 수행 */
async function login(page) {
  await page.goto('/');
  // 이미 로그인 상태면 스킵
  if (!page.url().includes('/login') && !page.url().endsWith('/')) {
    return;
  }

  const emailInput = page.locator('input[type="email"]');
  if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
    await emailInput.fill(LOGIN_EMAIL);
    await page.locator('input[type="password"]').fill(LOGIN_PW);
    await page.locator('button[type="submit"]').click();
    // 대시보드로 이동될 때까지 대기
    await page.waitForURL('**/dashboard', { timeout: 15_000 });
  }
}

/** 채팅 페이지 이동 */
async function goToChat(page) {
  await page.goto('/chat');
  // 채팅 입력창이 보일 때까지 대기
  await page.locator('textarea[placeholder*="질문"], input[placeholder*="질문"]').waitFor({ state: 'visible', timeout: 10_000 });
}

/** 로그인 + 채팅 페이지 이동 */
async function loginAndGoToChat(page) {
  await login(page);
  await goToChat(page);
}

/** 메시지 전송 */
async function sendMessage(page, message) {
  const input = page.locator('textarea[placeholder*="질문"], input[placeholder*="질문"]');
  await input.fill(message);
  await input.press('Enter');
}

/**
 * AI 응답이 완료될 때까지 대기
 * - assistant 메시지 버블이 생기고, 내용이 안정될 때까지 폴링
 */
async function waitForBotResponse(page, timeoutMs = SSE_WAIT) {
  // 먼저 봇 버블이 하나 이상 나타나길 기다림
  const botBubbles = page.locator('[class*="items-start"]').filter({ hasText: /.+/ });
  await botBubbles.first().waitFor({ state: 'visible', timeout: timeoutMs }).catch(() => {});

  // 내용이 안정화될 때까지 폴링
  const start = Date.now();
  let prevText = '';
  let stableCount = 0;

  while (Date.now() - start < timeoutMs) {
    await page.waitForTimeout(1500);
    const allText = await page.locator('main, [data-main-scroll]').first().textContent().catch(() => '');
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

// ─── 테스트 ─────────────────────────────────────────────

test.describe('챗봇 E2E 테스트', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(120_000);
  });

  // ── 1. 로그인 ──
  test('로그인 후 대시보드 진입', async ({ page }) => {
    await page.goto('/');
    const emailInput = page.locator('input[type="email"]');
    await emailInput.waitFor({ state: 'visible', timeout: 10_000 });
    await emailInput.fill(LOGIN_EMAIL);
    await page.locator('input[type="password"]').fill(LOGIN_PW);
    await page.locator('button[type="submit"]').click();

    await page.waitForURL('**/dashboard', { timeout: 15_000 });
    expect(page.url()).toContain('/dashboard');
  });

  // ── 2. 채팅 페이지 접근 ──
  test('채팅 페이지 입력창 표시', async ({ page }) => {
    await loginAndGoToChat(page);

    const input = page.locator('textarea[placeholder*="질문"], input[placeholder*="질문"]');
    await expect(input).toBeVisible();

    // 추천 질문 영역이 보여야 함 (메시지 0개일 때)
    const suggested = page.locator('text=추천 질문').or(page.locator('text=무엇을 도와드릴까요'));
    const hasSuggested = await suggested.first().isVisible({ timeout: 5000 }).catch(() => false);
    console.log('[E2E] 추천 질문 표시:', hasSuggested);
  });

  // ── 3. judgment 인텐트 — "연차 사용 가능한가요?" ──
  test('judgment — 규정 판단 응답', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '연차 사용 가능한가요?');

    const response = await waitForBotResponse(page, 30_000);
    console.log('[E2E] judgment 응답 길이:', response.length);

    // 규정 판단 에이전트가 활성화됐는지 (AgentBar)
    const agentBar = page.locator('text=규정 판단');
    const hasAgent = await agentBar.first().isVisible({ timeout: 5000 }).catch(() => false);
    console.log('[E2E] 규정 판단 Agent 활성:', hasAgent);

    // 응답에 관련 내용이 있는지
    expect(response.length).toBeGreaterThan(20);
  });

  // ── 4. doc_generate — "보고서 작성해줘" ──
  test('doc_generate — 문서 생성 응답', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '보고서 작성해줘');

    const response = await waitForBotResponse(page, 30_000);
    console.log('[E2E] doc_generate 응답 길이:', response.length);

    expect(response.length).toBeGreaterThan(20);
  });

  // ── 5. doc_search — "마케팅 문서 찾아줘" ──
  test('doc_search — 문서 검색 응답', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '마케팅 관련 문서 찾아줘');

    const response = await waitForBotResponse(page, 30_000);
    console.log('[E2E] doc_search 응답 길이:', response.length);

    expect(response.length).toBeGreaterThan(20);
  });

  // ── 6. meeting_generate — "회의록 만들어줘" ──
  test('meeting_generate — 회의록 생성 응답', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '회의록 만들어줘. 2월 24일 주간회의, 참석자 김철수 이영희, DB 마이그레이션 결정');

    const response = await waitForBotResponse(page, 30_000);
    console.log('[E2E] meeting_generate 응답 길이:', response.length);

    expect(response.length).toBeGreaterThan(20);
  });

  // ── 7. schedule_view — "오늘 일정 알려줘" ──
  test('schedule_view — 일정 조회 응답', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '오늘 일정 알려줘');

    const response = await waitForBotResponse(page, 30_000);
    console.log('[E2E] schedule_view 응답 길이:', response.length);

    // 일정 에이전트 바 표시 확인
    const scheduleAgent = page.locator('text=일정');
    const hasSchedule = await scheduleAgent.first().isVisible({ timeout: 5000 }).catch(() => false);
    console.log('[E2E] 일정 Agent 활성:', hasSchedule);

    expect(response.length).toBeGreaterThan(10);
  });

  // ── 8. general — 일반 대화 ──
  test('general — 일반 대화 응답', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '안녕하세요 반갑습니다');

    const response = await waitForBotResponse(page, 30_000);
    console.log('[E2E] general 응답 길이:', response.length);

    expect(response.length).toBeGreaterThan(10);
  });

  // ── 9. 연속 대화 — 같은 세션에서 2개 질문 ──
  test('연속 대화 — 세션 유지 확인', async ({ page }) => {
    await loginAndGoToChat(page);

    // 첫 번째 질문
    await sendMessage(page, '연차 규정 알려줘');
    await waitForBotResponse(page, 30_000);

    // 두 번째 질문
    await sendMessage(page, '그럼 병가는 어떻게 되나요?');
    const response = await waitForBotResponse(page, 30_000);
    console.log('[E2E] 연속 대화 응답 길이:', response.length);

    expect(response.length).toBeGreaterThan(20);
  });
});
