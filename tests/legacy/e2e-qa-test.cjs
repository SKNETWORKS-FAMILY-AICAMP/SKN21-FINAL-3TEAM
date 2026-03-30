const { chromium } = require('playwright');

const BASE = 'http://localhost:5174';
const EMAIL = 'jiyong1110@naver.com';
const PASS = 'tlswldyd1!';

const QA_QUESTIONS = [
  {
    question: '연차 규정에 대해 알려줘',
    expectKeywords: ['연차', '일'],
    description: 'QA 기본 — 규정 문서 질의',
  },
  {
    question: '보안 규정에서 USB 사용 관련 내용이 뭐야?',
    expectKeywords: ['USB', '보안'],
    description: 'QA 세부 — 특정 키워드 질의',
  },
];

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
    console.log('\n=== 1. 로그인 ===');
    await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 15000 });
    await page.fill('input[type="email"], input[name="email"]', EMAIL);
    await page.fill('input[type="password"], input[name="password"]', PASS);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(3000);

    const url = page.url();
    log('로그인', url.includes('login') ? 'FAIL' : 'PASS', url);

    // chat 페이지로 이동
    await page.goto(`${BASE}/chat`, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(3000);
    console.log('  현재 URL:', page.url());

    // 입력창 확인
    const inputSelector = 'textarea, input[placeholder*="메시지"], input[placeholder*="입력"], input[placeholder*="질문"]';
    const hasInput = await page.$(inputSelector);
    if (!hasInput) {
      // 디버깅: 페이지 내 모든 input/textarea 확인
      const allInputs = await page.$$eval('input, textarea', els =>
        els.map(e => `${e.tagName} type="${e.type}" placeholder="${e.placeholder}" class="${e.className?.substring(0, 50)}"`));
      console.log('  입력창 후보:', allInputs);
      await page.screenshot({ path: 'e2e-qa-debug.png' });
      console.log('  디버그 스크린샷: e2e-qa-debug.png');
    }

    // ── 헬퍼: 메시지 전송 + 응답 대기 ──
    async function sendAndWait(message, waitMs = 180000) {
      // 입력창 찾기 (더 넓은 셀렉터)
      let input = await page.$('textarea');
      if (!input) input = await page.$('input[type="text"]');
      if (!input) {
        console.log('  입력창 못 찾음');
        await page.screenshot({ path: 'e2e-qa-no-input.png' });
        return null;
      }

      // 입력 + 전송
      await input.click();
      await input.fill(message);
      await page.waitForTimeout(500);

      // Enter로 전송 또는 전송 버튼 클릭
      const sendBtn = await page.$('button[type="submit"], button[aria-label*="전송"], button[aria-label*="send"]');
      if (sendBtn) {
        await sendBtn.click();
      } else {
        await page.keyboard.press('Enter');
      }

      console.log('  메시지 전송 완료, 응답 대기 중... (최대 3분)');
      await page.waitForTimeout(10000); // RunPod cold start 대기

      // SSE 응답 완료 대기
      const startTime = Date.now();
      let prevText = '';
      let stableCount = 0;

      while (Date.now() - startTime < waitMs) {
        // 페이지 내 마지막 봇 메시지 텍스트 추출
        const currentText = await page.evaluate(() => {
          // surface-card 클래스를 가진 카드들 찾기
          const cards = document.querySelectorAll('.bg-surface-card, [class*="surface-card"]');
          if (cards.length === 0) return '';
          const lastCard = cards[cards.length - 1];
          return lastCard.textContent || '';
        });

        const elapsed = Math.round((Date.now() - startTime) / 1000);

        if (currentText.length > 20 && currentText === prevText) {
          stableCount++;
          if (stableCount >= 3) {
            console.log(`  응답 안정화 (${elapsed}초)`);
            break;
          }
        } else {
          stableCount = 0;
          if (currentText.length > prevText.length) {
            console.log(`  스트리밍 중... ${currentText.length}자 (${elapsed}초)`);
          }
        }
        prevText = currentText;
        await page.waitForTimeout(3000);
      }

      if (stableCount < 3) {
        console.log(`  타임아웃 (${Math.round(waitMs / 1000)}초)`);
      }

      await page.waitForTimeout(2000);
      return true;
    }

    // ── QA 테스트 실행 ──
    for (let i = 0; i < QA_QUESTIONS.length; i++) {
      const { question, expectKeywords, description } = QA_QUESTIONS[i];
      console.log(`\n=== ${i + 2}. ${description} ===`);
      console.log(`  질문: "${question}"`);

      const sent = await sendAndWait(question);
      if (!sent) {
        log(description, 'FAIL', '메시지 전송 실패');
        continue;
      }

      // 스크린샷
      await page.screenshot({ path: `e2e-qa-${i + 1}.png` });
      console.log(`  스크린샷: e2e-qa-${i + 1}.png`);

      // 마지막 카드에서 데이터 추출
      const responseData = await page.evaluate(() => {
        const cards = document.querySelectorAll('.bg-surface-card, [class*="surface-card"]');
        const result = {
          text: '',
          hasQACard: false,
          hasSources: false,
          sourceCount: 0,
          hasHint: false,
          hintText: '',
          hasOldCitations: false,
          hasOldConfBar: false,
        };

        if (cards.length === 0) return result;
        const lastCard = cards[cards.length - 1];
        result.text = lastCard.textContent || '';

        // QA 카드 확인
        result.hasQACard = result.text.includes('문서 Q&A');

        // 참고 문서 섹션
        const sourceMatch = result.text.match(/참고 문서\s*\((\d+)건\)/);
        if (sourceMatch) {
          result.hasSources = true;
          result.sourceCount = parseInt(sourceMatch[1]);
        }

        // 하단 힌트
        const hints = ['관련도가 높은', '정확하지 않을', '관련도가 낮은'];
        for (const h of hints) {
          if (result.text.includes(h)) {
            result.hasHint = true;
            result.hintText = h;
            break;
          }
        }

        // 구 UI 잔존 체크
        result.hasOldCitations = result.text.includes('인용 (');
        const header = lastCard.querySelector('[class*="border-b"]');
        if (header) result.hasOldConfBar = /%/.test(header.textContent || '');

        return result;
      });

      console.log(`  응답 길이: ${responseData.text.length}자`);
      console.log(`  QA 카드: ${responseData.hasQACard ? 'Y' : 'N'}`);
      console.log(`  참고 문서: ${responseData.hasSources ? `${responseData.sourceCount}건` : 'N'}`);
      console.log(`  하단 힌트: ${responseData.hasHint ? responseData.hintText : 'N'}`);
      console.log(`  구 인용 섹션: ${responseData.hasOldCitations ? '⚠️ 잔존' : 'N (제거됨)'}`);
      console.log(`  구 confidence 바: ${responseData.hasOldConfBar ? '⚠️ 잔존' : 'N (제거됨)'}`);

      if (responseData.text.length < 10) {
        log(description, 'FAIL', '응답 없음');
        continue;
      }

      // 키워드 매칭
      const matched = expectKeywords.filter(kw => responseData.text.includes(kw));
      const rate = matched.length / expectKeywords.length;
      console.log(`  키워드 매칭: ${matched.join(', ')} (${Math.round(rate * 100)}%)`);

      // UI 검증
      const issues = [];
      if (!responseData.hasQACard) issues.push('QA카드 없음');
      if (responseData.hasOldCitations) issues.push('구 인용 잔존');
      if (responseData.hasOldConfBar) issues.push('구 confidence 바 잔존');

      const preview = responseData.text.replace(/\s+/g, ' ').substring(0, 250);
      console.log(`  미리보기: ${preview}`);

      if (rate >= 0.5 && issues.length === 0) {
        log(description, 'PASS', `키워드 ${Math.round(rate * 100)}% | sources ${responseData.sourceCount}건`);
      } else if (rate >= 0.3) {
        log(description, 'WARN', `키워드 ${Math.round(rate * 100)}% | ${issues.join(', ') || 'UI OK'}`);
      } else {
        log(description, 'FAIL', `키워드 ${Math.round(rate * 100)}% | ${issues.join(', ') || 'UI OK'}`);
      }

      await page.waitForTimeout(2000);
    }

  } catch (err) {
    console.error('테스트 에러:', err.message);
    await page.screenshot({ path: 'e2e-qa-error.png' });
  } finally {
    console.log('\n' + '='.repeat(50));
    console.log('QA E2E 테스트 결과 요약');
    console.log('='.repeat(50));
    const pass = results.filter(r => r.status === 'PASS').length;
    const warn = results.filter(r => r.status === 'WARN').length;
    const fail = results.filter(r => r.status === 'FAIL').length;
    console.log(`PASS: ${pass} | WARN: ${warn} | FAIL: ${fail} | Total: ${results.length}`);
    results.forEach(r => {
      const icon = r.status === 'PASS' ? '✅' : r.status === 'FAIL' ? '❌' : '⚠️';
      console.log(`  ${icon} ${r.test}: ${r.detail}`);
    });
    await browser.close();
  }
})();
