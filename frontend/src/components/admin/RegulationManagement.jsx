import { useState } from 'react';
import Badge from '../common/Badge';
import { createRegulation, updateRegulation, deleteRegulation } from '../../api/admin';

export default function RegulationManagement({ regulations = [], onRefresh }) {
  const [showModal, setShowModal] = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [form, setForm] = useState({ title: '', category: '', article_number: '', content: '', version: '1.0' });
  const [saving, setSaving] = useState(false);

  const openAdd = () => {
    setEditTarget(null);
    setForm({ title: '', category: '', article_number: '', content: '', version: '1.0' });
    setShowModal(true);
  };

  const openEdit = (reg) => {
    setEditTarget(reg);
    setForm({
      title: reg.title,
      category: reg.category,
      article_number: reg.article_number,
      content: reg.content || '',
      version: reg.version || '1.0',
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!form.title.trim() || !form.category.trim() || !form.article_number.trim()) return;
    setSaving(true);
    try {
      if (editTarget) {
        await updateRegulation(editTarget.id, form);
      } else {
        await createRegulation(form);
      }
      setShowModal(false);
      onRefresh?.();
    } catch (e) {
      alert('저장 실패: ' + (e.response?.data?.detail || e.message));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteRegulation(deleteTarget.id);
      setDeleteTarget(null);
      onRefresh?.();
    } catch (e) {
      alert('삭제 실패: ' + (e.response?.data?.detail || e.message));
    }
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
            {['규정명', '카테고리', '조항번호', '버전', '관리'].map((h) => (
              <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-neutral-sub border-b-2 border-neutral-divider bg-surface-hover">{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {regulations.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-neutral-sub">등록된 규정이 없습니다</td></tr>
            ) : regulations.map((r) => (
              <tr key={r.id} className="hover:bg-surface-hover">
                <td className="px-4 py-3 text-[0.8125rem] font-semibold border-b border-neutral-divider">{r.title}</td>
                <td className="px-4 py-3 text-[0.8125rem] border-b border-neutral-divider">
                  <Badge variant="status-active">{r.category}</Badge>
                </td>
                <td className="px-4 py-3 text-[0.8125rem] border-b border-neutral-divider">{r.article_number}</td>
                <td className="px-4 py-3 text-[0.8125rem] border-b border-neutral-divider">v{r.version}</td>
                <td className="px-4 py-3 border-b border-neutral-divider">
                  <div className="flex gap-1.5">
                    <button className="btn-outline py-1 px-2.5 text-[0.6875rem]" onClick={() => openEdit(r)}>수정</button>
                    <button className="py-1 px-2.5 text-[0.6875rem] rounded-sm border border-error text-error bg-error-bg hover:bg-error hover:text-white transition" onClick={() => setDeleteTarget(r)}>삭제</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setShowModal(false)}>
          <div className="bg-surface-card rounded-lg border border-neutral-border shadow-lg w-[480px] p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-bold mb-4">{editTarget ? '규정 수정' : '규정 추가'}</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">규정명</label>
                <input type="text" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="규정명을 입력하세요" className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-neutral-sub block mb-1">카테고리</label>
                  <input type="text" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="예: 정보보안, 인사" className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500" />
                </div>
                <div>
                  <label className="text-xs font-semibold text-neutral-sub block mb-1">조항번호</label>
                  <input type="text" value={form.article_number} onChange={(e) => setForm({ ...form, article_number: e.target.value })} placeholder="예: 제10조" className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500" />
                </div>
              </div>
              <div>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">내용</label>
                <textarea value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} placeholder="규정 내용을 입력하세요" rows={4} className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 resize-none" />
              </div>
              <div>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">버전</label>
                <input type="text" value={form.version} onChange={(e) => setForm({ ...form, version: e.target.value })} className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button className="btn-outline" onClick={() => setShowModal(false)}>취소</button>
              <button className="btn-primary" onClick={handleSave} disabled={saving}>{saving ? '저장 중...' : '저장'}</button>
            </div>
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setDeleteTarget(null)}>
          <div className="bg-surface-card rounded-lg border border-neutral-border shadow-lg w-[360px] p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-bold mb-2">규정 삭제</h3>
            <p className="text-sm text-neutral-sub mb-5">
              <strong className="text-neutral-main">{deleteTarget.title}</strong>을(를) 삭제하시겠습니까?<br />이 작업은 되돌릴 수 없습니다.
            </p>
            <div className="flex justify-end gap-2">
              <button className="btn-outline" onClick={() => setDeleteTarget(null)}>취소</button>
              <button className="py-2 px-4 rounded-sm text-sm font-medium bg-error text-white hover:opacity-90 transition" onClick={handleDelete}>삭제</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
