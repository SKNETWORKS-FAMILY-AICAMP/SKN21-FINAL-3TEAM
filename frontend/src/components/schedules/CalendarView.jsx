import { useState, useRef, useEffect } from 'react';
import MeetLinkBadge from './MeetLinkBadge';

const TYPE_LABELS = { meeting: '회의', deadline: '마감일', google: '개인 일정' };
const TYPE_DOT = { meeting: 'bg-primary-500', deadline: 'bg-error', google: 'bg-success' };
const typeStyles = {
  meeting: 'bg-primary-50 text-primary-700',
  deadline: 'bg-error-bg text-error',
  google: 'bg-success-bg text-success',
};

function DayDetailPopup({ day, month, year, events, onClose }) {
  const ref = useRef(null);

  useEffect(() => {
    const handleClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose();
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20">
      <div ref={ref} className="bg-surface-card rounded-lg border border-neutral-border shadow-md w-[540px] h-[300px] max-h-[1000px] overflow-hidden">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-divider">
          <span className="text-sm font-bold text-neutral-main">{year}년 {month}월 {day}일</span>
          <button onClick={onClose} className="w-6 h-6 flex items-center justify-center rounded hover:bg-surface-hover text-neutral-muted text-sm">✕</button>
        </div>

        {/* 일정 목록 */}
        <div className="px-4 py-3 overflow-y-auto max-h-[320px]">
          {events.length === 0 ? (
            <p className="text-sm text-neutral-muted text-center py-6">등록된 일정이 없습니다</p>
          ) : (
            <ul className="space-y-2.5">
              {events.map((e, i) => (
                <li key={i} className="flex gap-3 items-start">
                  <span className={`w-2.5 h-2.5 rounded-full mt-1.5 shrink-0 ${TYPE_DOT[e.type] || 'bg-neutral-muted'}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-neutral-main">{e.label}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[11px] text-neutral-muted">{TYPE_LABELS[e.type] || e.type}</span>
                      {e.time && <span className="text-[11px] text-neutral-sub font-medium">{e.time}</span>}
                    </div>
                    {e.meetLink && <div className="mt-1"><MeetLinkBadge meetLink={e.meetLink} /></div>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CalendarView({ events = [] }) {
  const now = new Date();
  const [currentYear, setCurrentYear] = useState(now.getFullYear());
  const [currentMonth, setCurrentMonth] = useState(now.getMonth() + 1);
  const [view, setView] = useState('month');
  const [selectedDay, setSelectedDay] = useState(null);

  const todayDate = now.getDate();
  const todayYear = now.getFullYear();
  const todayMonth = now.getMonth() + 1;

  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];
  const firstDay = new Date(currentYear, currentMonth - 1, 1).getDay();
  const daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
  const prevDays = new Date(currentYear, currentMonth - 1, 0).getDate();

  const goToPrev = () => {
    if (currentMonth === 1) { setCurrentYear(currentYear - 1); setCurrentMonth(12); }
    else setCurrentMonth(currentMonth - 1);
  };
  const goToNext = () => {
    if (currentMonth === 12) { setCurrentYear(currentYear + 1); setCurrentMonth(1); }
    else setCurrentMonth(currentMonth + 1);
  };
  const goToToday = () => { setCurrentYear(todayYear); setCurrentMonth(todayMonth); };

  const days = [];
  for (let i = firstDay - 1; i >= 0; i--) days.push({ day: prevDays - i, other: true });
  for (let i = 1; i <= daysInMonth; i++) days.push({ day: i, other: false });
  const remaining = 7 - (days.length % 7);
  if (remaining < 7) {
    for (let i = 1; i <= remaining; i++) days.push({ day: i, other: true });
  }

  const getWeekDays = () => {
    const todayIdx = days.findIndex(
      (d) => !d.other && d.day === (currentYear === todayYear && currentMonth === todayMonth ? todayDate : 1)
    );
    const startIdx = todayIdx >= 0 ? todayIdx - (new Date(currentYear, currentMonth - 1, days[todayIdx]?.day || 1).getDay()) : 0;
    return days.slice(Math.max(0, startIdx), Math.max(0, startIdx) + 7);
  };

  const displayDays = view === 'week' ? getWeekDays() : days;

  const handleDayClick = (d) => {
    if (d.other) return;
    setSelectedDay(d.day);
  };

  const selectedEvents = selectedDay
    ? events.filter((e) => e.day === selectedDay)
    : [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="flex items-center gap-3">
          <div className="flex gap-1">
            <button onClick={goToPrev} className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">◀</button>
            <button onClick={goToNext} className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">▶</button>
          </div>
          <span className="text-base font-bold">{currentYear}년 {currentMonth}월</span>
          <button onClick={goToToday} className="text-[11px] px-2 py-1 rounded border border-neutral-divider text-neutral-muted hover:bg-primary-50 hover:text-primary-700 transition">오늘</button>
        </div>
        <div className="flex gap-1">
          <button
            onClick={() => setView('month')}
            className={`px-3 py-1 rounded-md text-xs font-medium transition ${view === 'month' ? 'bg-primary-50 text-primary-700 font-semibold' : 'text-neutral-sub hover:bg-surface-hover'}`}
          >월간</button>
          <button
            onClick={() => setView('week')}
            className={`px-3 py-1 rounded-md text-xs font-medium transition ${view === 'week' ? 'bg-primary-50 text-primary-700 font-semibold' : 'text-neutral-sub hover:bg-surface-hover'}`}
          >주간</button>
        </div>
      </div>
      <div className="card-body">
        <div className="grid grid-cols-7 gap-1">
          {dayNames.map((d) => (
            <div key={d} className="text-[11px] font-semibold text-neutral-muted py-2 text-center">{d}</div>
          ))}
          {displayDays.map((d, i) => {
            const dayEvents = events.filter((e) => e.day === d.day && !d.other);
            const isToday = !d.other && d.day === todayDate && currentYear === todayYear && currentMonth === todayMonth;
            return (
              <div
                key={i}
                onClick={() => handleDayClick(d)}
                className={`min-h-[150px] bg-surface-card border border-neutral-divider rounded-sm p-1.5 text-xs transition hover:border-primary-300 cursor-pointer ${
                  isToday ? 'border-primary-700 border-2' : ''
                } ${selectedDay === d.day && !d.other ? 'ring-2 ring-primary-500' : ''}`}
              >
                <div className={`font-semibold mb-1 ${d.other ? 'text-neutral-muted' : 'text-neutral-main'}`}>{d.day}</div>
                {dayEvents.map((e, j) => (
                  <div key={j} className="mb-0.5">
                    <div className={`text-[10px] px-1.5 py-0.5 rounded font-medium truncate ${typeStyles[e.type] || ''}`}>
                      {e.label}
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>

      {/* 날짜 클릭 시 상세 팝업 */}
      {selectedDay && (
        <DayDetailPopup
          day={selectedDay}
          month={currentMonth}
          year={currentYear}
          events={selectedEvents}
          onClose={() => setSelectedDay(null)}
        />
      )}
    </div>
  );
}
