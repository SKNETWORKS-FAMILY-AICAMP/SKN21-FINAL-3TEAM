import { useState } from 'react';
import useGoogleServices from '../../hooks/useGoogleServices';

// 00:00 ~ 23:50 (10분 간격) 타임 옵션 생성
const timeOptions = [];
for (let h = 0; h < 24; h++) {
  for (let m = 0; m < 60; m += 10) {
    const val = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    timeOptions.push(val);
  }
}

export default function ScheduleForm({ onSubmit, onClose }) {
  const { connected, hasScope } = useGoogleServices();
  const [form, setForm] = useState({
    title: '',
    date: '',
    startTime: '09:00',
    endTime: '10:00',
    type: 'meeting',
    allDay: false,
    includeMeet: false,
    attendeeEmails: '',
  });

  const canMeet = connected && hasScope('calendar');

  const handleSubmit = () => {
    const data = {
      ...form,
      start_time: form.allDay ? null : form.startTime,
      end_time: form.allDay ? null : form.endTime,
      attendee_emails: form.attendeeEmails
        ? form.attendeeEmails.split(',').map((e) => e.trim()).filter(Boolean)
        : [],
      include_meet: form.includeMeet,
    };
    onSubmit?.(data);
  };

  const selectClass = 'w-full px-3 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 bg-surface-card';

  return (
    <div className="card p-5">
      <h3 className="text-base font-bold mb-4">일정 추가</h3>
      <div className="space-y-3">
        {/* 제목 */}
        <div>
          <label className="text-[13px] font-semibold block mb-1">제목</label>
          <input
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="일정 제목을 입력하세요"
            className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] outline-none"
          />
        </div>

        {/* 일정 유형 */}
        <div>
          <label className="text-[13px] font-semibold block mb-1">일정 유형</label>
          <div className="flex gap-2">
            {[
              { value: 'meeting', label: '회의', dot: 'bg-primary-500' },
              { value: 'deadline', label: '마감일', dot: 'bg-error' },
              { value: 'google', label: '개인 일정', dot: 'bg-success' },
            ].map(({ value, label, dot }) => (
              <button
                key={value}
                type="button"
                onClick={() => setForm({ ...form, type: value })}
                className={`flex items-center gap-1.5 px-3.5 py-2 rounded-md border text-sm font-medium transition ${
                  form.type === value
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-neutral-border bg-surface-card text-neutral-sub hover:border-primary-300'
                }`}
              >
                <span className={`w-2.5 h-2.5 rounded-full ${dot}`} />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* 날짜 */}
        <div>
          <label className="text-[13px] font-semibold block mb-1">날짜</label>
          <input
            type="date"
            value={form.date}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
            onClick={(e) => e.target.showPicker?.()}
            className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 cursor-pointer"
          />
        </div>

        {/* 종일 토글 */}
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.allDay}
            onChange={(e) => setForm({ ...form, allDay: e.target.checked })}
            className="w-4 h-4 rounded border-neutral-border text-primary-700 focus:ring-primary-500"
          />
          <span className="text-sm text-neutral-main">종일</span>
        </label>

        {/* 시작 / 종료 시간 */}
        {!form.allDay && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[13px] font-semibold block mb-1">시작 시간</label>
              <select
                value={form.startTime}
                onChange={(e) => setForm({ ...form, startTime: e.target.value })}
                className={selectClass}
              >
                {timeOptions.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[13px] font-semibold block mb-1">종료 시간</label>
              <select
                value={form.endTime}
                onChange={(e) => setForm({ ...form, endTime: e.target.value })}
                className={selectClass}
              >
                {timeOptions.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
        )}

        {/* Google Meet 토글 */}
        {canMeet && (
          <div className="flex items-center gap-3 px-3 py-2.5 rounded-md border border-neutral-divider bg-surface-hover">
            <label className="flex items-center gap-2 cursor-pointer flex-1">
              <input
                type="checkbox"
                checked={form.includeMeet}
                onChange={(e) => setForm({ ...form, includeMeet: e.target.checked })}
                className="w-4 h-4 rounded border-neutral-border text-primary-700 focus:ring-primary-500"
              />
              <div className="flex items-center gap-1.5">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary-500">
                  <path d="M15.6 11.6L22 7v10l-6.4-4.5v-1zM4 5h9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7c0-1.1.9-2 2-2z" />
                </svg>
                <span className="text-sm font-medium text-neutral-main">Google Meet 링크 생성</span>
              </div>
            </label>
          </div>
        )}

        {/* 참석자 이메일 */}
        {form.includeMeet && (
          <div>
            <label className="text-[13px] font-semibold block mb-1">참석자 이메일</label>
            <input
              value={form.attendeeEmails}
              onChange={(e) => setForm({ ...form, attendeeEmails: e.target.value })}
              placeholder="콤마로 구분 (예: a@co.kr, b@co.kr)"
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] outline-none"
            />
            <p className="text-[11px] text-neutral-muted mt-1">Meet 링크가 포함된 초대 메일이 발송됩니다</p>
          </div>
        )}

        {/* 버튼 */}
        <div className="flex gap-2 pt-2">
          <button onClick={handleSubmit} className="btn-primary">등록</button>
          <button onClick={onClose} className="btn-outline">취소</button>
        </div>
      </div>
    </div>
  );
}
