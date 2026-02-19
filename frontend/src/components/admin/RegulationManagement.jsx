import { useState } from 'react';
import Badge from '../common/Badge';

const STATUSES = ['적용중', '개정중', '폐지'];

export default function RegulationManagement({ regulations = [] }) {
  const [data, setData] = useState(regulations);
  const [showModal, setShowModal] = useState(false);
  const [editIndex, setEditIndex] = useState(null);
  const [deleteIndex, setDeleteIndex] = useState(null);
  const [form, setForm] = useState({ name: '', count: 0, status: '적용중' });

  const openAdd = () => {
    setEditIndex(null);
    setForm({ name: '', count: 0, status: '적용중' });
    setShowModal(true);
  };

  const openEdit = (i) => {
    setEditIndex(i);
    setForm({ name: data[i].name, count: data[i].count, status: data[i].status });
    setShowModal(true);
  };

  const handleSave = () => {
    if (!form.name.trim()) return;
    if (editIndex !== null) {
      const n = [...data];
      n[editIndex] = { ...form, count: Number(form.count) };
      setData(n);
    } else {
      setData([...data, { ...form, count: Number(form.count) }]);
    }
    setShowModal(false);
  };

  const handleDelete = () => {
    setData(data.filter((_, i) => i !== deleteIndex));
    setDeleteIndex(null);
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">규정 관리</div>
        <button className="btn-primary" onClick={openAdd}>+ 규정 추가</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead><tr>
            {['규정명', '조항 수', '상태', '관리'].map((h) => <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-neutral-sub border-b-2 border-neutral-divider bg-surface-hover">{h}</th>)}
          </tr></thead>
          <tbody>
            {data.map((r, i) => (
              <tr key={i} className="hover:bg-surface-hover">
                <td className="px-4 py-3 text-[0.8125rem] font-semibold border-b border-neutral-divider">{r.name}</td>
                <td className="px-4 py-3 text-[0.8125rem] border-b border-neutral-divider">{r.count}개</td>
                <td className="px-4 py-3 border-b border-neutral-divider"><Badge variant={r.status === '적용중' ? 'status-active' : r.status === '개정중' ? 'status-revising' : 'status-completed'}>{r.status}</Badge></td>
                <td className="px-4 py-3 border-b border-neutral-divider">
                  <div className="flex gap-1.5">
                    <button className="btn-outline py-1 px-2.5 text-[0.6875rem]" onClick={() => openEdit(i)}>수정</button>
                    <button className="py-1 px-2.5 text-[0.6875rem] rounded-sm border border-error text-error bg-error-bg hover:bg-error hover:text-white transition" onClick={() => setDeleteIndex(i)}>삭제</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setShowModal(false)}>
          <div className="bg-surface-card rounded-lg border border-neutral-border shadow-lg w-[400px] p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-bold mb-4">{editIndex !== null ? '규정 수정' : '규정 추가'}</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">규정명</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="규정명을 입력하세요"
                  className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">조항 수</label>
                <input
                  type="number"
                  min="0"
                  value={form.count}
                  onChange={(e) => setForm({ ...form, count: e.target.value })}
                  className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">상태</label>
                <div className="flex gap-2">
                  {STATUSES.map((s) => (
                    <button
                      key={s}
                      onClick={() => setForm({ ...form, status: s })}
                      className={`flex-1 py-2 rounded-sm text-sm font-medium border transition ${form.status === s ? 'bg-primary-50 border-primary-500 text-primary-700' : 'border-neutral-border text-neutral-sub hover:bg-surface-hover'}`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button className="btn-outline" onClick={() => setShowModal(false)}>취소</button>
              <button className="btn-primary" onClick={handleSave}>저장</button>
            </div>
          </div>
        </div>
      )}

      {deleteIndex !== null && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setDeleteIndex(null)}>
          <div className="bg-surface-card rounded-lg border border-neutral-border shadow-lg w-[360px] p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-bold mb-2">규정 삭제</h3>
            <p className="text-sm text-neutral-sub mb-5">
              <strong className="text-neutral-main">{data[deleteIndex]?.name}</strong>을(를) 삭제하시겠습니까?<br />이 작업은 되돌릴 수 없습니다.
            </p>
            <div className="flex justify-end gap-2">
              <button className="btn-outline" onClick={() => setDeleteIndex(null)}>취소</button>
              <button className="py-2 px-4 rounded-sm text-sm font-medium bg-error text-white hover:opacity-90 transition" onClick={handleDelete}>삭제</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
