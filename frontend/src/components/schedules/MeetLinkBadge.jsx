/**
 * Google Meet 링크 뱃지 (팀원 E 담당)
 * - 캘린더 이벤트에 Meet 링크가 있으면 표시
 * - 클릭 시 새 탭에서 Meet 열기
 *
 * Props:
 *   meetLink: string | null
 */
export default function MeetLinkBadge({ meetLink }) {
  if (!meetLink) return null

  return (
    <a
      href={meetLink}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-green-50 text-green-700 hover:bg-green-100"
    >
      {/* TODO: 팀원 E — 아이콘 + 스타일 보완 */}
      Meet
    </a>
  )
}
