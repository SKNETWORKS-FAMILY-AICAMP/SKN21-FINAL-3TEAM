import { useState, useEffect, useMemo } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Users } from 'lucide-react';
import useGoogleServices from '../hooks/useGoogleServices';
import useAuthStore from '../store/authStore';
import { sendMeetingInvite } from '../api/google';
import { listSchedules, createSchedule, deleteSchedule } from '../api/schedules';
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
  const [myDbSchedules, setMyDbSchedules] = useState([]);
  const [refreshKey, setRefreshKey] = useState(0);

  // 팀 소속 사용자는 팀 일정 자동 활성화 (user 비동기 로드 대응)
  useEffect(() => {
    if (hasTeam) setShowTeamSchedules(true);
  }, [hasTeam]);

  // Google Calendar 연결 시 이벤트 자동 로드 (백엔드 기본값: ±3개월)
  useEffect(() => {
    if (connected && hasScope('calendar')) {
      fetchCalendarEvents();
    }
  }, [connected, hasScope, fetchCalendarEvents]);

  // 본인 DB 일정 로드 (Google Calendar 미연결 시에도 일정 표시)
  useEffect(() => {
    listSchedules().then((res) => {
      const schedules = (res.data || []).map((s) => {
        const start = new Date(s.start_time);
        const end = s.end_time ? new Date(s.end_time) : start;
        const hasTime = s.start_time.includes('T');
        const timeStr = hasTime
          ? `${start.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}~${end.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}`
          : null;
        return {
          month: start.getMonth() + 1,
          day: start.getDate(),
          type: s.schedule_type || 'meeting',
          label: s.title,
          time: timeStr,
          googleEventId: s.google_event_id,
          scheduleId: s.id,
          userId: s.user_id,
        };
      });
      setMyDbSchedules(schedules);
    }).catch(() => setMyDbSchedules([]));
  }, [refreshKey]);

  // 팀 일정 로드
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
              scheduleId: s.id,
              userId: s.user_id,
            };
          });
        setTeamSchedules(dbSchedules);
      }).catch(() => setTeamSchedules([]));
    } else {
      setTeamSchedules([]);
    }
  }, [showTeamSchedules, hasTeam, refreshKey]);


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

  // Google Calendar + 본인 DB + 팀원 일정 병합
  // DB 일정이 schedule_type을 정확히 보존하므로 DB 우선, Google Calendar에서 meetLink만 보강
  const allEvents = useMemo(() => {
    const dbGoogleIds = new Set(myDbSchedules.map((s) => s.googleEventId).filter(Boolean));

    // Google Calendar meet 링크 맵
    const googleMeetMap = {};
    events.forEach((e) => { if (e.id) googleMeetMap[e.id] = e.meetLink; });

    // DB에 이미 있는 Google Calendar 이벤트는 제거 (DB의 type이 정확)
    const uniqueGoogleEvents = events.filter((e) => !e.id || !dbGoogleIds.has(e.id));

    // DB 일정에 meetLink 보강
    const enrichedDbSchedules = myDbSchedules.map((s) => ({
      ...s,
      meetLink: s.googleEventId ? googleMeetMap[s.googleEventId] : undefined,
    }));

    return [...uniqueGoogleEvents, ...enrichedDbSchedules, ...teamSchedules];
  }, [events, myDbSchedules, teamSchedules]);

  // 삭제 권한 판단: 본인 일정 또는 관리자만 삭제 가능 (공휴일은 항상 X)
  const canDelete = (event) => {
    if (event.type === 'holiday') return false;
    if (!event.scheduleId && !event.id) return false;
    if (user?.is_admin) return true;
    // DB 일정: 본인이 등록한 것만 삭제 가능
    if (event.scheduleId) return event.userId === user?.id;
    // Google Calendar 전용 이벤트(DB에 없음): 본인 캘린더이므로 삭제 허용
    return true;
  };

  // 통합 삭제 핸들러: DB 삭제 + Google Calendar 삭제
  const handleDeleteEvent = async (event) => {
    if (event.scheduleId) {
      // DB 일정 → 백엔드에서 DB + Google Calendar 모두 삭제
      await deleteSchedule(event.scheduleId);
    } else if (event.id) {
      // Google Calendar 전용 이벤트 → 기존 방식
      await deleteCalendarEvent(event.id, event.calendarId);
    }
    setRefreshKey((k) => k + 1);
    if (connected && hasScope('calendar')) fetchCalendarEvents();
  };

  const [scheduleError, setScheduleError] = useState(null);

  const handleAddSchedule = async (data) => {
    setScheduleError(null);

    // 타임존 없는 로컬 시간 문자열 (DB: TIMESTAMP WITHOUT TIME ZONE)
    const startStr = data.allDay
      ? `${data.date}T00:00:00`
      : `${data.date}T${data.start_time}:00`;
    const endStr = data.allDay
      ? `${data.date}T23:59:59`
      : `${data.date}T${data.end_time}:00`;

    const startDateTime = new Date(startStr);
    const endDateTime = new Date(endStr);

    // 1. 백엔드 DB에 일정 저장
    let googleSynced = false;
    let dbSaved = false;
    try {
      const result = await createSchedule({
        title: data.title,
        description: data.description || '',
        start_time: startStr,
        end_time: endStr,
        schedule_type: data.type || 'meeting',
        is_team_visible: data.is_team_visible || false,
        include_meet: data.include_meet || false,
        attendee_emails: data.attendee_emails || [],
      });
      dbSaved = true;
      googleSynced = result?.data?.google_services?.calendar_synced || false;
    } catch (error) {
      console.error('일정 저장 실패:', error);
      const msg = error.response?.data?.detail || '일정 저장에 실패했습니다. 다시 시도해주세요.';
      setScheduleError(msg);
      throw error; // ScheduleForm의 try-catch에서 잡아서 폼을 닫지 않음
    }

    // 2. Google Calendar 동기화 (백엔드에서 이미 동기화했으면 스킵)
    if (connected && hasScope('calendar') && !googleSynced) {
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
          const meetResult = await createEventWithMeet(eventData);
          if (meetResult?.meet_link && data.attendee_emails?.length > 0 && hasScope('gmail_send')) {
            try {
              await sendMeetingInvite({
                recipient_emails: data.attendee_emails,
                meeting_title: data.title,
                meeting_time: startDateTime,
                meet_link: meetResult.meet_link,
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

    // 3. 새로고침 + 폼 닫기 (DB 저장 성공 시에만 실행)
    setRefreshKey((k) => k + 1);
    if (connected && hasScope('calendar')) fetchCalendarEvents();
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
            {scheduleError && (
              <div className="mb-2 p-3 bg-red-50 border border-red-300 rounded-md">
                <p className="text-sm text-red-600 font-medium">{scheduleError}</p>
              </div>
            )}
            <ScheduleForm onSubmit={handleAddSchedule} onClose={() => { setShowForm(false); setScheduleError(null); }} />
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
          {(calendarError || scheduleError) && (
            <div className="mb-5 p-4 bg-red-50 border border-red-300 rounded-md">
              <p className="text-sm text-red-600 font-medium">{calendarError || scheduleError}</p>
            </div>
          )}

          {calendarLoading ? (
            <div className="flex justify-center items-center h-64">
              <div className="text-neutral-sub">Google Calendar 이벤트 로딩 중...</div>
            </div>
          ) : (
            <>
              <CalendarView events={allEvents} onDeleteEvent={handleDeleteEvent} onCanDelete={canDelete} />
              {!connected && (
                <div className="mt-5 p-4 bg-surface-hover border border-neutral-divider rounded-md text-center">
                  <p className="text-sm text-neutral-sub">
                    Google Calendar에 연결하면 외부 일정도 함께 동기화됩니다.
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
