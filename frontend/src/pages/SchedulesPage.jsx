import { useState } from 'react';
import GoogleServicesConnect from '../components/schedules/GoogleServicesConnect';
import CalendarView from '../components/schedules/CalendarView';
import ScheduleForm from '../components/schedules/ScheduleForm';
import TasksPanel from '../components/schedules/TasksPanel';
import SheetsDashboard from '../components/schedules/SheetsDashboard';
import EmailReminderButton from '../components/schedules/EmailReminderButton';
import ActionItemList from '../components/dashboard/ActionItemList';

const mockEvents = [
  // ── 2월 ──
  { month: 2, day: 3, type: 'meeting', label: '보안점검 정기회의', time: '10:00~11:00' },
  { month: 2, day: 5, type: 'meeting', label: '프로젝트 킥오프', time: '14:00~15:30', meetLink: 'https://meet.google.com/abc-defg-hij' },
  { month: 2, day: 8, type: 'deadline', label: '권한검토 완료 마감' },
  { month: 2, day: 10, type: 'meeting', label: '인사규정 검토 회의', time: '09:30~10:30' },
  { month: 2, day: 13, type: 'meeting', label: '주간 스프린트 리뷰', time: '11:00~12:00', meetLink: 'https://meet.google.com/xyz-abcd-efg' },
  { month: 2, day: 18, type: 'google', label: '영화 <휴민트> 관람', time: '19:00~21:30' },
  { month: 2, day: 20, type: 'deadline', label: 'API 스키마 확정 마감' },
  { month: 2, day: 24, type: 'meeting', label: '중간 발표 리허설', time: '13:00~14:30' },
  { month: 2, day: 27, type: 'google', label: '팀 회식', time: '18:30~21:00' },

  // ── 1월 ──
  { month: 1, day: 6, type: 'meeting', label: '프로젝트 기획 회의', time: '10:00~11:30' },
  { month: 1, day: 15, type: 'google', label: '멘토링 세션', time: '16:00~17:00' },
  { month: 1, day: 22, type: 'deadline', label: '환경 세팅 완료 마감' },

  // ── 3월 ──
  { month: 3, day: 3, type: 'meeting', label: '3단계 Agent 개발 킥오프', time: '10:00~11:30', meetLink: 'https://meet.google.com/mar-kick-off' },
  { month: 3, day: 14, type: 'deadline', label: 'Google Services 연동 완료' },
  { month: 3, day: 24, type: 'meeting', label: '최종 발표 리허설', time: '13:00~15:00', meetLink: 'https://meet.google.com/final-prep' },
  { month: 3, day: 26, type: 'google', label: '팀 회식', time: '18:30~21:00' },
  { month: 3, day: 28, type: 'deadline', label: '배포 준비 완료 마감' },
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
    const d = new Date(data.date);
    const newEvent = {
      month: d.getMonth() + 1,
      day: d.getDate(),
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
              { dot: 'bg-red-400', l: '공휴일' },
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
