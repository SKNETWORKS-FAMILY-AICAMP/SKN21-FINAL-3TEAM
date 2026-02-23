import { Lightbulb } from 'lucide-react';

const borderColors = { deny: 'border-l-error', conditional: 'border-l-warning', ref: 'border-l-primary-300' };

export default function JudgmentCard({ result, resultIcon, summary, regulations = [], alternatives = [] }) {
  const resultColor = result === '조건부 가능' ? 'text-warning' : result?.includes('불가') ? 'text-error' : 'text-success';

  return (
    <div className="bg-surface-card rounded-[14px] border border-neutral-border overflow-hidden">
      {result && (
        <div className={`px-4 py-3 border-b border-neutral-divider flex items-center gap-2 font-bold text-sm ${resultColor}`}>
          <span className="text-[0.9375rem]">{resultIcon}</span>{result}
        </div>
      )}
      <div className="p-4">
        {summary && <p className="text-sm text-neutral-main leading-relaxed mb-3.5 whitespace-pre-wrap">{summary}</p>}
        {regulations.length > 0 && (
          <div className="mb-3.5">
            <div className="text-xs font-semibold text-neutral-sub mb-2">관련 규정 ({regulations.length}건)</div>
            {regulations.map((r, i) => (
              <div key={i} className={`px-3 py-2 bg-surface-hover rounded-lg mb-1.5 border-l-[3px] ${borderColors[r.type] || 'border-l-primary-300'}`}>
                <div className="text-xs font-semibold text-neutral-main">{r.name}</div>
                <div className="text-[0.6875rem] text-neutral-sub mt-0.5">{r.verdict}</div>
              </div>
            ))}
          </div>
        )}
        {alternatives.length > 0 && (
          <div>
            <div className="text-xs font-semibold text-neutral-sub mb-2 flex items-center gap-1"><Lightbulb size={14} /> 대안</div>
            {alternatives.map((a, i) => (
              <div key={i} className="text-xs text-neutral-main py-1.5 pl-3 border-l-2 border-l-accent-300 mb-1.5 leading-relaxed">{a}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
