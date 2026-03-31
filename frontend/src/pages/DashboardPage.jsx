import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Plus, Minus, Pencil, Check, RotateCcw, ArrowUp } from 'lucide-react';
import GreetingBanner from '../components/dashboard/GreetingBanner';
import TodaySchedule from '../components/dashboard/TodaySchedule';
import AIChatWidget from '../components/dashboard/AIChatWidget';
import ActivityTimeline from '../components/dashboard/ActivityTimeline';
import CalendarWidget from '../components/dashboard/CalendarWidget';
import RecentDocs from '../components/dashboard/RecentDocs';
import TeamMembersWidget from '../components/dashboard/TeamMembersWidget';
import TaskPipelineWidget from '../components/dashboard/TaskPipelineWidget';
import ApprovalQueueWidget from '../components/dashboard/ApprovalQueueWidget';
import ScheduleTimelineWidget from '../components/dashboard/ScheduleTimelineWidget';
import EmployeeTableWidget from '../components/dashboard/EmployeeTableWidget';
import WhatsOnWidget from '../components/dashboard/WhatsOnWidget';
import useUIStore from '../store/uiStore';
import useGoogleStore from '../store/googleStore';
import { FileText, HelpCircle, CalendarClock } from 'lucide-react';
import ErrorBoundary from '../components/common/ErrorBoundary';
import { listSchedules } from '../api/schedules';
import { listDocuments } from '../api/documents';
import { listSessions } from '../api/chat';
import { listPipelineTasks } from '../api/tasks';
import { listApprovals } from '../api/approvals';
import dayjs from 'dayjs';

// ── 날짜 유틸 ──
function isToday(dateStr) {
  if (!dateStr) return false;
  return dayjs(dateStr).format('YYYY-MM-DD') === dayjs().format('YYYY-MM-DD');
}

function formatTime12(dateStr) {
  if (!dateStr) return { time: '', period: '' };
  const d = new Date(dateStr);
  let h = d.getHours();
  const m = d.getMinutes();
  const period = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  return { time: `${h}:${String(m).padStart(2, '0')}`, period };
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  if (diff < 60000) return '방금 전';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}분 전`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}시간 전`;
  const d = new Date(dateStr);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function daysUntil(dateStr) {
  if (!dateStr) return null;
  const target = new Date(dateStr);
  const now = new Date();
  target.setHours(0, 0, 0, 0);
  now.setHours(0, 0, 0, 0);
  return Math.ceil((target - now) / 86400000);
}

