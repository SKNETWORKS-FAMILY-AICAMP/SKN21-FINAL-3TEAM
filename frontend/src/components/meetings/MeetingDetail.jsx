import { useRef, useCallback } from 'react';
import Badge from '../common/Badge';
import ActionItemPanel from './ActionItemPanel';

export default function MeetingDetail({ meeting }) {
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

  if (!meeting) return <div className="card p-10 text-center text-neutral-muted text-sm">회의를 선택하세요</div>;

  return (
    <div className="bg-surface-card rounded-md border border-neutral-border p-5 space-y-4" ref={printRef}>
      <div className="flex justify-between items-center">
        <h3 className="text-base font-bold">{meeting.title}</h3>
        <Badge variant={meeting.analyzed ? 'status-completed' : 'status-in-progress'}>{meeting.analyzed ? '분석완료' : '분석중'}</Badge>
      </div>
      <div>
        <div className="text-[0.8125rem] font-bold mb-2 flex items-center gap-1.5">ℹ️ 회의 정보</div>
        <div className="text-[0.8125rem] text-neutral-sub leading-[1.7]">{meeting.info}</div>
      </div>
      {meeting.riskLevel && (
        <div>
          <div className="text-[0.8125rem] font-bold mb-2 flex items-center gap-1.5">🤖 AI 분석 결과</div>
          <Badge variant={`risk-${meeting.riskLevel}`}>리스크: {meeting.riskLevel === 'medium' ? '중간' : meeting.riskLevel === 'high' ? '높음' : '낮음'}</Badge>
        </div>
      )}
      {meeting.decisions?.length > 0 && (
        <div>
          <div className="text-[0.8125rem] font-bold mb-2 flex items-center gap-1.5">📌 결정사항 ({meeting.decisions.length}건)</div>
          {meeting.decisions.map((d, i) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-sm hover:bg-surface-hover">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-500 flex-shrink-0" />
              <div><div className="text-[0.8125rem] font-semibold">{d.title}</div><div className="text-xs text-neutral-sub mt-0.5">담당: {d.assignee}</div></div>
            </div>
          ))}
        </div>
      )}
      {meeting.actionItems?.length > 0 && (
        <div>
          <div className="text-[0.8125rem] font-bold mb-2 flex items-center gap-1.5">✅ Action Items ({meeting.actionItems.length}건)</div>
          <ActionItemPanel items={meeting.actionItems} />
        </div>
      )}
      <div className="flex gap-2 pt-2 no-print">
        <button className="btn-primary">📄 원문 보기</button>
        <button className="btn-outline">📥 보고서 생성</button>
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
