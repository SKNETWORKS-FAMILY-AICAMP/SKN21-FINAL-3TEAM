import { useState, useEffect } from 'react';
import { Lightbulb, ChevronDown, AlertTriangle, ShieldCheck, FileText, X } from 'lucide-react';
import MarkdownText from './MarkdownText';

const borderColors = { deny: 'border-l-error', conditional: 'border-l-warning', ref: 'border-l-primary-300' };

const SCALE_SEGMENTS = [
  { pct: 50, bg: '#f87171', label: '근거 부족', range: '0~49%', desc: 'RAG 검색·규정 커버리지가 낮아 보정 점수가 크게 하락한 상태' },
  { pct: 20, bg: '#fbbf24', label: '적용 어려움', range: '50~69%', desc: '관련 규정은 검색되었으나 가중합 점수가 높지 않은 상태' },
  { pct: 20, bg: '#4ade80', label: '해석 필요', range: '70~89%', desc: 'LLM·RAG·커버리지 모두 양호하나 일부 감점 요소 존재' },
  { pct: 10, bg: '#16a34a', label: '높은 신뢰', range: '90~100%', desc: '모든 구성 요소가 높고 감점이 거의 없는 최고 신뢰 상태' },
];

function ConfidenceScaleBar() {
  const [hover, setHover] = useState(null);
  const active = hover !== null ? SCALE_SEGMENTS[hover] : null;
  return (
    <div className="pt-4 mx-auto" style={{ maxWidth: '85%' }}>
      {/* 막대 */}
      <div className="flex w-full h-3 rounded-full overflow-hidden">
        {SCALE_SEGMENTS.map((seg, i) => (
          <div
            key={seg.label}
            className="cursor-pointer transition-all duration-150"
            style={{
              width: `${seg.pct}%`,
              backgroundColor: seg.bg,
              opacity: hover !== null && hover !== i ? 0.35 : 1,
              transform: hover === i ? 'scaleY(1.8)' : 'scaleY(1)',
            }}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          />
        ))}
      </div>

      {/* 눈금 */}
      <div className="relative w-full mt-1" style={{ height: '0.875rem' }}>
        <span className="absolute text-[0.625rem] text-neutral-sub" style={{ left: 0 }}>0%</span>
        <span className="absolute text-[0.625rem] text-neutral-sub" style={{ left: '50%', transform: 'translateX(-50%)' }}>50%</span>
        <span className="absolute text-[0.625rem] text-neutral-sub" style={{ left: '70%', transform: 'translateX(-50%)' }}>70%</span>
        <span className="absolute text-[0.625rem] text-neutral-sub" style={{ left: '90%', transform: 'translateX(-50%)' }}>90%</span>
        <span className="absolute text-[0.625rem] text-neutral-sub" style={{ right: 0 }}>100%</span>
      </div>

      {/* 호버 시 구간 설명 (고정 높이) */}
      <div className="mt-1.5 h-9 flex items-center gap-2 px-2 rounded-md text-[0.6875rem] transition-colors duration-150" style={{ backgroundColor: active ? active.bg + '18' : 'transparent' }}>
        {active ? (
          <>
            <div className="w-2.5 h-2.5 rounded-full flex-shrink-0 mt-0.5" style={{ backgroundColor: active.bg }} />
            <div>
              <span className="font-semibold text-neutral-main">{active.label}</span>
              <span className="text-neutral-sub ml-1">({active.range})</span>
              <span className="text-neutral-sub ml-1">— {active.desc}</span>
            </div>
          </>
        ) : (
          <div className="w-full text-[0.625rem] text-neutral-400 text-center">각 구간에 마우스를 올리면 설명이 표시됩니다</div>
        )}
      </div>
    </div>
  );
}

function getConfidenceColor(value) {
  if (value >= 0.9) return { bar: 'bg-green-600', text: 'text-green-700' };
  if (value >= 0.7) return { bar: 'bg-green-500', text: 'text-green-600' };
  if (value >= 0.5) return { bar: 'bg-yellow-500', text: 'text-yellow-600' };
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

function RegulationPopup({ reg, onClose }) {
  const [fullContent, setFullContent] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  // 규정명에서 조항 번호 추출 (예: "정보보안규정 제25조" → "제25조")
  useEffect(() => {
    const articleMatch = reg.name?.match(/제\d+조/);
    if (articleMatch) {
      setLoading(true);
      import('../../api/regulations').then(({ getRegulationByArticle }) => {
        getRegulationByArticle(articleMatch[0])
          .then((res) => setFullContent(res.data?.content || res.content || null))
          .catch(() => setFullContent(null))
          .finally(() => setLoading(false));
      });
    }
  }, [reg.name]);

  const displayContent = fullContent || reg.verdict;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] flex flex-col border border-white/40 dark:border-white/10" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between px-5 py-4 border-b border-neutral-divider">
          <div className="flex items-center gap-2 pr-4">
            <FileText size={16} className="text-primary-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm font-bold text-neutral-main leading-snug">{reg.name}</div>
          </div>
          <button onClick={onClose} className="w-7 h-7 rounded-md flex items-center justify-center text-neutral-muted hover:bg-surface-hover transition flex-shrink-0">
            <X size={15} />
          </button>
        </div>
        <div className="overflow-y-auto px-5 py-4 flex-1">
          {loading ? (
            <p className="text-sm text-neutral-muted text-center py-8">규정 원문을 불러오는 중...</p>
          ) : displayContent ? (
            <p className="text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">{displayContent}</p>
          ) : (
            <p className="text-sm text-neutral-muted text-center py-8">내용이 없습니다.</p>
          )}
        </div>
        <div className="px-5 py-3 border-t border-neutral-divider flex justify-end">
          <button onClick={onClose} className="btn-outline text-xs px-4 py-1.5">닫기</button>
        </div>
      </div>
    </div>
  );
}

