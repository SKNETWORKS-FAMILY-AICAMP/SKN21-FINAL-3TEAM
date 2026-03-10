// @ts-check
import { test, expect } from '@playwright/test';
import { LOGIN_EMAIL, LOGIN_PW } from './helpers.js';

test.describe('챗봇 template_pick E2E', () => {

  test('회의록 써줘 → 템플릿 선택 버튼 표시 확인', async ({ page }) => {
    // 1. 로그인
    await page.goto('/login');
    await page.locator('input[type="email"]').waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('input[type="email"]').fill(LOGIN_EMAIL);
    await page.locator('input[type="password"]').fill(LOGIN_PW);
    await page.locator('form button[type="submit"], form button:has-text("로그인")').first().click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
    console.log('[Login] OK:', page.url());

    // 2. 챗봇 이동
    await page.goto('/chat');
    await page.waitForTimeout(2000);
    console.log('[Chat] URL:', page.url());
    await page.screenshot({ path: './e2e/results/tp-01-chat-page.png' });

    // 3. 채팅 입력
    const input = page.locator('[data-testid="chat-input"]');
    await input.waitFor({ state: 'visible', timeout: 10000 });
    await input.fill('3월 10일 정기회의에서 보안 시스템 업그레이드 논의했고 참석자는 김팀장, 이대리, 박사원입니다. 회의록 작성해주세요.');
    await input.press('Enter');
    console.log('[Chat] 메시지 전송 완료');

    // 4. SSE 응답 대기 (최대 60초)
    const start = Date.now();
    let prevText = '';
    let stableCount = 0;
    let foundTemplatePick = false;

    while (Date.now() - start < 60000) {
      await page.waitForTimeout(2000);

      const allText = await page.locator('[data-main-scroll]').first().textContent().catch(() => '');
      console.log(`[Wait] ${Math.round((Date.now()-start)/1000)}s | 텍스트길이=${allText.length}`);

      // template_pick 버튼 확인
      const buttons = page.locator('[data-testid="bot-message"] button, [data-main-scroll] button');
      const btnCount = await buttons.count();
      if (btnCount > 0) {
        for (let i = 0; i < btnCount; i++) {
          const btnText = await buttons.nth(i).textContent().catch(() => '');
          if (btnText.includes('회의록') || btnText.includes('기본')) {
            foundTemplatePick = true;
            console.log(`[Found] 템플릿 선택 버튼: "${btnText}"`);
          }
        }
      }

      if (foundTemplatePick) break;

      // 텍스트 안정화 체크
      if (allText === prevText && allText.length > 0) {
        stableCount++;
        if (stableCount >= 3) break;
      } else {
        stableCount = 0;
      }
      prevText = allText;
    }

    await page.screenshot({ path: './e2e/results/tp-02-response.png' });

    // 5. 결과 확인
    const finalText = await page.locator('[data-main-scroll]').first().textContent().catch(() => '');
    console.log('[Result] template_pick 발견:', foundTemplatePick);
    console.log('[Result] 응답 텍스트 (마지막 500자):', finalText?.slice(-500));

    // 양식 선택 관련 텍스트 확인
    const hasPickText = finalText?.includes('양식을 선택') || finalText?.includes('양식') || finalText?.includes('선택해주세요');
    console.log('[Result] 양식 선택 텍스트:', hasPickText);

    // doc_generate 카드가 바로 나왔는지 (template_pick 없이)
    const hasGenerate = finalText?.includes('다운로드') || finalText?.includes('요약') || finalText?.includes('결정사항');
    console.log('[Result] 바로 생성됨:', hasGenerate);

    await page.screenshot({ path: './e2e/results/tp-03-final.png' });
  });

});
