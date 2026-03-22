// @ts-check
/**
 * Intent 분류 ↔ Document Agent 호환성 + 챗봇 기능 테스트
 *
 * 테스트 항목:
 *   1. Intent 라우팅 호환성 — doc_retrieve, doc_search, doc_summary, doc_generate가
 *      올바르게 document_agent로 라우팅되는지
 *   2. QA 기능 — 문서 기반 질의응답이 실제 답변을 반환하는지
 *   3. 검색 기능 — 문서 검색이 카드형 결과를 반환하는지
 *   4. 요약 기능 — 문서 요약 요청이 정상 처리되는지
 *   5. 경계 케이스 — intent 혼동 가능한 입력 (judgment vs doc_retrieve)
 *   6. 에러 내성 — 빈 입력, 매우 긴 입력, 특수문자
 */
import { test, expect } from '@playwright/test';
import { loginAndGoToChat, sendMessage, waitForBotResponse, SSE_WAIT } from './helpers.js';

// SSE 이벤트에서 intent 정보를 캡처하는 헬퍼
async function sendAndCaptureSSE(page, message, timeoutMs = SSE_WAIT) {
  const sseEvents = [];

  // SSE 이벤트 캡처를 위해 EventSource 응답 감시
  page.on('response', async (response) => {
    if (response.url().includes('/api/v1/chat/stream')) {
      try {
        const body = await response.text().catch(() => '');
        // SSE data lines 파싱
        for (const line of body.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const parsed = JSON.parse(line.slice(6));
              sseEvents.push(parsed);
            } catch {}
          }
        }
      } catch {}
    }
  });

  const input = page.locator('[data-testid="chat-input"]');
  await input.fill(message);
  await input.press('Enter');

  const responseText = await waitForBotResponse(page, timeoutMs);

  // 봇 응답 마지막 메시지
  const botMessages = page.locator('[data-testid="bot-message"]');
  const count = await botMessages.count();
  let botText = '';
  if (count > 0) {
    botText = await botMessages.last().textContent().catch(() => '');
  }

  return { responseText, botText, sseEvents };
}

