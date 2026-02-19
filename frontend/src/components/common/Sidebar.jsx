import { NavLink, useNavigate } from 'react-router-dom';
import useAuthStore from '../../store/authStore';
import ThemeToggle from './ThemeToggle';
import { LayoutDashboard, MessageSquare, FilePlus, FileText, Users2, Calendar, Settings } from 'lucide-react';

const navItems = [
  { section: '메인', items: [
    { to: '/dashboard', icon: LayoutDashboard, label: '대시보드' },
    { to: '/chat', icon: MessageSquare, label: 'AI 챗봇' },
  ]},
  { section: 'AI 생성', items: [
    { to: '/document-generate', icon: FilePlus, label: '문서 생성' },
  ]},
  { section: '관리', items: [
    { to: '/documents', icon: FileText, label: '문서 관리', badge: 3 },
    { to: '/meetings', icon: Users2, label: '회의 관리' },
    { to: '/schedules', icon: Calendar, label: '일정 관리' },
  ]},
  { section: '시스템', items: [
    { to: '/admin', icon: Settings, label: '관리자 설정' },
  ]},
];

export default function Sidebar() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className="w-60 bg-sidebar-bg flex flex-col flex-shrink-0 overflow-y-auto">
      <a href="/dashboard" className="flex items-center gap-3 px-5 pt-6 pb-7">
        <div className="w-9 h-9 bg-accent-300 rounded-sm flex items-center justify-center text-lg font-bold text-primary-900">W</div>
        <span className="font-display text-lg font-bold text-sidebar-text tracking-tight">WorkFlow</span>
      </a>

      <nav className="flex-1">
        {navItems.map((section) => (
          <div key={section.section} className="mb-2">
            <div className="px-5 py-1.5 text-[0.625rem] font-semibold uppercase tracking-widest text-sidebar-text-muted opacity-70">
              {section.section}
            </div>
            {section.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-5 py-2.5 text-sm border-l-[3px] transition-all ${
                    isActive
                      ? 'bg-sidebar-active text-sidebar-text font-semibold border-l-accent-300'
                      : 'text-sidebar-text-muted border-l-transparent hover:bg-white/[0.06] hover:text-sidebar-text'
                  }`
                }
              >
                <item.icon size={18} />
                <span>{item.label}</span>
                {item.badge && (
                  <span className="ml-auto bg-accent-300 text-primary-900 text-[0.6875rem] font-bold px-2 py-px rounded-full">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-sidebar-border">
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-[34px] h-[34px] rounded-full bg-accent-300 flex items-center justify-center text-[0.8125rem] font-bold text-primary-900 flex-shrink-0">
            {user?.name?.[0] || '김'}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[0.8125rem] font-semibold text-sidebar-text truncate">{user?.name || '사용자'}</div>
            <div className="text-[0.6875rem] text-sidebar-text-muted truncate">{user?.is_admin ? '관리자' : '사용자'}</div>
            <div className="text-[0.6875rem] text-sidebar-text-muted truncate">{user?.email || ''}</div>
          </div>
          <ThemeToggle />
        </div>
        <button
          onClick={handleLogout}
          title="로그아웃 할래 말래"
          className="w-full py-2 rounded-md text-[0.8125rem] font-medium text-sidebar-text-muted border border-sidebar-border hover:bg-white/10 hover:text-sidebar-text transition"
        >
          로그아웃
        </button>
      </div>
    </aside>
  );
}
