import Badge from '../common/Badge';
import { TEMPLATE_LABELS } from '../../utils/constants';

export default function DocumentPreview({ data, onDownload, loading }) {
  if (!data) return null;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <span>📄</span>생성된 문서
          {data.templateType && (
            <Badge variant="document">{TEMPLATE_LABELS[data.templateType] || data.templateType}</Badge>
          )}
        </div>
        <div className="flex gap-2">
          <button onClick={() => onDownload?.('docx')} disabled={loading} className="btn-primary text-xs disabled:opacity-50">
            DOCX 다운로드
          </button>
          <button onClick={() => onDownload?.('pdf')} disabled={loading} className="btn-outline text-xs disabled:opacity-50">
            PDF 다운로드
          </button>
        </div>
      </div>
      <div className="card-body">
        {/* 문서 제목 */}
        {data.title && (
          <h3 className="text-lg font-bold text-neutral-main mb-4 pb-3 border-b border-neutral-divider">
            {data.title}
          </h3>
        )}

        {/* 필드별 내용 */}
        {data.fields?.length > 0 && (
          <div className="space-y-4">
            {data.fields.map((field, i) => (
              <div key={i}>
                <h4 className="text-[0.8125rem] font-bold text-primary-700 mb-1.5">{field.label}</h4>
                <div className="text-sm text-neutral-main leading-relaxed whitespace-pre-wrap bg-surface-hover rounded-sm p-3">
                  {field.value}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 또는 본문 텍스트 */}
        {data.content && !data.fields?.length && (
          <div className="text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">
            {data.content}
          </div>
        )}
      </div>
    </div>
  );
}
