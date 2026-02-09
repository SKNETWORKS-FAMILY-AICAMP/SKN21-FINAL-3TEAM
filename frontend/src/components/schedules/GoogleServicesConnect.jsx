/**
 * 통합 Google 서비스 연결 UI (팀원 E 담당)
 * - 4개 서비스 토글 (Calendar, Tasks, Gmail, Sheets)
 * - 연결/해제 버튼
 * - 연결됨 상태: scope 뱃지 표시
 */
export default function GoogleServicesConnect() {
  return (
    <div className="bg-white rounded-lg border p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Google 서비스 연결</h3>
      {/* TODO: 팀원 E 구현 */}
      {/* - useGoogleServices() 훅 사용 */}
      {/* - 미연결: 4개 scope 체크박스 + 연결 버튼 */}
      {/* - 연결됨: scope 뱃지 + 권한 추가/연결 해제 버튼 */}
    </div>
  )
}
