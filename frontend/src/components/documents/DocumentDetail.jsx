import { useRef, useCallback } from 'react';
import Badge from '../common/Badge';
import KeywordHighlight from '../common/KeywordHighlight';

export default function DocumentDetail({ doc, searchQuery = '' }) {
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

  if (!doc) return <div className="card p-10 text-center text-neutral-muted text-sm">문서를 선택하세요</div>;

  return (
    <div className="bg-surface-card rounded-md border border-neutral-border p-5" ref={printRef}>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-base font-bold"><KeywordHighlight text={doc.name} keyword={searchQuery} /></h3>
        <Badge variant={doc.status === '적용중' ? 'status-active' : 'status-revising'}>{doc.status}</Badge>
      </div>
      <div className="mb-4">
        <div className="text-[0.8125rem] font-bold text-neutral-main mb-2 flex items-center gap-1.5">📋 기본 정보</div>
        <div className="text-[0.8125rem] text-neutral-sub leading-[1.7]">분류: {doc.category} · 버전: {doc.version} · 수정일: {doc.date}<br/>범위: 🏢 회사 문서 · 파싱 상태: ✅ 완료</div>
      </div>
      {doc.riskLevel && (
        <div className="mb-4">
          <div className="text-[0.8125rem] font-bold text-neutral-main mb-2 flex items-center gap-1.5">🤖 AI 분석 결과</div>
          <Badge variant={`risk-${doc.riskLevel}`} className="mb-2">리스크: {doc.riskLevel === 'low' ? '낮음' : doc.riskLevel === 'medium' ? '중간' : '높음'}</Badge>
          {doc.analysis && <div className="text-[0.8125rem] text-neutral-sub leading-[1.7]"><KeywordHighlight text={doc.analysis} keyword={searchQuery} /></div>}
        </div>
      )}
      <div className="flex gap-2 mt-4 no-print">
        <button className="btn-primary">📄 원문 보기</button>
        <button className="btn-outline">📥 다운로드</button>
        <button onClick={handlePrint} className="btn-outline">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
            <polyline points="6 9 6 2 18 2 18 9" />
            <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
            <rect x="6" y="14" width="12" height="8" />
          </svg>
          인쇄
        </button>
      </div>
    </div>
  );
}
