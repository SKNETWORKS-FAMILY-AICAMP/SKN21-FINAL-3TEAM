import { useRef, useCallback } from 'react';
import Badge from '../common/Badge';
import { TEMPLATE_LABELS } from '../../utils/constants';

export default function DocumentPreview({ data, onDownload, loading }) {
  const printRef = useRef(null);

  const handlePrint = useCallback(() => {
    if (!printRef.current) return;
    printRef.current.classList.add('print-area');
    window.print();
    const cleanup = () => {
      printRef.current?.classList.remove('print-area');
      window.removeEventListener('afterprint', cleanup);
    };
    window.addEventListener('afterprint', cleanup);
  }, []);

  if (!data) return null;

  return (
    <div className="card" ref={printRef}>
      <div className="card-header no-print">
        <div className="card-title">
생성된 문서
          {data.templateType && (
            <Badge variant="document">{TEMPLATE_LABELS[data.templateType] || data.templateType}</Badge>
          )}
        </div>
        <div className="flex gap-2">
          <button onClick={handlePrint} className="btn-outline text-xs">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
              <polyline points="6 9 6 2 18 2 18 9" />
              <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
              <rect x="6" y="14" width="12" height="8" />
            </svg>
            인쇄
          </button>
          <button onClick={() => onDownload?.('docx')} disabled={loading} className="btn-primary text-xs disabled:opacity-50">
            DOCX 다운로드
          </button>
          <button onClick={() => onDownload?.('pdf')} disabled={loading} className="btn-outline text-xs disabled:opacity-50">
            PDF 다운로드
          </button>
        </div>
      </div>
      <div ref={printRef} className="card-body">
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
