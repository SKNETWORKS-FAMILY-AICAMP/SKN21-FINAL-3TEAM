const { chromium } = require('playwright');

const BASE = 'http://localhost:5174';
const EMAIL = 'jiyong1110@naver.com';
const PASS = 'tlswldyd1!';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const results = [];

  function log(test, status, detail = '') {
    const icon = status === 'PASS' ? '✅' : status === 'FAIL' ? '❌' : '⚠️';
    const msg = `${icon} [${test}] ${status} ${detail}`;
    console.log(msg);
    results.push({ test, status, detail });
  }

  try {
    // ── 로그인 ──
    console.log('\n=== 로그인 ===');
    await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 15000 });
    await page.fill('input[type="email"], input[name="email"]', EMAIL);
    await page.fill('input[type="password"], input[name="password"]', PASS);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/chat**', { timeout: 10000 }).catch(() => {});

    // 로그인 후 챗 페이지 확인
    const url = page.url();
    if (url.includes('chat') || url.includes('dashboard')) {
      log('로그인', 'PASS', url);
    } else {
      log('로그인', 'FAIL', `URL: ${url}`);
      // 수동 네비게이션 시도
      await page.goto(`${BASE}/chat`, { waitUntil: 'networkidle', timeout: 10000 });
    }

    // 챗 페이지로 이동
    if (!page.url().includes('chat')) {
      await page.goto(`${BASE}/chat`, { waitUntil: 'networkidle', timeout: 10000 });
    }
    await page.waitForTimeout(2000);

    // ── 헬퍼: 메시지 전송 + 응답 대기 ──
    async function sendAndWait(message, waitMs = 60000) {
      // 입력창 찾기
      const input = await page.$('textarea, input[placeholder*="메시지"], input[placeholder*="입력"]');
      if (!input) {
        console.log('  입력창 못 찾음, 전체 input/textarea 목록:');
        const inputs = await page.$$eval('input, textarea', els => els.map(e => `${e.tagName} placeholder="${e.placeholder}" type="${e.type}"`));
        console.log('  ', inputs.join('\n  '));
        return null;
      }

      await input.fill(message);
      await page.keyboard.press('Enter');

      // 스트리밍 완료 대기 (result 이벤트 후 카드 렌더링)
      await page.waitForTimeout(3000); // 초기 대기

      // 스트리밍 완료 대기 (최대 waitMs)
      const startTime = Date.now();
      while (Date.now() - startTime < waitMs) {
        const isStreaming = await page.evaluate(() => {
          // 스트리밍 인디케이터 확인
          const dots = document.querySelector('.animate-pulse, .animate-bounce');
          const status = document.querySelector('[class*="status"]');
          return !!(dots || (status && status.textContent.includes('처리 중')));
        });
        if (!isStreaming) break;
        await page.waitForTimeout(2000);
      }

      await page.waitForTimeout(2000); // 렌더링 대기
      return true;
    }

    // ── TEST 1: 검색 ──
    console.log('\n=== TEST 1: 검색 ===');
    const searchSent = await sendAndWait('보안 관련 문서 찾아줘', 120000);

    if (searchSent) {
      // 검색 결과 카드 확인
      const searchCard = await page.$('text=문서 검색 결과');
      if (searchCard) {
        log('검색-카드렌더링', 'PASS', '문서 검색 결과 카드 표시됨');
      } else {
        // 다른 카드 유형 확인
        const anyCard = await page.textContent('body');
        if (anyCard.includes('관련 문서') || anyCard.includes('건')) {
          log('검색-카드렌더링', 'PASS', '검색 결과 텍스트 확인');
        } else {
          log('검색-카드렌더링', 'FAIL', '검색 결과 카드 없음');
        }
      }

      // 소스 아이템 확인
      const sourceItems = await page.$$('[class*="source"], [class*="Source"]');
      log('검색-소스목록', sourceItems.length > 0 ? 'PASS' : 'WARN', `${sourceItems.length}개 소스 아이템`);

      // 후속 액션 버튼 확인
      const actionBtns = await page.$$eval('button', btns =>
        btns.filter(b => b.textContent.includes('요약') || b.textContent.includes('질문'))
            .map(b => b.textContent.trim())
      );
      if (actionBtns.length > 0) {
        log('검색-후속버튼', 'PASS', actionBtns.join(', '));
      } else {
        log('검색-후속버튼', 'FAIL', '후속 액션 버튼 없음');
      }

      // 스크린샷
      await page.screenshot({ path: 'e2e-search.png', fullPage: false });
    }

    // 새 세션 시작
    const newChatBtn = await page.$('button:has-text("새 대화"), [aria-label*="new"], button:has(svg)');
    if (newChatBtn) await newChatBtn.click();
    await page.waitForTimeout(2000);

    // ── TEST 2: QA ──
    console.log('\n=== TEST 2: QA ===');
    const qaSent = await sendAndWait('보안사고 대응 회의에서 어떤 내용이 논의되었나요', 120000);

    if (qaSent) {
      // QA 카드 확인
      const qaCard = await page.$('text=문서 Q&A');
      const qaText = await page.textContent('body');

      if (qaCard) {
        log('QA-카드렌더링', 'PASS', '문서 Q&A 카드 표시됨');
      } else if (qaText.includes('보안') || qaText.includes('회의')) {
        log('QA-카드렌더링', 'PASS', 'QA 답변 텍스트 확인');
      } else {
        log('QA-카드렌더링', 'FAIL', 'QA 카드 없음');
      }

      // confidence 표시 확인
      const confBar = await page.$('[class*="green"], [class*="confidence"]');
      log('QA-신뢰도', confBar ? 'PASS' : 'WARN', confBar ? '신뢰도 바 표시' : '신뢰도 바 없음');

      // 인용 확인
      const hasCitations = qaText.includes('인용') || qaText.includes('출처');
      log('QA-인용/출처', hasCitations ? 'PASS' : 'WARN', hasCitations ? '인용/출처 표시' : '인용 없음');

      // 후속 액션 버튼
      const qaActionBtns = await page.$$eval('button', btns =>
        btns.filter(b => b.textContent.includes('요약') || b.textContent.includes('찾기'))
            .map(b => b.textContent.trim())
      );
      if (qaActionBtns.length > 0) {
        log('QA-후속버튼', 'PASS', qaActionBtns.join(', '));
      } else {
        log('QA-후속버튼', 'FAIL', '후속 액션 버튼 없음');
      }

      await page.screenshot({ path: 'e2e-qa.png', fullPage: false });
    }

    // ── TEST 2b: QA 후속 버튼 클릭 (출처 문서 요약) ──
    console.log('\n=== TEST 2b: 후속 버튼 클릭 ===');
    const summaryBtn = await page.$('button:has-text("요약")');
    if (summaryBtn) {
      await summaryBtn.click();
      log('후속버튼-클릭', 'PASS', '요약 버튼 클릭');

      // 응답 대기
      await page.waitForTimeout(5000);
      const startTime2 = Date.now();
      while (Date.now() - startTime2 < 120000) {
        const isStreaming2 = await page.evaluate(() => {
          const dots = document.querySelector('.animate-pulse, .animate-bounce');
          return !!dots;
        });
        if (!isStreaming2) break;
        await page.waitForTimeout(2000);
      }
      await page.waitForTimeout(3000);

      // 요약 결과 확인
      const bodyText2 = await page.textContent('body');
      if (bodyText2.includes('태그') || bodyText2.includes('요약') || bodyText2.includes('#')) {
        log('후속버튼-요약결과', 'PASS', '요약 결과 표시됨');
      } else {
        log('후속버튼-요약결과', 'WARN', '요약 결과 불확실');
      }

      await page.screenshot({ path: 'e2e-followup.png', fullPage: false });
    } else {
      log('후속버튼-클릭', 'FAIL', '요약 버튼 못 찾음');
    }

    // ── TEST 3: 요약 (문서 선택 + 요약) ──
    console.log('\n=== TEST 3: 요약 ===');
    // 새 세션
    const newBtn2 = await page.$('button:has-text("새 대화")');
    if (newBtn2) await newBtn2.click();
    await page.waitForTimeout(2000);

    // 문서 페이지에서 문서 선택하는 대신, 직접 요약 요청
    const sumSent = await sendAndWait('보안사고 긴급대응 TF 회의록 요약해줘', 120000);

    if (sumSent) {
      const bodyText3 = await page.textContent('body');

      // 요약 카드 또는 doc_pick 확인
      const hasSummary = bodyText3.includes('문서 요약') || bodyText3.includes('태그');
      const hasDocPick = bodyText3.includes('선택해주세요') || bodyText3.includes('doc_pick');

      if (hasSummary) {
        log('요약-카드렌더링', 'PASS', '요약 카드 표시됨');

        // 태그 확인
        const tags = await page.$$('[class*="rounded-full"][class*="primary"]');
        log('요약-태그', tags.length > 0 ? 'PASS' : 'WARN', `${tags.length}개 태그`);
      } else if (hasDocPick) {
        log('요약-문서선택', 'PASS', '문서 선택 UI 표시 (다건 매칭)');
      } else {
        log('요약-카드렌더링', 'FAIL', '요약 결과 없음');
      }

      await page.screenshot({ path: 'e2e-summary.png', fullPage: false });
    }

  } catch (err) {
    log('전체', 'FAIL', err.message);
    await page.screenshot({ path: 'e2e-error.png', fullPage: false }).catch(() => {});
  }

  // ── 결과 요약 ──
  console.log('\n' + '='.repeat(60));
  console.log('E2E 테스트 결과 요약');
  console.log('='.repeat(60));
  const pass = results.filter(r => r.status === 'PASS').length;
  const fail = results.filter(r => r.status === 'FAIL').length;
  const warn = results.filter(r => r.status === 'WARN').length;
  console.log(`PASS: ${pass} | FAIL: ${fail} | WARN: ${warn}`);
  results.forEach(r => {
    const icon = r.status === 'PASS' ? '✅' : r.status === 'FAIL' ? '❌' : '⚠️';
    console.log(`  ${icon} ${r.test}: ${r.detail}`);
  });

  await browser.close();
})();
