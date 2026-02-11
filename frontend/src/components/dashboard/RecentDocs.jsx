import { Link } from 'react-router-dom';
import Badge from '../common/Badge';

export default function RecentDocs({ docs = [] }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><span>📄</span>최근 문서</div>
        <Link to="/documents" className="btn-primary text-xs">+ 업로드</Link>
      </div>
      <div className="card-body space-y-2">
        {docs.map((d, i) => (
          <Link key={i} to="/documents" className="flex items-center gap-3 p-3 rounded-sm border border-neutral-divider transition hover:border-primary-300 hover:bg-surface-hover">
            <div className="w-9 h-9 bg-primary-50 rounded-sm flex items-center justify-center text-base flex-shrink-0">📄</div>
            <div className="flex-1">
              <div className="text-[0.8125rem] font-semibold text-neutral-main">{d.name}</div>
              <div className="flex gap-2.5 text-[0.6875rem] text-neutral-muted mt-1">
                <span>{d.version}</span><span>{d.date}</span>
              </div>
            </div>
            <Badge variant={d.status === '적용중' ? 'status-active' : 'status-revising'}>{d.status}</Badge>
          </Link>
        ))}
      </div>
    </div>
  );
}
