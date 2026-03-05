import { useState } from 'react';
import { Link } from 'react-router-dom';
import Badge from '../common/Badge';
import { Calendar, MapPin, Users, CalendarClock, ChevronUp, ChevronDown } from 'lucide-react';

export default function TodaySchedule({ meetings = [], actions = [] }) {
  const [isCollapsed, setIsCollapsed] = useState(false);

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

      <div className="overflow-y-auto pr-2 custom-scrollbar space-y-2 mb-4">
        {displayMeetings.length === 0 && (
          <p className="text-sm font-bold text-neutral-muted py-2 text-center mt-4">오늘 예정된 회의가 없습니다.</p>
        )}
        {displayMeetings.map((m, i) => (
          <Link key={i} to="/schedules" className="group flex items-center gap-3 p-3 rounded-2xl border border-transparent bg-white/40 hover:border-primary-200 hover:shadow-soft transition-all duration-300 relative overflow-hidden">
            <div className="absolute inset-0 bg-primary-50 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
            <div className="relative z-10 text-center flex-shrink-0 bg-primary-50 w-12 h-12 rounded-xl flex flex-col items-center justify-center">
              {!m.isAllDay && <div className="text-[9px] text-primary-500 font-bold">{m.period || 'AM'}</div>}
              <div className="font-display text-base font-bold text-primary-700 leading-none mt-0.5">{m.isAllDay ? '종일' : m.time.split(' ')[0]}</div>
            </div>
            <div className="relative z-10 flex-1">
              <div className="text-[13px] font-bold text-neutral-main flex items-center gap-2">
                {/* Team Schedule Indicator */}
                {i % 2 !== 0 && <span className="text-[9px] bg-primary-50 text-primary-700 px-2 py-0.5 rounded-full border border-primary-100">[팀]</span>}
                {m.title}
              </div>
              <div className="flex gap-2.5 mt-1 text-[11px] text-neutral-muted font-medium">
                <span className="flex items-center gap-1"><MapPin size={10} className="text-primary-400" />{m.location}</span>
                <span className="flex items-center gap-1"><Users size={10} className="text-primary-400" />{m.attendees}명</span>
              </div>
            </div>
            <div className="relative z-10">
              <Badge variant="status-scheduled">예정</Badge>
            </div>
          </Link>
        ))}
      </div>

      {!isCollapsed && (
        <>
          {/* 구분선 지우고 간격만 */}
          <div className="pt-1" />

          {/* 섹션 2: 내일 일정 */}
          <div className="flex items-center justify-between mb-3 mt-1">
            <h3 className="text-[15px] font-bold text-neutral-main flex items-center gap-2">
              <CalendarClock className="text-primary-500" size={18} />
              내일 일정
            </h3>
          </div>
          <div className="space-y-2">
            {actions.length === 0 && (
              <p className="text-sm font-bold text-neutral-muted py-2 text-center">내일 예정된 일정이 없습니다.</p>
            )}
            {actions.map((item, i) => (
              <Link
                key={i}
                to="/schedules"
                className="group flex items-center gap-3 p-3 rounded-2xl border border-transparent bg-white/40 hover:border-primary-200 hover:shadow-soft transition-all duration-300 relative overflow-hidden"
              >
                <div className="absolute inset-0 bg-primary-50 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
                <div className="relative z-10 text-center flex-shrink-0 bg-primary-50 w-12 h-12 rounded-xl flex flex-col items-center justify-center">
                  <div className="text-[9px] text-primary-500 font-bold">{item.deadline.split(' ')[0] || ''}</div>
                  <div className="font-display text-base font-bold text-primary-700 leading-none mt-0.5">{item.deadline.split(' ').slice(1).join(' ') || item.deadline}</div>
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
          </div>
        </>
      )}
    </div>
  );
}