// ── 대시보드 데이터 훅 ──
function useDashboardData() {
  const [schedules, setSchedules] = useState([]);
  const [docs, setDocs] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [pipelineTasks, setPipelineTasks] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const calendarEvents = useGoogleStore((s) => s.calendarEvents);
  const googleConnected = useGoogleStore((s) => s.connected);
  const fetchCalendarEvents = useGoogleStore((s) => s.fetchCalendarEvents);
  const fetchGoogleStatus = useGoogleStore((s) => s.fetchStatus);

  const fetchAll = (isCancelled) => {
    // 각 요청 독립 처리 — 하나가 느려도 나머지에 영향 없음
    listSchedules({ include_team: true })
      .then(r => { if (!isCancelled()) setSchedules(r.data || []); })
      .catch(() => {})
      .finally(() => { if (!isCancelled()) setLoading(false); });

    listDocuments()
      .then(r => { if (!isCancelled()) setDocs(r.data || []); })
      .catch(() => {});

    listSessions()
      .then(data => { if (!isCancelled()) setSessions(data || []); })
      .catch(() => {});

    listPipelineTasks()
      .then(r => { if (!isCancelled()) setPipelineTasks(r.data || []); })
      .catch(() => {});

    listApprovals()
      .then(r => { if (!isCancelled()) setApprovals(r.data || []); })
      .catch(() => {});
  };

  // 마운트 시 DB 데이터 + Google 연결 상태 로드
  useEffect(() => {
    let cancelled = false;
    fetchAll(() => cancelled);
    fetchGoogleStatus();
    return () => { cancelled = true; };
  }, []);

  // Google 연결 상태 변경 시 캘린더 이벤트 fetch
  useEffect(() => {
    if (googleConnected) fetchCalendarEvents();
  }, [googleConnected]);

  // 탭 포커스 시 데이터 리페치 (다른 페이지에서 일정 변경 후 돌아올 때)
  useEffect(() => {
    const handleFocus = () => {
      fetchAll(() => false);
      if (googleConnected) fetchCalendarEvents();
    };
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [googleConnected]);

  // Google Calendar 전체 이벤트를 schedule 형식으로 변환 (연결된 경우만)
  const googleSchedules = (!googleConnected ? [] : (calendarEvents || []))
    .map(e => ({
      title: e.title || '제목 없음',
      start_time: e.start,
      end_time: e.end,
      google_meet_link: e.meet_link || null,
      google_event_id: e.event_id,
      description: '',
      schedule_type: e.event_type || 'meeting',
      _source: 'google',
    }));

  // 백엔드 DB + Google Calendar 합치기 (중복 제거: google_event_id 또는 제목+날짜 기준)
  const dbGoogleIds = new Set(schedules.map(s => s.google_event_id).filter(Boolean));
  const mergedSchedules = [...schedules];
  googleSchedules.forEach(ge => {
    // google_event_id로 중복 체크
    if (ge.google_event_id && dbGoogleIds.has(ge.google_event_id)) return;
    // 제목+같은 날짜로 중복 체크
    const startDate = new Date(ge.start_time).toDateString();
    const duplicate = schedules.some(
      s => s.title === ge.title && new Date(s.start_time).toDateString() === startDate
    );
    if (!duplicate) mergedSchedules.push(ge);
  });

  // 오늘 일정 → TodaySchedule meetings (오늘 시작하는 일정만)
  const todayKey = dayjs().format('YYYY-MM-DD');
  const endOfTodayStr = dayjs().endOf('day').toISOString();
  const todayMeetings = mergedSchedules
    .filter(s => s.start_time && dayjs(s.start_time).format('YYYY-MM-DD') === todayKey)
    .sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
    .map(s => {
      const startStr = String(s.start_time || '');
      const endStr = String(s.end_time || '');

      const isMidnightStart = startStr.includes('T00:00:00') || startStr.endsWith('T00:00');
      const isMidnightEnd = endStr.includes('T23:59:59') || endStr.includes('T00:00:00') || endStr.endsWith('T00:00');

      const isAllDay = startStr.length <= 10 || s.is_all_day || s.all_day || (isMidnightStart && isMidnightEnd && startStr !== endStr);

      // 멀티데이 일정의 end_time을 오늘 자정으로 클램핑
      const clampedEnd = s.end_time && dayjs(s.end_time).isAfter(dayjs().endOf('day'))
        ? endOfTodayStr
        : s.end_time;

      const { time, period } = formatTime12(s.start_time);
      return {
        time: isAllDay ? '종일' : time,
        period: isAllDay ? '' : period,
        title: s.title,
        location: s.google_meet_link ? '온라인 (Meet)' : s.description || '-',
        attendees: 0,
        scheduleType: s.schedule_type,
        start_time: s.start_time,
        end_time: clampedEnd,
        isAllDay,
      };
    });

  // 오늘 진행 중인 멀티데이 일정 (오늘 이전에 시작 & 오늘 이후에 종료) — 카드 형식으로 변환
  const inProgressMeetings = mergedSchedules
    .filter(s => {
      if (!s.start_time || !s.end_time) return false;
      const startKey = dayjs(s.start_time).format('YYYY-MM-DD');
      const endKey = dayjs(s.end_time).format('YYYY-MM-DD');
      return startKey < todayKey && endKey >= todayKey;
    })
    .map(s => ({
      time: '종일',
      period: '',
      title: s.title,
      location: s.google_meet_link ? '온라인 (Meet)' : s.description || '-',
      attendees: 0,
      scheduleType: s.schedule_type,
      start_time: s.start_time,
      end_time: s.end_time,
      isAllDay: true,
    }));

  // 내일 일정
  const upcomingActions = mergedSchedules
    .filter(s => {
      const d = daysUntil(s.start_time);
      return d === 1;
    })
    .sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
    .slice(0, 5)
    .map(s => {
      const { time, period } = formatTime12(s.start_time);
      return {
        title: s.title,
        assignee: s.user_name || s.assigned_to || '',
        deadline: time ? `${period} ${time}` : '종일',
        priority: 'low',
      };
    });

  // 최근 문서 (최신 5개)
  const recentDocs = (Array.isArray(docs) ? docs : [])
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 5)
    .map(d => ({
      name: d.title || d.file_name || '제목 없음',
      version: d.file_type || '',
      date: d.created_at ? new Date(d.created_at).toLocaleDateString('ko-KR') : '',
      status: d.status === 'completed' ? '완료' : d.status === 'processing' ? '처리중' : '업로드됨',
    }));

  // ScheduleTimelineWidget용: 오늘 시작 일정 + 오늘이 포함된 멀티데이 일정
  const timelineMeetings = [
    ...todayMeetings,
    ...mergedSchedules
      .filter(s => {
        if (!s.start_time || !s.end_time) return false;
        const startKey = dayjs(s.start_time).format('YYYY-MM-DD');
        const endKey = dayjs(s.end_time).format('YYYY-MM-DD');
        return startKey < todayKey && endKey >= todayKey;
      })
      .map(s => ({
        time: '종일',
        period: '',
        title: s.title,
        location: s.google_meet_link ? '온라인 (Meet)' : s.description || '-',
        attendees: 0,
        scheduleType: s.schedule_type,
        start_time: s.start_time,
        end_time: s.end_time,
        isAllDay: true,
      })),
  ];

  // 전체 일정을 CalendarWidget에 전달 (위젯 내부에서 월별 필터링)
  const allSchedules = mergedSchedules;

  // 최근 활동 타임라인 (문서 + 채팅 세션 + 일정 조합, 최신 6개)
  const activities = [];

  (Array.isArray(docs) ? docs : []).slice(0, 3).forEach(d => {
    activities.push({
      type: 'doc',
      icon: FileText,
      title: `${d.title || d.file_name || '문서'} 업로드`,
      description: `${d.file_type || ''} 문서가 업로드되었습니다.`,
      time: timeAgo(d.created_at),
      to: '/documents',
      _ts: new Date(d.created_at || 0).getTime(),
    });
  });

  (Array.isArray(sessions) ? sessions : []).slice(0, 3).forEach(s => {
    activities.push({
      type: 'query',
      icon: HelpCircle,
      title: `대화: "${s.name || '새 대화'}"`,
      description: `AI 대화 세션`,
      time: timeAgo(s.updated_at || s.created_at),
      to: '/chat',
      _ts: new Date(s.updated_at || s.created_at || 0).getTime(),
    });
  });

  schedules.slice(0, 3).forEach(s => {
    activities.push({
      type: 'schedule',
      icon: CalendarClock,
      title: `일정: ${s.title}`,
      description: s.description || `${s.schedule_type} 일정`,
      time: timeAgo(s.created_at),
      to: '/schedules',
      _ts: new Date(s.created_at || 0).getTime(),
    });
  });

  activities.sort((a, b) => b._ts - a._ts);
  const recentActivities = activities.slice(0, 6);

  // 브리핑용: 오늘 마감 태스크 (done 제외)
  const todayKey2 = dayjs().format('YYYY-MM-DD');
  const todayDueTasks = (Array.isArray(pipelineTasks) ? pipelineTasks : [])
    .filter(t => {
      if (!t.due_date || t.stage === 'done') return false;
      return dayjs(t.due_date).format('YYYY-MM-DD') === todayKey2;
    })
    .map(t => ({
      title: t.title,
      assignee: t.assignee || '',
      priority: t.priority || 'medium',
      stage: t.stage || 'todo',
    }));

  // 브리핑용: 마감 초과 태스크 (done 제외)
  const overdueTasks = (Array.isArray(pipelineTasks) ? pipelineTasks : [])
    .filter(t => {
      if (!t.due_date || t.stage === 'done') return false;
      return dayjs(t.due_date).format('YYYY-MM-DD') < todayKey2;
    })
    .map(t => ({
      title: t.title,
      assignee: t.assignee || '',
      priority: t.priority || 'medium',
      stage: t.stage || 'todo',
      dueDate: t.due_date,
    }));

  // 브리핑용: 대기 결재 건수
  const pendingApprovalCount = (Array.isArray(approvals) ? approvals : [])
    .filter(a => a.status === 'pending').length;

  // GreetingBanner 카운트
  const meetingCount = todayMeetings.length;
  const actionCount = upcomingActions.length;

  return {
    loading,
    todayMeetings,
    timelineMeetings,
    inProgressMeetings,
    upcomingActions,
    recentDocs,
    allSchedules,
    recentActivities,
    meetingCount,
    actionCount,
    todayDueTasks,
    overdueTasks,
    pendingApprovalCount,
  };
}

