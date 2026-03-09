import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Badge from '../common/Badge';
import { Calendar, MapPin, Users, CalendarClock, ChevronUp, ChevronDown } from 'lucide-react';
import dayjs from 'dayjs';

const getMeetingStatus = (m) => {
  const now = dayjs();
  const startTime = m.start_time
    ? dayjs(m.start_time)
    : dayjs(`${dayjs().format('YYYY-MM-DD')} ${m.time}`);
  const endTime = m.end_time
    ? dayjs(m.end_time)
    : m.duration
      ? startTime.add(m.duration, 'minute')
      : startTime.add(60, 'minute');

  if (now.isAfter(endTime)) return { variant: 'status-completed', label: '완료' };
  if (now.isAfter(startTime)) return { variant: 'status-in-progress', label: '진행중' };
  return { variant: 'status-scheduled', label: '예정' };
};


export default function TodaySchedule({ meetings = [], actions = [], loading = false }) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [, setNow] = useState(dayjs());

  useEffect(() => {
    const timer = setInterval(() => setNow(dayjs()), 60000);
    return () => clearInterval(timer);
  }, []);

  const displayMeetings = isCollapsed ? meetings.slice(0, 1) : meetings;

  return (
    <div className="card flex flex-col p-5 shadow-soft transition-all duration-300">
      {/* 섹션 1: 오늘 일정 */}
      <div
        className="flex items-center justify-between mb-3 cursor-pointer"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <h3 className="text-lg font-bold text-neutral-main flex items-center gap-2">
          <Calendar className="text-primary-500" size={20} />
          오늘 일정
        </h3>
        <button className="text-neutral-muted hover:text-primary-500 transition-colors p-1 rounded-full hover:bg-surface-hover">
          {isCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
        </button>
      </div>

      <div className="overflow-y-auto pr-2 custom-scrollbar space-y-2 mb-2">
        {loading ? (
          <div className="animate-pulse space-y-2 mt-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="flex items-center gap-3 p-3 rounded-2xl bg-neutral-100 dark:bg-neutral-800">
                <div className="w-12 h-12 rounded-xl bg-neutral-200 dark:bg-neutral-700 flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-3 bg-neutral-200 dark:bg-neutral-700 rounded w-3/4" />
                  <div className="h-2.5 bg-neutral-200 dark:bg-neutral-700 rounded w-1/2" />
                </div>
                <div className="w-12 h-5 bg-neutral-200 dark:bg-neutral-700 rounded-full" />
              </div>
            ))}
          </div>
        ) : (
          <>
            {displayMeetings.length === 0 && (
              <p className="text-sm font-bold text-neutral-muted py-2 text-center mt-4">오늘 예정된 회의가 없습니다.</p>
            )}
            {displayMeetings.map((m, i) => (
          <Link key={i} to="/schedules" className="group flex items-center gap-3 p-3 rounded-2xl border border-transparent bg-white/40 dark:bg-white/[0.06] dark:border-white/[0.08] hover:border-primary-200 dark:hover:border-white/20 hover:shadow-soft transition-all duration-300 relative overflow-hidden">
            <div className="absolute inset-0 bg-primary-50 dark:bg-white/[0.04] opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
            <div className="relative z-10 text-center flex-shrink-0 bg-primary-50 dark:bg-white/10 w-12 h-12 rounded-xl flex flex-col items-center justify-center">
              <div className="font-display text-base font-bold text-primary-700 dark:text-neutral-main leading-none">{m.isAllDay ? '종일' : m.time.split(' ')[0]}</div>
              {!m.isAllDay && <div className="text-[9px] text-primary-500 dark:text-neutral-sub font-bold mt-0.5">{m.period || 'AM'}</div>}
            </div>
            <div className="relative z-10 flex-1">
              <div className="text-[13px] font-bold text-neutral-main flex items-center gap-2">
                {i % 2 !== 0 && <span className="text-[9px] bg-primary-50 text-primary-700 px-2 py-0.5 rounded-full border border-primary-100">[팀]</span>}
                {m.title}
              </div>
              <div className="flex gap-2.5 mt-1 text-[11px] text-neutral-muted font-medium">
                <span className="flex items-center gap-1"><MapPin size={10} className="text-primary-400" />{m.location}</span>
                <span className="flex items-center gap-1"><Users size={10} className="text-primary-400" />{m.attendees}명</span>
              </div>
            </div>
            <div className="relative z-10">
              {(() => { const s = getMeetingStatus(m); return <Badge variant={s.variant}>{s.label}</Badge>; })()}
            </div>
          </Link>
            ))}
          </>
        )}
      </div>

      {!isCollapsed && (
        <>
          <div className="pt-1" />

          {/* 섹션 2: 내일 일정 */}
          <div className="flex items-center justify-between mb-3 mt-1">
            <h3 className="text-[15px] font-bold text-neutral-main flex items-center gap-2">
              <CalendarClock className="text-primary-500" size={18} />
              내일 일정
            </h3>
          </div>
          <div className="space-y-2">
            {loading ? (
              <div className="animate-pulse space-y-2">
                {[1, 2].map(i => (
                  <div key={i} className="flex items-center gap-3 p-3 rounded-2xl bg-neutral-100 dark:bg-neutral-800">
                    <div className="w-12 h-12 rounded-xl bg-neutral-200 dark:bg-neutral-700 flex-shrink-0" />
                    <div className="flex-1 space-y-2">
                      <div className="h-3 bg-neutral-200 dark:bg-neutral-700 rounded w-2/3" />
                      <div className="h-2.5 bg-neutral-200 dark:bg-neutral-700 rounded w-1/3" />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <>
                {actions.length === 0 && (
                  <p className="text-sm font-bold text-neutral-muted py-2 text-center">내일 예정된 일정이 없습니다.</p>
                )}
                {actions.map((item, i) => (
              <Link
                key={i}
                to="/schedules"
                className="group flex items-center gap-3 p-3 rounded-2xl border border-transparent bg-white/40 dark:bg-white/[0.06] dark:border-white/[0.08] hover:border-primary-200 dark:hover:border-white/20 hover:shadow-soft transition-all duration-300 relative overflow-hidden"
              >
                <div className="absolute inset-0 bg-primary-50 dark:bg-white/[0.04] opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
                <div className="relative z-10 text-center flex-shrink-0 bg-primary-50 dark:bg-white/10 w-12 h-12 rounded-xl flex flex-col items-center justify-center">
                  <div className="text-[9px] text-primary-500 dark:text-neutral-sub font-bold">{item.deadline.split(' ')[0] || ''}</div>
                  <div className="font-display text-base font-bold text-primary-700 dark:text-neutral-main leading-none mt-0.5">{item.deadline.split(' ').slice(1).join(' ') || item.deadline}</div>
                </div>
                <div className="relative z-10 flex-1">
                  <div className="text-[13px] font-bold text-neutral-main">
                    {item.title}
                  </div>
                  {item.assignee && (
                    <div className="mt-1 text-[11px] text-neutral-muted font-medium">
                      {item.assignee}
                    </div>
                  )}
                </div>
              </Link>
                ))}
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
