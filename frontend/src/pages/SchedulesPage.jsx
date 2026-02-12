import { useState, useEffect, useMemo } from 'react';
import useGoogleServices from '../hooks/useGoogleServices';
import GoogleServicesConnect from '../components/schedules/GoogleServicesConnect';
import CalendarView from '../components/schedules/CalendarView';
import ScheduleForm from '../components/schedules/ScheduleForm';
import TasksPanel from '../components/schedules/TasksPanel';
import SheetsDashboard from '../components/schedules/SheetsDashboard';

export default function SchedulesPage() {
  const { connected, calendarEvents, calendarLoading, calendarError, fetchCalendarEvents, hasScope } = useGoogleServices();
  const [showForm, setShowForm] = useState(false);
  const [activeTab, setActiveTab] = useState('calendar');

  // Google Calendar 연결 시 이벤트 자동 로드 (백엔드 기본값: ±3개월)
  useEffect(() => {
    if (connected && hasScope('calendar')) {
      fetchCalendarEvents();
    }
  }, [connected, hasScope, fetchCalendarEvents]);


  // Google Calendar 이벤트를 CalendarView 형식으로 변환
  const events = useMemo(() => {
    if (!calendarEvents || calendarEvents.length === 0) return [];

    return calendarEvents.map(event => {
      const start = new Date(event.start);
      const end = new Date(event.end);

      const hasTime = event.start.includes('T');
      const timeStr = hasTime
        ? `${start.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}~${end.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}`
        : null;

      return {
        month: start.getMonth() + 1,
        day: start.getDate(),
        type: 'google',
        label: event.title || '제목 없음',
        time: timeStr,
        meetLink: event.meet_link,
      };
    });
  }, [calendarEvents]);

  const handleAddSchedule = async (data) => {
    if (!data.date || !data.title) return;

    if (connected && hasScope('calendar')) {
      try {
        const startDateTime = new Date(`${data.date}T${data.start_time}:00`);
        const endDateTime = new Date(`${data.date}T${data.end_time}:00`);

        const eventData = {
          title: data.title,
          description: data.description || '',
          start_time: startDateTime,
          end_time: endDateTime,
          attendee_emails: data.attendees || [],
        };

        if (data.create_meet) {
          await useGoogleServices.getState().createEventWithMeet(eventData);
        } else {
          await useGoogleServices.getState().syncEventToGoogle(eventData);
        }

        fetchCalendarEvents();
      } catch (error) {
        console.error(error);
      }
    }

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
          {connected && hasScope('calendar') && (
            <button
              onClick={() => fetchCalendarEvents()}
              disabled={calendarLoading}
              className="btn-outline"
              title="Google Calendar 동기화"
            >
              {calendarLoading ? '🔄 동기화 중...' : '🔄 새로고침'}
            </button>
          )}
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

          {/* 에러 메시지 */}
          {calendarError && (
            <div className="mb-5 p-4 bg-error-bg border border-error rounded-md">
              <p className="text-sm text-error font-medium">{calendarError}</p>
            </div>
          )}

          {calendarLoading ? (
            <div className="flex justify-center items-center h-64">
              <div className="text-neutral-sub">Google Calendar 이벤트 로딩 중...</div>
            </div>
          ) : (
            <>
              <CalendarView events={events} />
              {!connected && (
                <div className="mt-5 p-4 bg-warning-bg border border-warning rounded-md text-center">
                  <p className="text-sm text-warning font-medium">
                    Google Calendar에 연결하면 실제 일정이 표시됩니다.
                  </p>
                </div>
              )}
            </>
          )}
        </>
      )}

      {activeTab === 'tasks' && <TasksPanel />}
      {activeTab === 'sheets' && <SheetsDashboard />}
    </div>
  );
}
