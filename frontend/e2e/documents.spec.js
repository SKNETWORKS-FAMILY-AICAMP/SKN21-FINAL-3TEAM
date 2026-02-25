import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import { login } from './helpers.js';

test.describe('문서 관리 페이지 테스트', () => {

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('1. 문서 관리 페이지 접근 및 기본 UI 확인', async ({ page }) => {
    await page.goto('/documents');
    await page.waitForLoadState('networkidle');

    // 페이지 제목
    await expect(page.locator('h1:has-text("문서 관리")')).toBeVisible();
    // 검색 입력창 — placeholder가 동적이므로 "검색" 포함 여부로 매칭
    await expect(page.locator('input[placeholder*="검색"]')).toBeVisible();
    // 검색 버튼
    await expect(page.locator('button:has-text("검색")')).toBeVisible();
    // 문서 목록 영역
    await expect(page.locator('text=문서 목록')).toBeVisible();
    // 업로드 영역
    await expect(page.locator('text=파일을 끌어다 놓거나 클릭하여 업로드')).toBeVisible();

    await page.screenshot({ path: 'e2e/results/docs_01_page_loaded.png' });
  });

  test('2. 문서 업로드 테스트 (txt 파일)', async ({ page }) => {
    await page.goto('/documents');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // 업로드 전 문서 수 확인
    const beforeText = await page.locator('[data-testid="doc-count"]').textContent();
    console.log('업로드 전:', beforeText);

    // 테스트용 txt 파일 생성
    const testFilePath = path.join(process.cwd(), 'e2e', 'test_upload_search.txt');
    fs.writeFileSync(testFilePath, '플레이라이트 검색 테스트 문서입니다.\n이 파일은 E2E 테스트용으로 생성되었습니다.\n키워드: Playwright, 문서검색, 테스트');

    // dialog 핸들러 등록
    page.on('dialog', async (dialog) => {
      console.log('Dialog:', dialog.message());
      await dialog.accept();
    });

    // 파일 업로드
    const fileInput = page.locator('input[type="file"]#file-upload');
    await fileInput.setInputFiles(testFilePath);

    // 업로드 처리 + alert 대기
    await page.waitForTimeout(8000);

    // 업로드 후 문서 수 확인
    const afterText = await page.locator('[data-testid="doc-count"]').textContent();
    console.log('업로드 후:', afterText);

    await page.screenshot({ path: 'e2e/results/docs_02_after_upload.png' });

    // 정리
    if (fs.existsSync(testFilePath)) fs.unlinkSync(testFilePath);
  });

  test('3. 문서 목록 로드 확인', async ({ page }) => {
    await page.goto('/documents');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // doc-count testid로 확인
    const countEl = page.locator('[data-testid="doc-count"]');
    await expect(countEl).toBeVisible();
    const countText = await countEl.textContent();
    console.log('문서 수:', countText);

    await page.screenshot({ path: 'e2e/results/docs_03_document_list.png' });
  });

  test('4. 문서 검색 기능 테스트 (제목 검색)', async ({ page }) => {
    await page.goto('/documents');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // 현재 문서 수
    const beforeText = await page.locator('[data-testid="doc-count"]').textContent();
    const beforeCount = parseInt(beforeText.match(/\d+/)?.[0] || '0');
    console.log('검색 전:', beforeText);

    // 없는 키워드로 검색 → 0개 되어야 함
    const searchInput = page.locator('input[placeholder*="검색"]');
    await searchInput.fill('ZZZZNOTEXIST999');
    await page.locator('button:has-text("검색")').click();
    await page.waitForTimeout(1000);

    const noResultText = await page.locator('[data-testid="doc-count"]').textContent();
    const noResultCount = parseInt(noResultText.match(/\d+/)?.[0] || '0');
    console.log('없는 키워드 검색:', noResultText);

    await page.screenshot({ path: 'e2e/results/docs_04_search_no_result.png' });

    expect(noResultCount).toBe(0);

    // 검색 초기화
    await searchInput.clear();
    await page.locator('button:has-text("검색")').click();
    await page.waitForTimeout(1000);

    const resetText = await page.locator('[data-testid="doc-count"]').textContent();
    const resetCount = parseInt(resetText.match(/\d+/)?.[0] || '0');
    console.log('검색 초기화:', resetText);

    await page.screenshot({ path: 'e2e/results/docs_05_search_reset.png' });

    expect(resetCount).toBe(beforeCount);
  });

  test('5. 스코프 필터 테스트 (전체/회사/팀)', async ({ page }) => {
    await page.goto('/documents');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const totalText = await page.locator('[data-testid="doc-count"]').textContent();
    console.log('전체:', totalText);
    await page.screenshot({ path: 'e2e/results/docs_06_scope_all.png' });

    // CustomSelect "전체" 클릭해서 드롭다운 열기
    // CustomSelect는 button으로 렌더됨 → "전체" 텍스트를 가진 버튼 찾기
    const scopeButtons = page.locator('button:has-text("전체")');
    const count = await scopeButtons.count();
    console.log('전체 버튼 수:', count);

    if (count > 0) {
      // 문서 목록 내 스코프 셀렉트 클릭
      await scopeButtons.first().click();
      await page.waitForTimeout(500);

      // "회사" 옵션 선택 — CustomSelect는 button으로 렌더
      const companyOption = page.locator('button:has-text("회사")');
      if (await companyOption.first().isVisible({ timeout: 2000 }).catch(() => false)) {
        await companyOption.first().click();
        await page.waitForTimeout(1000);
        const companyText = await page.locator('[data-testid="doc-count"]').textContent();
        console.log('회사 필터:', companyText);
        await page.screenshot({ path: 'e2e/results/docs_07_scope_company.png' });
      }
    }
  });

  test('6. 문서 상세보기 테스트', async ({ page }) => {
    await page.goto('/documents');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // 테이블 행 찾기
    const rows = page.locator('table tbody tr');
    const rowCount = await rows.count();
    console.log('테이블 행 수:', rowCount);

    if (rowCount > 0) {
      await rows.first().click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'e2e/results/docs_08_document_detail.png' });
    } else {
      console.log('문서가 없어서 상세보기 스킵');
      await page.screenshot({ path: 'e2e/results/docs_08_no_documents.png' });
    }
  });
});
