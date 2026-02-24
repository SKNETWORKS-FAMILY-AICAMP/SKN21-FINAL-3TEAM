import { useState } from 'react';
import { Lightbulb, ChevronDown, AlertTriangle, ShieldCheck } from 'lucide-react';
import MarkdownText from './MarkdownText';

const borderColors = { deny: 'border-l-error', conditional: 'border-l-warning', ref: 'border-l-primary-300' };

function getConfidenceColor(value) {
  if (value >= 0.7) return { bar: 'bg-green-500', text: 'text-green-600' };
  if (value >= 0.4) return { bar: 'bg-yellow-500', text: 'text-yellow-600' };
  return { bar: 'bg-red-500', text: 'text-red-600' };
}

function ConfidenceBar({ label, value, maxValue = 1 }) {
  const percentage = Math.min(Math.max((value / maxValue) * 100, 0), 100);
  const color = getConfidenceColor(value / maxValue);
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-[7.5rem] text-neutral-sub truncate">{label}</span>
      <div className="flex-1 h-2 bg-neutral-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color.bar} transition-all duration-300`} style={{ width: `${percentage}%` }} />
      </div>
      <span className={`w-10 text-right font-medium ${color.text}`}>{value.toFixed(2)}</span>
    </div>
  );
}

export default function JudgmentCard({ summary, regulations = [], alternatives = [], confidenceBreakdown, warnings, confidence }) {
  const [open, setOpen] = useState(false);

  const hasBreakdown = confidenceBreakdown && typeof confidenceBreakdown === 'object';
  const finalScore = hasBreakdown ? confidenceBreakdown.final : confidence;
  const hasScore = typeof finalScore === 'number';
  const scoreColor = hasScore ? getConfidenceColor(finalScore) : null;

  const penalty = hasBreakdown
    ? (confidenceBreakdown.conflict_penalty || 0) + (confidenceBreakdown.hallucination_penalty || 0) + (confidenceBreakdown.article_penalty || 0)
    : 0;

  const hasWarnings = Array.isArray(warnings) && warnings.length > 0;

  return (
    <div className="bg-surface-card rounded-[14px] border border-neutral-border overflow-hidden">
      <div className="p-4">
        {summary && <div className="text-sm text-neutral-main leading-relaxed mb-3.5"><MarkdownText>{summary}</MarkdownText></div>}
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

      {/* 신뢰도 분석 접이식 섹션 */}
      {hasBreakdown && (
        <div className="border-t border-neutral-divider">
          <button
            onClick={() => setOpen(!open)}
            className="w-full flex items-center gap-2 px-4 py-2.5 hover:bg-surface-hover transition text-left"
          >
            <ShieldCheck size={14} className={scoreColor?.text || 'text-neutral-sub'} />
            <span className="text-xs font-semibold text-neutral-main">신뢰도 분석</span>
            {hasScore && (
              <div className="flex items-center gap-1.5 ml-auto mr-2">
                <div className="w-20 h-2 bg-neutral-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${scoreColor.bar} transition-all duration-300`}
                    style={{ width: `${Math.min(finalScore * 100, 100)}%` }}
                  />
                </div>
                <span className={`text-xs font-bold ${scoreColor.text}`}>{(finalScore * 100).toFixed(1)}%</span>
              </div>
            )}
            <ChevronDown size={14} className={`text-neutral-muted transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
          </button>

          {open && (
            <div className="px-4 pb-3 space-y-3">
              {/* 구성 요소 */}
              <div className="space-y-1.5">
                <div className="text-[0.6875rem] font-semibold text-neutral-sub">구성 요소</div>
                {typeof confidenceBreakdown.llm_weighted === 'number' && (
                  <ConfidenceBar
                    label={`LLM 판단 (×${confidenceBreakdown.llm_weighted && confidenceBreakdown.llm_raw ? (confidenceBreakdown.llm_weighted / confidenceBreakdown.llm_raw).toFixed(1) : '0.6'})`}
                    value={confidenceBreakdown.llm_weighted}
                  />
                )}
                {typeof confidenceBreakdown.rag_weighted === 'number' && (
                  <ConfidenceBar
                    label={`RAG 검색 (×${confidenceBreakdown.rag_weighted && confidenceBreakdown.rag_score ? (confidenceBreakdown.rag_weighted / confidenceBreakdown.rag_score).toFixed(2) : '0.25'})`}
                    value={confidenceBreakdown.rag_weighted}
                  />
                )}
                {typeof confidenceBreakdown.coverage_weighted === 'number' && (
                  <ConfidenceBar
                    label={`규정 커버리지 (×${confidenceBreakdown.coverage_weighted && confidenceBreakdown.coverage_score ? (confidenceBreakdown.coverage_weighted / confidenceBreakdown.coverage_score).toFixed(2) : '0.15'})`}
                    value={confidenceBreakdown.coverage_weighted}
                  />
                )}
                {penalty !== 0 && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="w-[7.5rem] text-neutral-sub">감점</span>
                    <div className="flex-1" />
                    <span className="w-10 text-right font-medium text-red-500">{penalty > 0 ? `-${penalty.toFixed(2)}` : penalty.toFixed(2)}</span>
                  </div>
                )}
              </div>

              {/* 경고 */}
              {hasWarnings && (
                <div className="space-y-1">
                  <div className="text-[0.6875rem] font-semibold text-neutral-sub flex items-center gap-1">
                    <AlertTriangle size={12} className="text-yellow-500" />
                    경고
                  </div>
                  <ul className="space-y-0.5">
                    {warnings.map((w, i) => (
                      <li key={i} className="text-[0.6875rem] text-yellow-700 bg-yellow-50 rounded px-2 py-1">
                        {w}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
