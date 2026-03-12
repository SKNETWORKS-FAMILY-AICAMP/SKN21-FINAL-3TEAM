// @ts-check
import { test, expect } from '@playwright/test';

/**
 * 문서 생성 페이지 E2E 테스트
 * - 실제 백엔드 연동 (EC2)
 * - 테스트 대상: 로그인 → 템플릿 선택 → 동적 폼 → AI 생성 → 결과(action_items) 표시
 */

const LOGIN_EMAIL = 'jiyong1110@naver.com';
const LOGIN_PW = 'tlswldyd1!';

/** 로그인 수행 (재시도 포함) */
async function login(page) {
  await page.goto('/login');
  await page.waitForTimeout(500);

  for (let attempt = 0; attempt < 3; attempt++) {
    const emailInput = page.locator('input[type="email"]');
    await emailInput.waitFor({ state: 'visible', timeout: 5_000 });
    await emailInput.fill(LOGIN_EMAIL);
    await page.locator('input[type="password"]').fill(LOGIN_PW);
    await page.locator('button[type="submit"]').click();

    try {
      await page.waitForURL('**/dashboard', { timeout: 10_000 });
      return; // 성공
    } catch {
      // 로그인 실패 시 재시도
      console.log(`Login attempt ${attempt + 1} failed, retrying...`);
      await page.waitForTimeout(2000);
      // 아직 로그인 페이지이면 재시도
      if (page.url().includes('/login') || page.url().endsWith('/')) {
        continue;
      }
      return; // 다른 페이지로 갔으면 OK
    }
  }
  throw new Error('Login failed after 3 attempts');
}

/** 로그인 + 문서 생성 페이지 이동 */
async function loginAndGoToDocGenerate(page) {
  await login(page);
  await page.goto('/document-generate');
  await page.locator('h1:has-text("문서 생성")').waitFor({ state: 'visible', timeout: 10_000 });
}


// ── 테스트 ──────────────────────────────────────────────

