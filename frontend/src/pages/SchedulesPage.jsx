import { useState, useEffect, useMemo } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Users } from 'lucide-react';
import useGoogleServices from '../hooks/useGoogleServices';
import useAuthStore from '../store/authStore';
import { sendMeetingInvite } from '../api/google';
import { listSchedules, createSchedule } from '../api/schedules';
import GoogleServicesConnect from '../components/schedules/GoogleServicesConnect';
import CalendarView from '../components/schedules/CalendarView';
import ScheduleForm from '../components/schedules/ScheduleForm';
import ScheduleTypeManager from '../components/schedules/ScheduleTypeManager';
import TasksPanel from '../components/schedules/TasksPanel';
import SheetsDashboard from '../components/schedules/SheetsDashboard';
import useScheduleTypeStore, { DEFAULT_TYPES } from '../store/scheduleTypeStore';

export default function SchedulesPage() {
  const { isScrolled } = useOutletContext();
  const { connected, calendarEvents, calendarLoading, calendarError, fetchCalendarEvents, hasScope, syncEventToGoogle, createEventWithMeet, deleteCalendarEvent } = useGoogleServices();
  const { customTypes } = useScheduleTypeStore();
  const allTypes = [...DEFAULT_TYPES, ...customTypes];

  // calendarId → typeId 역매핑 (커스텀 유형이 Google Calendar에 연동된 경우)
  const calendarIdToType = useMemo(() => {
    const map = {};
    allTypes.forEach((t) => { if (t.calendarId) map[t.calendarId] = t.id; });
    return map;
  }, [allTypes]);

  const user = useAuthStore((s) => s.user);
  const hasTeam = !!user?.team;
  const [showForm, setShowForm] = useState(false);
  const [showTypeManager, setShowTypeManager] = useState(false);
  const [activeTab, setActiveTab] = useState('calendar');
  const [showTeamSchedules, setShowTeamSchedules] = useState(false);
  const [teamSchedules, setTeamSchedules] = useState([]);

  // Google Calendar 연결 시 이벤트 자동 로드 (백엔드 기본값: ±3개월)
  useEffect(() => {
    if (connected && hasScope('calendar')) {
      fetchCalendarEvents();
    }
  }, [connected, hasScope, fetchCalendarEvents]);

  // 팀 일정 토글 시 DB 일정 로드
  useEffect(() => {
    if (showTeamSchedules && hasTeam) {
      listSchedules({ include_team: true }).then((res) => {
        const dbSchedules = (res.data || [])
          .filter((s) => s.user_name && s.user_name !== user?.name) // 본인 제외, 팀원만
          .map((s) => {
            const start = new Date(s.start_time);
            const end = s.end_time ? new Date(s.end_time) : start;
            const timeStr = `${start.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}~${end.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}`;
            return {
              month: start.getMonth() + 1,
              day: start.getDate(),
              type: s.schedule_type || 'meeting',
              label: `[${s.user_name}] ${s.title}`,
              time: timeStr,
              isTeamMember: true,
            };
          });
        setTeamSchedules(dbSchedules);
      }).catch(() => setTeamSchedules([]));
    } else {
      setTeamSchedules([]);
    }
  }, [showTeamSchedules, hasTeam]);


  // Google Calendar 이벤트를 CalendarView 형식으로 변환 (연결된 경우만)
  const events = useMemo(() => {
    if (!connected || !calendarEvents || calendarEvents.length === 0) return [];

    return calendarEvents.map(event => {
      const start = new Date(event.start);
      const end = new Date(event.end);

      const hasTime = event.start.includes('T');
      const timeStr = hasTime
        ? `${start.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}~${end.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}`
        : null;

      return {
        id: event.event_id,
        calendarId: event.calendar_id,
        month: start.getMonth() + 1,
        day: start.getDate(),
        type: event.event_type || calendarIdToType[event.calendar_id] || 'google',
        label: event.title || '제목 없음',
        time: timeStr,
        meetLink: event.meet_link,
      };
    });
  }, [calendarEvents]);

  // 팀원 일정과 병합
  const allEvents = useMemo(() => {
    return [...events, ...teamSchedules];
  }, [events, teamSchedules]);

  const handleAddSchedule = async (data) => {
    if (!data.date || !data.title) return;

    const startDateTime = data.allDay
      ? new Date(`${data.date}T00:00:00`)
      : new Date(`${data.date}T${data.start_time}:00`);
    const endDateTime = data.allDay
      ? new Date(`${data.date}T23:59:59`)
      : new Date(`${data.date}T${data.end_time}:00`);

    // 백엔드 DB에 일정 저장 (팀 공유 정보 포함)
    try {
      await createSchedule({
        title: data.title,
        description: data.description || '',
        start_time: startDateTime.toISOString(),
        end_time: endDateTime.toISOString(),
        schedule_type: data.type || 'meeting',
        is_team_visible: data.is_team_visible || false,
        include_meet: data.include_meet || false,
        attendee_emails: data.attendee_emails || [],
      });
    } catch (error) {
      console.error('일정 저장 실패:', error);
    }

    // Google Calendar 연동 (연결된 경우에만)
    if (connected && hasScope('calendar')) {
      try {
        const selectedType = allTypes.find((t) => t.id === data.type);
        const eventData = {
          title: data.title,
          description: data.description || '',
          start_time: startDateTime,
          end_time: endDateTime,
          attendee_emails: data.attendee_emails || [],
          event_type: data.type || 'google',
          calendar_id: selectedType?.calendarId || 'primary',
        };

        if (data.include_meet) {
          const result = await createEventWithMeet(eventData);

          if (result?.meet_link && data.attendee_emails?.length > 0 && hasScope('gmail_send')) {
            try {
              await sendMeetingInvite({
                recipient_emails: data.attendee_emails,
                meeting_title: data.title,
                meeting_time: startDateTime.toISOString(),
                meet_link: result.meet_link,
              });
            } catch (emailErr) {
              console.error('회의 초대 메일 발송 실패:', emailErr);
            }
          }
        } else {
          await syncEventToGoogle(eventData);
        }
      } catch (error) {
        console.error('Google Calendar 동기화 실패:', error);
      }
    }

    setShowForm(false);
  };

  return (
    <div>
      {/* 헤더 */}
      <header className={`flex justify-between items-center sticky top-0 bg-surface-main z-10 overflow-hidden transition-all duration-300 ${isScrolled ? 'h-[56px]' : 'h-[100px]'}`}>
        <div>
          <h1 className={`font-bold transition-all duration-300 ${isScrolled ? 'text-lg' : 'text-2xl'}`}>일정 관리</h1>
          <p className={`text-neutral-sub transition-all duration-300 overflow-hidden ${isScrolled ? 'text-xs mt-0 max-h-0 opacity-0' : 'text-sm mt-1 max-h-6 opacity-100'}`}>Action Item과 회의 일정을 통합 관리합니다</p>
        </div>
        {activeTab === 'calendar' && (
          <div className="flex items-center gap-3">
            {hasTeam && (
              <button
                onClick={() => setShowTeamSchedules(!showTeamSchedules)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium border transition ${
                  showTeamSchedules
                    ? 'bg-primary-50 border-primary-500 text-primary-700'
                    : 'border-neutral-border text-neutral-sub hover:border-primary-300'
                }`}
              >
                <Users size={15} />
                팀 일정
              </button>
            )}
            {connected && hasScope('calendar') && (
              <button
                onClick={() => fetchCalendarEvents()}
                disabled={calendarLoading}
                className="btn-outline"
                title="Google Calendar 동기화"
              >
                {calendarLoading ? '동기화 중...' : '새로고침'}
              </button>
            )}
            <button
              onClick={() => setShowTypeManager(true)}
              className="btn-outline"
              title="일정 유형 관리"
            >
              유형 관리
            </button>
            <button onClick={() => setShowForm(!showForm)} className="btn-primary">
              {showForm ? '취소' : '+ 일정 추가'}
            </button>
          </div>
        )}
      </header>

      {/* Google 서비스 연결 */}
      <GoogleServicesConnect />

      {/* 유형 관리 모달 */}
      {showTypeManager && (
        <ScheduleTypeManager onClose={() => setShowTypeManager(false)} />
      )}

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
              <CalendarView events={allEvents} onDeleteEvent={deleteCalendarEvent} />
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
