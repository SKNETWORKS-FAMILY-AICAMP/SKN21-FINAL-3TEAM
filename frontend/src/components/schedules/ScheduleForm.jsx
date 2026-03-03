import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, Users } from 'lucide-react';
import useGoogleServices from '../../hooks/useGoogleServices';
import useScheduleTypeStore, { DEFAULT_TYPES } from '../../store/scheduleTypeStore';
import useAuthStore from '../../store/authStore';
import DatePicker from '../common/DatePicker';

// 00:00 ~ 23:50 (10분 간격) 타임 옵션 생성
const timeOptions = [];
for (let h = 0; h < 24; h++) {
  for (let m = 0; m < 60; m += 10) {
    const val = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    timeOptions.push(val);
  }
}

function TimeSelect({ value, onChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const [dropStyle, setDropStyle] = useState({});
  const triggerRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        triggerRef.current && !triggerRef.current.contains(e.target) &&
        listRef.current && !listRef.current.contains(e.target)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setDropStyle({
        position: 'fixed',
        top: rect.bottom + 2,
        left: rect.left,
        width: rect.width,
        zIndex: 9999,
      });
    }
  }, [isOpen]);

  // 드롭다운 열릴 때 선택된 항목으로 스크롤
  useEffect(() => {
    if (isOpen && listRef.current) {
      const selected = listRef.current.querySelector('[data-selected="true"]');
      if (selected) selected.scrollIntoView({ block: 'center' });
    }
  }, [isOpen]);

  return (
    <div className="relative" ref={triggerRef}>
      <button
        type="button"
        onClick={() => setIsOpen((o) => !o)}
        className="w-full flex items-center justify-between px-3 py-2.5 border border-neutral-border rounded-sm text-sm bg-surface-card hover:border-primary-400 outline-none transition"
      >
        <span>{value}</span>
        <ChevronDown size={14} className="text-neutral-muted" />
      </button>

      {isOpen && createPortal(
        <div
          ref={listRef}
          style={dropStyle}
          className="bg-white border border-neutral-border rounded-md shadow-lg overflow-y-auto max-h-48"
        >
          {timeOptions.map((t) => (
            <button
              key={t}
              type="button"
              data-selected={t === value}
              onClick={() => { onChange(t); setIsOpen(false); }}
              className={`w-full text-left px-3 py-1.5 text-sm transition ${
                t === value
                  ? 'bg-primary-50 text-primary-700 font-semibold'
                  : 'text-neutral-main hover:bg-surface-hover'
              }`}
            >
              {t}
            </button>
          ))}
        </div>,
        document.body
      )}
    </div>
  );
}

export default function ScheduleForm({ onSubmit, onClose }) {
  const { connected, hasScope } = useGoogleServices();
  const { customTypes } = useScheduleTypeStore();
  const user = useAuthStore((s) => s.user);
  const hasTeam = !!user?.team;
  const allTypes = [...DEFAULT_TYPES, ...customTypes];
  const [form, setForm] = useState({
    title: '',
    date: '',
    startTime: '09:00',
    endTime: '10:00',
    type: 'meeting',
    allDay: false,
    includeMeet: false,
    attendeeEmails: '',
    isTeamVisible: false,
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
      is_team_visible: form.isTeamVisible,
    };
    onSubmit?.(data);
  };

  return (
    <div className="card p-5">
      <h3 className="text-base font-bold mb-4">일정 추가</h3>
      <div className="space-y-3">
        {/* 제목 */}
        <div>
          <label className="text-[0.8125rem] font-semibold block mb-1">제목</label>
          <input
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="일정 제목을 입력하세요"
            className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] outline-none"
          />
        </div>

        {/* 일정 유형 */}
        <div>
          <label className="text-[0.8125rem] font-semibold block mb-1">일정 유형</label>
          <div className="flex flex-wrap gap-2">
            {allTypes.map(({ id, label, color }) => (
              <button
                key={id}
                type="button"
                onClick={() => setForm({ ...form, type: id })}
                className={`flex items-center gap-1.5 px-3.5 py-2 rounded-md border text-sm font-medium transition ${
                  form.type === id
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-neutral-border bg-surface-card text-neutral-sub hover:border-primary-300'
                }`}
              >
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* 팀에 공유 */}
        {hasTeam && (
          <div className="flex items-center gap-3 px-3 py-2.5 rounded-md border border-neutral-divider bg-surface-hover">
            <label className="flex items-center gap-2 cursor-pointer flex-1">
              <input
                type="checkbox"
                checked={form.isTeamVisible}
                onChange={(e) => setForm({ ...form, isTeamVisible: e.target.checked })}
                className="w-4 h-4 rounded border-neutral-border accent-primary-700"
              />
              <div className="flex items-center gap-1.5">
                <Users size={16} className="text-primary-500" />
                <span className="text-sm font-medium text-neutral-main">팀에 공유</span>
              </div>
            </label>
            <span className="text-[0.6875rem] text-neutral-muted">{user.team}팀 멤버에게 표시됩니다</span>
          </div>
        )}

        {/* 날짜 */}
        <div>
          <label className="text-[0.8125rem] font-semibold block mb-1">날짜</label>
          <DatePicker
            value={form.date}
            onChange={(dateStr) => setForm({ ...form, date: dateStr })}
            placeholder="날짜 선택..."
          />
        </div>

        {/* 종일 토글 */}
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.allDay}
            onChange={(e) => setForm({ ...form, allDay: e.target.checked })}
            className="w-4 h-4 rounded border-neutral-border accent-primary-700"
          />
          <span className="text-sm text-neutral-main">종일</span>
        </label>

        {/* 시작 / 종료 시간 */}
        {!form.allDay && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[0.8125rem] font-semibold block mb-1">시작 시간</label>
              <TimeSelect
                value={form.startTime}
                onChange={(t) => setForm({ ...form, startTime: t })}
              />
            </div>
            <div>
              <label className="text-[0.8125rem] font-semibold block mb-1">종료 시간</label>
              <TimeSelect
                value={form.endTime}
                onChange={(t) => setForm({ ...form, endTime: t })}
              />
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
                className="w-4 h-4 rounded border-neutral-border accent-primary-700"
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
            <label className="text-[0.8125rem] font-semibold block mb-1">참석자 이메일</label>
            <input
              value={form.attendeeEmails}
              onChange={(e) => setForm({ ...form, attendeeEmails: e.target.value })}
              placeholder="콤마로 구분 (예: a@co.kr, b@co.kr)"
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] outline-none"
            />
            <p className="text-[0.6875rem] text-neutral-muted mt-1">Meet 링크가 포함된 초대 메일이 발송됩니다</p>
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
