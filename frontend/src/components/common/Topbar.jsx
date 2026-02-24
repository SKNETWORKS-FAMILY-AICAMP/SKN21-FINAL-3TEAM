import { useState, useEffect, useRef } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, MessageSquare, FilePlus, FileText,
  Calendar, Settings, LogOut, KeyRound,
  StickyNote, Plus, Trash2, ArrowLeft, Check,
} from 'lucide-react';
import useAuthStore from '../../store/authStore';
import useUIStore from '../../store/uiStore';
import useChatStore from '../../store/chatStore';
import ThemeToggle from './ThemeToggle';
import { changePassword } from '../../api/auth';

const getNavItems = (isAdmin) => [
  { to: '/dashboard', icon: LayoutDashboard, label: '대시보드' },
  { to: '/chat', icon: MessageSquare, label: 'AI 챗봇' },
  { to: '/document-generate', icon: FilePlus, label: '문서 생성' },
  { to: '/documents', icon: FileText, label: '문서 관리' },
  { to: '/schedules', icon: Calendar, label: '일정 관리' },
  ...(isAdmin ? [{ to: '/admin', icon: Settings, label: '관리자 설정' }] : []),
];

function MemoPanel() {
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);
  const [draft, setDraft] = useState('');
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

  // 메모 선택 시 draft 초기화
  useEffect(() => {
    setDraft(activeMemo?.text || '');
    setSavedVisible(false);
  }, [activeMemoId]);

  // 저장됨 표시 2초 후 숨기기
  useEffect(() => {
    if (!savedVisible) return;
    const t = setTimeout(() => setSavedVisible(false), 2000);
    return () => clearTimeout(t);
  }, [savedVisible]);

  const handleSave = () => {
    if (!draft.trim()) return;
    updateMemo(activeMemo.id, draft);
    setSavedVisible(true);
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
          ? 'bg-primary-50 text-primary-900'
          : 'text-primary-700 hover:text-primary-900 hover:bg-primary-50'
          }`}
      >
        <StickyNote size={16} />
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
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="메모를 입력하세요..."
                rows={8}
                className="w-full px-2.5 py-2 text-xs rounded-md bg-white/[0.06] text-sidebar-text placeholder:text-sidebar-text-muted/50 border border-sidebar-border focus:border-accent-300 focus:outline-none resize-none"
              />
              <div className="flex items-center justify-between mt-2">
                <div className={`flex items-center gap-1 text-[0.625rem] text-accent-300 transition-opacity duration-300 ${savedVisible ? 'opacity-100' : 'opacity-0'}`}>
                  <Check size={10} />
                  저장됨
                </div>
                <button
                  onClick={handleSave}
                  disabled={!draft.trim()}
                  className="px-2.5 py-1 text-[0.625rem] font-semibold rounded bg-accent-500 text-white hover:bg-accent-600 transition disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  저장
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Topbar({ isScrolled = false }) {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef(null);
  const [pwModal, setPwModal] = useState(false);
  const [pwForm, setPwForm] = useState({ current: '', next: '', confirm: '' });
  const [pwError, setPwError] = useState('');
  const [pwSaving, setPwSaving] = useState(false);

  const handleLogout = () => {
    useChatStore.getState().reset();
    logout();
    navigate('/login');
  };

  const openPwModal = () => {
    setUserMenuOpen(false);
    setPwForm({ current: '', next: '', confirm: '' });
    setPwError('');
    setPwModal(true);
  };

  const handleChangePassword = async () => {
    if (!pwForm.current.trim()) return setPwError('현재 비밀번호를 입력하세요.');
    if (pwForm.next.length < 6) return setPwError('새 비밀번호는 6자 이상이어야 합니다.');
    if (pwForm.next !== pwForm.confirm) return setPwError('새 비밀번호가 일치하지 않습니다.');
    setPwSaving(true);
    setPwError('');
    try {
      await changePassword(pwForm.current, pwForm.next);
      setPwModal(false);
    } catch (e) {
      setPwError(e.response?.data?.detail || '비밀번호 변경에 실패했습니다.');
    } finally {
      setPwSaving(false);
    }
  };

  useEffect(() => {
    if (!userMenuOpen) return;
    const handler = (e) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [userMenuOpen]);

  return (
    <>
    <header className={`bg-surface-main flex-shrink-0 z-20 transition-all duration-300 ease-in-out ${isScrolled ? 'h-[56px] shadow-sm' : 'h-[100px]'}`}>
      <div className={`grid grid-cols-[1fr_auto_1fr] items-center px-10 transition-all duration-300 ease-in-out ${isScrolled ? 'py-2.5' : 'py-[30px]'}`}>

        {/* 좌측 - 로고 */}
        <div className="flex items-center">
          <a href="/dashboard" className="flex items-center gap-2.5">
            <div className={`bg-primary-700 rounded-sm flex items-center justify-center font-bold text-white font-display transition-all duration-300 ease-in-out ${isScrolled ? 'w-7 h-7 text-sm' : 'w-10 h-10 text-lg'}`}>W</div>
            <span className={`font-display font-bold text-primary-700 tracking-tight transition-all duration-300 ease-in-out ${isScrolled ? 'text-xl' : 'text-2xl'}`}>WorkFlow</span>
          </a>
        </div>

        {/* 중앙 - 네비게이션 */}
        <nav className="flex items-center gap-0">
          {getNavItems(user?.is_admin).map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `font-medium whitespace-nowrap border-b-2 transition-all duration-300 ease-in-out ${
                  isScrolled ? 'px-4 pb-1.5 text-sm' : 'px-5 pb-3 text-base'
                } ${isActive
                  ? 'text-primary-900 border-primary-700'
                  : 'text-primary-700 border-transparent hover:text-primary-900 hover:border-primary-700'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* 우측 - 유틸리티 */}
        <div className="flex items-center justify-end gap-3">
          <ThemeToggle />
          <MemoPanel />

          <div className="relative" ref={userMenuRef}>
            <button
              onClick={() => setUserMenuOpen((o) => !o)}
              className="flex items-center gap-2 px-2 py-1 rounded-md hover:bg-neutral-border/30 transition-all"
            >
              <div className={`rounded-full bg-accent-500 flex items-center justify-center font-bold text-white flex-shrink-0 transition-all duration-300 ease-in-out ${isScrolled ? 'w-6 h-6 text-[10px]' : 'w-7 h-7 text-xs'}`}>
                {user?.name?.[0] || '?'}
              </div>
              <span className={`font-medium text-neutral-sub transition-all duration-300 ease-in-out ${isScrolled ? 'text-xs' : 'text-sm'}`}>{user?.name || '사용자'}</span>
            </button>

            {userMenuOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-44 bg-surface-card border border-neutral-border rounded-md shadow-md z-50 overflow-hidden">
                <div className="px-3 py-2.5 border-b border-neutral-divider">
                  <div className="text-xs font-semibold text-neutral-main">{user?.name || '사용자'}</div>
                  <div className="text-[0.625rem] text-neutral-muted mt-0.5">{user?.is_admin ? '관리자' : '일반 사용자'}</div>
                </div>
                <button
                  onClick={openPwModal}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-neutral-sub hover:text-neutral-main hover:bg-neutral-divider transition-all"
                >
                  <KeyRound size={12} />
                  비밀번호 변경
                </button>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-neutral-sub hover:text-error hover:bg-neutral-divider transition-all"
                >
                  <LogOut size={12} />
                  로그아웃
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>

    {pwModal && (
      <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setPwModal(false)}>
        <div className="bg-surface-card rounded-lg border border-neutral-border shadow-lg w-[380px] p-6" onClick={(e) => e.stopPropagation()}>
          <h3 className="text-base font-bold mb-4">비밀번호 변경</h3>
          <div className="space-y-3">
            {[
              { label: '현재 비밀번호', key: 'current', placeholder: '현재 비밀번호를 입력하세요' },
              { label: '새 비밀번호', key: 'next', placeholder: '6자 이상 입력하세요' },
              { label: '새 비밀번호 확인', key: 'confirm', placeholder: '새 비밀번호를 다시 입력하세요' },
            ].map(({ label, key, placeholder }) => (
              <div key={key}>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">{label}</label>
                <input
                  type="password"
                  value={pwForm[key]}
                  onChange={(e) => setPwForm({ ...pwForm, [key]: e.target.value })}
                  placeholder={placeholder}
                  className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
                />
              </div>
            ))}
            {pwError && <p className="text-xs text-error">{pwError}</p>}
          </div>
          <div className="flex justify-end gap-2 mt-5">
            <button className="btn-outline" onClick={() => setPwModal(false)}>취소</button>
            <button className="btn-primary" onClick={handleChangePassword} disabled={pwSaving}>
              {pwSaving ? '변경 중...' : '변경'}
            </button>
          </div>
        </div>
      </div>
    )}
    </>
  );
}
