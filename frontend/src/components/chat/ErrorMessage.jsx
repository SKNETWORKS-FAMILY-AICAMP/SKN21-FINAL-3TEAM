/**
 * ErrorMessage - 에러/폴백 메시지 (팀원 E 담당)
 *
 * UI_UX.pdf: "[추가] 에러 상태 메시지 + 재시도 버튼"
 * 요구사항: NF-ST-001
 *
 * Props:
 *   - errorType: 에러 유형 ('agent_failed' | 'network' | 'timeout' | 'unknown')
 *   - message: 에러 메시지
 *   - onRetry: 재시도 콜백
 *   - fallbackMessage: 폴백 응답 (Agent 실패 시 대체 답변)
 *
 * 기능:
 *   - "응답 생성 실패 - 다시 시도해주세요" + 재시도 버튼
 *   - Agent 호출 실패 시 "다른 방식으로 답변드릴게요" 폴백 메시지
 */
export default function ErrorMessage() {
  return (
    <div>
      {/* TODO: 팀원 E 구현
        1. 에러 아이콘 + 메시지 표시
        2. 재시도 버튼
        3. Agent 폴백 메시지 (있을 경우)
      */}
    </div>
  )
}
