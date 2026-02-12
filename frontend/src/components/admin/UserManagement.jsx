import { useState } from 'react';
import Badge from '../common/Badge';

const ROLES = ['관리자', '일반'];
const DEPARTMENTS = ['정보보안팀', '개발팀', '인사팀', '기획팀', '경영지원팀'];

export default function UserManagement({ users = [] }) {
  const [data, setData] = useState(users);
  const [showModal, setShowModal] = useState(false);
  const [editIndex, setEditIndex] = useState(null);
  const [form, setForm] = useState({ name: '', department: DEPARTMENTS[0], role: '일반' });

  const toggleActive = (i) => {
    const n = [...data];
    n[i] = { ...n[i], active: !n[i].active };
    setData(n);
  };

  const openAdd = () => {
    setEditIndex(null);
    setForm({ name: '', department: DEPARTMENTS[0], role: '일반' });
    setShowModal(true);
  };

  const openEdit = (i) => {
    setEditIndex(i);
    setForm({ name: data[i].name, department: data[i].department, role: data[i].role });
    setShowModal(true);
  };

  const handleSave = () => {
    if (!form.name.trim()) return;
    if (editIndex !== null) {
      const n = [...data];
      n[editIndex] = { ...n[editIndex], ...form };
      setData(n);
    } else {
      setData([...data, { ...form, active: true }]);
    }
    setShowModal(false);
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><span>👥</span>사용자 관리</div>
        <button className="btn-primary" onClick={openAdd}>+ 사용자 추가</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead><tr>
            {['이름', '부서', '권한', '상태', '관리'].map((h) => <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-neutral-sub border-b-2 border-neutral-divider bg-surface-hover">{h}</th>)}
          </tr></thead>
          <tbody>
            {data.map((u, i) => (
              <tr key={i} className="hover:bg-surface-hover">
                <td className="px-4 py-3 text-[0.8125rem] font-semibold border-b border-neutral-divider">{u.name}</td>
                <td className="px-4 py-3 text-[0.8125rem] border-b border-neutral-divider">{u.department}</td>
                <td className="px-4 py-3 border-b border-neutral-divider"><Badge variant={u.role === '관리자' ? 'role-admin' : 'role-user'}>{u.role}</Badge></td>
                <td className="px-4 py-3 border-b border-neutral-divider">
                  <button onClick={() => toggleActive(i)} className={`w-11 h-[22px] rounded-full relative transition ${u.active ? 'bg-success' : 'bg-neutral-border'}`}>
                    <span className={`absolute w-[18px] h-[18px] rounded-full bg-white top-0.5 left-0.5 transition-transform ${u.active ? 'translate-x-[22px]' : 'translate-x-0'}`} />
                  </button>
                </td>
                <td className="px-4 py-3 border-b border-neutral-divider">
                  <button className="btn-outline py-1 px-2.5 text-[0.6875rem]" onClick={() => openEdit(i)}>수정</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setShowModal(false)}>
          <div className="bg-surface-card rounded-lg border border-neutral-border shadow-lg w-[400px] p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-bold mb-4">{editIndex !== null ? '사용자 수정' : '사용자 추가'}</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">이름</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="이름을 입력하세요"
                  className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">부서</label>
                <select
                  value={form.department}
                  onChange={(e) => setForm({ ...form, department: e.target.value })}
                  className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 bg-white"
                >
                  {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold text-neutral-sub block mb-1">권한</label>
                <div className="flex gap-2">
                  {ROLES.map((r) => (
                    <button
                      key={r}
                      onClick={() => setForm({ ...form, role: r })}
                      className={`flex-1 py-2 rounded-sm text-sm font-medium border transition ${form.role === r ? 'bg-primary-50 border-primary-500 text-primary-700' : 'border-neutral-border text-neutral-sub hover:bg-surface-hover'}`}
                    >
                      {r}
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
    </div>
  );
}
