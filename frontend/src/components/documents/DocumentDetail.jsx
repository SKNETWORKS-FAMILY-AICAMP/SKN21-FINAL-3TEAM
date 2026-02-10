import Badge from '../common/Badge';

export default function DocumentDetail({ doc }) {
  if (!doc) return <div className="card p-10 text-center text-neutral-muted text-sm">문서를 선택하세요</div>;

  return (
    <div className="bg-surface-card rounded-md border border-neutral-border p-5">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-base font-bold">{doc.name}</h3>
        <Badge variant={doc.status === '적용중' ? 'status-active' : 'status-revising'}>{doc.status}</Badge>
      </div>
      <div className="mb-4">
        <div className="text-[13px] font-bold text-neutral-main mb-2 flex items-center gap-1.5">📋 기본 정보</div>
        <div className="text-[13px] text-neutral-sub leading-[1.7]">분류: {doc.category} · 버전: {doc.version} · 수정일: {doc.date}<br/>범위: 🏢 회사 문서 · 파싱 상태: ✅ 완료</div>
      </div>
      {doc.riskLevel && (
        <div className="mb-4">
          <div className="text-[13px] font-bold text-neutral-main mb-2 flex items-center gap-1.5">🤖 AI 분석 결과</div>
          <Badge variant={`risk-${doc.riskLevel}`} className="mb-2">리스크: {doc.riskLevel === 'low' ? '낮음' : doc.riskLevel === 'medium' ? '중간' : '높음'}</Badge>
          {doc.analysis && <div className="text-[13px] text-neutral-sub leading-[1.7]">{doc.analysis}</div>}
        </div>
      )}
      <div className="flex gap-2 mt-4">
        <button className="btn-primary">📄 원문 보기</button>
        <button className="btn-outline">📥 다운로드</button>
      </div>
    </div>
  );
}
