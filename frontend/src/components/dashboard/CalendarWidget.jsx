import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronUp, ChevronDown } from 'lucide-react';

export default function CalendarWidget({ allSchedules = [] }) {
  const navigate = useNavigate();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [selectedDay, setSelectedDay] = useState(null);
  const [popoverStyle, setPopoverStyle] = useState({});
  const containerRef = useRef(null);

  const todayYear = now.getFullYear();
  const todayMonth = now.getMonth() + 1;
  const todayDate = now.getDate();

  // 현재 보고 있는 월 기준으로 일정 필터링
  const { events, schedules } = useMemo(() => {
    const ev = {};
    const sc = {};
    allSchedules.forEach(s => {
      const d = new Date(s.start_time);
      if (d.getFullYear() === year && d.getMonth() + 1 === month) {
        const day = d.getDate();
        ev[day] = s.schedule_type === 'meeting' ? 'meeting' : 'deadline';
        if (!sc[day]) sc[day] = [];
        sc[day].push(s);
      }
    });
    return { events: ev, schedules: sc };
  }, [allSchedules, year, month]);

  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];
  const firstDay = new Date(year, month - 1, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();
  const prevDays = new Date(year, month - 1, 0).getDate();
  const days = [];

  for (let i = firstDay - 1; i >= 0; i--) days.push({ day: prevDays - i, other: true });
  for (let i = 1; i <= daysInMonth; i++) days.push({ day: i, other: false });

  const goPrev = () => {
    setSelectedDay(null);
    if (month === 1) { setYear(year - 1); setMonth(12); }
    else setMonth(month - 1);
  };

  const goNext = () => {
    setSelectedDay(null);
    if (month === 12) { setYear(year + 1); setMonth(1); }
    else setMonth(month + 1);
  };

  const handleDayClick = useCallback((e, d) => {
    e.stopPropagation();
    if (d.other) return;

    if (selectedDay === d.day) {
      setSelectedDay(null);
      return;
    }

    const cell = e.currentTarget;
    const container = containerRef.current;
    if (!cell || !container) return;

    const cellRect = cell.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();

    const cellCenterX = cellRect.left + cellRect.width / 2 - containerRect.left;
    const cellTop = cellRect.top - containerRect.top;
    const cellBottom = cellRect.bottom - containerRect.top;

    const popoverW = 200;
    const style = { position: 'absolute', zIndex: 30, width: popoverW };

    // 하단 40% 날짜는 위로, 나머지는 아래로
    const isLowerHalf = cellBottom > containerRect.height * 0.6;
    if (isLowerHalf) {
      style.bottom = containerRect.height - cellTop + 4;
    } else {
      style.top = cellBottom + 4;
    }

    // 좌우 정렬
    let left = cellCenterX - popoverW / 2;
    if (left < 4) left = 4;
    if (left + popoverW > containerRect.width - 4) left = containerRect.width - popoverW - 4;
    style.left = left;

    setPopoverStyle(style);
    setSelectedDay(d.day);
  }, [selectedDay]);

  // 외부 클릭 시 닫기
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setSelectedDay(null);
      }
    };
    if (selectedDay !== null) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [selectedDay]);

  const selectedSchedules = selectedDay
    ? (schedules[selectedDay] || []).slice().sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
    : [];

  const formatTime = (timeStr) => {
    if (!timeStr) return '';
    const d = new Date(timeStr);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  };

  return (
    <div className="card transition-all duration-300 !overflow-visible">
      <div
        className="cursor-pointer flex justify-between items-center py-4 px-5"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center gap-2">
          <div className="text-sm font-bold text-neutral-main">{year}년 {month}월</div>
          <button
            onClick={(e) => { e.stopPropagation(); navigate('/schedules'); }}
            className="text-[0.625rem] text-primary-500 hover:text-primary-700 font-medium transition"
          >
            일정 관리 →
          </button>
        </div>
        <div className="flex gap-0.5 items-center">
          <button onClick={(e) => { e.stopPropagation(); goPrev(); }} className="w-5 h-5 rounded border border-neutral-border bg-surface-card text-[0.5rem] text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">◀</button>
          <button onClick={(e) => { e.stopPropagation(); goNext(); }} className="w-5 h-5 rounded border border-neutral-border bg-surface-card text-[0.5rem] text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">▶</button>
          <button className="ml-1 text-neutral-muted hover:text-primary-500 transition-colors p-0.5 rounded-full hover:bg-surface-hover">
            {isCollapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          </button>
        </div>
      </div>

      {!isCollapsed && (
        <div className="px-5 pb-5 pt-0 relative" ref={containerRef}>
          <div className="grid grid-cols-7 gap-px text-center">
            {dayNames.map((d) => (
              <div key={d} className="aspect-square flex items-center justify-center text-xs font-semibold text-neutral-muted">{d}</div>
            ))}
            {days.map((d, i) => {
              const ev = !d.other && events[d.day];
              const isToday = !d.other && d.day === todayDate && year === todayYear && month === todayMonth;
              const isSelected = !d.other && d.day === selectedDay;
              return (
                <div
                  key={i}
                  onClick={(e) => handleDayClick(e, d)}
                  className={`aspect-square text-xs font-medium rounded cursor-pointer relative transition hover:bg-surface-hover flex items-center justify-center ${d.other ? 'text-neutral-muted' : 'text-neutral-main'} ${isSelected ? 'ring-2 ring-primary-400 rounded-lg' : ''}`}
                >
                  <span className={`w-full h-full flex items-center justify-center rounded-full ${isToday ? 'bg-primary-700 text-white font-bold' : ''}`}>
                    {d.day}
                  </span>
                  {ev && (
                    <span className={`absolute bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full ${ev === 'meeting' ? 'bg-primary-500' : 'bg-error'}`} />
                  )}
                </div>
              );
            })}
          </div>

          {selectedDay !== null && (
            <div
              style={popoverStyle}
              className="bg-surface-card border border-neutral-border rounded-lg shadow-lg p-3"
            >
              <div className="text-xs font-bold text-neutral-main mb-2">
                {month}/{selectedDay} 일정
              </div>
              {selectedSchedules.length === 0 ? (
                <p className="text-xs text-neutral-muted">등록된 일정이 없습니다</p>
              ) : (
                <ul className="space-y-1.5 max-h-[120px] overflow-y-auto">
                  {selectedSchedules.map((s, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs">
                      <span className={`mt-0.5 w-1.5 h-1.5 rounded-full shrink-0 ${s.schedule_type === 'meeting' ? 'bg-primary-500' : 'bg-error'}`} />
                      <div className="min-w-0">
                        <div className="font-medium text-neutral-main truncate">{s.title}</div>
                        <div className="text-neutral-muted">{formatTime(s.start_time)}{s.end_time ? ` - ${formatTime(s.end_time)}` : ''}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
