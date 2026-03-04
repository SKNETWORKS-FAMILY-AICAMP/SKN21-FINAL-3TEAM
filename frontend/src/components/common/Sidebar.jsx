import { useState, useEffect, useRef } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import useAuthStore from '../../store/authStore';
import useUIStore from '../../store/uiStore';
import ThemeToggle from './ThemeToggle';
import api from '../../api/client';
import { LayoutDashboard, MessageSquare, FilePlus, FileText, Users2, Calendar, CheckSquare, Settings, Menu, LogOut, StickyNote, ChevronUp, ChevronDown, Plus, Trash2, ArrowLeft, Check } from 'lucide-react';

const TEAM_COLORS = {
  '개발': '#3B82F6',
  'QA기획': '#F59E0B',
  'UI/UX': '#10B981',
  '영업': '#8B5CF6',
  '마케팅': '#EC4899',
  'CS': '#06B6D4',
  'HR': '#F97316',
  '경영': '#A855F7',
};

const getNavItems = (isAdmin) => [
  {
    section: '메인', items: [
      { to: '/dashboard', icon: LayoutDashboard, label: '대시보드' },
    ]
  },
  {
    section: 'AI 생성', items: [
      { to: '/document-generate', icon: FilePlus, label: '문서 생성' },
    ]
  },
  {
    section: '관리', items: [
      { to: '/documents', icon: FileText, label: '문서 관리' },
      { to: '/meetings', icon: Users2, label: '회의 관리' },
      { to: '/schedules', icon: Calendar, label: '일정 관리' },
      { to: '/tasks', icon: CheckSquare, label: '태스크 관리' },
    ]
  },
  ...(isAdmin ? [{
    section: '시스템', items: [
      { to: '/admin', icon: Settings, label: '관리자 설정' },
    ]
  }] : []),
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const memos = useUIStore((s) => s.memos);
  const memoOpen = useUIStore((s) => s.memoOpen);
  const activeMemoId = useUIStore((s) => s.activeMemoId);
  const toggleMemo = useUIStore((s) => s.toggleMemo);
  const selectMemo = useUIStore((s) => s.selectMemo);
  const addMemo = useUIStore((s) => s.addMemo);
  const updateMemo = useUIStore((s) => s.updateMemo);
  const deleteMemo = useUIStore((s) => s.deleteMemo);
  const activeMemo = memos.find(m => m.id === activeMemoId);
  const [savedVisible, setSavedVisible] = useState(false);
  const saveTimerRef = useRef(null);
  const [teamCounts, setTeamCounts] = useState([]);
  const [deptOpen, setDeptOpen] = useState(true);

  useEffect(() => {
    const fetchTeamCounts = async () => {
      try {
        const res = await api.get('/admin/stats');
        // If stats API has user count, or we just use a simple approach
      } catch { }
      // Fallback: use hardcoded team list, counts will show from admin
      setTeamCounts(Object.keys(TEAM_COLORS).map(t => ({ team: t, count: '–' })));
    };
    fetchTeamCounts();
  }, []);

  const handleMemoChange = (e) => {
    updateMemo(activeMemo.id, e.target.value);
    setSavedVisible(false);
    clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => setSavedVisible(true), 500);
  };

  useEffect(() => {
    if (savedVisible) {
      const hide = setTimeout(() => setSavedVisible(false), 2000);
      return () => clearTimeout(hide);
    }
  }, [savedVisible]);

  useEffect(() => {
    setSavedVisible(false);
  }, [activeMemoId]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside
      className={`bg-sidebar-bg flex flex-col flex-shrink-0 transition-[width] duration-300 ease-in-out relative ${collapsed ? 'w-16' : 'w-60'
        }`}
    >
      {/* 스크롤 가능한 내부 영역 */}
      <div className="flex flex-col flex-1 overflow-y-auto">

        {/* 로고 + 햄버거 버튼 */}
        <div className={`flex px-4 pt-5 pb-5 ${collapsed ? 'flex-col items-center gap-3' : 'items-center justify-between'}`}>
          <a
            href="/dashboard"
            className={`flex items-center gap-3 overflow-hidden ${collapsed ? 'justify-center' : ''}`}
          >
            <img src="/logo.png" alt="Logo" className={`${collapsed ? 'w-10' : 'w-14'} object-contain mix-blend-multiply transition-all`} />
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
          {getNavItems(user?.is_admin).map((section) => (
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
                    `flex items-center gap-2.5 py-2.5 text-sm border-l-[3px] transition-all overflow-hidden ${collapsed ? 'px-0 justify-center border-l-transparent' : 'px-5'
                    } ${isActive
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

        {/* Department 섹션 */}
        {!collapsed && (
          <div className="border-t border-sidebar-border px-3 py-2">
            <button
              onClick={() => setDeptOpen(!deptOpen)}
              className="w-full flex items-center justify-between px-2 py-1.5 text-[0.625rem] font-semibold uppercase tracking-widest text-sidebar-text-muted opacity-70"
            >
              <span>Department</span>
              {deptOpen ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
            </button>
            {deptOpen && (
              <div className="mt-1 space-y-0.5">
                {Object.entries(TEAM_COLORS).map(([team, color]) => (
                  <div
                    key={team}
                    className={`flex items-center gap-2.5 px-2 py-1.5 rounded-md text-[0.75rem] cursor-default ${user?.team === team ? 'bg-white/[0.08] text-sidebar-text font-semibold' : 'text-sidebar-text-muted hover:bg-white/[0.04]'
                      } transition-colors`}
                  >
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                    <span className="truncate">{team}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        <div className={`border-t border-sidebar-border ${collapsed ? 'px-2' : 'px-3'} py-2`}>
          {collapsed ? (
            <button
              onClick={toggleMemo}
              title={`메모 (${memos.length})`}
              className="w-full flex items-center justify-center py-2 rounded-md text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06] transition-all relative"
            >
              <StickyNote size={18} />
              {memos.length > 0 && (
                <span className="absolute top-1 right-1 w-3.5 h-3.5 rounded-full bg-accent-300 text-primary-900 text-[0.5rem] font-bold flex items-center justify-center">
                  {memos.length}
                </span>
              )}
            </button>
          ) : (
            <>
              <button
                onClick={() => { if (activeMemoId) selectMemo(null); else toggleMemo(); }}
                className="w-full flex items-center justify-between px-2 py-1.5 rounded-md text-[0.75rem] font-medium text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06] transition-all"
              >
                <span className="flex items-center gap-1.5">
                  {activeMemoId ? <ArrowLeft size={14} /> : <StickyNote size={14} />}
                  {activeMemoId ? '목록으로' : '메모'}
                  {!memoOpen && memos.length > 0 && (
                    <span className="text-[0.625rem] bg-white/10 px-1.5 rounded-full">{memos.length}</span>
                  )}
                </span>
                {!activeMemoId && (
                  <span className="flex items-center gap-1">
                    {memoOpen && (
                      <span
                        role="button"
                        tabIndex={0}
                        onClick={(e) => { e.stopPropagation(); addMemo(); }}
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); addMemo(); } }}
                        className="w-5 h-5 flex items-center justify-center rounded hover:bg-white/10"
                        title="새 메모"
                      >
                        <Plus size={14} />
                      </span>
                    )}
                    {memoOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                  </span>
                )}
              </button>

              {memoOpen && !activeMemoId && (
                <div className="mt-1 flex flex-col gap-0.5 max-h-36 overflow-y-auto">
                  {memos.length === 0 ? (
                    <div className="text-[0.6875rem] text-sidebar-text-muted/50 text-center py-3">
                      메모가 없습니다
                    </div>
                  ) : (
                    memos.map((m) => (
                      <div
                        key={m.id}
                        onClick={() => selectMemo(m.id)}
                        className="group flex items-center gap-1.5 px-2 py-1.5 rounded-md hover:bg-white/[0.06] cursor-pointer"
                      >
                        <span className="flex-1 min-w-0 text-[0.6875rem] text-sidebar-text truncate">
                          {m.text.split('\n')[0] || '빈 메모'}
                        </span>
                        <button
                          onClick={(e) => { e.stopPropagation(); deleteMemo(m.id); }}
                          className="opacity-0 group-hover:opacity-100 flex-shrink-0 p-0.5 rounded hover:bg-white/10 text-sidebar-text-muted hover:text-red-400 transition-all"
                          title="삭제"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              )}

              {memoOpen && activeMemo && (
                <div className="mt-1">
                  <textarea
                    autoFocus
                    value={activeMemo.text}
                    onChange={handleMemoChange}
                    placeholder="메모를 입력하세요..."
                    rows={5}
                    className="w-full px-2 py-1.5 text-[0.75rem] rounded-md bg-white/[0.06] text-sidebar-text placeholder:text-sidebar-text-muted/50 border border-sidebar-border focus:border-accent-300 focus:outline-none resize-none"
                  />
                  <div className={`flex items-center gap-1 px-1 pt-1 text-[0.625rem] text-accent-300 transition-opacity duration-300 ${savedVisible ? 'opacity-100' : 'opacity-0'}`}>
                    <Check size={10} />
                    <span>자동 저장됨</span>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

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
                <div className="text-[0.6875rem] text-sidebar-text-muted truncate flex items-center gap-1.5">
                  {user?.team && <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: TEAM_COLORS[user.team] || '#888' }} />}
                  {user?.team || (user?.is_admin ? '관리자' : '사용자')}
                </div>
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
            <div className="relative group">
              <button
                onClick={handleLogout}
                className="w-full py-2 rounded-md text-[0.8125rem] font-medium text-sidebar-text-muted border border-sidebar-border hover:bg-white/10 hover:text-sidebar-text transition"
              >
                로그아웃
              </button>
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 rounded bg-gray-800 text-white text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-150">
                로그아웃 할래 말래
              </div>
            </div>
          )}
        </div>

      </div> {/* 스크롤 내부 영역 끝 */}
    </aside>
  );
}
