import { useRef, useCallback } from 'react';

export default function MeetingPreview({ data, onDownload, loading }) {
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
        <div className="card-title"><span>📋</span>생성된 회의록</div>
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
      <div className="card-body">
        {/* 회의 정보 */}
        <div className="flex flex-wrap gap-4 text-xs text-neutral-sub mb-4 pb-4 border-b border-neutral-divider">
          {data.title && <span className="font-semibold text-neutral-main">{data.title}</span>}
          {data.date && <span>📅 {data.date}</span>}
          {data.attendees?.length > 0 && <span>👥 {data.attendees.join(', ')}</span>}
        </div>

        {/* 요약 */}
        {data.summary && (
          <div className="mb-4">
            <h4 className="text-[0.8125rem] font-bold text-neutral-main mb-2">요약</h4>
            <p className="text-sm text-neutral-main leading-relaxed whitespace-pre-wrap bg-surface-hover rounded-sm p-3">
              {data.summary}
            </p>
          </div>
        )}

        {/* 결정사항 */}
        {data.decisions?.length > 0 && (
          <div className="mb-4">
            <h4 className="text-[0.8125rem] font-bold text-neutral-main mb-2">결정사항 ({data.decisions.length}건)</h4>
            <div className="space-y-1.5">
              {data.decisions.map((d, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-neutral-main">
                  <span className="text-success flex-shrink-0">✓</span>
                  <span className="leading-relaxed">{d}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Items */}
        {data.actionItems?.length > 0 && (
          <div>
            <h4 className="text-[0.8125rem] font-bold text-neutral-main mb-2">Action Items ({data.actionItems.length}건)</h4>
            <div className="space-y-2">
              {data.actionItems.map((item, i) => (
                <div key={i} className="flex items-start gap-2 px-3 py-2.5 bg-surface-hover rounded-sm text-sm">
                  <span className="flex-shrink-0">☐</span>
                  <div className="flex-1">
                    <span className="text-neutral-main">{item.task}</span>
                    <div className="flex gap-3 mt-1 text-xs text-neutral-muted">
                      {item.assignee && <span>👤 {item.assignee}</span>}
                      {item.deadline && <span>📅 {item.deadline}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
