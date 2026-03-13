import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, Users, FolderOpen, ChevronLeft, ChevronRight } from 'lucide-react';
import useGoogleServices from '../../hooks/useGoogleServices';
import useScheduleTypeStore, { DEFAULT_TYPES } from '../../store/scheduleTypeStore';
import useAuthStore from '../../store/authStore';
import { listProjects } from '../../api/tasks';
import DatePicker from '../common/DatePicker';

// 00:00 ~ 23:50 (10분 간격) 타임 옵션 생성
const timeOptions = [];
for (let h = 0; h < 24; h++) {
  for (let m = 0; m < 60; m += 15) {
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
          className="bg-surface-card border border-neutral-border rounded-md shadow-lg overflow-y-auto max-h-48"
        >
          {timeOptions.map((t) => (
            <button
              key={t}
              type="button"
              data-selected={t === value}
              onClick={() => { onChange(t); setIsOpen(false); }}
              className={`w-full text-left px-3 py-1.5 text-sm transition ${t === value
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

const DAYS = ['일', '월', '화', '수', '목', '금', '토'];
const MONTHS = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'];

function RangePicker({ startDate, endDate, onChange }) {
  const today = new Date();
  const [viewDate, setViewDate] = useState(() => startDate ? new Date(startDate) : today);
  const [selecting, setSelecting] = useState('start');

  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const lastDate = new Date(year, month + 1, 0).getDate();
  const cells = [...Array(firstDay).fill(null), ...Array.from({ length: lastDate }, (_, i) => i + 1)];

  const toStr = (y, m, d) => `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;

  const handleSelect = (day) => {
    const selected = toStr(year, month, day);
    if (selecting === 'start') {
      onChange(selected, '');
      setSelecting('end');
    } else {
      if (selected < startDate) {
        onChange(selected, startDate);
      } else {
        onChange(startDate, selected);
      }
      setSelecting('start');
    }
  };

  const isStart = (day) => toStr(year, month, day) === startDate;
  const isEnd = (day) => toStr(year, month, day) === endDate;
  const isInRange = (day) => {
    if (!startDate || !endDate) return false;
    const d = toStr(year, month, day);
    return d > startDate && d < endDate;
  };
  const isTodayCell = (day) => day === today.getDate() && month === today.getMonth() && year === today.getFullYear();

  return (
    <div className="border border-neutral-border rounded-lg p-2 bg-surface-card">
      <div className="flex items-center justify-between mb-1.5">
        <button type="button" onClick={() => setViewDate(new Date(year, month - 1, 1))} className="p-1 hover:bg-surface-hover rounded transition">
          <ChevronLeft size={13} />
        </button>
        <span className="text-xs font-semibold text-neutral-main">{year}년 {MONTHS[month]}</span>
        <button type="button" onClick={() => setViewDate(new Date(year, month + 1, 1))} className="p-1 hover:bg-surface-hover rounded transition">
          <ChevronRight size={13} />
        </button>
      </div>
      <div className="flex gap-1.5 mb-1.5 text-[0.6875rem]">
        <div className={`flex-1 text-center py-1 rounded border transition ${selecting === 'start' ? 'bg-primary-50 text-primary-700 font-semibold border-primary-300' : 'bg-surface-hover text-neutral-sub border-transparent'}`}>
          시작: {startDate || '선택'}
        </div>
        <div className={`flex-1 text-center py-1 rounded border transition ${selecting === 'end' ? 'bg-primary-50 text-primary-700 font-semibold border-primary-300' : 'bg-surface-hover text-neutral-sub border-transparent'}`}>
          종료: {endDate || '선택'}
        </div>
      </div>
      <div className="grid grid-cols-7">
        {DAYS.map((d, i) => (
          <div key={d} className={`text-center text-[0.625rem] font-medium py-0.5 ${i === 0 ? 'text-red-400' : i === 6 ? 'text-blue-400' : 'text-neutral-muted'}`}>{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {cells.map((day, idx) => day ? (
          <button
            key={idx}
            type="button"
            onClick={() => handleSelect(day)}
            className={[
              'w-full h-7 flex items-center justify-center text-[0.6875rem] transition',
              isStart(day) || isEnd(day) ? 'bg-primary-700 text-white font-semibold rounded' :
                isInRange(day) ? 'bg-primary-100 text-primary-800' :
                  isTodayCell(day) ? 'border border-primary-400 text-primary-700 font-semibold hover:bg-primary-50 rounded' :
                    idx % 7 === 0 ? 'text-red-400 hover:bg-surface-hover rounded' :
                      idx % 7 === 6 ? 'text-blue-400 hover:bg-surface-hover rounded' :
                        'text-neutral-main hover:bg-surface-hover rounded',
              isInRange(day) ? 'rounded-none' : '',
            ].join(' ')}
          >
            {day}
          </button>
        ) : <div key={idx} />)}
      </div>
    </div>
  );
}

function addOneHour(timeStr) {
  const [h, m] = timeStr.split(':').map(Number);
  const totalMin = h * 60 + m + 60;
  if (totalMin >= 24 * 60) return '23:50';
  return `${String(Math.floor(totalMin / 60)).padStart(2, '0')}:${String(totalMin % 60).padStart(2, '0')}`;
}

export default function ScheduleForm({ onSubmit, onClose, initialData }) {
  const isEditMode = !!initialData;
  const { connected, hasScope } = useGoogleServices();
  const { customTypes } = useScheduleTypeStore();
  const user = useAuthStore((s) => s.user);
  const hasTeam = !!user?.team;
  const allTypes = [...DEFAULT_TYPES, ...customTypes];
  const [form, setForm] = useState({
    title: initialData?.title || '',
    date: initialData?.date || '',
    endDate: initialData?.endDate || '',
    startTime: initialData?.startTime || '09:00',
    endTime: initialData?.endTime || '10:00',
    type: initialData?.type || 'meeting',
    allDay: initialData?.allDay || false,
    includeMeet: false,
    attendeeEmails: '',
    isTeamVisible: initialData?.isTeamVisible || false,
    projectName: initialData?.projectName || '',
  });
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [projects, setProjects] = useState([]);
  const [shareToProject, setShareToProject] = useState(!!initialData?.projectName);

  useEffect(() => {
    listProjects().then((res) => {
      const list = res.data || [];
      // 이름 기준 중복 제거
      const seen = new Set();
      const unique = list.filter((p) => {
        if (seen.has(p.name)) return false;
        seen.add(p.name);
        return true;
      });
      setProjects(unique);
    }).catch(() => setProjects([]));
  }, []);

  const canMeet = connected && hasScope('calendar');

  const handleSubmit = async () => {
    // 유효성 검사
    const newErrors = {};
    if (!form.title.trim()) newErrors.title = '제목을 입력하세요';
    if (!form.date) newErrors.date = '날짜를 선택하세요';
    if (!form.allDay && form.endTime <= form.startTime) newErrors.endTime = '종료 시간은 시작 시간보다 늦어야 합니다';
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    setErrors({});
    setSubmitting(true);
    try {
      const data = {
        ...form,
        start_time: form.allDay ? null : form.startTime,
        end_time: form.allDay ? null : form.endTime,
        attendee_emails: form.attendeeEmails
          ? form.attendeeEmails.split(',').map((e) => e.trim()).filter(Boolean)
          : [],
        include_meet: form.includeMeet,
        is_team_visible: form.isTeamVisible,
        project_name: form.projectName || null,
      };
      await onSubmit?.(data);
    } catch {
      // 에러는 상위(SchedulesPage)에서 처리됨
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl p-6 rounded-2xl border border-white/40 dark:border-white/10 shadow-2xl">
      <h3 className="text-lg font-black mb-5 text-neutral-900 dark:text-white tracking-tight">{isEditMode ? '일정 수정' : '일정 추가'}</h3>
      <div className="space-y-3">
        {/* 제목 */}
        <div>
          <input
            value={form.title}
            onChange={(e) => { setForm({ ...form, title: e.target.value }); setErrors((p) => ({ ...p, title: undefined })); }}
            placeholder="일정 제목을 입력하세요"
            className={`w-full px-4 py-3 rounded-xl border transition-all text-sm focus:ring-2 focus:ring-primary-500 outline-none bg-white/50 dark:bg-black/20 ${errors.title ? 'border-red-400' : 'border-neutral-divider dark:border-white/10'}`}
          />
          {errors.title && <p className="text-[10px] text-red-500 mt-1 ml-1 font-bold">{errors.title}</p>}
        </div>

        {/* 일정 유형 */}
        <div>
          <label className="text-[11px] font-black uppercase tracking-wider text-neutral-400 mb-2 ml-1">일정 유형</label>
          <div className="flex flex-wrap gap-2">
            {allTypes.map(({ id, label, color }) => (
              <button
                key={id}
                type="button"
                onClick={() => setForm({ ...form, type: id })}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-[11px] font-black transition-all ${form.type === id
                  ? 'border-primary-500 bg-primary-500 text-white shadow-lg shadow-primary-500/20'
                  : 'border-neutral-divider dark:border-white/10 bg-white/50 dark:bg-black/20 text-neutral-500'
                  }`}
              >
                <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* 공유 설정 */}
        {(hasTeam || projects.length > 0) && (
          <div className="space-y-2">
            <div className="flex justify-center gap-2">
              {hasTeam && (
                <button
                  type="button"
                  onClick={() => setForm({ ...form, isTeamVisible: !form.isTeamVisible })}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-[11px] font-black transition-all ${form.isTeamVisible
                    ? 'border-emerald-500 bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'
                    : 'border-neutral-divider dark:border-white/10 bg-white/50 dark:bg-black/20 text-neutral-500'
                  }`}
                >
                  <Users size={13} />
                  {user.team}팀 공유
                </button>
              )}
              {projects.length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    const next = !shareToProject;
                    setShareToProject(next);
                    if (!next) setForm({ ...form, projectName: '' });
                    else setForm({ ...form, projectName: projects[0]?.name || '' });
                  }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-[11px] font-black transition-all ${shareToProject
                    ? 'border-violet-500 bg-violet-500 text-white shadow-lg shadow-violet-500/20'
                    : 'border-neutral-divider dark:border-white/10 bg-white/50 dark:bg-black/20 text-neutral-500'
                  }`}
                >
                  <FolderOpen size={13} />
                  프로젝트 공유
                </button>
              )}
            </div>
            {shareToProject && projects.length > 0 && (
              <select
                value={form.projectName}
                onChange={(e) => setForm({ ...form, projectName: e.target.value })}
                className="w-full px-3 py-2 border border-neutral-border rounded-lg text-sm bg-white dark:bg-black/20 outline-none focus:border-primary-500 transition"
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.name}>{p.name}</option>
                ))}
              </select>
            )}
          </div>
        )}

        {/* 날짜 */}
        <div>
          <label className="text-[0.8125rem] font-semibold block mb-2">날짜</label>
          <RangePicker
            startDate={form.date}
            endDate={form.endDate}
            onChange={(start, end) => {
              setForm(f => ({ ...f, date: start, endDate: end }));
              setErrors((p) => ({ ...p, date: undefined }));
            }}
          />
          {errors.date && <p className="text-xs text-red-500 mt-1">{errors.date}</p>}
        </div>

        {/* 종일 + Google Meet */}
        <div className="flex items-center justify-between">
          {canMeet && (
            <label className="flex items-center gap-2 cursor-pointer">
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
          )}
          <label className="flex items-center gap-2 cursor-pointer ml-auto pr-3">
            <input
              type="checkbox"
              checked={form.allDay}
              onChange={(e) => setForm({ ...form, allDay: e.target.checked })}
              className="w-4 h-4 rounded border-neutral-border accent-primary-700"
            />
            <span className="text-sm text-neutral-main">종일</span>
          </label>
        </div>

        {/* 시작 / 종료 시간 */}
        {!form.allDay && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[0.8125rem] font-semibold block mb-1">시작 시간</label>
                <TimeSelect
                  value={form.startTime}
                  onChange={(t) => setForm({ ...form, startTime: t, endTime: addOneHour(t) })}
                />
              </div>
              <div>
                <label className="text-[0.8125rem] font-semibold block mb-1">종료 시간</label>
                <TimeSelect
                  value={form.endTime}
                  onChange={(t) => { setForm({ ...form, endTime: t }); setErrors((p) => ({ ...p, endTime: undefined })); }}
                />
              </div>
            </div>
            {errors.endTime && <p className="text-xs text-red-500 mt-1 whitespace-nowrap">{errors.endTime}</p>}
          </>
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
        <div className="flex gap-2 pt-4">
          <button onClick={onClose} disabled={submitting} className="flex-1 py-3 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all">취소</button>
          <button onClick={handleSubmit} disabled={submitting} className="flex-1 py-3 bg-primary-700 text-white text-xs font-black rounded-xl shadow-xl shadow-primary-700/20 hover:bg-primary-800 hover:scale-105 transition-all">
            {submitting ? (isEditMode ? '수정 중...' : '등록 중...') : (isEditMode ? '수정' : '등록')}
          </button>
        </div>
      </div>
    </div>
  );
}
