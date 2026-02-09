/**
 * 사이드바 (팀원 E 담당)
 */
import { NavLink } from 'react-router-dom'

const navItems = [
  { path: '/dashboard', label: '대시보드' },
  { path: '/chat', label: 'AI 챗봇' },
  { path: '/documents', label: '문서 관리' },
  { path: '/meetings', label: '회의 관리' },
  { path: '/schedules', label: '일정 관리' },
  { path: '/admin', label: '관리자' },
]

export default function Sidebar() {
  return (
    <aside className="w-64 bg-white border-r border-gray-200 p-4">
      <div className="text-xl font-bold text-primary mb-8 px-2">
        WorkFlow Agent
      </div>
      <nav className="space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `block px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-600 hover:bg-gray-50'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
