import { Link } from 'react-router-dom';
import Badge from '../common/Badge';
import { FileText } from 'lucide-react';

export default function RecentDocs({ docs = [] }) {
  return (
    <div className="rounded-2xl border border-white/60 overflow-hidden bg-white/60 dark:bg-gray-800/60 backdrop-blur-md shadow-md">
      <div className="card-header">
        <div className="card-title"><FileText size={16} className="text-neutral-sub" />최근 문서</div>
        <Link to="/documents" className="btn-primary text-xs">+ 업로드</Link>
      </div>
      <div className="card-body space-y-2">
        {docs.length === 0 && (
          <p className="text-sm text-neutral-muted py-2">업로드된 문서가 없습니다.</p>
        )}
        {docs.map((d, i) => (
          <Link key={i} to="/documents" className="flex items-center gap-3 p-3 rounded-sm border border-neutral-border transition hover:bg-surface-hover">
            <div className="w-9 h-9 bg-primary-50 rounded-sm flex items-center justify-center flex-shrink-0 text-primary-700"><FileText size={18} /></div>
            <div className="flex-1">
              <div className="text-[0.8125rem] font-semibold text-neutral-main">{d.name}</div>
              <div className="flex gap-2.5 text-[0.6875rem] text-neutral-muted mt-1">
                <span>{d.version}</span><span>{d.date}</span>
              </div>
            </div>
            <Badge variant={
              d.status === '적용중' || d.status === '완료' ? 'status-active' :
              d.status === '처리중' ? 'status-in-progress' : 'status-revising'
            }>{d.status}</Badge>
          </Link>
        ))}
      </div>
    </div>
  );
}
