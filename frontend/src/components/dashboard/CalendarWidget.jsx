import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronUp, ChevronDown } from 'lucide-react';

export default function CalendarWidget({ events = {} }) {
  const navigate = useNavigate();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const todayYear = now.getFullYear();
  const todayMonth = now.getMonth() + 1;
  const todayDate = now.getDate();

  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];
  const firstDay = new Date(year, month - 1, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();
  const prevDays = new Date(year, month - 1, 0).getDate();
  const days = [];

  for (let i = firstDay - 1; i >= 0; i--) days.push({ day: prevDays - i, other: true });
  for (let i = 1; i <= daysInMonth; i++) days.push({ day: i, other: false });

  const goPrev = () => {
    if (month === 1) { setYear(year - 1); setMonth(12); }
    else setMonth(month - 1);
  };

  const goNext = () => {
    if (month === 12) { setYear(year + 1); setMonth(1); }
    else setMonth(month + 1);
  };

  return (
    <div className={`rounded-2xl border border-white/60 bg-white/60 dark:bg-gray-800/60 backdrop-blur-md shadow-md transition-all duration-300 ${isCollapsed ? '' : ''}`}>
      <div
        className="card-body cursor-pointer flex justify-between items-center pb-2"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="text-[0.9375rem] font-bold text-neutral-main">{year}년 {month}월</div>
        <div className="flex gap-1 items-center">
          <button onClick={(e) => { e.stopPropagation(); goPrev(); }} className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">◀</button>
          <button onClick={(e) => { e.stopPropagation(); goNext(); }} className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">▶</button>
          <button className="ml-2 text-neutral-muted hover:text-primary-500 transition-colors p-1 rounded-full hover:bg-surface-hover">
            {isCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
          </button>
        </div>
      </div>

      {!isCollapsed && (
        <div className="card-body pt-0">
          <div className="grid grid-cols-7 gap-0.5 text-center" onClick={(e) => { e.stopPropagation(); navigate('/schedules'); }}>
            {dayNames.map((d) => <div key={d} className="text-[0.6875rem] font-semibold text-neutral-muted py-2">{d}</div>)}
            {days.map((d, i) => {
              const ev = events[d.day];
              const isToday = !d.other && d.day === todayDate && year === todayYear && month === todayMonth;
              return (
                <div key={i} className={`py-3.5 text-[0.8125rem] font-medium rounded-lg cursor-pointer relative transition hover:bg-surface-hover flex items-center justify-center ${d.other ? 'text-neutral-muted' : 'text-neutral-main'}`}>
                  <span className={`w-10 h-10 flex items-center justify-center rounded-full ${isToday ? 'bg-primary-700 text-white font-bold' : ''}`}>
                    {d.day}
                  </span>
                  {ev && !d.other && (
                    <span className={`absolute bottom-0.5 left-1/2 -translate-x-1/2 w-[5px] h-[5px] rounded-full ${ev === 'meeting' ? 'bg-primary-500' : 'bg-error'}`} />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