// ── 위젯 레지스트리 (props는 DashboardPage에서 주입) ──
const WIDGET_REGISTRY = {
  WhatsOnWidget: { component: WhatsOnWidget, label: '이번 달 현황' },
  ScheduleTimelineWidget: { component: ScheduleTimelineWidget, label: '타임라인 일정' },
  TodaySchedule: { component: TodaySchedule, label: '오늘 일정' },
  ActivityTimeline: { component: ActivityTimeline, label: '최근 활동' },
  AIChatWidget: { component: AIChatWidget, label: 'AI 어시스턴트' },
  CalendarWidget: { component: CalendarWidget, label: '캘린더' },
  RecentDocs: { component: RecentDocs, label: '최근 문서' },
  TeamMembersWidget: { component: TeamMembersWidget, label: '팀원 상태' },
  EmployeeTableWidget: { component: EmployeeTableWidget, label: '팀원 테이블' },
  TaskPipelineWidget: { component: TaskPipelineWidget, label: '태스크 파이프라인' },
  ApprovalQueueWidget: { component: ApprovalQueueWidget, label: '승인 대기열' },
};

// ── 위젯 카드 ──
function WidgetItem({ id, col, editMode, onHide, isDragging, isDropTarget, onDragStart, onDragEnd, onDragOver, onDrop, widgetProps }) {
  const entry = WIDGET_REGISTRY[id];
  if (!entry) return null;
  const { component: Comp } = entry;
  const props = widgetProps[id] || {};

  if (!editMode) return <Comp {...props} />;

  return (
    <div
      draggable
      onDragStart={(e) => { e.stopPropagation(); onDragStart(id); }}
      onDragEnd={onDragEnd}
      onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); onDragOver(id, col); }}
      onDrop={(e) => { e.preventDefault(); e.stopPropagation(); onDrop(id, col); }}
      className={`relative group transition-opacity ${isDragging ? 'opacity-30' : ''}`}
    >
      {/* 드롭 위치 표시선 */}
      {isDropTarget && !isDragging && (
        <div className="absolute -top-3 left-0 right-0 h-1 bg-primary-500 rounded-full z-20 shadow-sm" />
      )}
      <div className="card border-2 border-dashed border-transparent hover:border-primary-300 dark:hover:border-primary-600 transition-colors cursor-grab active:cursor-grabbing">
        <Comp {...props} />
      </div>
      <button
        onClick={() => onHide(id)}
        className="absolute -top-1 -right-1 z-10 w-6 h-6 rounded-full bg-surface-card text-neutral-muted border border-neutral-border flex items-center justify-center shadow-lg hover:scale-110 transition-transform"
      >
        <X size={14} />
      </button>
    </div>
  );
}

