import { useState, useEffect, useMemo } from 'react';
import useGoogleServices from '../hooks/useGoogleServices';
import GoogleServicesConnect from '../components/schedules/GoogleServicesConnect';
import CalendarView from '../components/schedules/CalendarView';
import ScheduleForm from '../components/schedules/ScheduleForm';
import TasksPanel from '../components/schedules/TasksPanel';
import SheetsDashboard from '../components/schedules/SheetsDashboard';
import EmailReminderButton from '../components/schedules/EmailReminderButton';

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

  // 30초마다 자동 갱신
  useEffect(() => {
    if (!connected || !hasScope('calendar')) return;

    const interval = setInterval(() => {
      fetchCalendarEvents();
    }, 30000);

    return () => clearInterval(interval);
  }, [connected, hasScope, fetchCalendarEvents]);

  // Google Calendar 이벤트를 CalendarView 형식으로 변환
  const events = useMemo(() => {
    console.log('[SchedulesPage] Calendar 이벤트 변환:', calendarEvents);
    if (!calendarEvents || calendarEvents.length === 0) {
      console.log('[SchedulesPage] Calendar 이벤트 없음');
      return [];
    }

    const converted = calendarEvents.map(event => {
      // 백엔드 응답 형식: { title, start: "ISO string", end: "ISO string", meet_link }
      const start = new Date(event.start);
      const end = new Date(event.end);

      // 시간 포맷 (dateTime이 있으면 시간 표시, date만 있으면 종일)
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

    console.log('[SchedulesPage] 변환된 이벤트:', converted);
    return converted;
  }, [calendarEvents]);

  const handleAddSchedule = async (data) => {
    if (!data.date || !data.title) return;

    // Google Calendar 연결 시 실제 API로 추가
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

        // Google Meet 포함 여부에 따라 다른 API 호출
        if (data.create_meet) {
          await useGoogleServices.getState().createEventWithMeet(eventData);
        } else {
          await useGoogleServices.getState().syncEventToGoogle(eventData);
        }

        alert('✅ Google Calendar에 일정이 추가되었습니다!');
      } catch (error) {
        alert('❌ 일정 추가 실패: ' + (error.message || '알 수 없는 오류'));
        console.error(error);
      }
    } else {
      alert('⚠️ Google Calendar에 연결되지 않았습니다. 먼저 연결해주세요.');
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

          {/* 에러 메시지 */}
          {calendarError && (
            <div className="mb-5 p-4 bg-error-bg border border-error rounded-md">
              <p className="text-sm text-error font-medium">❌ {calendarError}</p>
            </div>
          )}

          {/* 디버깅 정보 */}
          <div className="mb-5 p-3 bg-info-bg border border-neutral-border rounded-md text-xs space-y-1">
            <div className="font-semibold mb-2">🔍 디버깅 정보</div>
            <div>Google 연결: {connected ? '✅ 연결됨' : '❌ 연결 안됨'}</div>
            <div>Calendar 권한: {hasScope('calendar') ? '✅ 있음' : '❌ 없음'}</div>
            <div>이벤트 개수: {calendarEvents?.length || 0}개</div>
            <div>변환된 이벤트: {events?.length || 0}개</div>
            {calendarEvents && calendarEvents.length > 0 && (
              <details className="mt-2">
                <summary className="cursor-pointer font-semibold">첫 번째 이벤트 원본 데이터</summary>
                <pre className="mt-2 p-2 bg-surface-card rounded text-[0.625rem] overflow-auto max-h-40">
                  {JSON.stringify(calendarEvents[0], null, 2)}
                </pre>
              </details>
            )}
            {events && events.length > 0 && (
              <details className="mt-2">
                <summary className="cursor-pointer font-semibold">첫 번째 변환된 이벤트</summary>
                <pre className="mt-2 p-2 bg-surface-card rounded text-[0.625rem] overflow-auto">
                  {JSON.stringify(events[0], null, 2)}
                </pre>
              </details>
            )}
          </div>

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
                    ⚠️ Google Calendar에 연결하면 실제 일정이 표시됩니다.
                  </p>
                </div>
              )}
              {connected && !hasScope('calendar') && (
                <div className="mt-5 p-4 bg-error-bg border border-error rounded-md text-center">
                  <p className="text-sm text-error font-medium">
                    ❌ Google Calendar 권한이 없습니다. 다시 연결해주세요.
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
