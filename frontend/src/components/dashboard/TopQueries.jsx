/**
 * TopQueries - Top 질의 응답 (팀원 E 담당)
 *
 * UI_UX.pdf: "Top 질의 응답 (월/주/일 탭으로 인기 질문 랭킹)"
 *
 * Props:
 *   - queries: 인기 질문 목록 [{question, count, intent, lastAsked}]
 *   - period: 기간 필터 ('daily' | 'weekly' | 'monthly')
 *   - onPeriodChange: 기간 변경 콜백
 *
 * 기능:
 *   - 월/주/일 탭 전환
 *   - 인기 질문 랭킹 목록 (횟수, Intent 뱃지)
 *   - 클릭 시 해당 질문으로 챗봇 이동
 */
export default function TopQueries() {
  return (
    <div>
      {/* TODO: 팀원 E 구현
        1. 월/주/일 탭 버튼
        2. 랭킹 목록 (순위, 질문, 횟수, Intent 뱃지)
        3. 클릭 시 챗봇 페이지로 이동 + 질문 자동 입력
      */}
    </div>
  )
}
