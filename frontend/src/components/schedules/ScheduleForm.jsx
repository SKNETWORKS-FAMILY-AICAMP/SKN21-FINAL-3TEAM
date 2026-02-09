/**
 * ScheduleForm (팀원 E 담당)
 * - 일정 생성 폼
 * - Google Meet 토글 (hasScope('calendar') 일 때만 표시)
 * - 참석자 이메일 입력 (Meet 토글 ON 시)
 *
 * Props:
 *   onCreated: () => void
 */
export default function ScheduleForm({ onCreated }) {
  return (
    <div>
      {/* TODO: 팀원 E 구현 */}
      {/* - title, description, start_time, end_time, schedule_type, priority */}
      {/* - include_meet 체크박스 (hasScope('calendar') 일 때만) */}
      {/* - attendee_emails 입력 (include_meet ON 시) */}
      {/* - createScheduleWithMeet() API 호출 → onCreated 콜백 */}
    </div>
  )
}
