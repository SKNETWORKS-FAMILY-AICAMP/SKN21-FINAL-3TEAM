import { useState } from 'react';
import { Link } from 'react-router-dom';
import Badge from '../common/Badge';
import { FileText, ChevronUp, ChevronDown } from 'lucide-react';

export default function RecentDocs({ docs = [], loading = false }) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <div className="card flex flex-col p-6 shadow-soft transition-all duration-300">
      <div
        className="flex items-center justify-between mb-4 cursor-pointer"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <h3 className="text-lg font-bold text-neutral-main flex items-center gap-2">
          <FileText className="text-primary-500" size={24} />
          팀 최근 문서
        </h3>
        <div className="flex items-center gap-3">
          <Link
            to="/documents"
            className="text-xs font-bold text-primary-600 hover:text-white bg-primary-50 hover:bg-primary-500 px-4 py-2 rounded-full transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            + 업로드
          </Link>
          <button className="text-neutral-muted hover:text-primary-500 transition-colors p-1 rounded-full hover:bg-surface-hover">
            {isCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
          </button>
        </div>
      </div>

      <div className="overflow-y-auto pr-2 custom-scrollbar space-y-3">
        {loading ? (
          <div className="animate-pulse space-y-3 mt-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="flex items-center gap-4 p-4 rounded-3xl bg-neutral-100 dark:bg-neutral-800">
                <div className="w-10 h-10 rounded-2xl bg-neutral-200 dark:bg-neutral-700 flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-3 bg-neutral-200 dark:bg-neutral-700 rounded w-3/4" />
                  <div className="h-2.5 bg-neutral-200 dark:bg-neutral-700 rounded w-1/2" />
                </div>
                <div className="w-14 h-5 bg-neutral-200 dark:bg-neutral-700 rounded-full" />
              </div>
            ))}
          </div>
        ) : (
          <>
            {docs.length === 0 && !isCollapsed && (
              <p className="text-sm font-bold text-neutral-muted py-2 text-center mt-4">업로드된 문서가 없습니다.</p>
            )}
            {docs.slice(0, isCollapsed ? 1 : 999).map((d, i) => (
          <Link key={i} to="/documents" className="group flex items-center gap-4 p-4 rounded-3xl border border-transparent bg-white hover:border-primary-200 hover:shadow-soft transition-all duration-300 relative overflow-hidden">
            <div className="absolute inset-0 bg-primary-50 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
            <div className="relative z-10 w-10 h-10 bg-primary-50 rounded-2xl flex items-center justify-center flex-shrink-0 text-primary-700">
              <FileText size={20} />
            </div>
            <div className="relative z-10 flex-1">
              <div className="text-sm font-bold text-neutral-main flex items-center gap-2">
                {d.name}
                {/* Team Document Indicator */}
                {i % 2 === 0 && <span className="px-2 py-0.5 rounded-full bg-accent-50 text-accent-700 text-[10px] border border-accent-100">Team</span>}
              </div>
              <div className="flex gap-2.5 text-xs text-neutral-muted mt-1 font-medium">
                <span>{d.version}</span><span>{d.date}</span>
              </div>
            </div>
            <div className="relative z-10">
              <Badge variant={
                d.status === '적용중' || d.status === '완료' ? 'status-active' :
                  d.status === '처리중' ? 'status-in-progress' : 'status-revising'
              }>{d.status}</Badge>
            </div>
          </Link>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
