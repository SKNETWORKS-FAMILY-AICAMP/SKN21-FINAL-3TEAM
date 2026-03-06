import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import useGoogleServices from '../hooks/useGoogleServices';
import useAuthStore from '../store/authStore';
import { sendMeetingInvite } from '../api/google';
import { listSchedules, createSchedule, updateSchedule, deleteSchedule } from '../api/schedules';
import GoogleServicesConnect from '../components/schedules/GoogleServicesConnect';
import SlackConnect from '../components/schedules/SlackConnect';
import CalendarView from '../components/schedules/CalendarView';
import ScheduleForm from '../components/schedules/ScheduleForm';
import ScheduleTypeManager from '../components/schedules/ScheduleTypeManager';
import TasksPanel from '../components/schedules/TasksPanel';
import SheetsDashboard from '../components/schedules/SheetsDashboard';
import useScheduleTypeStore, { DEFAULT_TYPES } from '../store/scheduleTypeStore';

export default function SchedulesPage() {

  const [searchParams] = useSearchParams();
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
  const [editingSchedule, setEditingSchedule] = useState(null);
  const [showTypeManager, setShowTypeManager] = useState(false);
  const [activeTab, setActiveTab] = useState(() => {
    const tab = searchParams.get('tab');
    return ['calendar', 'tasks', 'sheets'].includes(tab) ? tab : 'calendar';
  });
  const [taskActions, setTaskActions] = useState(null);
  const [sheetActions, setSheetActions] = useState(null);
  const [teamSchedules, setTeamSchedules] = useState([]);
  const [myDbSchedules, setMyDbSchedules] = useState([]);
  const [refreshKey, setRefreshKey] = useState(0);

  // Google Calendar 연결 시 이벤트 자동 로드 (백엔드 기본값: ±3개월)
  useEffect(() => {
    if (connected && hasScope('calendar')) {
      fetchCalendarEvents();
    }
  }, [connected, hasScope, fetchCalendarEvents]);

  // 본인 DB 일정 로드 (Google Calendar 미연결 시에도 일정 표시)
  useEffect(() => {
    listSchedules().then((res) => {
      const schedules = [];
      (res.data || []).forEach((s) => {
        const start = new Date(s.start_time);
        const end = s.end_time ? new Date(s.end_time) : start;
        const hasTime = s.start_time.includes('T');
        const timeStr = hasTime
          ? `${start.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}~${end.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}`
          : null;
        const baseEvent = {
          type: s.schedule_type || 'meeting',
          label: s.is_team_visible ? `[팀] ${s.title}` : s.title,
          time: timeStr,
          rawStartTime: hasTime ? `${String(start.getHours()).padStart(2, '0')}:${String(start.getMinutes()).padStart(2, '0')}` : null,
          rawEndTime: hasTime ? `${String(end.getHours()).padStart(2, '0')}:${String(end.getMinutes()).padStart(2, '0')}` : null,
          googleEventId: s.google_event_id,
          scheduleId: s.id,
          userId: s.user_id,
          isTeamVisible: s.is_team_visible || false,
          startDate: `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`,
          endDate: `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, '0')}-${String(end.getDate()).padStart(2, '0')}`,
        };
        // 여러 날짜에 걸친 일정은 각 날짜별로 이벤트 생성
        const startDay = new Date(start.getFullYear(), start.getMonth(), start.getDate());
        const endDay = new Date(end.getFullYear(), end.getMonth(), end.getDate());
        const cur = new Date(startDay);
        while (cur <= endDay) {
          schedules.push({
            ...baseEvent,
            year: cur.getFullYear(),
            month: cur.getMonth() + 1,
            day: cur.getDate(),
          });
          cur.setDate(cur.getDate() + 1);
        }
      });
      setMyDbSchedules(schedules);
    }).catch(() => setMyDbSchedules([]));
  }, [refreshKey]);

  // 팀 일정 로드
  useEffect(() => {
    if (hasTeam) {
      listSchedules({ include_team: true }).then((res) => {
        const dbSchedules = [];
        (res.data || [])
          .filter((s) => s.user_name && s.user_name !== user?.name) // 본인 제외, 팀원만
          .forEach((s) => {
            const start = new Date(s.start_time);
            const end = s.end_time ? new Date(s.end_time) : start;
            const timeStr = `${start.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}~${end.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}`;
            const baseEvent = {
              type: s.schedule_type || 'meeting',
              label: `[팀] ${s.title}`,
              time: timeStr,
              isTeamMember: true,
              scheduleId: s.id,
              userId: s.user_id,
            };
            const startDay = new Date(start.getFullYear(), start.getMonth(), start.getDate());
            const endDay = new Date(end.getFullYear(), end.getMonth(), end.getDate());
            const cur = new Date(startDay);
            while (cur <= endDay) {
              dbSchedules.push({
                ...baseEvent,
                month: cur.getMonth() + 1,
                day: cur.getDate(),
              });
              cur.setDate(cur.getDate() + 1);
            }
          });
        setTeamSchedules(dbSchedules);
      }).catch(() => setTeamSchedules([]));
    } else {
      setTeamSchedules([]);
    }
  }, [hasTeam, refreshKey]);


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

  // 수정 권한: 본인 DB 일정만 수정 가능 (관리자도 남의 일정 수정 불가)
  const canEdit = (event) => {
    if (event.type === 'holiday') return false;
    if (!event.scheduleId) return false;
    return event.userId === user?.id;
  };

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

  // 수정 아이콘 클릭 → 폼 열기 (기존 데이터 프리필)
  const handleEditEvent = (event) => {
    if (!event.scheduleId) return; // DB 일정만 수정 가능
    const eventYear = event.year || new Date().getFullYear();
    setEditingSchedule({
      id: event.scheduleId,
      title: event.label,
      date: event.startDate || `${eventYear}-${String(event.month).padStart(2, '0')}-${String(event.day).padStart(2, '0')}`,
      endDate: event.endDate || '',
      startTime: event.rawStartTime || '09:00',
      endTime: event.rawEndTime || '10:00',
      type: event.type || 'meeting',
      allDay: !event.time,
      isTeamVisible: event.isTeamVisible || false,
    });
    setShowForm(true);
  };

  // 일정 수정 제출 핸들러
  const handleUpdateSchedule = async (data) => {
    setScheduleError(null);
    const startTime = data.start_time || data.startTime || '00:00';
    const endTime = data.end_time || data.endTime || '23:59';
    const endDateStr = data.endDate || data.date;
    const startStr = data.allDay
      ? `${data.date}T00:00:00`
      : `${data.date}T${startTime}:00`;
    const endStr = data.allDay
      ? `${endDateStr}T23:59:59`
      : `${endDateStr}T${endTime}:00`;

    try {
      await updateSchedule(editingSchedule.id, {
        title: data.title,
        description: data.description || '',
        start_time: startStr,
        end_time: endStr,
        schedule_type: data.type || 'meeting',
        is_team_visible: data.is_team_visible || false,
      });
    } catch (error) {
      console.error('일정 수정 실패:', error);
      const detail = error.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : '일정 수정에 실패했습니다.';
      setScheduleError(msg);
      throw error;
    }

    setRefreshKey((k) => k + 1);
    if (connected && hasScope('calendar')) fetchCalendarEvents();
    setShowForm(false);
    setEditingSchedule(null);
  };

  const [scheduleError, setScheduleError] = useState(null);

  const handleAddSchedule = async (data) => {
    setScheduleError(null);

    // 타임존 없는 로컬 시간 문자열 (DB: TIMESTAMP WITHOUT TIME ZONE)
    const sTime = data.start_time || data.startTime || '00:00';
    const eTime = data.end_time || data.endTime || '23:59';
    const endDateStr = data.endDate || data.date;
    const startStr = data.allDay
      ? `${data.date}T00:00:00`
      : `${data.date}T${sTime}:00`;
    const endStr = data.allDay
      ? `${endDateStr}T23:59:59`
      : `${endDateStr}T${eTime}:00`;

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
      const detail = error.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : '일정 저장에 실패했습니다. 다시 시도해주세요.';
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
      <header className="flex justify-between items-center bg-surface-main overflow-hidden h-[100px]">
        <div>
          <h1 className="font-bold text-2xl">일정 관리</h1>
          <p className="text-neutral-sub text-sm mt-1">Action Item과 회의 일정을 통합 관리합니다</p>
        </div>
      </header>

      {/* Google 서비스 연결 */}
      <GoogleServicesConnect />

      {/* Slack 연결 */}
      <SlackConnect />

      {/* 유형 관리 모달 */}
      {showTypeManager && (
        <ScheduleTypeManager onClose={() => setShowTypeManager(false)} />
      )}

      {/* 일정 추가 팝업 */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20" onClick={() => { setShowForm(false); setEditingSchedule(null); }}>
          <div className="w-[420px]" onClick={(e) => e.stopPropagation()}>
            {scheduleError && (
              <div className="mb-2 p-3 bg-red-50 border border-red-300 rounded-md">
                <p className="text-sm text-red-600 font-medium">{scheduleError}</p>
              </div>
            )}
            <ScheduleForm
              onSubmit={editingSchedule ? handleUpdateSchedule : handleAddSchedule}
              onClose={() => { setShowForm(false); setEditingSchedule(null); setScheduleError(null); }}
              initialData={editingSchedule}
            />
          </div>
        </div>
      )}

      {/* 탭 네비게이션 + 액션 버튼 */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex gap-1">
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
        <div className="flex items-center gap-2">
          {activeTab === 'calendar' && (
            <>
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
              <button onClick={() => { setShowForm(!showForm); setEditingSchedule(null); }} className="btn-primary">
                {showForm ? '취소' : '+ 일정 추가'}
              </button>
            </>
          )}
          {activeTab === 'tasks' && taskActions && (
            <>
              <button
                onClick={() => taskActions.refresh()}
                disabled={taskActions.tasksLoading}
                className="btn-outline"
              >
                {taskActions.tasksLoading ? '동기화 중...' : '새로고침'}
              </button>
              <button onClick={() => taskActions.openCreate()} className="btn-primary">
                + Task 추가
              </button>
            </>
          )}
          {activeTab === 'sheets' && sheetActions && (
            <button
              onClick={() => sheetActions.create()}
              disabled={sheetActions.creating || sheetActions.sheetsLoading}
              className="btn-primary"
            >
              {sheetActions.creating ? '생성 중...' : '+ 새 시트'}
            </button>
          )}
        </div>
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
              <CalendarView events={allEvents} onDeleteEvent={handleDeleteEvent} onCanDelete={canDelete} onEditEvent={handleEditEvent} onCanEdit={canEdit} />
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

      {activeTab === 'tasks' && <TasksPanel externalActions onReady={setTaskActions} />}
      {activeTab === 'sheets' && <SheetsDashboard externalActions onReady={setSheetActions} />}
    </div>
  );
}
