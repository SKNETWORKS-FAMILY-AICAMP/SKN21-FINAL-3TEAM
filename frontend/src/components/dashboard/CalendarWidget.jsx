export default function CalendarWidget({ year = 2026, month = 2, today = 5, events = {} }) {
  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];
  const firstDay = new Date(year, month - 1, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();
  const prevDays = new Date(year, month - 1, 0).getDate();
  const days = [];

  for (let i = firstDay - 1; i >= 0; i--) days.push({ day: prevDays - i, other: true });
  for (let i = 1; i <= daysInMonth; i++) days.push({ day: i, other: false });

  return (
    <div className="card">
      <div className="card-body">
        <div className="flex justify-between items-center mb-4">
          <div className="text-[15px] font-bold text-neutral-main">{year}년 {month}월</div>
          <div className="flex gap-1">
            <button className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 hover:border-primary-300 transition">◀</button>
            <button className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 hover:border-primary-300 transition">▶</button>
          </div>
        </div>
        <div className="grid grid-cols-7 gap-0.5 text-center">
          {dayNames.map((d) => <div key={d} className="text-[11px] font-semibold text-neutral-muted py-2">{d}</div>)}
          {days.map((d, i) => {
            const ev = events[d.day];
            const isToday = !d.other && d.day === today;
            return (
              <div key={i} className={`py-2 text-[13px] font-medium rounded-lg cursor-pointer relative transition hover:bg-surface-hover ${d.other ? 'text-neutral-muted' : 'text-neutral-main'} ${isToday ? 'bg-primary-700 text-white font-bold hover:bg-primary-900' : ''}`}>
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
