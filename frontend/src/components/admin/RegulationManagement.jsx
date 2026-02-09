import Badge from '../common/Badge';

export default function RegulationManagement({ regulations = [] }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><span>📄</span>규정 관리</div>
        <button className="btn-primary">+ 규정 추가</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead><tr>
            {['규정명', '조항 수', '상태', '관리'].map((h) => <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-neutral-sub border-b-2 border-neutral-divider bg-surface-hover">{h}</th>)}
          </tr></thead>
          <tbody>
            {regulations.map((r, i) => (
              <tr key={i} className="hover:bg-surface-hover">
                <td className="px-4 py-3 text-[13px] font-semibold border-b border-neutral-divider">{r.name}</td>
                <td className="px-4 py-3 text-[13px] border-b border-neutral-divider">{r.count}개</td>
                <td className="px-4 py-3 border-b border-neutral-divider"><Badge variant={r.status === '적용중' ? 'status-active' : 'status-revising'}>{r.status}</Badge></td>
                <td className="px-4 py-3 border-b border-neutral-divider">
                  <div className="flex gap-1.5">
                    <button className="btn-outline py-1 px-2.5 text-[11px]">수정</button>
                    <button className="btn-danger py-1 px-2.5 text-[11px]">삭제</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
