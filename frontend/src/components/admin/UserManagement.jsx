import { useState } from 'react';
import Badge from '../common/Badge';
import { createUser, updateUserPermissions, deleteUser } from '../../api/admin';

export default function UserManagement({ users = [], onRefresh }) {
  const [showModal, setShowModal] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [form, setForm] = useState({ name: '', email: '', password: '', is_admin: false });
  const [saving, setSaving] = useState(false);

  const openAdd = () => {
    setForm({ name: '', email: '', password: '', is_admin: false });
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.email.trim() || !form.password.trim()) return;
    setSaving(true);
    try {
      await createUser(form);
      setShowModal(false);
      onRefresh?.();
    } catch (e) {
      alert('사용자 추가 실패: ' + (e.response?.data?.detail || e.message));
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (user) => {
    try {
      await updateUserPermissions(user.id, {
        is_admin: user.is_admin,
        is_active: !user.is_active,
      });
      onRefresh?.();
    } catch (e) {
      alert('상태 변경 실패: ' + (e.response?.data?.detail || e.message));
    }
  };

  const toggleAdmin = async (user) => {
    try {
      await updateUserPermissions(user.id, {
        is_admin: !user.is_admin,
        is_active: user.is_active,
      });
      onRefresh?.();
    } catch (e) {
      alert('권한 변경 실패: ' + (e.response?.data?.detail || e.message));
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteUser(deleteTarget.id);
      setDeleteTarget(null);
      onRefresh?.();
    } catch (e) {
      alert('삭제 실패: ' + (e.response?.data?.detail || e.message));
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">사용자 관리</div>
        <button className="btn-primary" onClick={openAdd}>+ 사용자 추가</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead><tr>
            {['이름', '이메일', '권한', '상태', '관리'].map((h) => (
              <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-neutral-sub border-b-2 border-neutral-divider bg-surface-hover">{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {users.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-neutral-sub">등록된 사용자가 없습니다</td></tr>
            ) : users.map((u) => (
              <tr key={u.id} className="hover:bg-surface-hover">
                <td className="px-4 py-3 text-[0.8125rem] font-semibold border-b border-neutral-divider">{u.name}</td>
                <td className="px-4 py-3 text-[0.8125rem] border-b border-neutral-divider">{u.email}</td>
                <td className="px-4 py-3 border-b border-neutral-divider">
                  <button onClick={() => toggleAdmin(u)}>
                    <Badge variant={u.is_admin ? 'role-admin' : 'role-user'}>{u.is_admin ? '관리자' : '일반'}</Badge>
                  </button>
                </td>
                <td className="px-4 py-3 border-b border-neutral-divider">
                  <button onClick={() => toggleActive(u)} className={`w-10 h-[22px] rounded-full relative transition ${u.is_active ? 'bg-success' : 'bg-neutral-border'}`}>
                    <span className={`absolute left-[2px] top-[2px] w-[18px] h-[18px] rounded-full bg-white shadow-sm transition-transform ${u.is_active ? 'translate-x-[18px]' : 'translate-x-0'}`} />
                  </button>
                </td>
                <td className="px-4 py-3 border-b border-neutral-divider">
                  <button className="py-1 px-2.5 text-[0.6875rem] rounded-sm border border-error text-error bg-error-bg hover:bg-error hover:text-white transition" onClick={() => setDeleteTarget(u)}>삭제</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setShowModal(false)}>
          <div className="bg-surface-card rounded-lg border border-neutral-border shadow-lg w-[400px] p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-bold mb-4">사용자 추가</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">이름</label>
                <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="이름을 입력하세요" className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500" />
              </div>
              <div>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">이메일</label>
                <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="이메일을 입력하세요" className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500" />
              </div>
              <div>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">비밀번호</label>
                <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="비밀번호를 입력하세요" className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500" />
              </div>
              <div>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">권한</label>
                <div className="flex gap-2">
                  {[{ label: '일반', val: false }, { label: '관리자', val: true }].map(({ label, val }) => (
                    <button key={label} onClick={() => setForm({ ...form, is_admin: val })} className={`flex-1 py-2 rounded-sm text-sm font-medium border transition ${form.is_admin === val ? 'bg-primary-50 border-primary-500 text-primary-700' : 'border-neutral-border text-neutral-sub hover:bg-surface-hover'}`}>{label}</button>
                  ))}
                </div>
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
            <h3 className="text-base font-bold mb-2">사용자 삭제</h3>
            <p className="text-sm text-neutral-sub mb-5">
              <strong className="text-neutral-main">{deleteTarget.name}</strong> ({deleteTarget.email})을(를) 삭제하시겠습니까?<br />이 작업은 되돌릴 수 없습니다.
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
