import { useState, useEffect, useRef, useMemo } from 'react';
import { NavLink, useNavigate, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { createPortal } from 'react-dom';
import {
  LayoutDashboard, MessageSquare, FilePlus, FileText,
  Calendar, Settings, LogOut, Video, ArrowUpRight,
  StickyNote, Plus, Trash2, ArrowLeft, Check, User, Menu, X as XIcon, X
} from 'lucide-react';
import useAuthStore from '../../store/authStore';
import useUIStore from '../../store/uiStore';
import useChatStore from '../../store/chatStore';
import ThemeToggle from './ThemeToggle';
import { listSchedules } from '../../api/schedules';
import { listCalendarEvents } from '../../api/google';
import dayjs from 'dayjs';
import client from '../../api/client';

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

  const [position, setPosition] = useState({ x: null, y: null });
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef({ startX: 0, startY: 0, initialX: 0, initialY: 0 });

  // 패널 외부 클릭 시 닫기 (드래그 중이 아닐 때만)
  useEffect(() => {
    if (!open || isDragging) return;
    const handler = (e) => {
      // 드래그 핸들(헤더) 클릭 시에는 닫지 않음
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false);
        selectMemo(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, selectMemo, isDragging]);

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

  const handlePointerDown = (e) => {
    // Only left click
    if (e.button !== 0) return;
    // Don't drag if clicking buttons
    if (e.target.closest('button')) return;

    setIsDragging(true);

    // If position is not initialized yet (first drag), use current rect
    let startX = position.x;
    let startY = position.y;

    if (startX === null && panelRef.current) {
      const rect = panelRef.current.getBoundingClientRect();
      startX = rect.left;
      startY = rect.top;
    }

    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initialX: startX,
      initialY: startY,
    };

    e.preventDefault(); // Prevent text selection
  };

  useEffect(() => {
    if (!isDragging) return;

    const handlePointerMove = (e) => {
      const dx = e.clientX - dragRef.current.startX;
      const dy = e.clientY - dragRef.current.startY;
      setPosition({
        x: dragRef.current.initialX + dx,
        y: dragRef.current.initialY + dy,
      });
    };

    const handlePointerUp = () => {
      setIsDragging(false);
    };

    window.addEventListener('mousemove', handlePointerMove);
    window.addEventListener('mouseup', handlePointerUp);
    return () => {
      window.removeEventListener('mousemove', handlePointerMove);
      window.removeEventListener('mouseup', handlePointerUp);
    };
  }, [isDragging]);

  return (
    <div className="relative" ref={panelRef}>
      {/* 메모 버튼 */}
      <button
        onClick={() => setOpen((o) => !o)}
        title="메모"
        className={`w-10 h-10 rounded-full bg-white/40 dark:bg-white/10 shadow-sm border border-neutral-100/50 dark:border-white/10 flex items-center justify-center transition-colors relative ${open
          ? 'text-primary-900 border-primary-200 bg-white/60'
          : 'text-neutral-600 dark:text-neutral-300 hover:bg-white/60 dark:hover:bg-white/20'
          }`}
      >
        <FileText size={18} />
      </button>

      {/* 플로팅 메모 패널 */}
      {open && (
        <div
          ref={panelRef}
          className={`absolute w-72 bg-[#56728A]/80 dark:bg-[#141416]/80 backdrop-blur-xl border border-white/20 dark:border-white/10 rounded-xl shadow-xl overflow-hidden ${isDragging ? 'z-[100]' : 'z-50'}`}
          style={{
            // 드래그된 적이 있으면 그 위치 사용, 아니면 기본 위치(버튼 아래)
            ...(position.x !== null
              ? { position: 'fixed', left: position.x, top: position.y }
              : { right: 0, top: '100%', marginTop: '8px' }
            )
          }}
        >
          {/* 헤더 (드래그 핸들) */}
          <div
            className="flex items-center justify-between px-3 py-2.5 border-b border-sidebar-border cursor-move select-none active:bg-sidebar-border/30 transition-colors"
            onMouseDown={handlePointerDown}
          >
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
            <div className="flex items-center gap-1">
              <button
                onClick={addMemo}
                title="새 메모"
                className="w-6 h-6 flex items-center justify-center rounded hover:bg-white/10 text-sidebar-text-muted hover:text-sidebar-text transition"
              >
                <Plus size={14} />
              </button>
              <button
                onClick={handleClose}
                title="닫기"
                className="w-6 h-6 flex items-center justify-center rounded hover:bg-red-500/20 text-sidebar-text-muted hover:text-red-400 transition"
              >
                <XIcon size={14} />
              </button>
            </div>
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

/** 백엔드 상태 표시 (dev용 — 제거 시 이 컴포넌트 + 사용처 1줄 삭제) */
function BackendStatus() {
  const [status, setStatus] = useState('checking'); // 'ok' | 'down' | 'checking'
  const checkRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const res = await fetch('/health', { signal: AbortSignal.timeout(3000) });
        if (mounted) setStatus(res.ok ? 'ok' : 'down');
      } catch {
        if (mounted) setStatus('down');
      }
    };
    checkRef.current = check;
    check();
    const id = setInterval(check, 10_000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  const colors = {
    ok: 'bg-emerald-400 shadow-[0_0_6px_#34d399]',
    down: 'bg-red-400 shadow-[0_0_6px_#f87171] animate-pulse',
    checking: 'bg-yellow-400 shadow-[0_0_6px_#facc15] animate-pulse',
  };
  const labels = { ok: 'API 연결됨', down: 'API 끊김', checking: '확인 중...' };

  return (
    <div
      className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-white/30 dark:bg-white/5 border border-neutral-200/30 dark:border-white/10 cursor-pointer"
      title={`${labels[status]} (클릭: 재확인)`}
      onClick={() => { setStatus('checking'); checkRef.current?.(); }}
    >
      <div className={`w-2 h-2 rounded-full ${colors[status]}`} />
      <span className="text-[10px] font-bold text-neutral-600 dark:text-neutral-300 select-none">{labels[status]}</span>
    </div>
  );
}

// ── 상단바 컴포넌트 ──
export default function Topbar({ isScrolled = false }) {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const topbarScheduleHidden = useUIStore((s) => s.dashboard?.topbarScheduleHidden);
  const scheduleRefreshKey = useUIStore((s) => s.scheduleRefreshKey);

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef(null);

  const [allDayMeetings, setAllDayMeetings] = useState([]);
  const [teamMembers, setTeamMembers] = useState([]);
  const [currentTime, setCurrentTime] = useState(dayjs());
  const [hoveredEventId, setHoveredEventId] = useState(null);

  // 1분마다 현재 시간 업데이트
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(dayjs());
    }, 60000);
    return () => clearInterval(timer);
  }, []);

  // 당일 전체 일정을 유지 (과거 일정 포함)
  const todaySchedules = useMemo(() => {
    return allDayMeetings;
  }, [allDayMeetings]);

  const teamMemberMap = useMemo(() => {
    const map = {};
    teamMembers.forEach(m => {
      map[m.email] = { name: m.name, avatar: m.avatar };
    });
    return map;
  }, [teamMembers]);

  const PLAYHEAD_X_PCT = 35; // 35% from left

  const { eventLayouts, nowPixelX } = useMemo(() => {
    if (!todaySchedules || todaySchedules.length === 0) {
      return { eventLayouts: [], nowPixelX: 0 };
    }

    const PX_PER_MIN = 3.5; // 1시간 = 210px
    const startOfDay = dayjs().startOf('day');

    const layouts = [];

    // 1. 모든 일정을 시간 비례로 매핑
    todaySchedules.forEach((event, idx) => {
      const startTime = dayjs(event.start_time);
      const endTime = event.end_time ? dayjs(event.end_time) : dayjs(event.start_time).add(1, 'hour');

      const startDiffMins = startTime.diff(startOfDay, 'minute');
      let durationMins = endTime.diff(startTime, 'minute');

      // 최소 너비 제한 (너무 짧은 일정 방지, 20분 = 70px)
      let displayDurationMins = durationMins;
      if (displayDurationMins < 20) displayDurationMins = 20;

      const left = startDiffMins * PX_PER_MIN;
      const width = displayDurationMins * PX_PER_MIN;

      // 겹침 판별용 물리적 공간 (실제 시간 기반)
      const physicalRight = left + (durationMins * PX_PER_MIN);

      const isActive = !currentTime.isBefore(startTime) && currentTime.isBefore(endTime);
      const isPast = !currentTime.isBefore(endTime);

      layouts.push({
        event,
        left,
        width,
        isActive,
        isPast,
        bgColor: BLOCK_COLORS[(event.originalIndex || 0) % BLOCK_COLORS.length],
        isTeamEvent: event.schedule_type === 'meeting' || event.is_team_visible,
        staggerLayer: 0 // 밑에서 계산됨
      });
    });

    // 2. 물리적 겹침(Time Overlap)을 판별하여 staggerLayer 할당
    // 시작 시간 순 정렬
    layouts.sort((a, b) => a.left - b.left);

    const layers = [];
    layouts.forEach(lo => {
      let placed = false;
      for (let i = 0; i < layers.length; i++) {
        const lastInLayer = layers[i][layers[i].length - 1];
        // 시각적(width) 겹침을 기준으로 레이어 분리 (시각적 겹침 방지)
        if (lo.left >= lastInLayer.left + lastInLayer.width + 10) { // +10px 여백 추가
          layers[i].push(lo);
          lo.staggerLayer = i;
          placed = true;
          break;
        }
      }
      if (!placed) {
        layers.push([lo]);
        lo.staggerLayer = layers.length - 1;
      }
    });

    // 3. 현재 시간의 Pixel 좌표 계산
    const currentMins = currentTime.diff(startOfDay, 'minute');
    const computedNowPixelX = currentMins * PX_PER_MIN;

    return { eventLayouts: layouts, nowPixelX: computedNowPixelX };
  }, [todaySchedules, currentTime]);

  useEffect(() => {
    const fetchTeam = async () => {
      try {
        const res = await client.get('/auth/team-members');
        setTeamMembers(res.data || []);
      } catch (err) {
        console.error('Failed to fetch team members', err);
      }
    };
    if (user?.id) fetchTeam();
  }, [user]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const todayStr = dayjs().format('YYYY-MM-DD');
        const endOfDayStr = dayjs().add(1, 'day').format('YYYY-MM-DD');

        const timeMinStr = dayjs().startOf('day').toISOString();
        const timeMaxStr = dayjs().endOf('day').toISOString();

        const [schedulesRes, googleRes] = await Promise.all([
          listSchedules({
            start_time_gte: `${todayStr}T00:00:00`,
            start_time_lt: `${endOfDayStr}T00:00:00`,
            include_team: true,
            skip: 0,
          }),
          listCalendarEvents(timeMinStr, timeMaxStr).then(res => res.data || []).catch(() => [])
        ]);

        let dbSchedules = (schedulesRes.items || schedulesRes.data || []);
        let googleSchedules = Array.isArray(googleRes) ? googleRes : [];

        const todayKey = dayjs().format('YYYY-MM-DD');
        const isToday = (dateStr) => dateStr && dayjs(dateStr).format('YYYY-MM-DD') === todayKey;
        const mergedSchedules = [...dbSchedules];

        googleSchedules.forEach(ge => {
          const googleAttendees = (ge.attendees || []).map(a => {
            const email = a.email;
            const teamMember = teamMemberMap[email];
            return teamMember
              ? { name: teamMember.name, avatar: teamMember.avatar }
              : { name: a.displayName || email.split('@')[0], avatar: null };
          });

          const normalizedGe = {
            ...ge,
            start_time: ge.start,
            end_time: ge.end,
            schedule_type: 'google',
            attendees: googleAttendees
          };
          const duplicate = dbSchedules.some(
            s => s.title === normalizedGe.title && isToday(s.start_time)
          );
          if (!duplicate) mergedSchedules.push(normalizedGe);
        });

        let todayAllMeetings = mergedSchedules
          .filter(s => {
            if (!isToday(s.start_time)) return false;

            const startStr = String(s.start_time || '');
            const endStr = String(s.end_time || '');

            // 1. 날짜만 있는 경우 (YYYY-MM-DD 등 길이 10 이하)
            if (startStr.length <= 10) return false;

            // 2. 명시적 플래그
            if (s.is_all_day || s.all_day) return false;

            // 3. 멀티데이 일정 제외 (start와 end 날짜가 다르면)
            if (endStr && dayjs(s.end_time).format('YYYY-MM-DD') !== todayKey) return false;

            return true;
          })
          .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));

        todayAllMeetings.forEach((s, i) => s.originalIndex = i);

        setAllDayMeetings(todayAllMeetings);

      } catch (err) {
        console.error('Failed to fetch topbar data', err);
      }
    };
    if (user?.id) fetchData();
  }, [user, scheduleRefreshKey]);

  const handleLogout = () => {
    useChatStore.getState().reset();
    logout();
    navigate('/login');
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
      <header className={`absolute top-0 inset-x-0 z-40 transition-all duration-300 ease-in-out flex flex-col ${isScrolled ? 'pt-5 h-[60px] bg-transparent pointer-events-none' : (topbarScheduleHidden ? 'pt-1 h-[80px] bg-transparent' : 'pt-5 h-[160px] bg-transparent')}`}>

        {/* === Row 1: Schedule Timeline (Top) === */}
        {!topbarScheduleHidden && (
          <div className={`flex justify-center w-full px-4 md:px-10 transition-all duration-300 ease-in-out transform origin-top ${isScrolled ? 'hidden md:flex opacity-100 scale-[0.9] pointer-events-auto h-[56px] mb-0 mt-1' : 'opacity-100 scale-100 h-[56px] mb-4'}`}>
            <div className="hidden md:flex justify-center w-[580px] xl:w-[720px]">
              <div className={`border text-primary-800 dark:text-neutral-100 rounded-[32px] flex items-center p-1.5 w-full transition-all duration-300 ${isScrolled ? 'bg-white/40 dark:bg-[#111317]/40 backdrop-blur-lg border-neutral-200/50 dark:border-white/10 shadow-[0_8px_30px_rgb(0,0,0,0.08)]' : 'bg-white/10 dark:bg-black/10 border-neutral-200/20 dark:border-white/5 shadow-sm'}`}>

                {/* 왼쪽 Label section */}
                <div className="flex items-center gap-3 pl-5 pr-3 whitespace-nowrap border-r border-neutral-200/50 dark:border-white/10">
                  <span className="text-sm font-bold tracking-tight text-primary-900 dark:text-white">Your Schedule</span>
                  <div className="bg-white/20 dark:bg-white/5 rounded-full px-3 py-1.5 flex items-center gap-2 border border-neutral-200/20 dark:border-white/10">
                    <Calendar size={13} className="text-primary-600 dark:text-neutral-300" />
                    <span className="text-[11px] text-primary-700 dark:text-neutral-200 font-bold">{dayjs().format('DD MMMM')}</span>
                  </div>
                </div>

                {/* 타임라인 영역 (Outer: visible, Inner: hidden) */}
                <div className="flex-1 relative h-[56px] mx-1 rounded-[28px]">
                  {/* 둥근 테두리 및 마스크 레이어 */}
                  <div className="absolute inset-0 overflow-hidden rounded-[28px] border border-neutral-200/50 dark:border-white/10 shadow-inner bg-transparent">
                    {eventLayouts.length > 0 ? (
                      <div
                        className="absolute top-0 bottom-0 transition-transform duration-1000 ease-linear"
                        style={{
                          left: `${PLAYHEAD_X_PCT}%`,
                          transform: `translateX(-${nowPixelX}px)`
                        }}
                      >
                        {eventLayouts.map(({ event, left, staggerLayer, width, bgColor, isActive, isPast }) => {
                          const isHovered = hoveredEventId === event.id;
                          // zIndex 우선순위 (값이 클수록 위에 표시):
                          // 1. Hover 시: 50
                          // 2. 현재 시간 포함(isActive): 30 - staggerLayer (동시에 진행중일 때 일찍 시작한 게 위)
                          // 3. 미래(앞으로 올) 일정: 20 - staggerLayer
                          // 4. 지난 과거 일정(isPast): 10 - staggerLayer (가장 멀리 배치)
                          const baseZ = isActive ? 30 - staggerLayer : isPast ? 10 - staggerLayer : 20 - staggerLayer;
                          const finalZ = isHovered ? 50 : baseZ;

                          return (
                            <div
                              key={event.id}
                              onMouseEnter={() => setHoveredEventId(event.id)}
                              onMouseLeave={() => setHoveredEventId(null)}
                              className={`absolute top-[3px] bottom-[3px] rounded-[21px] flex items-center text-white cursor-pointer transition-all ${isActive ? 'shadow-[0_0_15px_rgba(255,255,255,0.3)]' : ''}`}
                              title={`${dayjs(event.start_time).format('hh:mm A')} - ${dayjs(event.end_time || dayjs(event.start_time).add(1, 'hour')).format('hh:mm A')} ${event.title}`}
                              style={{
                                left: `${left}px`,
                                width: `${width}px`,
                                zIndex: finalZ,
                                transform: isHovered
                                  ? `translate(${staggerLayer * 4}px, -4px) scale(1.02)`
                                  : `translate(${staggerLayer * 4}px, 0px)`,
                                boxShadow: isHovered
                                  ? '0 8px 20px rgba(0,0,0,0.4)'
                                  : (staggerLayer > 0 ? '0 4px 10px rgba(0,0,0,0.15)' : '0 2px 5px rgba(0,0,0,0.1)')
                              }}
                            >
                              {/* 실제 카드 배경과 이너 마스크 (여기에 overflow-hidden 적용) */}
                              <div
                                className={`absolute inset-0 rounded-[21px] overflow-hidden border ${isActive ? 'border-white/40' : 'border-white/20'}`}
                                style={{ backgroundColor: bgColor }}
                              >
                                <div className="flex items-center gap-2 w-full h-full px-3 min-w-0">
                                  {/* Inline Avatar Stack on Hover */}
                                  <AnimatePresence>
                                    {isHovered && (
                                      <motion.div
                                        initial={{ width: 0, opacity: 0, x: -10 }}
                                        animate={{ width: 'auto', opacity: 1, x: 0 }}
                                        exit={{ width: 0, opacity: 0, x: -10 }}
                                        className="flex -space-x-2 items-center shrink-0 pr-1"
                                      >
                                        {(event.attendees || []).length > 0 ? (
                                          (event.attendees || []).slice(0, 3).map((a, i) => (
                                            <div key={i} className="w-6 h-6 rounded-full border border-white/40 bg-accent-500 overflow-hidden shrink-0" title={a.name || a.email}>
                                              {a.avatar ? (
                                                <img src={a.avatar} alt={a.name} className="w-full h-full object-cover" />
                                              ) : (
                                                <div className="w-full h-full flex items-center justify-center text-white text-[9px] font-bold">{(a.name || a.email || '?')[0]}</div>
                                              )}
                                            </div>
                                          ))
                                        ) : (
                                          <div className="w-6 h-6 rounded-full border border-white/40 bg-accent-500 overflow-hidden shrink-0">
                                            {user?.avatar ? (
                                              <img src={user.avatar} alt={user.name} className="w-full h-full object-cover" />
                                            ) : (
                                              <div className="w-full h-full flex items-center justify-center text-white text-[9px] font-bold">
                                                {user?.name?.[0] || 'Me'}
                                              </div>
                                            )}
                                          </div>
                                        )}
                                        {(event.attendees || []).length > 3 && (
                                          <div className="w-6 h-6 rounded-full border border-white/40 bg-white/10 flex items-center justify-center text-white text-[9px] font-bold shrink-0 z-10">
                                            +{(event.attendees || []).length - 3}
                                          </div>
                                        )}
                                      </motion.div>
                                    )}
                                  </AnimatePresence>

                                  <span className="font-bold text-[12px] text-white whitespace-nowrap shrink-0">
                                    {dayjs(event.start_time).format('h:mm')} - {dayjs(event.end_time || dayjs(event.start_time).add(1, 'hour')).format('h:mm')}
                                  </span>
                                  <span className="text-white/50 text-[11px] shrink-0">|</span>
                                  <span className="text-[12px] font-bold truncate text-white leading-none tracking-wide">{event.title}</span>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="flex w-full h-full items-center justify-center">
                        <span className="text-[13px] font-bold text-neutral-500 dark:text-neutral-300">No scheduled events today</span>
                      </div>
                    )}
                  </div>

                  {/* Fixed Playhead (Now Indicator) - Outside of hidden mask */}
                  {eventLayouts.length > 0 && (
                    <div className="absolute top-0 bottom-0 z-50 pointer-events-none flex flex-col items-center" style={{ left: `${PLAYHEAD_X_PCT}%`, transform: 'translateX(-50%)' }}>
                      <div className="absolute -top-[14px] z-10 bg-primary-900 dark:bg-primary-800 text-white text-[10px] xl:text-[11px] font-bold px-2.5 py-0.5 rounded-full shadow-md flex items-center gap-1.5 whitespace-nowrap">
                        <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse shadow-[0_0_4px_#4ade80]" />
                        {currentTime.format('h:mm A')}
                      </div>
                      <div className="absolute top-[4px] bottom-0 w-[1.5px] bg-primary-900 dark:bg-primary-400/80 z-0 shadow-sm" />
                    </div>
                  )}
                </div>

                {/* 더보기 버튼 */}
                <Link to="/schedules" className="w-[44px] h-[44px] ml-1 mr-1 rounded-full bg-primary-900 dark:bg-white/10 flex items-center justify-center hover:bg-primary-700 dark:hover:bg-white/20 transition-colors text-white focus:outline-none flex-shrink-0 shadow-sm">
                  <ArrowUpRight size={18} strokeWidth={2.5} />
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* === Row 2: Navigation Bar (Bottom) === */}
        <div className={`flex items-center justify-between px-4 md:px-10 flex-shrink-0 transition-all duration-300 ease-in-out ${isScrolled ? 'opacity-100 md:opacity-0 pointer-events-auto md:pointer-events-none h-[60px] md:h-0 overflow-hidden bg-white/80 dark:bg-[#363A48]/80 backdrop-blur-md md:bg-transparent shadow-sm md:shadow-none' : `opacity-100 ${topbarScheduleHidden ? 'h-[76px]' : 'h-[60px]'} pointer-events-auto`}`}>

          {/* 좌측 - 로고 */}
          <div className="flex-1 flex items-center shrink-0">
            <Link to="/dashboard" className="flex items-center gap-3">
              <img src="/logo.png" alt="Logo" className="w-24 h-auto object-contain py-1" />
            </Link>
          </div>

          {/* 모바일 햄버거 */}
          <button
            className="md:hidden p-2 rounded-md text-primary-700 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-white/5 transition ml-auto"
            onClick={() => setMobileMenuOpen((o) => !o)}
          >
            {mobileMenuOpen ? <XIcon size={22} /> : <Menu size={22} />}
          </button>

          {/* 중앙 - 네비게이션 메뉴 (데스크톱) */}
          <nav className="hidden md:flex flex-none items-center gap-2 lg:gap-6">
            {getNavItems(user?.is_admin).map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-4 py-2 text-[13px] font-bold transition-all duration-200 border-b-2 ${isActive
                    ? 'text-primary-900 border-primary-700 dark:text-white dark:border-white'
                    : 'text-neutral-500 border-transparent hover:text-primary-900 dark:text-neutral-400 dark:hover:text-white'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {item.label}
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          {/* 우측 - 유틸리티 (데스크톱) */}
          <div className="flex-1 hidden md:flex items-center justify-end gap-3 transition-opacity duration-300">
            <BackendStatus />
            <ThemeToggle />
            <MemoPanel />

            <div className="relative" ref={userMenuRef}>
              <button
                onClick={() => setUserMenuOpen((o) => !o)}
                className="flex items-center gap-2 px-2 py-1.5 rounded-full hover:bg-neutral-border/30 dark:hover:bg-white/10 transition-all border border-transparent hover:border-neutral-200 dark:hover:border-white/10"
              >
                <div className="w-8 h-8 rounded-full bg-accent-500 border border-neutral-border/20 flex items-center justify-center font-bold text-white flex-shrink-0 overflow-hidden shadow-sm text-xs">
                  {user?.profile_image || user?.profile_picture || user?.avatar || user?.avatar_url ? (
                    <img src={user?.profile_image || user?.profile_picture || user?.avatar || user?.avatar_url} alt={user.name} className="w-full h-full object-cover" />
                  ) : (
                    user?.name?.[0] || '?'
                  )}
                </div>
              </button>

              {userMenuOpen && (
                <div className="absolute right-0 top-full mt-2 w-56 bg-surface-card border border-neutral-border/80 rounded-xl shadow-xl z-50 overflow-hidden backdrop-blur-md">
                  <div className="px-4 py-3.5 border-b border-neutral-divider bg-surface-hover/50">
                    <div className="text-sm font-bold text-neutral-main">{user?.name || '사용자'}</div>
                    <div className="flex items-center gap-2 mt-1.5">
                      <span className="px-2 py-0.5 rounded bg-primary-50 dark:bg-primary-900 text-primary-700 dark:text-primary-100 text-[10px] font-bold uppercase tracking-wider">{user?.is_admin ? 'ADMIN' : 'USER'}</span>
                      {user?.team && (
                        <span className="px-2 py-0.5 rounded bg-neutral-100 dark:bg-white/10 text-neutral-600 dark:text-neutral-300 text-[10px] font-bold">{user.team}</span>
                      )}
                    </div>
                  </div>
                  <div className="p-1">
                    <button
                      onClick={() => { navigate('/mypage'); setUserMenuOpen(false); }}
                      className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-neutral-sub hover:text-neutral-main hover:bg-neutral-divider/50 rounded-lg transition-all"
                    >
                      <User size={14} />
                      마이페이지
                    </button>
                  </div>
                  <div className="p-1 border-t border-neutral-divider">
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-error hover:bg-error-bg/50 rounded-lg transition-all"
                    >
                      <LogOut size={14} />
                      로그아웃
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* 모바일 네비게이션 드롭다운 */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed inset-x-0 top-[120px] bg-surface-card border-b border-neutral-border shadow-lg z-50 transform transition-transform">
          <nav className="flex flex-col px-4 py-2">
            {getNavItems(user?.is_admin).map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-3 rounded-md text-sm font-medium transition ${isActive
                    ? 'text-primary-900 bg-primary-50'
                    : 'text-neutral-sub hover:bg-surface-hover'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3 px-6 py-3 border-t border-neutral-divider">
            <ThemeToggle />
            <MemoPanel />
            <span className="text-xs text-neutral-sub ml-auto font-bold">{user?.name || '사용자'}</span>
          </div>
        </div>
      )}

    </>
  );
}