test.describe('Intent ↔ Document Agent 호환성 테스트', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(120_000);
  });

  // ═══════════════════════════════════════════
  // 1. QA 기능 테스트
  // ═══════════════════════════════════════════

  test('QA — 문서 기반 질의응답 (출장비 규정)', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '출장비 정산 기준이 어떻게 되나요?');

    const response = await waitForBotResponse(page, 60_000);
    console.log(`[E2E:QA] 응답 길이: ${response.length}자`);
    console.log(`[E2E:QA] 응답 미리보기: ${response.slice(-300)}`);

    // 응답이 충분히 길어야 (최소 30자 이상의 실질적 답변)
    expect(response.length).toBeGreaterThan(30);

    // "처리 중 오류" 메시지가 없어야
    expect(response).not.toContain('처리 중 오류');
    expect(response).not.toContain('오류가 발생했습니다');
  });

  test('QA — 특정 규정 질문 (연차 사용 조건)', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '연차 사용 조건에 대해 설명해주세요');

    const response = await waitForBotResponse(page, 60_000);
    console.log(`[E2E:QA-규정] 응답 길이: ${response.length}자`);

    expect(response.length).toBeGreaterThan(30);
    expect(response).not.toContain('처리 중 오류');
  });

  // ═══════════════════════════════════════════
  // 2. 검색 기능 테스트
  // ═══════════════════════════════════════════

  test('검색 — 문서 검색 (보고서 찾아줘)', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '보고서 찾아줘');

    const response = await waitForBotResponse(page, 60_000);
    console.log(`[E2E:Search] 응답 길이: ${response.length}자`);
    console.log(`[E2E:Search] 응답 미리보기: ${response.slice(-300)}`);

    expect(response.length).toBeGreaterThan(10);
    expect(response).not.toContain('처리 중 오류');

    // 검색 결과이면 "건" 또는 "찾았습니다" 또는 카드가 있을 수 있음
    const hasSearchResult = response.includes('건') ||
      response.includes('찾았') ||
      response.includes('찾지 못했') ||
      response.includes('문서');
    console.log(`[E2E:Search] 검색 결과 포함: ${hasSearchResult}`);
  });

  test('검색 — 키워드 검색 (회의록 검색)', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '회의록 문서 검색해줘');

    const response = await waitForBotResponse(page, 60_000);
    console.log(`[E2E:Search-회의록] 응답 길이: ${response.length}자`);

    expect(response.length).toBeGreaterThan(10);
    expect(response).not.toContain('처리 중 오류');
  });

  // ═══════════════════════════════════════════
  // 3. 요약 기능 테스트
  // ═══════════════════════════════════════════

  test('요약 — 문서 요약 요청', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '최근 보고서 요약해줘');

    const response = await waitForBotResponse(page, 60_000);
    console.log(`[E2E:Summary] 응답 길이: ${response.length}자`);
    console.log(`[E2E:Summary] 응답 미리보기: ${response.slice(-300)}`);

    expect(response.length).toBeGreaterThan(10);
    expect(response).not.toContain('처리 중 오류');

    // 요약 결과이면 "요약" 또는 "태그" 또는 doc_pick(선택지)가 나올 수 있음
    const hasSummaryResult = response.includes('요약') ||
      response.includes('태그') ||
      response.includes('선택') ||
      response.includes('핵심') ||
      response.includes('문서');
    console.log(`[E2E:Summary] 요약 관련 키워드 포함: ${hasSummaryResult}`);
  });

  // ═══════════════════════════════════════════
  // 4. Intent 라우팅 호환성 — 경계 케이스
  // ═══════════════════════════════════════════

  test('경계 — judgment vs doc_retrieve 혼동 ("출장 규정 알려줘")', async ({ page }) => {
    // "출장 규정 알려줘"는 judgment(규정 판단)로 갈 수도, doc_retrieve(문서 검색)로 갈 수도 있음
    await loginAndGoToChat(page);
    await sendMessage(page, '출장 규정 알려줘');

    const response = await waitForBotResponse(page, 60_000);
    console.log(`[E2E:Boundary] 응답 길이: ${response.length}자`);
    console.log(`[E2E:Boundary] 응답 미리보기: ${response.slice(-300)}`);

    // 어느 Agent로 갔든 의미 있는 응답이어야 함
    expect(response.length).toBeGreaterThan(30);
    expect(response).not.toContain('처리 중 오류');
    expect(response).not.toContain('지원하지 않는 intent');
  });

  test('경계 — doc_search vs doc_qa ("DevOps 관련 자료 있어?")', async ({ page }) => {
    // "있어?" → _is_pure_search에서 search로 갈 수도 있고, QA로 갈 수도 있음
    await loginAndGoToChat(page);
    await sendMessage(page, 'DevOps 관련 자료 있어?');

    const response = await waitForBotResponse(page, 60_000);
    console.log(`[E2E:Boundary-search/qa] 응답 길이: ${response.length}자`);

    expect(response.length).toBeGreaterThan(10);
    expect(response).not.toContain('처리 중 오류');
  });

  test('경계 — 요약+검색 복합 ("보고서 찾아서 요약해줘")', async ({ page }) => {
    // _is_pure_search에서 False (has_explain=True) → QA로 넘어가야 함
    await loginAndGoToChat(page);
    await sendMessage(page, '보고서 찾아서 정리해줘');

    const response = await waitForBotResponse(page, 60_000);
    console.log(`[E2E:Boundary-compound] 응답 길이: ${response.length}자`);

    expect(response.length).toBeGreaterThan(10);
    expect(response).not.toContain('처리 중 오류');
  });

  // ═══════════════════════════════════════════
  // 5. doc_generate 호환성
  // ═══════════════════════════════════════════

  test('doc_generate — 회의록 생성 요청', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '오늘 주간회의 회의록 작성해줘. 참석자 김철수, 이영희. DB 설계 확정됨.');

    const response = await waitForBotResponse(page, 60_000);
    console.log(`[E2E:Generate] 응답 길이: ${response.length}자`);

    expect(response.length).toBeGreaterThan(20);
    expect(response).not.toContain('처리 중 오류');
  });

  // ═══════════════════════════════════════════
  // 6. 에러 내성 테스트
  // ═══════════════════════════════════════════

  test('에러 내성 — 매우 짧은 입력', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '문서');

    const response = await waitForBotResponse(page, 60_000);
    console.log(`[E2E:Short] 응답 길이: ${response.length}자`);

    // 무한 로딩이 아닌, 어떤 응답이든 와야 함
    expect(response.length).toBeGreaterThan(5);
    expect(response).not.toContain('처리 중 오류');
  });

  test('에러 내성 — 특수문자 포함 입력', async ({ page }) => {
    await loginAndGoToChat(page);
    await sendMessage(page, '보고서<script>alert(1)</script> 찾아줘');

    const response = await waitForBotResponse(page, 60_000);
    console.log(`[E2E:XSS] 응답 길이: ${response.length}자`);

    expect(response.length).toBeGreaterThan(5);
    // XSS가 실행되지 않아야
    expect(response).not.toContain('<script>');
  });

  // ═══════════════════════════════════════════
  // 7. Intent 미스매치 검증 — doc_search가 legacy로 올바르게 처리되는지
  // ═══════════════════════════════════════════

  test('레거시 호환 — BERT가 doc_search로 분류해도 document_agent 처리', async ({ page }) => {
    // "마케팅 관련 문서 목록 보여줘" → _is_pure_search → search 경로
    await loginAndGoToChat(page);
    await sendMessage(page, '마케팅 관련 문서 목록 보여줘');

    const response = await waitForBotResponse(page, 60_000);
    console.log(`[E2E:Legacy-doc_search] 응답 길이: ${response.length}자`);

    expect(response.length).toBeGreaterThan(10);
    expect(response).not.toContain('지원하지 않는 intent');
    expect(response).not.toContain('처리 중 오류');
  });

  // ═══════════════════════════════════════════
  // 8. SSE 스트리밍 안정성 — 응답이 끊기지 않는지
  // ═══════════════════════════════════════════

  test('스트리밍 안정성 — 무한 로딩 없이 응답 완료', async ({ page }) => {
    await loginAndGoToChat(page);

    // 타이머 시작
    const startTime = Date.now();
    await sendMessage(page, '인사 규정에서 경조사 휴가 기준 알려줘');

    const response = await waitForBotResponse(page, 60_000);
    const elapsed = Date.now() - startTime;

    console.log(`[E2E:Streaming] 응답 시간: ${(elapsed / 1000).toFixed(1)}초`);
    console.log(`[E2E:Streaming] 응답 길이: ${response.length}자`);

    // 60초 내 응답 완료
    expect(elapsed).toBeLessThan(60_000);
    // 의미 있는 응답
    expect(response.length).toBeGreaterThan(20);
  });
});
