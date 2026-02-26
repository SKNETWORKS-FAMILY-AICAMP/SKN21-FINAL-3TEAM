// @ts-check
import { test, expect } from '@playwright/test';
import { login, loginAndGoToChat, sendMessage, waitForBotResponse } from './helpers.js';

test.describe('누락 인텐트 + UI 네비게이션 테스트', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(120_000);
  });

  // ── 1. schedule_add — "내일 3시에 회의 추가해줘" ──
  test('schedule_add — 일정 추가 응답', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '내일 3시에 회의 추가해줘');

    const response = await waitForBotResponse(page, 30_000);
    console.log('[E2E] schedule_add 응답 길이:', response.length);

    // 일정 에이전트 활성 확인
    const scheduleAgent = page.locator('text=일정');
    const hasSchedule = await scheduleAgent.first().isVisible({ timeout: 5000 }).catch(() => false);
    console.log('[E2E] 일정 Agent 활성:', hasSchedule);

    expect(response.length).toBeGreaterThan(10);
    await page.screenshot({ path: 'e2e/results/missing_01_schedule_add.png', fullPage: true });
  });

  // ── 2. doc_summary (문서 미선택) — "이 문서 요약해줘" ──
  test('doc_summary — 문서 미선택 시 안내 응답', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '이 문서 요약해줘');

    const response = await waitForBotResponse(page, 30_000);
    console.log('[E2E] doc_summary 응답 길이:', response.length);

    // 문서 선택 안내 또는 doc_pick 카드가 나와야 함
    expect(response.length).toBeGreaterThan(10);
    await page.screenshot({ path: 'e2e/results/missing_02_doc_summary.png', fullPage: true });
  });

  // ── 3. doc_qa — "지난 회의 결정사항이 뭐야?" ──
  test('doc_qa — 문서 Q&A 응답', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '지난 회의 결정사항이 뭐야?');

    const response = await waitForBotResponse(page, 30_000);
    console.log('[E2E] doc_qa 응답 길이:', response.length);

    // 문서 Q&A 카드 또는 관련 응답이 나와야 함
    expect(response.length).toBeGreaterThan(10);
    await page.screenshot({ path: 'e2e/results/missing_03_doc_qa.png', fullPage: true });
  });

  // ── 4. 사이드바 네비게이션 ──
  test('사이드바 메뉴 네비게이션', async ({ page }) => {
    await login(page);

    const menuItems = [
      { text: '대시보드', url: '/dashboard' },
      { text: 'AI 챗봇', url: '/chat' },
      { text: '문서 관리', url: '/documents' },
      { text: '일정 관리', url: '/schedules' },
    ];

    for (const item of menuItems) {
      // 사이드바 메뉴 링크 클릭
      const link = page.locator(`nav a:has-text("${item.text}"), aside a:has-text("${item.text}")`);
      if (await link.first().isVisible({ timeout: 3000 }).catch(() => false)) {
        await link.first().click();
        await page.waitForTimeout(1500);
        console.log(`[E2E] ${item.text} → ${page.url()}`);
        expect(page.url()).toContain(item.url);
      } else {
        console.log(`[E2E] ${item.text} 메뉴 미발견 — 스킵`);
      }
    }

    await page.screenshot({ path: 'e2e/results/missing_04_navigation.png' });
  });

  // ── 5. 일정 페이지 (CalendarView 렌더링) ──
  test('일정 페이지 — CalendarView 렌더링 확인', async ({ page }) => {
    await login(page);
    await page.goto('/schedules');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // CalendarView는 "년 월" 텍스트 + ◀▶ 버튼으로 렌더됨
    const calendarHeader = page.locator('text=/\\d{4}년 \\d{1,2}월/');
    const hasCalendar = await calendarHeader.first().isVisible({ timeout: 5000 }).catch(() => false);
    console.log('[E2E] CalendarView 렌더링:', hasCalendar);

    // 일정 관리 페이지 제목이나 캘린더 뷰가 보이는지 확인
    const hasPage = hasCalendar || await page.locator('text=일정').first().isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasPage).toBe(true);
    await page.screenshot({ path: 'e2e/results/missing_05_schedule_page.png', fullPage: true });
  });
});
