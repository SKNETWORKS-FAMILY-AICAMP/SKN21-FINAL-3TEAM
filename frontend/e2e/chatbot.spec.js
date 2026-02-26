// @ts-check
import { test, expect } from '@playwright/test';
import { login, goToChat, loginAndGoToChat, sendMessage, waitForBotResponse } from './helpers.js';

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
    await emailInput.fill('jiyong1110@naver.com');
    await page.locator('input[type="password"]').fill('tlswldyd1!');
    await page.locator('button[type="submit"]').click();

    await page.waitForURL('**/dashboard', { timeout: 15_000 });
    expect(page.url()).toContain('/dashboard');
  });

  // ── 2. 채팅 페이지 접근 ──
  test('채팅 페이지 입력창 표시', async ({ page }) => {
    await loginAndGoToChat(page);

    const input = page.locator('[data-testid="chat-input"]');
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