// ── 컬럼 ──
function WidgetColumn({ col, items, editMode, onHide, dragId, dropTarget, onDragStart, onDragEnd, onDragOver, onDrop, onColumnDragOver, onColumnDrop, widgetProps }) {
  if (!editMode) {
    return (
      <div className="space-y-5 min-w-0 overflow-hidden">
        {items.map(id => (
          <WidgetItem key={id} id={id} editMode={false} onHide={onHide} widgetProps={widgetProps} />
        ))}
      </div>
    );
  }

  const isColumnEndTarget = dropTarget?.end && dropTarget?.col === col;

  return (
    <div
      className={`space-y-5 min-h-32 glass-container transition-all ${isColumnEndTarget ? 'outline-dashed outline-2 outline-primary-400 bg-primary-50/30 dark:bg-primary-900/10' : ''}`}
      onDragOver={(e) => { e.preventDefault(); onColumnDragOver(col); }}
      onDrop={(e) => { e.preventDefault(); onColumnDrop(col); }}
    >
      {items.map(id => (
        <WidgetItem
          key={id}
          id={id}
          col={col}
          editMode
          onHide={onHide}
          isDragging={dragId === id}
          isDropTarget={dropTarget?.id === id}
          onDragStart={onDragStart}
          onDragEnd={onDragEnd}
          onDragOver={onDragOver}
          onDrop={onDrop}
          widgetProps={widgetProps}
        />
      ))}
    </div>
  );
}


