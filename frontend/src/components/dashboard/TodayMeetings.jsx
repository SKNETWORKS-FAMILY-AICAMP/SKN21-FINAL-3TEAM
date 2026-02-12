import { Link } from 'react-router-dom';
import Badge from '../common/Badge';

export default function TodayMeetings({ meetings = [] }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><span>📅</span>오늘의 회의</div>
        <Link to="/meetings" className="btn-secondary text-xs">+ 새 회의</Link>
      </div>
      <div className="card-body space-y-2.5">
        {meetings.map((m, i) => (
          <Link key={i} to="/meetings" className="flex items-center gap-3.5 p-3.5 rounded-sm border border-neutral-border transition hover:bg-surface-hover">
            <div className="text-center flex-shrink-0">
              <div className="font-display text-lg font-bold text-primary-700">{m.time}</div>
              <div className="text-[0.6875rem] text-neutral-muted font-medium">{m.period}</div>
            </div>
            <div className="flex-1">
              <div className="text-sm font-semibold text-neutral-main">{m.title}</div>
              <div className="flex gap-3 mt-1 text-xs text-neutral-sub">
                <span>📍 {m.location}</span>
                <span>👥 {m.attendees}명</span>
              </div>
            </div>
            <Badge variant="status-scheduled">예정</Badge>
          </Link>
        ))}
      </div>
    </div>
  );
}
