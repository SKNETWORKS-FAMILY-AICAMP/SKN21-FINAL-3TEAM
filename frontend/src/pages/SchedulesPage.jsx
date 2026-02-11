import { useState } from 'react';
import GoogleServicesConnect from '../components/schedules/GoogleServicesConnect';
import CalendarView from '../components/schedules/CalendarView';
import ScheduleForm from '../components/schedules/ScheduleForm';
import TasksPanel from '../components/schedules/TasksPanel';
import SheetsDashboard from '../components/schedules/SheetsDashboard';
import EmailReminderButton from '../components/schedules/EmailReminderButton';
import ActionItemList from '../components/dashboard/ActionItemList';

const mockEvents = [
  { day: 3, type: 'meeting', label: '보안점검 정기회의' },
  { day: 4, type: 'google', label: '팀 점심' },
  { day: 5, type: 'meeting', label: '보안점검 정기회의', meetLink: 'https://meet.google.com/abc-defg-hij' },
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
  const [showForm, setShowForm] = useState(false);
  const [activeTab, setActiveTab] = useState('calendar');
  const [events, setEvents] = useState(() => {
    const saved = localStorage.getItem('dudu_schedules');
    return saved ? [...mockEvents, ...JSON.parse(saved)] : mockEvents;
  });

  const handleAddSchedule = (data) => {
    if (!data.date || !data.title) return;
    const day = new Date(data.date).getDate();
    const newEvent = {
      day,
      type: data.type || 'meeting',
      label: data.title,
      time: `${data.start_time}~${data.end_time}`,
      date: data.date,
    };
    setEvents((prev) => {
      const updated = [...prev, newEvent];
      // mock 제외하고 사용자 추가분만 저장
      const userEvents = updated.filter((e) => e.date);
      localStorage.setItem('dudu_schedules', JSON.stringify(userEvents));
      return updated;
    });
    setShowForm(false);
  };

  return (
    <div>
      {/* 헤더 */}
      <header className="flex justify-between items-center py-6 sticky top-0 bg-surface-main z-10">
        <div>
          <h1 className="text-2xl font-bold">일정 관리</h1>
          <p className="text-sm text-neutral-sub mt-1">Action Item과 회의 일정을 통합 관리합니다</p>
        </div>
        <div className="flex items-center gap-3">
          <EmailReminderButton bulk daysBefore={3} />
          <button onClick={() => setShowForm(!showForm)} className="btn-primary">
            {showForm ? '취소' : '+ 일정 추가'}
          </button>
        </div>
      </header>

      {/* Google 서비스 연결 */}
      <GoogleServicesConnect />

      {/* 일정 추가 팝업 */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20" onClick={() => setShowForm(false)}>
          <div className="w-[420px]" onClick={(e) => e.stopPropagation()}>
            <ScheduleForm onSubmit={handleAddSchedule} onClose={() => setShowForm(false)} />
          </div>
        </div>
      )}

      {/* 탭 네비게이션 */}
      <div className="flex gap-1 mb-5">
        {[
          { key: 'calendar', label: '캘린더' },
          { key: 'tasks', label: 'Tasks' },
          { key: 'sheets', label: 'Sheets' },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition ${
              activeTab === key
                ? 'bg-primary-50 text-primary-700 font-semibold'
                : 'text-neutral-sub hover:bg-surface-hover'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* 탭 컨텐츠 */}
      {activeTab === 'calendar' && (
        <>
          {/* 범례 */}
          <div className="flex gap-4 mb-5">
            {[
              { dot: 'bg-primary-500', l: '회의' },
              { dot: 'bg-error', l: '마감일' },
              { dot: 'bg-success', l: 'Google Calendar' },
            ].map(({ dot, l }) => (
              <div key={l} className="flex items-center gap-1.5 text-xs text-neutral-sub">
                <span className={`w-2.5 h-2.5 rounded-full ${dot}`} />{l}
              </div>
            ))}
          </div>
          <CalendarView events={events} />
          <div className="mt-5">
            <ActionItemList items={mockActions} />
          </div>
        </>
      )}

      {activeTab === 'tasks' && <TasksPanel />}
      {activeTab === 'sheets' && <SheetsDashboard />}
    </div>
  );
}
