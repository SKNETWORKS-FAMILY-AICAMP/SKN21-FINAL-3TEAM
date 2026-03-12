// @ts-check
import { test, expect } from '@playwright/test';

/**
 * 문서 생성 디버깅 테스트
 * - 회의록 생성 요청 → 네트워크 요청/응답 캡처 → 무한로딩 원인 파악
 */

const LOGIN_EMAIL = 'jiyong1110@naver.com';
const LOGIN_PW = 'tlswldyd1!';

test('디버그: 회의록 AI 생성 네트워크 추적', async ({ page }) => {
  test.setTimeout(180_000);

  // 네트워크 로깅
  const apiLogs = [];
  page.on('request', req => {
    if (req.url().includes('/api/')) {
      apiLogs.push(`>> ${req.method()} ${req.url()}`);
    }
  });
  page.on('response', res => {
    if (res.url().includes('/api/')) {
      apiLogs.push(`<< ${res.status()} ${res.url()}`);
    }
  });
  page.on('requestfailed', req => {
    if (req.url().includes('/api/')) {
      apiLogs.push(`!! FAILED ${req.url()} ${req.failure()?.errorText}`);
    }
  });

  // 콘솔 로깅
  page.on('console', msg => {
    if (msg.type() === 'error') {
      apiLogs.push(`[CONSOLE ERROR] ${msg.text()}`);
    }
  });

  // 1. 로그인
  await page.goto('/login');
  await page.locator('input[type="email"]').fill(LOGIN_EMAIL);
  await page.locator('input[type="password"]').fill(LOGIN_PW);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL('**/dashboard', { timeout: 15_000 });
  console.log('✅ 로그인 성공');

  // 2. 문서 생성 페이지
  await page.goto('/document-generate');
  await page.locator('h1:has-text("문서 생성")').waitFor({ state: 'visible', timeout: 10_000 });
  console.log('✅ 문서 생성 페이지 로드');

  // 3. 회의록 선택
  await page.locator('button:has-text("회의록")').first().click();
  await page.locator('label:has-text("회의 제목")').waitFor({ state: 'visible', timeout: 10_000 });

  // 4. 폼 입력
  await page.locator('label:has-text("회의 제목")').locator('..').locator('input').fill('디버그 테스트 회의');

  // 팀 선택
  const teamSelect = page.locator('label:has-text("팀")').locator('..').locator('select');
  await teamSelect.waitFor({ state: 'visible', timeout: 5_000 });
  const teamOptions = teamSelect.locator('option');
  const optCount = await teamOptions.count();
  for (let i = 1; i < optCount; i++) {
    const val = await teamOptions.nth(i).getAttribute('value');
    if (val) {
      await teamSelect.selectOption(val);
      break;
    }
  }
  await page.waitForTimeout(500);

  // 참석자 선택
  await page.locator('text=팀원을 선택하세요').click();
  await page.waitForTimeout(500);
  const memberItems = page.locator('.absolute.top-full >> div.cursor-pointer');
  const memberCount = await memberItems.count();
  if (memberCount >= 1) {
    await memberItems.nth(0).click();
  }
  await page.waitForTimeout(300);
  await page.mouse.click(10, 10);
  await page.waitForTimeout(300);
  await page.evaluate(() => {
    const overlay = document.querySelector('.fixed.inset-0');
    if (overlay) overlay.click();
  });
  await page.waitForTimeout(300);

  // 회의 내용
  await page.locator('label:has-text("회의 내용")').locator('..').locator('textarea').fill(
    '디버그 테스트 회의 내용. vLLM 엔드포인트 연결 확인.'
  );

  console.log('✅ 폼 입력 완료');
  await page.screenshot({ path: 'e2e/results/debug-01-form-filled.png' });

  // API 로그 초기화 (생성 요청만 추적)
  apiLogs.length = 0;

  // 5. AI 회의록 생성 클릭
  console.log('🔄 AI 회의록 생성 클릭...');
  await page.locator('button:has-text("AI 회의록 생성")').click();

  // 로딩 상태 확인
  try {
    await expect(page.locator('button:has-text("AI 생성 중")')).toBeVisible({ timeout: 5_000 });
    console.log('✅ 로딩 상태 진입');
  } catch {
    console.log('⚠️ 로딩 상태 버튼 미감지');
  }

  await page.screenshot({ path: 'e2e/results/debug-02-loading.png' });

  // 6. 30초 대기하면서 10초마다 스크린샷 + 로그
  for (let i = 1; i <= 6; i++) {
    await page.waitForTimeout(10_000);
    console.log(`⏱️ ${i * 10}초 경과 — API 로그:`, JSON.stringify(apiLogs));
    await page.screenshot({ path: `e2e/results/debug-03-wait-${i * 10}s.png` });

    // 결과가 나왔는지 확인
    const resultVisible = await page.locator('text=생성된 회의록').isVisible().catch(() => false);
    const errorVisible = await page.locator('text=실패').isVisible().catch(() => false);
    const errorVisible2 = await page.locator('text=오류').isVisible().catch(() => false);

    if (resultVisible) {
      console.log('✅ 결과 표시됨!');
      break;
    }
    if (errorVisible || errorVisible2) {
      console.log('❌ 에러 표시됨!');
      break;
    }
  }

  // 최종 로그 출력
  console.log('📋 전체 API 로그:', JSON.stringify(apiLogs, null, 2));
  await page.screenshot({ path: 'e2e/results/debug-04-final.png', fullPage: true });
});
