import Badge from '../common/Badge';

export default function GenerateCard({ title, templateType, fields = [], downloadUrl, onDownload }) {
  const typeLabels = { meeting_minutes: '회의록', report: '보고서', jd: '채용 공고', proposal: '제안서' };

  return (
    <div className="bg-surface-card rounded-[14px] border border-neutral-border overflow-hidden">
      <div className="px-4 py-3 border-b border-neutral-divider flex items-center justify-between">
        <div className="flex items-center gap-2 font-bold text-sm text-primary-700">
{title || '문서 생성 완료'}
        </div>
        {templateType && <Badge variant="document">{typeLabels[templateType] || templateType}</Badge>}
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
