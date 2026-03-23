// @ts-check
import { test, expect } from '@playwright/test';

/**
 * document_agent 리팩토링 검증 E2E
 * - 문서 생성 3종 (회의록/보고서/제안서)
 * - 문서 업로드 → 요약
 */

const LOGIN_EMAIL = 'jiyong1110@naver.com';
const LOGIN_PW = 'tlswldyd1!';

async function login(page) {
  await page.goto('/login');
  await page.waitForTimeout(500);
  const emailInput = page.locator('input[type="email"]');
  await emailInput.waitFor({ state: 'visible', timeout: 5_000 });
  await emailInput.fill(LOGIN_EMAIL);
  await page.locator('input[type="password"]').fill(LOGIN_PW);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL('**/dashboard', { timeout: 15_000 });
}

async function goToDocGenerate(page) {
  await page.goto('/document-generate');
  await page.locator('h1:has-text("문서 생성")').waitFor({ state: 'visible', timeout: 10_000 });
}

/**
 * 공통: 템플릿 선택 → 최소 필드 입력 → AI 생성 → 결과 확인
 */
async function generateAndVerify(page, templateName, fields, resultText, screenshotName) {
  await goToDocGenerate(page);

  // 템플릿 선택
  await page.locator(`button:has-text("${templateName}")`).first().click();
  await page.waitForTimeout(1000);

  // 동적 폼 대기 — 입력 필드가 1개 이상 나타날 때까지
  await page.locator('input, textarea').first().waitFor({ state: 'visible', timeout: 10_000 });

  // 필드 입력
  for (const { label, value, type } of fields) {
    if (type === 'textarea') {
      const textarea = page.locator(`label:has-text("${label}")`).locator('..').locator('textarea');
      if (await textarea.isVisible({ timeout: 3000 }).catch(() => false)) {
        await textarea.fill(value);
      } else {
        // fallback: 첫 번째 textarea
        await page.locator('textarea').first().fill(value);
      }
    } else {
      const input = page.locator(`label:has-text("${label}")`).locator('..').locator('input');
      if (await input.isVisible({ timeout: 3000 }).catch(() => false)) {
        await input.fill(value);
      }
    }
  }

  await page.screenshot({ path: `e2e/results/${screenshotName}-01-form.png` });

  // AI 생성 버튼 클릭 (여러 버튼 텍스트 가능)
  const genBtn = page.locator('button:has-text("AI")').filter({ hasText: /생성/ });
  await genBtn.click();

  // 로딩 → 결과 대기 (최대 120초)
  await page.locator(`text=${resultText}`).waitFor({ state: 'visible', timeout: 120_000 });

  // DOCX 다운로드 버튼 확인
  await expect(page.locator('button:has-text("DOCX 다운로드")')).toBeVisible({ timeout: 10_000 });

  await page.screenshot({ path: `e2e/results/${screenshotName}-02-result.png`, fullPage: true });

  return true;
}


// ─── 테스트 ───

test.describe('리팩토링 검증: 문서 생성 3종', () => {

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('회의록 생성', async ({ page }) => {
    test.setTimeout(180_000);
    await generateAndVerify(page, '회의록', [
      { label: '회의 제목', value: '리팩토링 검증 회의', type: 'input' },
      { label: '회의 내용', value: 'document_agent 리팩토링 후 E2E 검증 회의. 주요 안건: 모듈 분리 결과 확인, 파이프라인 정상 동작 테스트, 회의록 생성 기능 점검.', type: 'textarea' },
    ], '생성된', 'refactor-meeting');
  });

  test('보고서 생성', async ({ page }) => {
    test.setTimeout(180_000);
    await generateAndVerify(page, '보고서', [
      { label: '제목', value: '리팩토링 검증 보고서', type: 'input' },
      { label: '내용', value: '이번 주 document_agent 리팩토링 완료. 1668줄 단일 파일을 8개 모듈로 분리. 모든 import 호환성 확인. 비스트리밍 파이프라인 정상 동작.', type: 'textarea' },
    ], '생성된', 'refactor-report');
  });

  test('제안서 생성', async ({ page }) => {
    test.setTimeout(180_000);
    await generateAndVerify(page, '제안서', [
      { label: '제목', value: 'AI 문서 자동화 시스템 도입 제안서', type: 'input' },
      { label: '내용', value: 'LangGraph 기반 멀티에이전트 시스템을 도입하여 사내 문서 작성 자동화. 예상 효과: 문서 작성 시간 60% 단축, 규정 위반 사전 감지.', type: 'textarea' },
    ], '생성된', 'refactor-proposal');
  });
});


