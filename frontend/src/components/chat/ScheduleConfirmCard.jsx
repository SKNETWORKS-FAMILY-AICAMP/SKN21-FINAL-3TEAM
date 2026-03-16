import { useState, useEffect } from 'react';
import TimeSelect, { addOneHour } from '../common/TimeSelect';
import MemberMultiSelect from '../common/MemberMultiSelect';
import ScheduleCard from './ScheduleCard';
import { createSchedule } from '../../api/schedules';
import { getAllMembers } from '../../api/auth';

export default function ScheduleConfirmCard({ initialData, onConfirmed }) {
  const sched = initialData || {};

  // 초기값 파싱
  const startDt = sched.start_time ? new Date(sched.start_time) : null;
  const endDt = sched.end_time ? new Date(sched.end_time) : null;

  const initDate = startDt
    ? `${startDt.getFullYear()}-${String(startDt.getMonth() + 1).padStart(2, '0')}-${String(startDt.getDate()).padStart(2, '0')}`
    : '';
  const initStartTime = startDt
    ? `${String(startDt.getHours()).padStart(2, '0')}:${String(startDt.getMinutes()).padStart(2, '0')}`
    : '09:00';
  const initEndTime = endDt
    ? `${String(endDt.getHours()).padStart(2, '0')}:${String(endDt.getMinutes()).padStart(2, '0')}`
    : addOneHour(initStartTime);

  const [title, setTitle] = useState(sched.title || '');
  const [date, setDate] = useState(initDate);
  const [startTime, setStartTime] = useState(initStartTime);
  const [endTime, setEndTime] = useState(initEndTime);
  const [includeMeet, setIncludeMeet] = useState(false);
  const [selectedAttendeeIds, setSelectedAttendeeIds] = useState([]);
  const [members, setMembers] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    getAllMembers()
      .then((res) => {
        const list = res.data || [];
        setMembers(list.map((u) => ({
          id: u.id,
          name: u.name,
          team: u.team,
          email: u.email,
          avatar: u.avatar || null,
        })));
      })
      .catch(() => setMembers([]));
  }, []);

  const handleSubmit = async () => {
    if (!title.trim() || !date) return;
    setSubmitting(true);
    try {
      const attendeeEmails = selectedAttendeeIds
        .map((id) => members.find((m) => String(m.id) === id)?.email)
        .filter(Boolean);

      const startISO = `${date}T${startTime}:00`;
      const endISO = `${date}T${endTime}:00`;

      const payload = {
        title,
        start_time: startISO,
        end_time: endISO,
        schedule_type: sched.schedule_type || 'meeting',
        include_meet: includeMeet,
        attendee_emails: attendeeEmails,
      };

      const res = await createSchedule(payload);
      const apiResult = res.data || res;

      setResult(apiResult);
      setSubmitted(true);
      onConfirmed?.(apiResult);
    } catch (err) {
      console.error('[ScheduleConfirmCard] 등록 실패:', err);
    } finally {
      setSubmitting(false);
    }
  };

  // 등록 완료 → 읽기전용 ScheduleCard로 전환
  if (submitted && result) {
    const gs = result.google_services || {};
    const schedResult = result.schedule || result;
    const resultStart = schedResult.start_time || `${date}T${startTime}`;
    return (
      <ScheduleCard
        title={title}
        date={typeof resultStart === 'string' ? resultStart.split('T')[0] : date}
        time={typeof resultStart === 'string' ? resultStart.split('T')[1]?.slice(0, 5) : startTime}
        synced={gs.calendar_synced || false}
        meetLink={gs.meet_link || null}
        emailSent={gs.email_sent || false}
        emailCount={gs.email_count || (gs.email_sent ? selectedAttendeeIds.length : 0)}
      />
    );
  }

  return (
    <div className="bg-surface-card rounded-lg border border-neutral-border overflow-hidden">
      <div className="px-4 py-3 border-b border-neutral-divider flex items-center gap-2 font-bold text-sm text-primary-700">
        일정 등록 확인
      </div>
      <div className="p-4 space-y-3">
        {/* 제목 */}
        <div>
          <label className="text-xs font-semibold text-neutral-sub block mb-1">제목</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-2 border border-neutral-border rounded-lg text-sm bg-white dark:bg-neutral-800 outline-none focus:border-primary-500 transition"
            placeholder="일정 제목"
          />
        </div>

        {/* 날짜 */}
        <div>
          <label className="text-xs font-semibold text-neutral-sub block mb-1">날짜</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full px-3 py-2 border border-neutral-border rounded-lg text-sm bg-white dark:bg-neutral-800 outline-none focus:border-primary-500 transition"
          />
        </div>

        {/* 시작 / 종료 시간 */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-semibold text-neutral-sub block mb-1">시작 시간</label>
            <TimeSelect
              value={startTime}
              onChange={(t) => { setStartTime(t); setEndTime(addOneHour(t)); }}
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-neutral-sub block mb-1">종료 시간</label>
            <TimeSelect
              value={endTime}
              onChange={(t) => setEndTime(t)}
            />
          </div>
        </div>

        {/* Google Meet */}
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={includeMeet}
            onChange={(e) => setIncludeMeet(e.target.checked)}
            className="w-4 h-4 rounded border-neutral-border accent-primary-700"
          />
          <div className="flex items-center gap-1.5">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary-500">
              <path d="M15.6 11.6L22 7v10l-6.4-4.5v-1zM4 5h9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7c0-1.1.9-2 2-2z" />
            </svg>
            <span className="text-sm font-medium text-neutral-main">Google Meet 링크 생성</span>
          </div>
        </label>

        {/* 참석자 */}
        <div>
          <label className="text-xs font-semibold text-neutral-sub block mb-1">참석자</label>
          <MemberMultiSelect
            members={members}
            selectedIds={selectedAttendeeIds}
            onChange={setSelectedAttendeeIds}
            placeholder="참석자를 선택하세요"
          />
        </div>

        {/* 등록 버튼 */}
        <button
          onClick={handleSubmit}
          disabled={submitting || !title.trim() || !date}
          className="w-full py-2.5 bg-primary-700 text-white text-sm font-bold rounded-lg shadow hover:bg-primary-800 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? '등록 중...' : '일정 등록'}
        </button>
      </div>
    </div>
  );
}
