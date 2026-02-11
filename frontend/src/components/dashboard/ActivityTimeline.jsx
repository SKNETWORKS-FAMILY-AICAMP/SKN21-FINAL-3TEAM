import { Link } from 'react-router-dom';

const iconStyles = {
  doc: 'bg-primary-50',
  query: 'bg-accent-50',
  meeting: 'bg-info-bg',
  schedule: 'bg-success-bg',
};

export default function ActivityTimeline({ activities = [] }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><span>⏱️</span>최근 활동</div>
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-success-bg text-success text-xs font-semibold">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/><path d="M9 12l2 2 4-4"/></svg>
          자동 스캔 중
        </div>
      </div>
      <div className="card-body">
        {activities.map((a, i) => (
          <Link key={i} to={a.to || '#'} className={`flex items-center gap-3 px-2 py-3 rounded-sm transition hover:bg-surface-hover ${i < activities.length - 1 ? 'border-b border-neutral-divider' : ''}`}>
            <div className={`w-9 h-9 rounded-sm flex items-center justify-center text-base flex-shrink-0 ${iconStyles[a.type] || 'bg-primary-50'}`}>{a.icon}</div>
            <div className="flex-1">
              <div className="text-[0.8125rem] font-semibold text-neutral-main">{a.title}</div>
              <div className="text-[0.75rem] text-neutral-sub mt-0.5">{a.description}</div>
            </div>
            <span className="text-[0.6875rem] text-neutral-muted whitespace-nowrap ml-auto">{a.time}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
