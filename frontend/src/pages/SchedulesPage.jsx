import GoogleCalendarConnect from '../components/schedules/GoogleCalendarConnect';
import CalendarView from '../components/schedules/CalendarView';
import ActionItemList from '../components/dashboard/ActionItemList';

const mockEvents = [
  { day: 3, type: 'meeting', label: '보안점검 정기회의' },
  { day: 4, type: 'google', label: '팀 점심' },
  { day: 5, type: 'meeting', label: '보안점검 정기회의' },
  { day: 5, type: 'google', label: '1:1 미팅' },
  { day: 6, type: 'deadline', label: '교육계획서 D-1' },
  { day: 8, type: 'deadline', label: '권한검토 D-3' },
  { day: 10, type: 'meeting', label: '인사규정 검토' },
  { day: 12, type: 'deadline', label: '서약서수집 D-7' },
];

const mockActions = [
  { title: '정보보안 교육 계획서 제출', assignee: '김정보', deadline: 'D-1 · 2026-02-06', priority: 'high' },
  { title: '개인정보 접근 권한 검토', assignee: '이개발', deadline: 'D-3 · 2026-02-08', priority: 'medium' },
  { title: '신규 입사자 보안 서약서 수집', assignee: '박인사', deadline: 'D-7 · 2026-02-12', priority: 'low' },
];

export default function SchedulesPage() {
  return (
    <div>
      <header className="flex justify-between items-center py-6 sticky top-0 bg-surface-main z-10">
        <div><h1 className="text-2xl font-bold">일정 관리</h1><p className="text-sm text-neutral-sub mt-1">Action Item과 회의 일정을 통합 관리합니다</p></div>
        <button className="btn-primary">+ 일정 추가</button>
      </header>
      <GoogleCalendarConnect connected email="kimjungbo@company.com" />
      <div className="flex gap-4 mb-5">
        {[{ dot: 'bg-primary-500', l: '회의' }, { dot: 'bg-error', l: '마감일' }, { dot: 'bg-success', l: 'Google Calendar' }].map(({ dot, l }) => (
          <div key={l} className="flex items-center gap-1.5 text-xs text-neutral-sub"><span className={`w-2.5 h-2.5 rounded-full ${dot}`} />{l}</div>
        ))}
      </div>
      <CalendarView events={mockEvents} />
      <div className="mt-5"><ActionItemList items={mockActions} /></div>
    </div>
  );
}
