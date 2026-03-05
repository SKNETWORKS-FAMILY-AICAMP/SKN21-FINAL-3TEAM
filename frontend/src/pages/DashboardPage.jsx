import { useState, useEffect } from 'react';
import { X, Plus, Minus, Pencil, Check, RotateCcw } from 'lucide-react';
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
import { SkeletonCard } from '../components/common/Skeleton';
import useUIStore from '../store/uiStore';
import useGoogleStore from '../store/googleStore';
import { FileText, HelpCircle, CalendarClock } from 'lucide-react';
import { listSchedules } from '../api/schedules';
import { listDocuments } from '../api/documents';
import { listSessions } from '../api/chat';

// ── 날짜 유틸 ──
function isToday(dateStr) {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  const now = new Date();
  return d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
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
  const [loading, setLoading] = useState(true);
  const calendarEvents = useGoogleStore((s) => s.calendarEvents);
  const googleConnected = useGoogleStore((s) => s.connected);

  useEffect(() => {
    let cancelled = false;
    async function fetchAll() {
      const results = await Promise.allSettled([
        listSchedules({ include_team: true }).then(r => r.data),
        listDocuments().then(r => r.data),
        listSessions(),
      ]);
      if (cancelled) return;
      if (results[0].status === 'fulfilled') setSchedules(results[0].value || []);
      if (results[1].status === 'fulfilled') setDocs(results[1].value || []);
      if (results[2].status === 'fulfilled') setSessions(results[2].value || []);
      setLoading(false);
    }
    fetchAll();
    return () => { cancelled = true; };
  }, []);

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

  // 오늘 일정 → TodaySchedule meetings
  const todayMeetings = mergedSchedules
    .filter(s => isToday(s.start_time))
    .sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
    .map(s => {
      const { time, period } = formatTime12(s.start_time);
      return {
        time,
        period,
        title: s.title,
        location: s.google_meet_link ? '온라인 (Meet)' : s.description || '-',
        attendees: 0,
        scheduleType: s.schedule_type,
        start_time: s.start_time,
        end_time: s.end_time,
      };
    });

  // 마감 임박 (7일 이내 deadline 일정)
  const upcomingActions = mergedSchedules
    .filter(s => {
      if (s.schedule_type === 'meeting' && isToday(s.start_time)) return false;
      const d = daysUntil(s.end_time || s.start_time);
      return d !== null && d >= 0 && d <= 7;
    })
    .sort((a, b) => new Date(a.end_time || a.start_time) - new Date(b.end_time || b.start_time))
    .slice(0, 5)
    .map(s => {
      const d = daysUntil(s.end_time || s.start_time);
      return {
        title: s.title,
        assignee: '',
        deadline: d === 0 ? 'D-Day' : `D-${d}`,
        priority: d <= 1 ? 'high' : d <= 3 ? 'medium' : 'low',
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

  // GreetingBanner 카운트
  const meetingCount = todayMeetings.length;
  const actionCount = upcomingActions.length;

  return {
    loading,
    todayMeetings,
    upcomingActions,
    recentDocs,
    allSchedules,
    recentActivities,
    meetingCount,
    actionCount,
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
        className="absolute -top-2 -right-2 z-10 w-6 h-6 rounded-full bg-surface-card text-neutral-muted border border-neutral-border flex items-center justify-center shadow-lg hover:scale-110 transition-transform"
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

// ── 숨긴 위젯 카드 ──
function HiddenWidgetCard({ id, onRestore }) {
  const entry = WIDGET_REGISTRY[id];
  if (!entry) return null;

  return (
    <button
      onClick={() => onRestore(id)}
      className="flex items-center gap-2 px-4 py-3 rounded-lg border-2 border-dashed border-neutral-300 dark:border-neutral-600 text-neutral-sub hover:border-primary-400 hover:text-primary-700 dark:hover:border-primary-500 dark:hover:text-primary-400 transition-colors"
    >
      <Plus size={16} />
      <span className="text-sm font-medium">{entry.label}</span>
    </button>
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
    upcomingActions,
    recentDocs,
    allSchedules,
    recentActivities,
    meetingCount,
    actionCount,
  } = useDashboardData();

  // 위젯별 props 매핑
  const widgetProps = {
    WhatsOnWidget: {},
    ScheduleTimelineWidget: { meetings: todayMeetings },
    TodaySchedule: { meetings: todayMeetings, actions: upcomingActions },
    ActivityTimeline: { activities: recentActivities },
    AIChatWidget: {},
    CalendarWidget: { allSchedules },
    RecentDocs: { docs: recentDocs },
    TeamMembersWidget: {},
    EmployeeTableWidget: {},
    TaskPipelineWidget: {},
    ApprovalQueueWidget: {},
  };

  const [dragId, setDragId] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);

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
      <GreetingBanner meetingCount={meetingCount} actionCount={actionCount} riskCount={0} />

      {loading && (
        <div className="mt-5 grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-5 min-w-0">
          <div className="space-y-5"><SkeletonCard lines={4} /><SkeletonCard lines={3} /><SkeletonCard lines={2} /></div>
          <div className="space-y-5"><SkeletonCard lines={2} /><SkeletonCard lines={3} /></div>
        </div>
      )}

      <div className="mt-5 grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-5 min-w-0">
        <WidgetColumn col="leftColumn" items={leftColumn} editMode={editMode} onHide={hideWidget} {...dragProps} widgetProps={widgetProps} />
        <WidgetColumn col="rightColumn" items={rightColumn} editMode={editMode} onHide={hideWidget} {...dragProps} widgetProps={widgetProps} />
      </div>

      {/* 숨긴 위젯 영역 및 레이아웃 제어 */}
      {editMode && (
        <div className="mt-5 space-y-4">
          {/* 상단 레이아웃 제어 */}
          <div>
            <p className="text-xs text-neutral-muted mb-2 font-medium">상단 레이아웃 제어</p>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={toggleTopbarSchedule}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg border-2 border-dashed transition-colors ${
                  dashboard.topbarScheduleHidden 
                    ? 'border-neutral-300 dark:border-neutral-600 text-neutral-sub hover:border-primary-400 hover:text-primary-700 dark:hover:border-primary-500 dark:hover:text-primary-400' 
                    : 'border-primary-300 text-primary-700 bg-primary-50 dark:border-primary-700 dark:text-primary-300 dark:bg-primary-900/20 hover:border-error hover:text-error hover:bg-error-bg'
                }`}
              >
                {dashboard.topbarScheduleHidden ? <Plus size={16} /> : <Minus size={16} className="text-error" />}
                <span className="text-sm font-medium">상단 스케줄 바 {dashboard.topbarScheduleHidden ? '복원' : '숨기기'}</span>
              </button>
            </div>
          </div>

          {/* 숨긴 위젯 요소가 있을 경우만 렌더링 */}
          {hidden.length > 0 && (
            <div>
              <p className="text-xs text-neutral-muted mb-2 font-medium">숨긴 위젯 (클릭하여 복원)</p>
              <div className="flex flex-wrap gap-3">
                {hidden.map(id => (
                  <HiddenWidgetCard key={id} id={id} onRestore={restoreWidget} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 하단 편집/완료 버튼 */}
      <div className="flex items-center justify-center gap-3 mt-8">
        <button
          onClick={toggleEditMode}
          className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors shadow-sm ${editMode
            ? 'bg-success text-white hover:bg-success/90'
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
    </div>
  );
}
