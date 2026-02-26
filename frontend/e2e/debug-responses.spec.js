// @ts-check
import { test, expect } from '@playwright/test';
import { loginAndGoToChat, goToChat, sendAndCapture } from './helpers.js';

test.describe('챗봇 응답 디버그', () => {
  test.setTimeout(300_000);

  test('모든 인텐트 응답 내용 캡처', async ({ page }) => {
    await loginAndGoToChat(page);

    // 1. judgment
    const r1 = await sendAndCapture(page, '연차 사용 가능한가요?', 'judgment');
    await page.screenshot({ path: 'e2e/results/debug_01_judgment.png', fullPage: true });

    // 새 세션 (페이지 새로고침)
    await goToChat(page);

    // 2. doc_search
    const r2 = await sendAndCapture(page, '마케팅 관련 문서 찾아줘', 'doc_search');
    await page.screenshot({ path: 'e2e/results/debug_02_doc_search.png', fullPage: true });

    await goToChat(page);

    // 3. doc_generate
    const r3 = await sendAndCapture(page, '보고서 작성해줘', 'doc_generate');
    await page.screenshot({ path: 'e2e/results/debug_03_doc_generate.png', fullPage: true });

    await goToChat(page);

    // 4. schedule_view
    const r4 = await sendAndCapture(page, '오늘 일정 알려줘', 'schedule_view');
    await page.screenshot({ path: 'e2e/results/debug_04_schedule_view.png', fullPage: true });

    await goToChat(page);

    // 5. general
    const r5 = await sendAndCapture(page, '안녕하세요', 'general');
    await page.screenshot({ path: 'e2e/results/debug_05_general.png', fullPage: true });

    await goToChat(page);

    // 6. 재택근무 규정 (문제의 질문)
    const r6 = await sendAndCapture(page, '재택근무 규정 알려줘', 'judgment_재택');
    await page.screenshot({ path: 'e2e/results/debug_06_재택근무.png', fullPage: true });

    // 요약 출력
    console.log('\n\n' + '='.repeat(30));
    console.log('===== 응답 요약 =====');
    console.log(`judgment (연차):     ${r1.length}자`);
    console.log(`doc_search (마케팅): ${r2.length}자`);
    console.log(`doc_generate (보고서): ${r3.length}자`);
    console.log(`schedule_view (일정): ${r4.length}자`);
    console.log(`general (안녕):      ${r5.length}자`);
    console.log(`judgment (재택근무): ${r6.length}자`);
  });
});
