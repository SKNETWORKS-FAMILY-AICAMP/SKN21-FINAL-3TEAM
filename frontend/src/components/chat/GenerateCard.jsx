import { AlertTriangle, CheckCircle, Info } from 'lucide-react';
import Badge from '../common/Badge';

export default function GenerateCard({ title, templateType, fields = [], actionItems = [], downloadUrl, onDownload, modelName, regulationCheck, warnings }) {
  const typeLabels = { meeting_minutes: '회의록', report: '보고서', jd: '채용 공고', proposal: '제안서' };

  return (
    <div className="bg-surface-card rounded-lg border border-neutral-border overflow-hidden">
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

        {/* 규정 검증 결과 */}
        {regulationCheck?.notes?.length > 0 && (
          <div className="mb-4 space-y-1.5">
            <div className="text-[0.8125rem] font-semibold text-neutral-sub mb-1 flex items-center gap-1">
              <AlertTriangle size={14} className="text-yellow-500" />
              규정 검증 결과
            </div>
            {regulationCheck.notes.map((n, i) => (
              <div key={i} className={`flex items-start gap-1.5 p-2.5 rounded-lg border text-xs ${
                n.result === 'no' ? 'bg-red-50 border-red-200 text-red-700' :
                n.result === 'conditional' ? 'bg-yellow-50 border-yellow-200 text-yellow-700' :
                'bg-green-50 border-green-200 text-green-700'
              }`}>
                {n.result === 'no' ? <AlertTriangle size={13} className="shrink-0 mt-0.5" /> :
                 n.result === 'conditional' ? <Info size={13} className="shrink-0 mt-0.5" /> :
                 <CheckCircle size={13} className="shrink-0 mt-0.5" />}
                <div>
                  <span className="font-semibold">{n.result === 'no' ? '[위반]' : n.result === 'conditional' ? '[조건부]' : '[부합]'} {n.topic}</span>
                  <p className="text-[0.6875rem] mt-0.5">{n.reason}</p>
                  {n.regulation && <p className="text-[0.625rem] mt-0.5 italic opacity-75">근거: {n.regulation}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
        {Array.isArray(warnings) && warnings.length > 0 && !regulationCheck?.notes?.length && (
          <div className="mb-4 space-y-1">
            {warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-1.5 text-xs text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-lg px-3 py-2">
                <AlertTriangle size={13} className="text-yellow-500 mt-0.5 shrink-0" />
                <span>{w}</span>
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
