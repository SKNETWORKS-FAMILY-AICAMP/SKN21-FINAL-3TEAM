import { useState } from 'react';

export default function CalendarWidget({ events = {} }) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

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
    <div className="card">
      <div className="card-body">
        <div className="flex justify-between items-center mb-4">
          <div className="text-[0.9375rem] font-bold text-neutral-main">{year}년 {month}월</div>
          <div className="flex gap-1">
            <button onClick={goPrev} className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">◀</button>
            <button onClick={goNext} className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">▶</button>
          </div>
        </div>
        <div className="grid grid-cols-7 gap-0.5 text-center">
          {dayNames.map((d) => <div key={d} className="text-[0.6875rem] font-semibold text-neutral-muted py-2">{d}</div>)}
          {days.map((d, i) => {
            const ev = events[d.day];
            const isToday = !d.other && d.day === todayDate && year === todayYear && month === todayMonth;
            return (
              <div key={i} className={`py-2 text-[0.8125rem] font-medium rounded-lg cursor-pointer relative transition hover:bg-surface-hover ${d.other ? 'text-neutral-muted' : 'text-neutral-main'} ${isToday ? 'bg-primary-700 text-white font-bold hover:bg-primary-900' : ''}`}>
                {d.day}
                {ev && !d.other && (
                  <span className={`absolute bottom-0.5 left-1/2 -translate-x-1/2 w-[5px] h-[5px] rounded-full ${ev === 'meeting' ? 'bg-primary-500' : 'bg-error'}`} />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
