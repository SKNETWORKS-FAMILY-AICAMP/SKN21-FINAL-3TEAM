import { useState, useRef, useEffect } from 'react';
import MeetLinkBadge from './MeetLinkBadge';

const TYPE_LABELS = { meeting: '회의', deadline: '마감일', google: '개인 일정', holiday: '공휴일' };
const TYPE_DOT = { meeting: 'bg-primary-500', deadline: 'bg-error', google: 'bg-success', holiday: 'bg-error' };
const typeStyles = {
  meeting: 'bg-primary-50 text-primary-700',
  deadline: 'bg-error-bg text-error',
  google: 'bg-success-bg text-success',
  holiday: 'bg-error-bg text-error',
};

// 한국 공휴일 (고정 공휴일 + 연도별 음력 공휴일)
function getKoreanHolidays(year) {
  // 고정 공휴일
  const fixed = [
    { month: 1, day: 1, label: '신정' },
    { month: 3, day: 1, label: '삼일절' },
    { month: 5, day: 5, label: '어린이날' },
    { month: 6, day: 6, label: '현충일' },
    { month: 8, day: 15, label: '광복절' },
    { month: 10, day: 3, label: '개천절' },
    { month: 10, day: 9, label: '한글날' },
    { month: 12, day: 25, label: '크리스마스' },
  ];

  // 음력 기반 공휴일 (연도별 양력 변환 — 주요 연도)
  const lunarByYear = {
    2025: [
      { month: 1, day: 28, label: '설날 연휴' },
      { month: 1, day: 29, label: '설날' },
      { month: 1, day: 30, label: '설날 연휴' },
      { month: 5, day: 5, label: '부처님오신날' },
      { month: 10, day: 5, label: '추석 연휴' },
      { month: 10, day: 6, label: '추석' },
      { month: 10, day: 7, label: '추석 연휴' },
    ],
    2026: [
      { month: 2, day: 16, label: '설날 연휴' },
      { month: 2, day: 17, label: '설날' },
      { month: 2, day: 18, label: '설날 연휴' },
      { month: 5, day: 24, label: '부처님오신날' },
      { month: 9, day: 24, label: '추석 연휴' },
      { month: 9, day: 25, label: '추석' },
      { month: 9, day: 26, label: '추석 연휴' },
    ],
    2027: [
      { month: 2, day: 6, label: '설날 연휴' },
      { month: 2, day: 7, label: '설날' },
      { month: 2, day: 8, label: '설날 연휴' },
      { month: 5, day: 13, label: '부처님오신날' },
      { month: 10, day: 14, label: '추석 연휴' },
      { month: 10, day: 15, label: '추석' },
      { month: 10, day: 16, label: '추석 연휴' },
    ],
  };

  const lunar = lunarByYear[year] || [];
  return [...fixed, ...lunar].map((h) => ({ ...h, type: 'holiday' }));
}

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
                      <span className="text-[0.6875rem] text-neutral-muted">{TYPE_LABELS[e.type] || e.type}</span>
                      {e.time && <span className="text-[0.6875rem] text-neutral-sub font-medium">{e.time}</span>}
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

