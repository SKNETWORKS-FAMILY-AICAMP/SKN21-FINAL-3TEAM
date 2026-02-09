/**
 * 상단 헤더 (팀원 E 담당)
 */
import useAuthStore from '../../store/authStore'

export default function Header() {
  const { user } = useAuthStore()

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-600">{user?.name || '사용자'}</span>
      </div>
    </header>
  )
}
