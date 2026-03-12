import Badge from '../common/Badge';

export default function GenerateCard({ title, templateType, fields = [], actionItems = [], downloadUrl, onDownload, modelName }) {
  const typeLabels = { meeting_minutes: '회의록', report: '보고서', jd: '채용 공고', proposal: '제안서' };

  return (
    <div className="bg-surface-card rounded-[14px] border border-neutral-border overflow-hidden">
      <div className="px-4 py-3 border-b border-neutral-divider flex items-center justify-between">
        <div className="flex items-center gap-2 font-bold text-sm text-primary-700">
{title || '문서 생성 완료'}
        </div>
        <div className="flex items-center gap-2">
          {templateType && <Badge variant="document">{typeLabels[templateType] || templateType}</Badge>}
          {modelName && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[0.6875rem] font-medium bg-violet-100 text-violet-700">
              {modelName.includes('LoRA') ? '🔧 ' : '🤖 '}{modelName}
            </span>
          )}
        </div>
      </div>
      <div className="p-4">
        {fields.length > 0 && (
          <div className="space-y-2 mb-4">
            {fields.map((f, i) => (
              <div key={i} className="text-[0.8125rem]">
                <span className="font-semibold text-neutral-sub">{f.label}: </span>
                <span className="text-neutral-main">{f.value}</span>
              </div>
            ))}
          </div>
        )}

        {/* Action Items (회의록만) */}
        {actionItems.length > 0 && (
          <div className="mb-4">
            <div className="text-[0.8125rem] font-semibold text-neutral-sub mb-2">Action Items</div>
            <div className="space-y-1.5">
              {actionItems.map((item, i) => (
                <div key={i} className="flex items-start gap-2 text-[0.8125rem]">
                  <span className="text-neutral-400 shrink-0">{i + 1}.</span>
                  <div>
                    <span className="text-neutral-main">{item.task}</span>
                    {(item.assignee || item.due_date) && (
                      <span className="text-neutral-sub ml-1.5 text-xs">
                        {item.assignee && `(${item.assignee})`}
                        {item.due_date && ` ~${item.due_date}`}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={onDownload}
            className="btn-primary text-xs"
          >
            다운로드
          </button>
          {downloadUrl && (
            <a href={downloadUrl} target="_blank" rel="noreferrer" className="btn-outline text-xs">
              미리보기
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