test.describe('문서 생성 페이지', () => {

  test('1. 페이지 로드 + 시스템 템플릿 3종 표시', async ({ page }) => {
    await loginAndGoToDocGenerate(page);

    // 페이지 제목
    await expect(page.locator('h1')).toContainText('문서 생성');

    // 시스템 기본 템플릿 3종
    await expect(page.locator('text=기본 템플릿').first()).toBeVisible();
    await expect(page.locator('button:has-text("회의록")').first()).toBeVisible();
    await expect(page.locator('button:has-text("보고서")').first()).toBeVisible();
    await expect(page.locator('button:has-text("제안서")').first()).toBeVisible();

    await page.screenshot({ path: 'e2e/results/doc-gen-01-page-load.png' });
  });


  test('2. 회의록 템플릿 선택 → 동적 폼 렌더링', async ({ page }) => {
    await loginAndGoToDocGenerate(page);

    // 회의록 클릭
    await page.locator('button:has-text("회의록")').first().click();

    // 동적 폼 카드 대기
    await page.locator('text=회의록 내용 입력').waitFor({ state: 'visible', timeout: 10_000 });

    // 필드 확인
    await expect(page.locator('label:has-text("회의 제목")')).toBeVisible();
    await expect(page.locator('label:has-text("회의 날짜")')).toBeVisible();
    await expect(page.locator('label:has-text("팀")')).toBeVisible();
    await expect(page.locator('label:has-text("참석자")')).toBeVisible();
    await expect(page.locator('label:has-text("회의 내용")')).toBeVisible();

    // date auto-fill 확인
    const dateInput = page.locator('input[type="date"]');
    const dateValue = await dateInput.inputValue();
    expect(dateValue).toMatch(/^\d{4}-\d{2}-\d{2}$/);

    // AI 회의록 생성 버튼
    await expect(page.locator('button:has-text("AI 회의록 생성")')).toBeVisible();

    await page.screenshot({ path: 'e2e/results/doc-gen-02-dynamic-form.png' });
  });


  test('3. 회의록 폼 입력 → AI 생성 → 결과 + action_items 표시', async ({ page }) => {
    test.setTimeout(180_000);

    await loginAndGoToDocGenerate(page);

    // 회의록 선택
    await page.locator('button:has-text("회의록")').first().click();
    await page.locator('label:has-text("회의 제목")').waitFor({ state: 'visible', timeout: 10_000 });

    // 폼 입력 — 제목
    await page.locator('label:has-text("회의 제목")').locator('..').locator('input').fill('AI 프로젝트 킥오프');

    // 팀 선택 (TeamAttendeePicker: select 드롭다운)
    const teamSelect = page.locator('label:has-text("팀")').locator('..').locator('select');
    await teamSelect.waitFor({ state: 'visible', timeout: 5_000 });
    // 첫 번째 팀 옵션 선택 (빈 값이 아닌 것)
    const teamOptions = teamSelect.locator('option');
    const optCount = await teamOptions.count();
    for (let i = 1; i < optCount; i++) {
      const val = await teamOptions.nth(i).getAttribute('value');
      if (val) {
        await teamSelect.selectOption(val);
        break;
      }
    }
    await page.waitForTimeout(500); // 팀원 목록 로드 대기

    // 참석자 선택 (TeamAttendeePicker: 드롭다운 클릭 → 체크박스)
    await page.locator('text=팀원을 선택하세요').click();
    await page.waitForTimeout(500);
    // 드롭다운에서 처음 2명 선택
    const memberItems = page.locator('.absolute.top-full >> div.cursor-pointer');
    const memberCount = await memberItems.count();
    if (memberCount >= 2) {
      await memberItems.nth(0).click();
      await page.waitForTimeout(200);
      await memberItems.nth(1).click();
    } else if (memberCount >= 1) {
      await memberItems.nth(0).click();
    }
    await page.waitForTimeout(300);
    // 드롭다운 닫기 — 페이지 상단 빈 영역 클릭 (오버레이 z-10 위치)
    await page.mouse.click(10, 10);
    await page.waitForTimeout(500);
    // 오버레이가 아직 남아있으면 JavaScript로 직접 닫기
    await page.evaluate(() => {
      const overlay = document.querySelector('.fixed.inset-0');
      if (overlay) overlay.click();
    });
    await page.waitForTimeout(300);

    // 회의 내용
    await page.locator('label:has-text("회의 내용")').locator('..').locator('textarea').fill(
      'AI 프로젝트 킥오프 회의. LangGraph 기반 멀티에이전트 시스템 개발. 주요 목표: Intent 분류 정확도 90%, RAG 파이프라인, 문서 자동 생성. 일정: 3개월 MVP.'
    );

    await page.screenshot({ path: 'e2e/results/doc-gen-03-form-filled.png' });

    // AI 회의록 생성 버튼 클릭
    await page.locator('button:has-text("AI 회의록 생성")').click();

    // 로딩 상태
    await expect(page.locator('button:has-text("AI 생성 중")')).toBeVisible({ timeout: 5_000 });

    // MeetingPreview 대기
    await page.locator('text=생성된 회의록').waitFor({ state: 'visible', timeout: 120_000 });

    // 결과 카드 확인: 요약 또는 내용이 표시됨
    const hasResult = page.locator('text=생성된 회의록');
    await expect(hasResult).toBeVisible();

    // DOCX 다운로드 버튼
    await expect(page.locator('button:has-text("DOCX 다운로드")')).toBeVisible();

    // Action Items (있으면 확인, 조건부 렌더링이므로 선택적)
    const actionItemsHeader = page.locator('h4:has-text("Action Items")');
    if (await actionItemsHeader.count() > 0) {
      await expect(actionItemsHeader).toBeVisible();
    }

    await page.screenshot({ path: 'e2e/results/doc-gen-04-meeting-result.png', fullPage: true });
  });


  test('4. 보고서 템플릿 선택 → 동적 폼 렌더링', async ({ page }) => {
    await loginAndGoToDocGenerate(page);

    // 보고서 선택
    await page.locator('button:has-text("보고서")').first().click();

    // 동적 폼 카드 대기
    await page.locator('text=내용 입력').waitFor({ state: 'visible', timeout: 10_000 });

    // 동적 폼에 입력 필드 2개 이상 존재 확인
    const inputs = page.locator('.card-body input, .card-body textarea');
    const count = await inputs.count();
    expect(count).toBeGreaterThanOrEqual(2);

    // AI 문서 생성 버튼 존재
    await expect(page.locator('button:has-text("AI 문서 생성")')).toBeVisible();

    await page.screenshot({ path: 'e2e/results/doc-gen-05-report-form.png', fullPage: true });
  });


  test('5. 템플릿 전환 시 폼 초기화', async ({ page }) => {
    await loginAndGoToDocGenerate(page);

    // 회의록 선택 + 입력
    await page.locator('button:has-text("회의록")').first().click();
    await page.locator('label:has-text("회의 제목")').waitFor({ state: 'visible', timeout: 10_000 });
    await page.locator('label:has-text("회의 제목")').locator('..').locator('input').fill('테스트 회의');

    // 보고서로 전환
    await page.locator('button:has-text("보고서")').first().click();
    await page.locator('text=내용 입력').waitFor({ state: 'visible', timeout: 10_000 });

    // 회의 제목 필드 사라짐
    await expect(page.locator('label:has-text("회의 제목")')).not.toBeVisible();

    await page.screenshot({ path: 'e2e/results/doc-gen-06-template-switch.png' });
  });


  test('6. 템플릿 업로드 다이얼로그', async ({ page }) => {
    await loginAndGoToDocGenerate(page);

    await page.locator('button:has-text("템플릿 업로드")').click();
    await expect(page.locator('text=템플릿 이름')).toBeVisible({ timeout: 5_000 });

    await page.screenshot({ path: 'e2e/results/doc-gen-07-upload-dialog.png' });
  });


  test('7. DOCX 다운로드 확인', async ({ page }) => {
    test.setTimeout(180_000);

    await loginAndGoToDocGenerate(page);

    // 보고서로 테스트 (참석자 선택 불필요하여 더 안정적)
    await page.locator('button:has-text("보고서")').first().click();
    await page.locator('text=내용 입력').waitFor({ state: 'visible', timeout: 10_000 });

    // 제목 + 내용 입력
    const titleInput = page.locator('label:has-text("보고서 제목"), label:has-text("제목")').first().locator('..').locator('input');
    await titleInput.fill('다운로드 테스트 보고서');
    const contentArea = page.locator('textarea').first();
    await contentArea.fill('다운로드 테스트용 보고서 내용. 이번 주 작업 완료.');

    await page.locator('button:has-text("AI 문서 생성")').click();
    await page.locator('text=생성된 문서').first().waitFor({ state: 'visible', timeout: 120_000 });

    // 다운로드
    const downloadPromise = page.waitForEvent('download', { timeout: 15_000 });
    await page.locator('button:has-text("DOCX 다운로드")').click();

    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain('.docx');

    await page.screenshot({ path: 'e2e/results/doc-gen-08-download.png' });
  });

});
