import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import useAuthStore from '../../store/authStore';
import ThemeToggle from './ThemeToggle';
import { LayoutDashboard, MessageSquare, FilePlus, FileText, Users2, Calendar, Settings, Menu, LogOut } from 'lucide-react';

const navItems = [
  { section: '메인', items: [
    { to: '/dashboard', icon: LayoutDashboard, label: '대시보드' },
    { to: '/chat', icon: MessageSquare, label: 'AI 챗봇' },
  ]},
  { section: 'AI 생성', items: [
    { to: '/document-generate', icon: FilePlus, label: '문서 생성' },
  ]},
  { section: '관리', items: [
    { to: '/documents', icon: FileText, label: '문서 관리' },
    { to: '/meetings', icon: Users2, label: '회의 관리' },
    { to: '/schedules', icon: Calendar, label: '일정 관리' },
  ]},
  { section: '시스템', items: [
    { to: '/admin', icon: Settings, label: '관리자 설정' },
  ]},
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside
      className={`bg-sidebar-bg flex flex-col flex-shrink-0 transition-[width] duration-300 ease-in-out relative ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      {/* 스크롤 가능한 내부 영역 */}
      <div className="flex flex-col flex-1 overflow-y-auto">

      {/* 로고 + 햄버거 버튼 */}
      <div className={`flex flex-col px-4 pt-5 pb-5 gap-3 ${collapsed ? 'items-center' : ''}`}>
        <a
          href="/dashboard"
          className={`flex items-center gap-3 overflow-hidden ${collapsed ? 'justify-center' : ''}`}
        >
          <div className="w-9 h-9 bg-accent-300 rounded-sm flex items-center justify-center text-lg font-bold text-primary-900 flex-shrink-0">W</div>
          {!collapsed && (
            <span className="font-display text-lg font-bold text-sidebar-text tracking-tight whitespace-nowrap">WorkFlow</span>
          )}
        </a>

        <button
          onClick={() => setCollapsed(!collapsed)}
          title={collapsed ? '메뉴 펼치기' : '메뉴 접기'}
          className="w-9 h-9 flex items-center justify-center rounded-md text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06] transition-all"
        >
          <Menu size={20} />
        </button>
      </div>

      {/* 네비게이션 */}
      <nav className="flex-1">
        {navItems.map((section) => (
          <div key={section.section} className="mb-2">
            {/* 섹션 레이블: 접혔을 때 구분선으로 대체 */}
            {!collapsed ? (
              <div className="px-5 py-1.5 text-[0.625rem] font-semibold uppercase tracking-widest text-sidebar-text-muted opacity-70">
                {section.section}
              </div>
            ) : (
              <div className="mx-3 my-1.5 border-t border-sidebar-border opacity-30" />
            )}

            {section.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                title={collapsed ? item.label : undefined}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 py-2.5 text-sm border-l-[3px] transition-all overflow-hidden ${
                    collapsed ? 'px-0 justify-center border-l-transparent' : 'px-5'
                  } ${
                    isActive
                      ? 'bg-sidebar-active text-sidebar-text font-semibold border-l-accent-300'
                      : 'text-sidebar-text-muted border-l-transparent hover:bg-white/[0.06] hover:text-sidebar-text'
                  }`
                }
              >
                <item.icon size={18} className="flex-shrink-0" />
                {!collapsed && (
                  <>
                    <span className="whitespace-nowrap">{item.label}</span>
                    {item.badge && (
                      <span className="ml-auto bg-accent-300 text-primary-900 text-[0.6875rem] font-bold px-2 py-px rounded-full">
                        {item.badge}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* 유저 프로필 */}
      <div className={`py-4 border-t border-sidebar-border ${collapsed ? 'px-0' : 'px-5'}`}>
        <div className={`flex items-center mb-3 ${collapsed ? 'justify-center' : 'gap-2.5'}`}>
          <div
            className="w-[34px] h-[34px] rounded-full bg-accent-300 flex items-center justify-center text-[0.8125rem] font-bold text-primary-900 flex-shrink-0"
            title={collapsed ? (user?.name || '사용자') : undefined}
          >
            {user?.name?.[0] || '김'}
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <div className="text-[0.8125rem] font-semibold text-sidebar-text truncate">{user?.name || '사용자'}</div>
              <div className="text-[0.6875rem] text-sidebar-text-muted truncate">{user?.is_admin ? '관리자' : '사용자'}</div>
              <div className="text-[0.6875rem] text-sidebar-text-muted truncate">{user?.email || ''}</div>
            </div>
          )}
          {!collapsed && <ThemeToggle />}
        </div>

        {collapsed ? (
          <div className="flex flex-col items-center gap-2">
            <ThemeToggle />
            <button
              onClick={handleLogout}
              title="로그아웃"
              className="w-9 h-9 rounded-md flex items-center justify-center text-sidebar-text-muted border border-sidebar-border hover:bg-white/10 hover:text-sidebar-text transition"
            >
              <LogOut size={16} />
            </button>
          </div>
        ) : (
          <button
            onClick={handleLogout}
            title="로그아웃 할래 말래"
            className="w-full py-2 rounded-md text-[0.8125rem] font-medium text-sidebar-text-muted border border-sidebar-border hover:bg-white/10 hover:text-sidebar-text transition"
          >
            로그아웃
          </button>
        )}
      </div>

      </div> {/* 스크롤 내부 영역 끝 */}
    </aside>
  );
}