export default function JudgmentCard({ summary, regulations = [], alternatives = [], confidenceBreakdown, warnings, confidence }) {
  const [open, setOpen] = useState(false);
  const [selectedReg, setSelectedReg] = useState(null);

  const hasBreakdown = confidenceBreakdown && typeof confidenceBreakdown === 'object';
  const finalScore = hasBreakdown ? confidenceBreakdown.final : confidence;
  const hasScore = typeof finalScore === 'number';
  const scoreColor = hasScore ? getConfidenceColor(finalScore) : null;

  const penalty = hasBreakdown
    ? (confidenceBreakdown.conflict_penalty || 0) + (confidenceBreakdown.hallucination_penalty || 0) + (confidenceBreakdown.article_penalty || 0)
    : 0;

  const hasWarnings = Array.isArray(warnings) && warnings.length > 0;

  return (
    <>
      <div className="bg-surface-card rounded-lg border border-neutral-border overflow-hidden">
        <div className="p-4">
          {regulations.length > 0 && (
            <div className="mb-3.5">
              <div className="text-xs font-semibold text-neutral-sub mb-2">관련 규정 ({regulations.length}건)</div>
              {regulations.map((r, i) => (
                <button key={i} onClick={() => setSelectedReg(r)} className={`w-full text-left px-3 py-2 bg-surface-hover rounded-lg mb-1.5 border-l-[3px] hover:bg-primary-50 hover:border-l-primary-500 transition cursor-pointer ${borderColors[r.type] || 'border-l-primary-300'}`}>
                  <div className="text-xs font-semibold text-neutral-main">{r.name}</div>
                  <div className="text-[0.6875rem] text-neutral-sub mt-0.5 line-clamp-2">{r.verdict}</div>
                  <div className="text-[0.625rem] text-primary-500 mt-1 font-medium">전체 보기 →</div>
                </button>
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
                {/* LLM Raw vs 보정 점수 비교 */}
                {typeof confidenceBreakdown.llm_raw === 'number' && hasScore && (
                  <div className="flex items-center gap-3 text-[0.6875rem] text-neutral-sub bg-neutral-50 rounded-lg px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      <span>LLM 원본 점수:</span>
                      <span className="font-bold text-neutral-main">{(confidenceBreakdown.llm_raw * 100).toFixed(1)}%</span>
                    </div>
                    <span className="text-neutral-300">→</span>
                    <div className="flex items-center gap-1.5">
                      <span>보정 후:</span>
                      <span className={`font-bold ${scoreColor.text}`}>{(finalScore * 100).toFixed(1)}%</span>
                    </div>
                    {confidenceBreakdown.llm_raw !== finalScore && (
                      <span className={`text-[0.625rem] ${finalScore < confidenceBreakdown.llm_raw ? 'text-red-500' : 'text-green-600'}`}>
                        ({finalScore < confidenceBreakdown.llm_raw ? '' : '+'}{((finalScore - confidenceBreakdown.llm_raw) * 100).toFixed(1)}%p)
                      </span>
                    )}
                  </div>
                )}

                {/* 구성 요소 */}
                <div className="space-y-1.5">
                  <div className="text-[0.6875rem] font-semibold text-neutral-sub">구성 요소</div>
                  {typeof confidenceBreakdown.llm_weighted === 'number' && (
                    <ConfidenceBar
                      label="LLM 판단 (×0.6)"
                      value={confidenceBreakdown.llm_weighted}
                    />
                  )}
                  {typeof confidenceBreakdown.rag_weighted === 'number' && (
                    <ConfidenceBar
                      label="RAG 검색 (×0.25)"
                      value={confidenceBreakdown.rag_weighted}
                    />
                  )}
                  {typeof confidenceBreakdown.coverage_weighted === 'number' && (
                    <ConfidenceBar
                      label="규정 커버리지 (×0.15)"
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

                {/* 신뢰도 기준 바 (호버 툴팁) */}
                <div className="mt-5">
                  <ConfidenceScaleBar />
                </div>
              </div>
            )}
          </div>
        )}

        {/* 줄글 (summary) — 규정 + 신뢰도 아래에 표시 */}
        {summary && (
          <div className="border-t border-neutral-divider p-4">
            <div className="text-sm text-neutral-main leading-relaxed"><MarkdownText>{summary}</MarkdownText></div>
          </div>
        )}
      </div>

      {selectedReg && <RegulationPopup reg={selectedReg} onClose={() => setSelectedReg(null)} />}
    </>
  );
}