// 연간 뷰 — 12개월 미니 캘린더
function YearView({ year, events, todayYear, todayMonth, todayDate, onMonthClick }) {
  const monthNames = ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월'];
  const dayNamesShort = ['일','월','화','수','목','금','토'];

  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 gap-4">
      {monthNames.map((name, mIdx) => {
        const month = mIdx + 1;
        const firstDay = new Date(year, mIdx, 1).getDay();
        const daysInMonth = new Date(year, month, 0).getDate();
        const monthEvents = events.filter((e) => e.month === month);

        const cells = [];
        for (let i = 0; i < firstDay; i++) cells.push(null);
        for (let d = 1; d <= daysInMonth; d++) cells.push(d);

        return (
          <div
            key={month}
            onClick={() => onMonthClick(month)}
            className="bg-surface-card border border-neutral-divider rounded-lg p-4 cursor-pointer hover:border-primary-300 transition"
          >
            <div className="text-sm font-bold text-neutral-main mb-2 text-center">{name}</div>
            <div className="grid grid-cols-7 gap-px">
              {dayNamesShort.map((d) => (
                <div key={d} className="text-[0.625rem] text-neutral-muted text-center pb-1">{d}</div>
              ))}
              {cells.map((d, i) => {
                const isToday = d && year === todayYear && month === todayMonth && d === todayDate;
                const isHoliday = d && monthEvents.some((e) => e.day === d && e.type === 'holiday');
                const hasEvent = d && monthEvents.some((e) => e.day === d && e.type !== 'holiday');
                return (
                  <div key={i} className="flex items-center justify-center h-7">
                    {d ? (
                      <span className={`text-[0.6875rem] w-6 h-6 flex items-center justify-center rounded-full
                        ${isToday ? 'bg-primary-700 text-white font-bold' : ''}
                        ${isHoliday && !isToday ? 'bg-error-bg text-error font-semibold' : ''}
                        ${hasEvent && !isToday && !isHoliday ? 'bg-primary-50 text-primary-700 font-semibold' : ''}
                        ${!isToday && !hasEvent && !isHoliday ? 'text-neutral-sub' : ''}
                      `}>{d}</span>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function CalendarView({ events = [] }) {
  const now = new Date();
  const [currentYear, setCurrentYear] = useState(now.getFullYear());
  const [currentMonth, setCurrentMonth] = useState(now.getMonth() + 1);
  const [view, setView] = useState('month');
  const [selectedDay, setSelectedDay] = useState(null);
  const [showHolidays, setShowHolidays] = useState(true);

  const holidays = showHolidays ? getKoreanHolidays(currentYear) : [];
  const mergedEvents = [...events, ...holidays];

  const todayDate = now.getDate();
  const todayYear = now.getFullYear();
  const todayMonth = now.getMonth() + 1;

  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];
  const firstDay = new Date(currentYear, currentMonth - 1, 1).getDay();
  const daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
  const prevDays = new Date(currentYear, currentMonth - 1, 0).getDate();

  const goToPrev = () => {
    if (view === 'year') { setCurrentYear(currentYear - 1); return; }
    if (currentMonth === 1) { setCurrentYear(currentYear - 1); setCurrentMonth(12); }
    else setCurrentMonth(currentMonth - 1);
  };
  const goToNext = () => {
    if (view === 'year') { setCurrentYear(currentYear + 1); return; }
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

  const handleYearMonthClick = (month) => {
    setCurrentMonth(month);
    setView('month');
  };

  const selectedEvents = selectedDay
    ? mergedEvents.filter((e) => e.day === selectedDay && e.month === currentMonth)
    : [];

  const VIEW_BTNS = [
    { key: 'month', label: '월간' },
    { key: 'week', label: '주간' },
    { key: 'year', label: '연간' },
  ];

  return (
    <div className="card">
      <div className="card-header">
        <div className="flex items-center gap-3">
          <div className="flex gap-1">
            <button onClick={goToPrev} className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">◀</button>
            <button onClick={goToNext} className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">▶</button>
          </div>
          <span className="text-base font-bold">
            {view === 'year' ? `${currentYear}년` : `${currentYear}년 ${currentMonth}월`}
          </span>
          <button onClick={goToToday} className="text-[0.6875rem] px-2 py-1 rounded border border-neutral-divider text-neutral-muted hover:bg-primary-50 hover:text-primary-700 transition">오늘</button>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowHolidays(!showHolidays)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition ${
              showHolidays
                ? 'border-error bg-error-bg text-error'
                : 'border-neutral-divider bg-surface-card text-neutral-muted hover:bg-surface-hover'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${showHolidays ? 'bg-error' : 'bg-neutral-muted'}`} />
            공휴일
          </button>
          <div className="w-px h-4 bg-neutral-divider" />
          <div className="flex gap-1">
            {VIEW_BTNS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setView(key)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition ${view === key ? 'bg-primary-50 text-primary-700 font-semibold' : 'text-neutral-sub hover:bg-surface-hover'}`}
              >{label}</button>
            ))}
          </div>
        </div>
      </div>
      <div className="card-body">
        {view === 'year' ? (
          <YearView
            year={currentYear}
            events={mergedEvents}
            todayYear={todayYear}
            todayMonth={todayMonth}
            todayDate={todayDate}
            onMonthClick={handleYearMonthClick}
          />
        ) : (
        <div className="grid grid-cols-7 gap-1">
          {dayNames.map((d) => (
            <div key={d} className="text-[0.6875rem] font-semibold text-neutral-muted py-2 text-center">{d}</div>
          ))}
          {displayDays.map((d, i) => {
            const dayEvents = mergedEvents.filter((e) => e.day === d.day && e.month === currentMonth && !d.other);
            const isToday = !d.other && d.day === todayDate && currentYear === todayYear && currentMonth === todayMonth;
            return (
              <div
                key={i}
                onClick={() => handleDayClick(d)}
                className={`${view === 'week' ? 'min-h-[320px]' : 'min-h-[150px]'} bg-surface-card border border-neutral-divider rounded-sm p-1.5 text-xs transition hover:border-primary-300 cursor-pointer ${
                  isToday ? 'border-primary-700 border-2' : ''
                } ${selectedDay === d.day && !d.other ? 'ring-2 ring-primary-500' : ''}`}
              >
                <div className={`font-semibold mb-1 ${d.other ? 'text-neutral-muted' : 'text-neutral-main'}`}>{d.day}</div>
                {dayEvents.map((e, j) => (
                  <div key={j} className="mb-0.5">
                    <div className={`text-[0.625rem] px-1.5 py-0.5 rounded font-medium truncate ${typeStyles[e.type] || ''}`}>
                      {e.label}
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
        )}
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