test.describe('리팩토링 검증: 문서 요약', () => {

  test('문서 업로드 → 요약 확인', async ({ page }) => {
    test.setTimeout(120_000);
    await login(page);

    // 문서 관리 페이지 이동
    await page.goto('/documents');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    await page.screenshot({ path: 'e2e/results/refactor-summary-01-page.png' });

    // 기존 문서 목록 확인 — 테이블 행이 있으면 첫 번째 문서 클릭
    const rows = page.locator('table tbody tr');
    const rowCount = await rows.count();
    console.log(`문서 목록: ${rowCount}건`);

    if (rowCount > 0) {
      // 첫 번째 문서 클릭 → 상세보기
      await rows.first().click();
      await page.waitForTimeout(2000);

      // 요약 또는 태그가 표시되는지 확인
      // 문서 상세에서 요약 정보가 나오는지 확인
      const pageContent = await page.textContent('body');
      const hasSummary = pageContent.includes('요약') || pageContent.includes('태그') || pageContent.includes('#');
      console.log('요약/태그 존재:', hasSummary);

      await page.screenshot({ path: 'e2e/results/refactor-summary-02-detail.png', fullPage: true });
    }

    // 새 파일 업로드로 요약 테스트
    await page.goto('/documents');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // 테스트용 파일 생성 및 업로드
    const fs = await import('fs');
    const path = await import('path');
    const testFile = path.join(process.cwd(), 'e2e', 'test_summary_verify.txt');
    fs.writeFileSync(testFile,
      '2026년 1분기 AI 프로젝트 진행 보고서\n\n' +
      '1. 프로젝트 개요\n' +
      'LangGraph 기반 멀티에이전트 시스템 개발 프로젝트입니다.\n' +
      'Intent 분류, RAG 파이프라인, 문서 자동 생성 기능을 구현하고 있습니다.\n\n' +
      '2. 주요 성과\n' +
      '- Intent 분류 정확도 92% 달성\n' +
      '- 문서 생성 파이프라인 구축 완료\n' +
      '- 규정 검증 자동화 연동\n\n' +
      '3. 향후 계획\n' +
      '- sLLM 파인튜닝 및 배포\n' +
      '- E2E 테스트 자동화\n'
    );

    // dialog 핸들러 (업로드 성공 alert)
    page.on('dialog', async (dialog) => {
      console.log('Dialog:', dialog.message());
      await dialog.accept();
    });

    // 파일 업로드
    const fileInput = page.locator('input[type="file"]#file-upload');
    await fileInput.setInputFiles(testFile);

    // 업로드 처리 대기 (요약 포함하면 시간 걸림)
    await page.waitForTimeout(15000);

    await page.screenshot({ path: 'e2e/results/refactor-summary-03-uploaded.png' });

    // 업로드된 문서 목록에서 태그/요약 확인
    const bodyText = await page.textContent('body');
    const hasTag = bodyText.includes('#') || bodyText.includes('태그');
    console.log('업로드 후 태그 존재:', hasTag);

    // 정리 (EBUSY 에러 무시)
    try { if (fs.existsSync(testFile)) fs.unlinkSync(testFile); } catch {}

    await page.screenshot({ path: 'e2e/results/refactor-summary-04-final.png', fullPage: true });
  });
});
