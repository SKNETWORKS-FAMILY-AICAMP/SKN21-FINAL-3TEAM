// @ts-check
import { test, expect } from '@playwright/test';

const LOGIN_EMAIL = 'jiyong1110@naver.com';
const LOGIN_PW = 'tlswldyd1!';

async function loginAndGoToChat(page) {
  await page.goto('/');
  const emailInput = page.locator('input[type="email"]');
  if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
    await emailInput.fill(LOGIN_EMAIL);
    await page.locator('input[type="password"]').fill(LOGIN_PW);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL('**/dashboard', { timeout: 15_000 });
  }
  await page.goto('/chat');
  await page.locator('input[placeholder*="질문"]').waitFor({ state: 'visible', timeout: 10_000 });
}

async function sendAndCapture(page, message, label) {
  const input = page.locator('input[placeholder*="질문"]');
  await input.fill(message);
  await input.press('Enter');

  const start = Date.now();
  let prevText = '';
  let stableCount = 0;

  while (Date.now() - start < 60_000) {
    await page.waitForTimeout(2000);
    const allText = await page.locator('[data-main-scroll]').first().textContent().catch(() => '');
    if (allText === prevText && allText.length > 0) {
      stableCount++;
      if (stableCount >= 2) break;
    } else {
      stableCount = 0;
    }
    prevText = allText;
  }

  const botMessages = page.locator('[class*="items-start"]');
  const count = await botMessages.count();
  let botText = '';
  if (count > 0) {
    botText = await botMessages.last().textContent().catch(() => '');
  }

  console.log(`\n${'='.repeat(70)}`);
  console.log(`[${label}] 질문: "${message}"`);
  console.log(`${'─'.repeat(70)}`);
  console.log(`[${label}] 응답 (${botText.length}자):`);
  console.log(botText);
  console.log(`${'='.repeat(70)}`);

  return botText;
}

test.describe('Judgment Agent 디버그 테스트', () => {
  test.setTimeout(600_000);

  test('judgment 질문 7개 응답 검증', async ({ page }) => {
    const questions = [
      { msg: '연차 사용 가능한가요?', label: '연차', expect: ['연차', '휴가', '출근'] },
      { msg: '재택근무 규정 알려줘', label: '재택근무', expect: ['재택', '원격', 'VPN'] },
      { msg: '지각하면 어떻게 돼?', label: '지각', expect: ['지각', '근태', '징계'] },
      { msg: '퇴직금 어떻게 계산해?', label: '퇴직금', expect: ['퇴직', '근속', '급여'] },
      { msg: '야근 수당 규정 알려줘', label: '야근수당', expect: ['야근', '수당', '연장', '근로'] },
      { msg: '경조사 휴가 며칠이야?', label: '경조사', expect: ['경조', '휴가', '일'] },
      { msg: '인센티브 지급 기준이 뭐야?', label: '인센티브', expect: ['인센티브', '성과', '지급', '기준'] },
    ];

    const results = [];

    for (let i = 0; i < questions.length; i++) {
      const q = questions[i];

      // 매 질문마다 새 세션
      await loginAndGoToChat(page);
      const response = await sendAndCapture(page, q.msg, q.label);
      await page.screenshot({ path: `e2e/results/judgment_${String(i + 1).padStart(2, '0')}_${q.label}.png`, fullPage: true });

      // 검증
      const has1bu = response.includes('## 1부');
      const has2bu = response.includes('## 2부');
      const hasKeyword = q.expect.some(kw => response.includes(kw));
      const isClarify = response.includes('다음 중 어느 것에 가까운가요');
      const isError = response.includes('오류') || response.includes('에러') || response.length < 20;

      results.push({
        label: q.label,
        len: response.length,
        hasKeyword,
        has1bu,
        has2bu,
        isClarify,
        isError,
      });
    }

    // 최종 요약
    console.log('\n\n' + '='.repeat(70));
    console.log('===== Judgment Agent 테스트 결과 요약 =====');
    console.log('='.repeat(70));
    let pass = 0;
    let fail = 0;
    for (const r of results) {
      const issues = [];
      if (r.has1bu) issues.push('"## 1부" 헤더 노출');
      if (r.has2bu) issues.push('"## 2부" 헤더 노출');
      if (r.isClarify) issues.push('clarify로 빠짐');
      if (r.isError) issues.push('에러/빈응답');
      if (!r.hasKeyword) issues.push('핵심 키워드 없음');

      const status = issues.length === 0 ? 'PASS' : 'FAIL';
      if (status === 'PASS') pass++; else fail++;

      console.log(`${status}  ${r.label.padEnd(10)} ${r.len}자  ${issues.length > 0 ? issues.join(', ') : '정상'}`);
    }
    console.log(`\n총: ${pass} PASS / ${fail} FAIL (${results.length}개)`);
    console.log('='.repeat(70));

    // 하나라도 clarify로 빠지면 실패
    for (const r of results) {
      expect(r.isClarify, `${r.label}: clarify로 빠짐`).toBe(false);
    }
  });
});
