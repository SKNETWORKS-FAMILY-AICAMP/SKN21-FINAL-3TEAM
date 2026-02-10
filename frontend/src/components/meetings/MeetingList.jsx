import Badge from '../common/Badge';

export default function MeetingList({ meetings = [], selected, onSelect }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><span>📅</span>회의 목록</div>
        <span className="text-xs text-neutral-muted">총 {meetings.length}건</span>
      </div>
      <div className="card-body space-y-2.5">
        {meetings.map((m, i) => (
          <div key={i} onClick={() => onSelect?.(m)}
            className={`flex items-center gap-3.5 p-3.5 rounded-sm border border-neutral-divider cursor-pointer transition hover:border-primary-300 hover:bg-surface-hover ${selected?.id === m.id ? 'border-l-[3px] border-l-primary-500' : ''}`}>
            <div className="text-center flex-shrink-0">
              <div className="font-display text-lg font-bold text-primary-700">{m.dateShort}</div>
              <div className="text-[11px] text-neutral-muted font-medium">{m.dayOfWeek}</div>
            </div>
            <div className="flex-1">
              <div className="text-sm font-semibold text-neutral-main">{m.title}</div>
              <div className="flex gap-3 mt-1 text-xs text-neutral-sub">
                <span>👥 {m.attendeeCount}명</span>
                <span>⏱ {m.duration}</span>
              </div>
            </div>
            <Badge variant={m.analyzed ? 'status-completed' : 'status-in-progress'}>{m.analyzed ? '분석완료' : '분석중'}</Badge>
          </div>
        ))}
      </div>
    </div>
  );
}
