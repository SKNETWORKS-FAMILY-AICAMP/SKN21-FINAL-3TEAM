/**
 * 알림 메일 발송 버튼 (팀원 E 담당)
 * - 단일 Action Item 기한 알림 메일 발송
 * - 클릭 → 이메일 입력 → 발송
 *
 * Props:
 *   actionItemId: number
 *   assignee: string
 *   onSent: () => void
 */
export default function EmailReminderButton({ actionItemId, assignee, onSent }) {
  return (
    <div>
      {/* TODO: 팀원 E 구현 */}
      {/* - hasScope('gmail_send') 확인 → 미연결 시 숨김 */}
      {/* - 클릭 시 이메일 입력 인라인 폼 표시 */}
      {/* - sendReminder() API 호출 → onSent 콜백 */}
    </div>
  )
}
