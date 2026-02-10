export default function ScheduleCard({ title, date, time, synced }) {
  return (
    <div className="bg-surface-card rounded-[14px] border border-neutral-border overflow-hidden">
      <div className="px-4 py-3 border-b border-neutral-divider flex items-center gap-2 font-bold text-sm text-success">
        <span className="text-[15px]">✅</span>일정 등록 완료
      </div>
      <div className="p-4">
        <div className="bg-accent-50 rounded-[10px] p-3.5">
          <div className="text-sm font-semibold text-neutral-main mb-2">📅 {title}</div>
          <div className="text-[13px] text-neutral-sub leading-[1.8]">{date}<br />{time}</div>
          {synced && (
            <div className="mt-2 text-[11px] text-success font-medium flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-success" />Google Calendar 동기화됨
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
