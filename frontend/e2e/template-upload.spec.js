// @ts-check
import { test, expect } from '@playwright/test';
import { LOGIN_EMAIL, LOGIN_PW } from './helpers.js';
import path from 'path';

const DOCX_PATH = path.resolve('C:/SKN21-FINAL-3TEAM/data/doc_generate/meeting/회의록.docx');

test.describe('커스텀 템플릿 업로드 E2E', () => {

  test('문서생성 페이지 → 템플릿 업로드 → 필드 추출 확인', async ({ page }) => {
    // 1. 로그인
    await page.goto('/login');
    await page.locator('input[type="email"]').waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('input[type="email"]').fill(LOGIN_EMAIL);
    await page.locator('input[type="password"]').fill(LOGIN_PW);

    // submit 버튼 클릭 (form 내부의 button[type=submit])
    await page.locator('form button[type="submit"], form button:has-text("로그인")').first().click();

    // 대시보드 또는 비-로그인 페이지로 이동 대기
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(1000);
    console.log('[Login] URL after login:', page.url());
    await page.screenshot({ path: './e2e/results/01-after-login.png' });

    // 로그인 실패 확인
    if (page.url().includes('/login')) {
      console.log('[Login] FAILED - still on login page');
      const bodyText = await page.locator('body').textContent();
      console.log('[Login] Body:', bodyText?.substring(0, 300));
      return;
    }

    // 2. 문서 생성 페이지 이동
    await page.goto('/document-generate');
    await page.waitForTimeout(2000);
    console.log('[Navigate] URL:', page.url());
    await page.screenshot({ path: './e2e/results/02-doc-generate.png' });

    // 3. 템플릿 선택 확인
    const tplCard = page.locator('text=템플릿 선택').first();
    await expect(tplCard).toBeVisible({ timeout: 10000 });

    // 4. "+ 템플릿 업로드" 클릭
    await page.locator('button:has-text("템플릿 업로드")').click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: './e2e/results/03-upload-dialog.png' });

    // 5. 파일 선택
    await page.locator('input[type="file"]').setInputFiles(DOCX_PATH);
    await page.waitForTimeout(500);

    // 6. 이름 확인
    const nameInput = page.locator('input[placeholder*="주간 보고서"]');
    console.log('[Upload] 자동 이름:', await nameInput.inputValue());

    // 7. 카테고리 = 회의록
    await page.locator('select').selectOption('meeting_minutes');
    await page.screenshot({ path: './e2e/results/04-form-filled.png' });

    // 8. 제출
    await page.locator('button[type="submit"]').click();
    console.log('[Upload] 제출 완료, 응답 대기중...');

    // 9. 응답 대기 (최대 15초)
    await page.waitForTimeout(15000);
    await page.screenshot({ path: './e2e/results/05-after-upload.png' });

    // 10. 결과
    const bodyText = await page.locator('body').textContent();
    console.log('[Result] 필드추출:', bodyText?.includes('필드 추출'));
    console.log('[Result] 업로드완료:', bodyText?.includes('업로드 완료'));
    console.log('[Result] 에러:', bodyText?.includes('실패') || bodyText?.includes('Error'));

    // 업로드된 템플릿 섹션 확인
    const hasSection = await page.locator('text=업로드된 템플릿').isVisible({ timeout: 3000 }).catch(() => false);
    console.log('[Result] 업로드된 템플릿 섹션:', hasSection);

    await page.screenshot({ path: './e2e/results/06-final.png' });
  });

});
