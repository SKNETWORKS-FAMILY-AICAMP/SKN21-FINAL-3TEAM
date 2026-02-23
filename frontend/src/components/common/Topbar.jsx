import { useState, useEffect, useRef } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, MessageSquare, FilePlus, FileText,
  Users2, Calendar, Settings, Bell, LogOut,
  StickyNote, Plus, Trash2, ArrowLeft, Check,
} from 'lucide-react';
import useAuthStore from '../../store/authStore';
import useUIStore from '../../store/uiStore';
import ThemeToggle from './ThemeToggle';

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: '대시보드' },
  { to: '/chat', icon: MessageSquare, label: 'AI 챗봇' },
  { to: '/document-generate', icon: FilePlus, label: '문서 생성' },
  { to: '/documents', icon: FileText, label: '문서 관리' },
  { to: '/meetings', icon: Users2, label: '회의 관리' },
  { to: '/schedules', icon: Calendar, label: '일정 관리' },
  { to: '/admin', icon: Settings, label: '관리자 설정' },
];

function MemoPanel() {
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);
  const saveTimerRef = useRef(null);
  const [savedVisible, setSavedVisible] = useState(false);

  const memos = useUIStore((s) => s.memos);
  const activeMemoId = useUIStore((s) => s.activeMemoId);
  const selectMemo = useUIStore((s) => s.selectMemo);
  const addMemo = useUIStore((s) => s.addMemo);
  const updateMemo = useUIStore((s) => s.updateMemo);
  const deleteMemo = useUIStore((s) => s.deleteMemo);
  const activeMemo = memos.find((m) => m.id === activeMemoId);

  // 패널 외부 클릭 시 닫기
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false);
        selectMemo(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, selectMemo]);

  // 메모 전환 시 저장 표시 초기화
  useEffect(() => {
    setSavedVisible(false);
  }, [activeMemoId]);

  // 자동 저장 표시 숨기기
  useEffect(() => {
    if (!savedVisible) return;
    const t = setTimeout(() => setSavedVisible(false), 2000);
    return () => clearTimeout(t);
  }, [savedVisible]);

  const handleChange = (e) => {
    updateMemo(activeMemo.id, e.target.value);
    setSavedVisible(false);
    clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => setSavedVisible(true), 500);
  };

  const handleClose = () => {
    setOpen(false);
    selectMemo(null);
  };

  return (
    <div className="relative" ref={panelRef}>
      {/* 메모 버튼 */}
      <button
        onClick={() => setOpen((o) => !o)}
        title="메모"
        className={`w-8 h-8 flex items-center justify-center rounded-md transition relative ${open
          ? 'bg-sidebar-active text-sidebar-text'
          : 'text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06]'
          }`}
      >
        <StickyNote size={16} />
        {memos.length > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-accent-300 text-primary-900 text-[0.5rem] font-bold flex items-center justify-center">
            {memos.length}
          </span>
        )}
      </button>

      {/* 플로팅 메모 패널 */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-72 bg-sidebar-bg border border-sidebar-border rounded-md shadow-lg z-50 overflow-hidden">
          {/* 헤더 */}
          <div className="flex items-center justify-between px-3 py-2.5 border-b border-sidebar-border">
            {activeMemoId ? (
              <button
                onClick={() => selectMemo(null)}
                className="flex items-center gap-1.5 text-xs font-medium text-sidebar-text-muted hover:text-sidebar-text transition"
              >
                <ArrowLeft size={13} />
                목록으로
              </button>
            ) : (
              <span className="text-xs font-semibold text-sidebar-text">
                메모 {memos.length > 0 && <span className="text-sidebar-text-muted font-normal">({memos.length})</span>}
              </span>
            )}
            <button
              onClick={addMemo}
              title="새 메모"
              className="w-6 h-6 flex items-center justify-center rounded hover:bg-white/10 text-sidebar-text-muted hover:text-sidebar-text transition"
            >
              <Plus size={14} />
            </button>
          </div>

          {/* 메모 목록 */}
          {!activeMemoId && (
            <div className="max-h-64 overflow-y-auto">
              {memos.length === 0 ? (
                <div className="py-8 text-center text-xs text-sidebar-text-muted opacity-60">
                  메모가 없습니다
                  <br />
                  <button
                    onClick={addMemo}
                    className="mt-2 text-accent-300 hover:underline"
                  >
                    + 새 메모 만들기
                  </button>
                </div>
              ) : (
                memos.map((m) => (
                  <div
                    key={m.id}
                    onClick={() => selectMemo(m.id)}
                    className="group flex items-center gap-2 px-3 py-2.5 hover:bg-white/[0.06] cursor-pointer border-b border-sidebar-border/50 last:border-0"
                  >
                    <StickyNote size={13} className="text-sidebar-text-muted flex-shrink-0 opacity-60" />
                    <span className="flex-1 min-w-0 text-xs text-sidebar-text truncate">
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

          {/* 메모 편집 */}
          {activeMemoId && activeMemo && (
            <div className="p-3">
              <textarea
                autoFocus
                value={activeMemo.text}
                onChange={handleChange}
                placeholder="메모를 입력하세요..."
                rows={8}
                className="w-full px-2.5 py-2 text-xs rounded-md bg-white/[0.06] text-sidebar-text placeholder:text-sidebar-text-muted/50 border border-sidebar-border focus:border-accent-300 focus:outline-none resize-none"
              />
              <div className={`flex items-center gap-1 mt-1 text-[0.625rem] text-accent-300 transition-opacity duration-300 ${savedVisible ? 'opacity-100' : 'opacity-0'}`}>
                <Check size={10} />
                자동 저장됨
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Topbar() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="h-16 bg-sidebar-bg border-b border-sidebar-border flex items-center px-6 gap-6 flex-shrink-0 z-20">
      {/* 로고 */}
      <a href="/dashboard" className="flex items-center gap-2.5 flex-shrink-0">
        <div className="w-8 h-8 bg-accent-300 rounded-sm flex items-center justify-center text-base font-bold text-primary-900 font-display">W</div>
        <span className="font-display text-base font-bold text-sidebar-text tracking-tight">WorkFlow</span>
      </a>

      {/* 네비게이션 */}
      <nav className="flex items-center gap-1 flex-1">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all whitespace-nowrap ${isActive
                ? 'bg-sidebar-active text-sidebar-text'
                : 'text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06]'
              }`
            }
          >
            <item.icon size={15} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* 우측 유틸리티 */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <ThemeToggle />
        <MemoPanel />
        <button
          className="w-8 h-8 flex items-center justify-center rounded-md text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06] relative transition"
          title="알림"
        >
          <Bell size={16} />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-accent-300 rounded-full" />
        </button>

        <div className="flex items-center gap-2 pl-3 border-l border-sidebar-border">
          <div className="w-7 h-7 rounded-full bg-accent-300 flex items-center justify-center text-xs font-bold text-primary-900 flex-shrink-0">
            {user?.name?.[0] || '?'}
          </div>
          <div className="leading-none">
            <div className="text-xs font-semibold text-sidebar-text">{user?.name || '사용자'}</div>
            <div className="text-[0.625rem] text-sidebar-text-muted mt-0.5">{user?.is_admin ? '관리자' : '사용자'}</div>
          </div>
        </div>

        <button
          onClick={handleLogout}
          title="로그아웃"
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06] border border-sidebar-border transition-all"
        >
          <LogOut size={13} />
          로그아웃
        </button>
      </div>
    </header>
  );
}
