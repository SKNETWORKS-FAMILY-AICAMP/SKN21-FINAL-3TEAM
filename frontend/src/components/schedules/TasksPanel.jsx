/**
 * Google Tasks 관리 패널 (팀원 E 담당)
 * - 할 일 목록 (체크박스)
 * - Push (앱→Tasks) / Pull (Tasks→앱) 동기화 버튼
 */
export default function TasksPanel() {
  return (
    <div className="bg-white rounded-lg border p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">Google Tasks</h3>
      {/* TODO: 팀원 E 구현 */}
      {/* - hasScope('tasks') 확인 → 미연결 시 안내 메시지 */}
      {/* - tasks 목록 렌더링 (체크박스 + 제목 + 마감일) */}
      {/* - Push/Pull 버튼 */}
    </div>
  )
}
