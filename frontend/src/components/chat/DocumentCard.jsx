export default function DocumentCard({ title, summary, riskLevel }) {
  const riskColors = { high: 'bg-error-bg text-error', medium: 'bg-warning-bg text-warning', low: 'bg-success-bg text-success' };
  const riskLabels = { high: '높음', medium: '중간', low: '낮음' };

  return (
    <div className="bg-surface-card rounded-[14px] border border-neutral-border overflow-hidden">
      <div className="px-4 py-3 border-b border-neutral-divider flex items-center gap-2 font-bold text-sm text-primary-700">
{title || '문서 분석 결과'}
      </div>
      <div className="p-4">
        {riskLevel && (
          <span className={`badge mb-3 inline-block ${riskColors[riskLevel]}`}>리스크: {riskLabels[riskLevel]}</span>
        )}
        {summary && <p className="text-[0.8125rem] text-neutral-main leading-[1.7]">{summary}</p>}
      </div>
    </div>
  );
}
