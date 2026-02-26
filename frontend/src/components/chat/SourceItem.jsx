export default function SourceItem({ source, index, onSelect }) {
  const score = typeof source.score === 'number' ? source.score : null;
  const pct = score !== null ? Math.round(score * 100) : null;
  const scoreColor = score >= 0.7 ? 'text-green-600' : score >= 0.4 ? 'text-yellow-600' : 'text-red-500';
  const barColor = score >= 0.7 ? 'bg-green-500' : score >= 0.4 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <button
      onClick={() => onSelect?.(source)}
      className="w-full text-left px-3 py-2 bg-surface-hover rounded-lg mb-1.5 border-l-[3px] border-l-accent-300 hover:border-l-accent-500 hover:bg-accent-50 transition"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs font-semibold text-neutral-main truncate">
          {source.title || source.name || source.source || `출처 ${index + 1}`}
          {source.page && <span className="text-neutral-muted font-normal ml-1">p.{source.page}</span>}
        </div>
        {pct !== null && (
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <div className="w-12 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
            </div>
            <span className={`text-[0.625rem] font-semibold ${scoreColor}`}>{pct}%</span>
          </div>
        )}
      </div>
      {source.content && <div className="text-[0.6875rem] text-neutral-sub mt-0.5 line-clamp-2">{source.content}</div>}
      <div className="mt-1 text-[0.6875rem] text-accent-600 font-medium">전체 보기 →</div>
    </button>
  );
}
