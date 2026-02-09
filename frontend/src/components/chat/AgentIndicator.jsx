/**
 * AgentIndicator - Agent 호출 인디케이터 (팀원 E 담당)
 *
 * UI_UX.pdf: "Agent 호출 인디케이터 (문서 Agent 호출 중...)"
 *
 * Props:
 *   - agentType: 호출 중인 Agent ('judgment' | 'document' | 'schedule')
 *   - status: 상태 메시지 ("판단 Agent 호출 중...", "규정 검색 중...")
 *   - isLoading: 로딩 상태
 *
 * 기능:
 *   - SSE에서 'status' 이벤트 수신 시 표시
 *   - Agent 종류별 아이콘 (판단/문서/일정)
 *   - 로딩 스피너 + 상태 메시지
 */
export default function AgentIndicator() {
  return (
    <div>
      {/* TODO: 팀원 E 구현
        1. Agent 아이콘 (판단:⚖️, 문서:📄, 일정:📅)
        2. 로딩 스피너 애니메이션
        3. 상태 메시지 텍스트
      */}
    </div>
  )
}
