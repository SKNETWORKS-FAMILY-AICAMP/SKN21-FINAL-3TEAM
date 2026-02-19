import { Reorder } from 'framer-motion';
import { X, Plus, Pencil, Check, RotateCcw } from 'lucide-react';
import GreetingBanner from '../components/dashboard/GreetingBanner';
import TodaySchedule from '../components/dashboard/TodaySchedule';
import AIChatWidget from '../components/dashboard/AIChatWidget';
import ActivityTimeline from '../components/dashboard/ActivityTimeline';
import CalendarWidget from '../components/dashboard/CalendarWidget';
import RecentDocs from '../components/dashboard/RecentDocs';
import useUIStore from '../store/uiStore';
import { FileText, HelpCircle, Calendar, CalendarClock } from 'lucide-react';

// ── mock 데이터 ──
const mockActivities = [
  { type: 'doc', icon: FileText, title: '정보보안 지침 v2.3 업로드', description: '새 문서가 업로드되어 파싱 완료되었습니다.', time: '5분 전', to: '/documents' },
  { type: 'query', icon: HelpCircle, title: '질의응답: "외부 반출 승인 절차"', description: 'AI가 Yes/No 판단과 근거를 제공했습니다.', time: '12분 전', to: '/chat' },
  { type: 'meeting', icon: Calendar, title: '보안점검 회의록 분석 완료', description: '5개 결정사항, 8개 Action Item 추출됨', time: '1시간 전', to: '/meetings' },
  { type: 'schedule', icon: CalendarClock, title: '일정 변경: 인사규정 검토회의', description: '2월 7일 → 2월 10일로 변경되었습니다.', time: '2시간 전', to: '/schedules' },
];

const mockActions = [
  { title: '정보보안 교육 계획서 제출', assignee: '김정보', deadline: 'D-1', priority: 'high' },
  { title: '개인정보 접근 권한 검토', assignee: '이개발', deadline: 'D-3', priority: 'medium' },
  { title: '신규 입사자 보안 서약서 수집', assignee: '박인사', deadline: 'D-7', priority: 'low' },
];

const mockMeetings = [
  { time: '10:00', period: 'AM', title: '보안점검 정기회의', location: '회의실 A', attendees: 5 },
  { time: '2:00', period: 'PM', title: '인사규정 개정 검토', location: '온라인', attendees: 8 },
];

const mockDocs = [
  { name: '정보보안 지침 v2.3', version: 'v2.3', date: '2026-02-05', status: '적용중' },
  { name: '인사규정 매뉴얼', version: 'v1.8', date: '2026-01-28', status: '개정중' },
];

const calEvents = { 3: 'meeting', 6: 'deadline', 10: 'meeting' };

// ── 위젯 레지스트리 ──
const WIDGET_REGISTRY = {
  TodaySchedule: { component: TodaySchedule, label: '오늘 일정', props: { meetings: mockMeetings, actions: mockActions } },
  ActivityTimeline: { component: ActivityTimeline, label: '최근 활동', props: { activities: mockActivities } },
  AIChatWidget: { component: AIChatWidget, label: 'AI 어시스턴트', props: {} },
  CalendarWidget: { component: CalendarWidget, label: '캘린더', props: { events: calEvents } },
  RecentDocs: { component: RecentDocs, label: '최근 문서', props: { docs: mockDocs } },
};

// ── 위젯 카드 (편집 모드에서 래핑) ──
function WidgetItem({ id, editMode, onHide }) {
  const entry = WIDGET_REGISTRY[id];
  if (!entry) return null;
  const { component: Comp, props } = entry;

  if (!editMode) return <Comp {...props} />;

  return (
    <div className="relative group">
      <div className="rounded-lg border-2 border-dashed border-primary-300 dark:border-primary-600">
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

// ── 컬럼 (Reorder 그룹) ──
function DraggableColumn({ items, onReorder, editMode, onHide }) {
  if (!editMode) {
    return (
      <div className="space-y-5">
        {items.map(id => (
          <WidgetItem key={id} id={id} editMode={false} onHide={onHide} />
        ))}
      </div>
    );
  }

  return (
    <Reorder.Group axis="y" values={items} onReorder={onReorder} className="space-y-5">
      {items.map(id => (
        <Reorder.Item key={id} value={id} className="cursor-grab active:cursor-grabbing">
          <WidgetItem id={id} editMode onHide={onHide} />
        </Reorder.Item>
      ))}
    </Reorder.Group>
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
    setLeftColumn, setRightColumn,
    hideWidget, restoreWidget, resetDashboard,
  } = useUIStore();

  const { leftColumn, rightColumn, hidden } = dashboard;

  return (
    <div className="py-6">
      <GreetingBanner meetingCount={2} actionCount={2} riskCount={0} />

      <div className="mt-5 grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-5">
        <DraggableColumn
          items={leftColumn}
          onReorder={setLeftColumn}
          editMode={editMode}
          onHide={hideWidget}
        />
        <DraggableColumn
          items={rightColumn}
          onReorder={setRightColumn}
          editMode={editMode}
          onHide={hideWidget}
        />
      </div>

      {/* 숨긴 위젯 영역 */}
      {editMode && hidden.length > 0 && (
        <div className="mt-5">
          <p className="text-xs text-neutral-muted mb-2 font-medium">숨긴 위젯 (클릭하여 복원)</p>
          <div className="flex flex-wrap gap-3">
            {hidden.map(id => (
              <HiddenWidgetCard key={id} id={id} onRestore={restoreWidget} />
            ))}
          </div>
        </div>
      )}

      {/* 하단 편집/완료 버튼 */}
      <div className="flex items-center justify-center gap-3 mt-8">
        <button
          onClick={toggleEditMode}
          className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors shadow-sm ${
            editMode
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