// ── 메인 페이지 ──
export default function DashboardPage() {
  const {
    dashboard, editMode, toggleEditMode,
    hideWidget, restoreWidget, resetDashboard, moveWidget,
    toggleTopbarSchedule,
  } = useUIStore();

  const { leftColumn, rightColumn, hidden } = dashboard;
  const {
    loading,
    todayMeetings,
    timelineMeetings,
    inProgressMeetings,
    upcomingActions,
    recentDocs,
    allSchedules,
    recentActivities,
    meetingCount,
    actionCount,
    todayDueTasks,
    overdueTasks,
    pendingApprovalCount,
  } = useDashboardData();

  // 위젯별 props 매핑
  const widgetProps = {
    WhatsOnWidget: {},
    ScheduleTimelineWidget: { meetings: timelineMeetings, loading },
    TodaySchedule: { meetings: [...inProgressMeetings, ...todayMeetings], actions: upcomingActions, loading, todayDueTasks, overdueTasks, pendingApprovalCount },
    ActivityTimeline: { activities: recentActivities, loading },
    AIChatWidget: {},
    CalendarWidget: { allSchedules },
    RecentDocs: { docs: recentDocs, loading },
    TeamMembersWidget: {},
    EmployeeTableWidget: {},
    TaskPipelineWidget: {},
    ApprovalQueueWidget: {},
  };

  const [dragId, setDragId] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);
  const [showScrollTop, setShowScrollTop] = useState(false);

  useEffect(() => {
    // Layout.jsx에서 `<main>` 태그가 스크롤을 담당하고 있음.
    const mainContent = document.querySelector('main');

    if (!mainContent) return;

    const handleScroll = (e) => {
      // main 태그의 scrollTop 속성으로 스크롤 위치 감지
      if (e.target.scrollTop > 300) {
        setShowScrollTop(true);
      } else {
        setShowScrollTop(false);
      }
    };

    mainContent.addEventListener('scroll', handleScroll, { passive: true });
    return () => mainContent.removeEventListener('scroll', handleScroll, { passive: true });
  }, []);

  const scrollToTop = () => {
    const mainContent = document.querySelector('main');
    if (mainContent) {
      mainContent.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleDragStart = (id) => setDragId(id);
  const handleDragEnd = () => { setDragId(null); setDropTarget(null); };
  const handleDragOver = (id, col) => { if (dragId !== id) setDropTarget({ id, col }); };
  const handleDrop = (targetId, targetCol) => {
    if (dragId && dragId !== targetId) moveWidget(dragId, targetId, targetCol);
    setDragId(null);
    setDropTarget(null);
  };
  const handleColumnDragOver = (col) => setDropTarget({ col, end: true });
  const handleColumnDrop = (col) => {
    if (dragId) moveWidget(dragId, null, col);
    setDragId(null);
    setDropTarget(null);
  };

  const dragProps = { dragId, dropTarget, onDragStart: handleDragStart, onDragEnd: handleDragEnd, onDragOver: handleDragOver, onDrop: handleDrop, onColumnDragOver: handleColumnDragOver, onColumnDrop: handleColumnDrop };

  return (
    <div className="py-6">
      <GreetingBanner meetingCount={meetingCount} actionCount={actionCount} riskCount={0} taskCount={todayDueTasks.length} overdueCount={overdueTasks.length} approvalCount={pendingApprovalCount} />


      {loading ? (
        <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
          <div className="w-10 h-10 border-[3px] border-primary-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm font-bold text-neutral-muted">대시보드 불러오는 중...</p>
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4 }}
          className="mt-5 grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-5 min-w-0"
        >
          <WidgetColumn col="leftColumn" items={leftColumn} editMode={editMode} onHide={hideWidget} {...dragProps} widgetProps={widgetProps} />
          <WidgetColumn col="rightColumn" items={rightColumn} editMode={editMode} onHide={hideWidget} {...dragProps} widgetProps={widgetProps} />
        </motion.div>
      )}

      {/* ── Widget Edit Mode UI ── */}
      <AnimatePresence>
        {editMode && (
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="mt-12 space-y-12 bg-white/30 dark:bg-black/10 backdrop-blur-xl p-10 rounded-[3.5rem] border border-dashed border-neutral-300 dark:border-neutral-800"
          >
            {/* 상단 레이아웃 제어 */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-6 bg-primary-500 rounded-full" />
                <h3 className="text-xl font-black text-neutral-900 dark:text-white tracking-tighter">상단 레이아웃 제어</h3>
              </div>
              <div className="flex flex-wrap gap-4">
                <button
                  onClick={toggleTopbarSchedule}
                  className={`flex items-center gap-3 px-6 py-4 rounded-2xl border-2 border-dashed transition-all group ${dashboard.topbarScheduleHidden
                    ? 'border-neutral-300 dark:border-neutral-700 text-neutral-500 hover:border-primary-500 hover:text-primary-600'
                    : 'border-primary-500 bg-primary-500/5 text-primary-600 dark:text-primary-400 hover:border-error hover:text-error'
                    }`}
                >
                  {dashboard.topbarScheduleHidden ? (
                    <Plus size={18} className="group-hover:rotate-90 transition-transform" />
                  ) : (
                    <Minus size={18} className="group-hover:scale-125 transition-transform" />
                  )}
                  <span className="text-sm font-black">상단 스케줄 바 {dashboard.topbarScheduleHidden ? '복원' : '숨기기'}</span>
                </button>
              </div>
            </div>

            {/* 사용 가능한 위젯 (Visual Previews) */}
            <div className="space-y-6">
              <div className="flex items-end justify-between border-b border-neutral-divider pb-6">
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-6 bg-indigo-500 rounded-full" />
                  <h3 className="text-3xl font-black text-neutral-900 dark:text-white tracking-tighter">사용 가능한 위젯</h3>
                </div>
                <p className="text-[11px] text-neutral-400 font-bold uppercase tracking-widest px-4 py-2 bg-neutral-100 dark:bg-white/5 rounded-full">
                  위젯을 드래그하여 대시보드로 옮기거나 + 를 눌러 추가하세요.
                </p>
              </div>

              {hidden.length === 0 ? (
                <div className="py-20 flex flex-col items-center justify-center opacity-40">
                  <RotateCcw size={48} className="text-neutral-300 mb-4" />
                  <p className="text-sm font-bold text-neutral-400">모든 위젯이 활성화되어 있습니다.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  {hidden.map(id => {
                    const entry = WIDGET_REGISTRY[id];
                    if (!entry || !entry.component) return null;
                    const Comp = entry.component;
                    const props = widgetProps[id] || {};
                    return (
                      <motion.div
                        key={`preview-${id}`}
                        draggable
                        onDragStart={(e) => { e.stopPropagation(); handleDragStart(id); }}
                        onDragEnd={handleDragEnd}
                        className="relative group cursor-grab active:cursor-grabbing h-fit"
                      >
                        {/* Add Button */}
                        <button
                          type="button"
                          onClick={() => restoreWidget(id)}
                          className="absolute top-1 right-1 z-10 w-6 h-6 rounded-full bg-surface-card text-neutral-muted border border-neutral-border flex items-center justify-center shadow-lg hover:scale-110 transition-transform"
                        >
                          <Plus size={14} className="group-hover/btn:rotate-90 transition-transform duration-300" />
                        </button>

                        {/* Dashed Border Container */}
                        <div className="absolute inset-0 border-2 border-dashed border-neutral-300 dark:border-neutral-700 rounded-[3rem] -z-10 group-hover:border-primary-400 group-hover:bg-primary-500/5 transition-all duration-300 bg-white/10 dark:bg-black/10" />

                        {/* Widget Wrapper (Scaled or constrained for preview) */}
                        <div className="p-6 overflow-hidden rounded-[3rem] opacity-60 group-hover:opacity-100 transition-all duration-300 scale-[0.96] group-hover:scale-100 min-h-[100px]">
                          <div className="pointer-events-none select-none filter blur-[0.3px] group-hover:blur-0 transition-all duration-500 grayscale-[0.2] group-hover:grayscale-0 pointer-events-none">
                            <ErrorBoundary fallback={<div className="p-4 text-xs text-red-400">Preview Load Error</div>}>
                              <Comp {...props} previewMode />
                            </ErrorBoundary>
                          </div>
                        </div>

                        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-white/90 dark:bg-neutral-900/90 backdrop-blur-md px-6 py-2 rounded-full border border-neutral-divider dark:border-white/10 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300 translate-y-4 group-hover:translate-y-0">
                          <span className="text-[12px] font-black uppercase tracking-[0.2em] text-neutral-500 dark:text-neutral-400">
                            {entry.label}
                          </span>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 하단 편집/완료 버튼 */}
      <div className="flex items-center justify-center gap-3 mt-8">
        <button
          onClick={toggleEditMode}
          className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors shadow-sm ${editMode
            ? 'bg-primary-500 text-white hover:bg-primary-700'
            : 'bg-surface-card border border-neutral-border text-neutral-main hover:bg-surface-hover'
            }`}
        >
          {editMode ? <><Check size={16} /> 완료</> : <><Pencil size={16} /> 편집</>}
        </button>
        {editMode && (
          <button
            onClick={resetDashboard}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-neutral-sub border border-neutral-border hover:bg-surface-hover transition-colors"
          >
            <RotateCcw size={14} /> 초기화
          </button>
        )}
      </div>
      {/* 하단 스크롤 투 탑 버튼 (플로팅) */}
      <div
        className={`fixed bottom-[30px] left-[30px] z-50 transition-all duration-300 transform ${showScrollTop ? 'opacity-100 translate-y-0 pointer-events-auto' : 'opacity-0 translate-y-4 pointer-events-none'}`}
      >
        <button
          onClick={scrollToTop}
          className="w-12 h-12 bg-white/30 dark:bg-neutral-800/30 backdrop-blur-sm border border-neutral-border/50 text-neutral-400 hover:bg-primary-500 hover:text-white hover:border-primary-500 hover:shadow-xl rounded-full shadow-lg flex items-center justify-center transition-colors focus:outline-none"
          title="맨 위로 가기"
        >
          <ArrowUp size={20} className="text-primary-600 dark:text-primary-400 font-bold stroke-[3px]" />
        </button>
      </div>
    </div>
  );
}
