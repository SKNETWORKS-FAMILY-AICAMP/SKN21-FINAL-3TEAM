import { useState, useEffect, useRef } from 'react';
import { NavLink, useNavigate, Link } from 'react-router-dom';
import {
  LayoutDashboard, MessageSquare, FilePlus, FileText,
  Calendar, Settings, LogOut, KeyRound, Video, ArrowUpRight,
  StickyNote, Plus, Trash2, ArrowLeft, Check, User, Menu, X as XIcon
} from 'lucide-react';
import useAuthStore from '../../store/authStore';
import useUIStore from '../../store/uiStore';
import useChatStore from '../../store/chatStore';
import ThemeToggle from './ThemeToggle';
import { changePassword, getTeamMembers } from '../../api/auth';
import { listSchedules } from '../../api/schedules';
import { listCalendarEvents } from '../../api/google';
import dayjs from 'dayjs';

const BLOCK_COLORS = [
  '#8EA1B1', // Blueish
  '#9DB099', // Greenish
  '#B1C9C2', // Mint
  '#C58B8B', // Rose
  '#C5A58B', // Tan
  '#C5B173', // Yellow/Gold
  '#C5919F', // Pink
  '#9F91C5', // Lavender
  '#A5A173', // Olive
  '#73A5A1', // Teal
  '#A19F83', // Khaki
  '#9FA183', // Moss
];

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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const [allDayMeetings, setAllDayMeetings] = useState([]);
  const [currentTime, setCurrentTime] = useState(dayjs());
  const [teamMembers, setTeamMembers] = useState([]);

  // 1분마다 현재 시간 업데이트
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(dayjs());
    }, 60000);
    return () => clearInterval(timer);
  }, []);

  // 현재 시간에 활성화된 일정만 필터링 (useMemo로 실시간성 확보)
  const todaySchedules = useMemo(() => {
    return allDayMeetings.filter(s => {
      const endTime = s.end_time ? dayjs(s.end_time) : dayjs(s.start_time).add(1, 'hour');
      return endTime.isAfter(currentTime);
    });
  }, [allDayMeetings, currentTime]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const todayStr = dayjs().format('YYYY-MM-DD');
        const endOfDayStr = dayjs().add(1, 'day').format('YYYY-MM-DD');
        
        const [schedulesRes, teamRes, googleRes] = await Promise.all([
          listSchedules({
            start_time_gte: `${todayStr}T00:00:00`,
            start_time_lt: `${endOfDayStr}T00:00:00`,
            include_team: true,
            skip: 0,
          }),
          getTeamMembers().catch(() => ({ data: [] })),
          listCalendarEvents(todayStr, endOfDayStr).then(res => res.data || []).catch(() => [])
        ]);
        
        let dbSchedules = (schedulesRes.items || schedulesRes.data || []);
        let googleSchedules = Array.isArray(googleRes) ? googleRes : [];
        
        const isToday = (dateStr) => dayjs(dateStr).isSame(dayjs(), 'day');
        const mergedSchedules = [...dbSchedules];
        
        googleSchedules.forEach(ge => {
          const duplicate = dbSchedules.some(
            s => s.title === ge.title && isToday(s.start_time)
          );
          if (!duplicate) mergedSchedules.push(ge);
        });

        let todayAllMeetings = mergedSchedules
          .filter(s => isToday(s.start_time))
          .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
        
        todayAllMeetings.forEach((s, i) => s.originalIndex = i);

        setAllDayMeetings(todayAllMeetings);

        const members = teamRes.data || teamRes || [];
        setTeamMembers((Array.isArray(members) ? members : []).filter(m => m.id !== user?.id));
      } catch (err) {
        console.error('Failed to fetch topbar data', err);
      }
    };
    if (user?.id) fetchData();
  }, [user]);

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
      <header className={`flex-shrink-0 z-20 transition-all duration-300 ease-in-out ${isScrolled ? 'h-[60px] bg-transparent pointer-events-none -mb-[60px]' : 'h-[100px] bg-white/40 backdrop-blur-md border-b border-white/20'}`}>
        <div className={`flex items-center justify-between px-4 md:grid md:grid-cols-[1fr_auto_1fr] md:px-10 h-full transition-all duration-300 ease-in-out ${isScrolled ? 'pointer-events-auto' : ''}`}>

          {/* 좌측 - 로고 */}
          <div className={`flex items-center transition-opacity duration-300 ${isScrolled ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}>
            <a href="/dashboard" className="flex items-center gap-3">
              <img src="/logo.png" alt="Logo" className={`object-contain transition-all py-1 ${isScrolled ? 'w-14' : 'w-24'}`} />
            </a>
          </div>

          {/* 모바일 햄버거 */}
          <button
            className="md:hidden p-2 rounded-md text-primary-700 hover:bg-primary-50 transition"
            onClick={() => setMobileMenuOpen((o) => !o)}
          >
            {mobileMenuOpen ? <XIcon size={22} /> : <Menu size={22} />}
          </button>

          {/* 중앙 - Your Schedule Timeline (데스크톱) */}
          <div className="hidden md:flex justify-center w-[650px] xl:w-[800px]">
            <div className={`bg-white border border-neutral-200 text-neutral-800 rounded-[32px] flex items-center p-1.5 w-full shadow-sm transition-transform duration-300 transform origin-center ${isScrolled ? 'scale-[0.88]' : 'scale-100'}`}>
              
              {/* 왼쪽 Label section */}
              <div className="flex items-center gap-3 pl-5 pr-3 whitespace-nowrap border-r border-neutral-200">
                <span className="text-sm font-extrabold tracking-tight text-neutral-800">Your Schedule</span>
                <div className="bg-neutral-50 rounded-full px-3 py-1.5 flex items-center gap-2 border border-neutral-200">
                  <Calendar size={13} className="text-neutral-500" />
                  <span className="text-[11px] text-neutral-600 font-semibold">{dayjs().format('DD MMMM')}</span>
                </div>
              </div>
              
              {/* 타임라인 영역 */}
              <div className="flex-1 bg-neutral-50/50 rounded-full flex items-center px-1 mx-1 h-[48px] relative overflow-visible border border-neutral-100 shadow-inner">
                {todaySchedules.length > 0 ? (() => {
                  const currentEvent = todaySchedules[0];
                  const isTeamEvent = currentEvent.schedule_type === 'meeting' || currentEvent.is_team_visible;
                  const activeBgColor = BLOCK_COLORS[(currentEvent.originalIndex || 0) % BLOCK_COLORS.length];

                  return (
                    <div className="flex w-full items-center relative group cursor-default">
                      {/* Active Event Block */}
                      <div className="h-[42px] rounded-[21px] flex items-center justify-between text-white px-3 min-w-[320px] max-w-[65%] w-full relative z-20 shadow-sm overflow-visible flex-shrink-0 border border-white/10 transition-colors" style={{ backgroundColor: activeBgColor }}>
                      
                        <div className="flex items-center gap-3 w-full">
                          {/* 참석자 아바타 */}
                          <div className="flex -space-x-1.5 items-center pl-1">
                            <div className="h-7 w-7 rounded-full bg-white shadow-sm border-2 flex items-center justify-center overflow-hidden z-30" style={{ borderColor: activeBgColor }}>
                              {user?.profile_image || user?.profile_picture || user?.avatar || user?.avatar_url ? (
                                <img src={user?.profile_image || user?.profile_picture || user?.avatar || user?.avatar_url} alt={user.name} className="w-full h-full object-cover" />
                              ) : (
                                <span className="text-[10px] font-bold" style={{ color: activeBgColor }}>{user?.name?.[0] || 'Me'}</span>
                              )}
                            </div>
                            {isTeamEvent && (
                              <>
                                {teamMembers.slice(0, 2).map((member, idx) => {
                                  const zClass = idx === 0 ? 'z-20' : 'z-10';
                                  return (
                                    <div key={member.id} className={`h-7 w-7 rounded-full shadow-sm border-2 bg-white flex items-center justify-center overflow-hidden ${zClass}`} style={{ borderColor: activeBgColor }}>
                                      {member.profile_image || member.profile_picture || member.avatar || member.avatar_url ? (
                                        <img src={member.profile_image || member.profile_picture || member.avatar || member.avatar_url} alt={member.name} className="w-full h-full object-cover" />
                                      ) : (
                                        <span className="text-[10px] font-bold" style={{ color: activeBgColor }}>{member.name?.[0] || 'T'}</span>
                                      )}
                                    </div>
                                  );
                                })}
                                {teamMembers.length > 2 && (
                                  <div className="h-7 w-7 rounded-full bg-white/30 shadow-sm border-2 border-white/50 flex items-center justify-center z-0 backdrop-blur-sm">
                                    <span className="text-[10px] font-bold text-white">+{teamMembers.length - 2}</span>
                                  </div>
                                )}
                              </>
                            )}
                          </div>
                   
                          <div className="flex items-center gap-2 flex-1 min-w-0 pr-2">
                            <div className="text-white/40">
                              <ArrowUpRight size={14} strokeWidth={3} />
                            </div>
                            <div className="font-bold text-[13px] text-white whitespace-nowrap pl-1 pr-3 border-r border-white/30 truncate" title={dayjs(currentEvent.start_time).format('h:mm A')}>
                              {dayjs(currentEvent.start_time).format('h:mm A')}
                            </div>
                            <div className="flex-1 flex justify-start pl-2 min-w-0" title={currentEvent.title}>
                              <span className="text-[13px] font-extrabold truncate text-white shrink leading-none pt-0.5 tracking-wide">{currentEvent.title}</span>
                            </div>
                          </div>

                          {/* 우측 아이콘 */}
                          <div className="flex gap-1.5 shrink-0">
                            {currentEvent.meet_link && (
                              <a href={currentEvent.meet_link} target="_blank" rel="noreferrer" className="w-6 h-6 flex items-center justify-center bg-white hover:bg-neutral-100 rounded-full transition-all shadow-sm" style={{ color: activeBgColor }}>
                                <Video size={12} strokeWidth={2.5} />
                              </a>
                            )}
                          </div>
                        </div>
                      
                        {/* Current Time Indicator */}
                        <div className="absolute -top-4 right-1/4 bg-neutral-800 text-white text-[9px] font-bold px-2 py-0.5 rounded-full z-50 shadow-md flex items-center gap-1.5 border border-neutral-700/50">
                          <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse shadow-[0_0_4px_#4ade80]" />
                          {currentTime.format('h:mm A')}
                        </div>
                      </div>
                    
                      {/* Upcoming Next Event (Overlapping) */}
                      {todaySchedules.length > 1 && (() => {
                        const nextEvent = todaySchedules[1];
                        const nextBgColor = BLOCK_COLORS[(nextEvent.originalIndex || 0) % BLOCK_COLORS.length];
                        const isNextTeamEvent = nextEvent.schedule_type === 'meeting' || nextEvent.is_team_visible;

                        return (
                          <div 
                            className="h-[42px] rounded-[21px] flex items-center justify-between text-white/90 px-3 pl-8 -ml-6 flex-shrink-0 w-[30%] min-w-[120px] border border-white/10 shadow-inner overflow-hidden relative z-10 transition-all hover:scale-[1.02] cursor-default" 
                            style={{ backgroundColor: nextBgColor }}
                          >
                            <div className="flex items-center gap-2 w-full">
                              <div className="font-bold text-[11px] whitespace-nowrap border-r border-white/20 pr-2">
                                {dayjs(nextEvent.start_time).format('h:mm A')}
                              </div>
                              <div className="flex-1 min-w-0">
                                <span className="text-[11px] font-extrabold truncate block" title={nextEvent.title}>
                                  {nextEvent.title}
                                </span>
                              </div>
                              {/* Small Avatar for Next Event */}
                              <div className="flex -space-x-1 items-center grayscale-[0.3] opacity-80 scale-90">
                                <div className="h-5 w-5 rounded-full bg-white/20 border border-white/30 flex items-center justify-center overflow-hidden">
                                  {user?.profile_image || user?.profile_picture || user?.avatar || user?.avatar_url ? (
                                    <img src={user?.profile_image || user?.profile_picture || user?.avatar || user?.avatar_url} alt={user.name} className="w-full h-full object-cover" />
                                  ) : (
                                    <span className="text-[8px] font-bold text-white">{user?.name?.[0] || 'Me'}</span>
                                  )}
                                </div>
                                {isNextTeamEvent && (
                                  <div className="h-5 w-5 rounded-full bg-white/10 border border-white/20 flex items-center justify-center">
                                    <span className="text-[8px] font-bold text-white/70">T</span>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  ); })() : (
                    <div className="flex w-full h-full items-center justify-center">
                      <span className="text-[13px] font-bold text-neutral-400">No scheduled events today</span>
                    </div>
                  )}
              </div>

              {/* 더보기 버튼 */}
              <Link to="/schedules" className="w-[36px] h-[36px] ml-1 mr-1 rounded-full bg-neutral-900 flex items-center justify-center hover:bg-neutral-800 transition-colors text-white focus:outline-none flex-shrink-0 shadow-sm">
                <ArrowUpRight size={16} strokeWidth={2.5} />
              </Link>
            </div>
          </div>

          {/* 우측 - 유틸리티 (데스크톱) */}
          <div className={`hidden md:flex items-center justify-end gap-3 transition-opacity duration-300 ${isScrolled ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}>
            <ThemeToggle />
            <MemoPanel />

            <div className="relative" ref={userMenuRef}>
              <button
                onClick={() => setUserMenuOpen((o) => !o)}
                className="flex items-center gap-2 px-2 py-1 rounded-md hover:bg-neutral-border/30 transition-all"
              >
                <div className={`rounded-full bg-accent-500 border border-neutral-border/20 flex items-center justify-center font-bold text-white flex-shrink-0 transition-all duration-300 ease-in-out overflow-hidden shadow-sm ${isScrolled ? 'w-6 h-6 text-[10px]' : 'w-8 h-8 text-xs'}`}>
                  {user?.profile_image || user?.profile_picture || user?.avatar || user?.avatar_url ? (
                    <img src={user?.profile_image || user?.profile_picture || user?.avatar || user?.avatar_url} alt={user.name} className="w-full h-full object-cover" />
                  ) : (
                    user?.name?.[0] || '?'
                  )}
                </div>
                <span className={`font-medium text-neutral-sub transition-all duration-300 ease-in-out ${isScrolled ? 'text-xs' : 'text-sm'}`}>{user?.name || '사용자'}</span>
                {user?.team && (
                  <span className={`px-1.5 py-0.5 rounded bg-primary-50 text-primary-700 font-medium transition-all duration-300 ease-in-out ${isScrolled ? 'text-[9px]' : 'text-[10px]'}`}>{user.team}</span>
                )}
              </button>

              {userMenuOpen && (
                <div className="absolute right-0 top-full mt-1.5 w-44 bg-surface-card border border-neutral-border rounded-md shadow-md z-50 overflow-hidden">
                  <div className="px-3 py-2.5 border-b border-neutral-divider">
                    <div className="text-xs font-semibold text-neutral-main">{user?.name || '사용자'}</div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="text-[0.625rem] text-neutral-muted">{user?.is_admin ? '관리자' : '일반 사용자'}</span>
                      {user?.team && (
                        <span className="px-1.5 py-px rounded bg-primary-50 text-primary-700 text-[0.625rem] font-medium">{user.team}</span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => { navigate('/mypage'); setUserMenuOpen(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-neutral-sub hover:text-neutral-main hover:bg-neutral-divider transition-all"
                  >
                    <User size={12} />
                    마이페이지
                  </button>
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

      {/* 모바일 네비게이션 드롭다운 */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed inset-x-0 top-[56px] bg-surface-card border-b border-neutral-border shadow-lg z-40">
          <nav className="flex flex-col px-4 py-2">
            {getNavItems(user?.is_admin).map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-3 rounded-md text-sm font-medium transition ${
                    isActive
                      ? 'text-primary-900 bg-primary-50'
                      : 'text-neutral-sub hover:bg-surface-hover'
                  }`
                }
              >
                <item.icon size={18} />
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3 px-6 py-3 border-t border-neutral-divider">
            <ThemeToggle />
            <MemoPanel />
            <span className="text-xs text-neutral-sub ml-auto">{user?.name || '사용자'}</span>
          </div>
        </div>
      )}

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
