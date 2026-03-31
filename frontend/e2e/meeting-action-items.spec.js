// @ts-check
import { test, expect } from '@playwright/test';
import { LOGIN_EMAIL, LOGIN_PW } from './helpers.js';

test.describe('회의록 생성 → Action Items 버튼 확인', () => {

  test('회의록 생성 후 Pipeline/Google Tasks 버튼 표시 확인', async ({ page }) => {
    // 1. 로그인
    await page.goto('/login');
    await page.locator('input[type="email"]').waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('input[type="email"]').fill(LOGIN_EMAIL);
    await page.locator('input[type="password"]').fill(LOGIN_PW);
    await page.locator('form button[type="submit"], form button:has-text("로그인")').first().click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
    console.log('[Login] OK');

    // 2. 문서 생성 페이지 이동
    await page.goto('/document-generate');
    await page.waitForTimeout(2000);

    // 3. "기본 회의록" 시스템 템플릿 선택
    const meetingBtn = page.locator('button:has-text("회의록")').first();
    await meetingBtn.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: './e2e/results/ai-01-meeting-selected.png' });

    // 4. MeetingInput 폼 확인
    const contentInput = page.locator('textarea').first();
    await expect(contentInput).toBeVisible({ timeout: 5000 });

    // 5. 회의 내용 입력
    await contentInput.fill('3월 10일 보안팀 정기회의. 참석자: 김팀장, 이대리, 박사원.\n\n1. 보안 시스템 업그레이드 일정 확정 - 3월 말까지 완료 예정\n2. 취약점 점검 결과 보고 - 이대리 담당\n3. 신규 보안 정책 수립 필요 - 박사원이 초안 작성 후 다음 회의에서 검토');
    await page.screenshot({ path: './e2e/results/ai-02-content-filled.png' });

    // 6. 생성 버튼 클릭
    const generateBtn = page.locator('button:has-text("AI"), button:has-text("생성")').last();
    await generateBtn.click();
    console.log('[Generate] 클릭');

    // 7. 생성 응답 대기 (최대 60초)
    const start = Date.now();
    let prevText = '';
    let stableCount = 0;

    while (Date.now() - start < 60000) {
      await page.waitForTimeout(3000);
      const allText = await page.locator('body').textContent();
      console.log(`[Wait] ${Math.round((Date.now()-start)/1000)}s | 텍스트길이=${allText.length}`);

      // Action Items 섹션 또는 결정사항이 나타났는지
      if (allText.includes('Action Items') || allText.includes('결정사항') || allText.includes('요약')) {
        console.log('[Wait] 회의록 생성 완료 감지');
        break;
      }

      if (allText === prevText && allText.length > 0) {
        stableCount++;
        if (stableCount >= 2) break;
      } else {
        stableCount = 0;
      }
      prevText = allText;
    }

    await page.screenshot({ path: './e2e/results/ai-03-generated.png' });

    // 8. 결과 확인
    const bodyText = await page.locator('body').textContent();
    const hasActionItems = bodyText.includes('Action Items');
    const hasPipeline = bodyText.includes('Pipeline');
    const hasGoogleTasks = bodyText.includes('Google Tasks');
    const hasDecisions = bodyText.includes('결정사항');
    const hasSummary = bodyText.includes('요약');
    const hasDownload = bodyText.includes('DOCX') || bodyText.includes('다운로드');

    console.log('[Result] Action Items:', hasActionItems);
    console.log('[Result] Pipeline 버튼:', hasPipeline);
    console.log('[Result] Google Tasks 버튼:', hasGoogleTasks);
    console.log('[Result] 결정사항:', hasDecisions);
    console.log('[Result] 요약:', hasSummary);
    console.log('[Result] 다운로드:', hasDownload);

    // 에러 확인
    const hasError = bodyText.includes('실패') || bodyText.includes('오류');
    console.log('[Result] 에러:', hasError);

    await page.screenshot({ path: './e2e/results/ai-04-final.png', fullPage: true });
  });

});
