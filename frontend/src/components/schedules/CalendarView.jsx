export default function CalendarView({ year = 2026, month = 2, today = 5, events = [] }) {
  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];
  const firstDay = new Date(year, month - 1, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();
  const days = [];
  const prevDays = new Date(year, month - 1, 0).getDate();

  for (let i = firstDay - 1; i >= 0; i--) days.push({ day: prevDays - i, other: true });
  for (let i = 1; i <= daysInMonth; i++) days.push({ day: i, other: false });
  while (days.length < 14) days.push({ day: days.length - daysInMonth - firstDay + 1, other: true });

  const typeStyles = { meeting: 'bg-primary-50 text-primary-700', deadline: 'bg-error-bg text-error', google: 'bg-success-bg text-success' };

  return (
    <div className="card">
      <div className="card-header">
        <div className="flex items-center gap-3">
          <div className="flex gap-1">
            <button className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">◀</button>
            <button className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">▶</button>
          </div>
          <span className="text-base font-bold">{year}년 {month}월</span>
        </div>
        <div className="flex gap-1">
          <button className="px-3 py-1 rounded-md text-xs font-medium text-neutral-sub hover:bg-surface-hover">월간</button>
          <button className="px-3 py-1 rounded-md text-xs font-semibold bg-primary-50 text-primary-700">주간</button>
        </div>
      </div>
      <div className="card-body">
        <div className="grid grid-cols-7 gap-1">
          {dayNames.map((d) => <div key={d} className="text-[11px] font-semibold text-neutral-muted py-2 text-center">{d}</div>)}
          {days.map((d, i) => {
            const dayEvents = events.filter((e) => e.day === d.day && !d.other);
            const isToday = !d.other && d.day === today;
            return (
              <div key={i} className={`min-h-[80px] bg-surface-card border border-neutral-divider rounded-sm p-1.5 text-xs transition hover:border-primary-300 cursor-pointer ${isToday ? 'border-primary-700 border-2' : ''}`}>
                <div className={`font-semibold mb-1 ${d.other ? 'text-neutral-muted' : 'text-neutral-main'}`}>{d.day}</div>
                {dayEvents.map((e, j) => (
                  <div key={j} className={`text-[10px] px-1.5 py-0.5 rounded mb-0.5 font-medium truncate ${typeStyles[e.type] || ''}`}>{e.label}</div>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
