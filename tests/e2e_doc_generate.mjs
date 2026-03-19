import { chromium } from 'playwright';

const FRONT = 'http://localhost:5173';
const BACK = 'http://localhost:8000';
const EMAIL = 'jiyong1110@naver.com';
const PASS = 'tlswldyd1!';
const DIR = 'tests/screenshots';

async function run() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

  // 1. 로그인 (API로 토큰 획득 → localStorage 주입)
  console.log('[1] 로그인...');
  const resp = await fetch(`${BACK}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: EMAIL, password: PASS }),
  });
  const { access_token, user_name } = await resp.json();
  console.log(`  토큰: ${access_token ? 'OK' : 'FAIL'}, 사용자: ${user_name}`);

  await page.goto(FRONT);
  await page.evaluate(({ token, name }) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('cached_user', JSON.stringify({ id: 6, name, team: '개발' }));
  }, { token: access_token, name: user_name });

  // 2. 문서 생성 페이지
  console.log('[2] 문서 생성 페이지...');
  await page.goto(`${FRONT}/document-generate`);
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${DIR}/01_doc_generate.png`, fullPage: true });
  console.log(`  URL: ${page.url()}`);

  // 3. 시스템 템플릿 - 회의록
  console.log('[3] 시스템 - 회의록...');
  const meetBtn = page.locator('button', { hasText: '회의록' }).first();
  if (await meetBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await meetBtn.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${DIR}/02_system_meeting.png`, fullPage: true });
    console.log('  OK');
  } else {
    console.log('  회의록 버튼 없음');
  }

  // 4. 시스템 템플릿 - 보고서
  console.log('[4] 시스템 - 보고서...');
  const repBtn = page.locator('button', { hasText: '보고서' }).first();
  if (await repBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await repBtn.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${DIR}/03_system_report.png`, fullPage: true });
    console.log('  OK');
  }

  // 5. 커스텀 템플릿
  console.log('[5] 커스텀 템플릿...');
  const customBtn = page.locator('button', { hasText: 'korean_key_test' }).first();
  if (await customBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await customBtn.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${DIR}/04_custom_selected.png`, fullPage: true });
    console.log('  선택됨');

    // 자연어 입력 영역 (스크롤 후 확인)
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(500);
    const textarea = page.locator('textarea[placeholder*="자유롭게"], textarea[placeholder*="예:"]').first();
    if (await textarea.isVisible({ timeout: 3000 }).catch(() => false)) {
      await textarea.fill('오늘 오후 3시에 회의실B에서 김철수, 이영희 참석해서 신규 프로젝트 킥오프 회의했어. DB 설계 이번주까지 끝내기로 했고 API 문서는 김철수가 담당하기로 함.');
      await page.waitForTimeout(500);
      await page.screenshot({ path: `${DIR}/05_custom_input.png`, fullPage: true });
      console.log('  자연어 입력 완료');

      // AI 채우기 버튼 확인
      const fillBtn = page.locator('button', { hasText: 'AI가 필드 채우기' }).first();
      console.log(`  AI 채우기 버튼: ${await fillBtn.isVisible() ? '있음' : '없음'}`);
    } else {
      console.log('  자연어 입력 textarea 없음');
    }

    // 필드 폼 확인
    const inputs = await page.locator('.card-body input, .card-body textarea').count();
    console.log(`  필드 입력 요소: ${inputs}개`);
  } else {
    console.log('  커스텀 템플릿 없음 — 업로드된 템플릿 섹션 확인');
    await page.screenshot({ path: `${DIR}/04_no_custom.png`, fullPage: true });
  }

  // 6. 업로드 다이얼로그
  console.log('[6] 업로드 다이얼로그...');
  const upBtn = page.locator('button', { hasText: '템플릿 업로드' }).first();
  if (await upBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await upBtn.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${DIR}/06_upload_dialog.png`, fullPage: true });
    console.log('  OK');
    await page.locator('button', { hasText: '취소' }).first().click().catch(() => {});
  }

  console.log('\n완료!');
  await browser.close();
}

run().catch(e => { console.error(e); process.exit(1); });
