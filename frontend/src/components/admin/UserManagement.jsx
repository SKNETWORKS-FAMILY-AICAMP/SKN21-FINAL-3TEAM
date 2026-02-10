import { useState } from 'react';
import Badge from '../common/Badge';

export default function UserManagement({ users = [] }) {
  const [data, setData] = useState(users);
  const toggleActive = (i) => { const n = [...data]; n[i] = { ...n[i], active: !n[i].active }; setData(n); };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><span>👥</span>사용자 관리</div>
        <button className="btn-primary">+ 사용자 추가</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead><tr>
            {['이름', '부서', '권한', '상태', '관리'].map((h) => <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-neutral-sub border-b-2 border-neutral-divider bg-surface-hover">{h}</th>)}
          </tr></thead>
          <tbody>
            {data.map((u, i) => (
              <tr key={i} className="hover:bg-surface-hover">
                <td className="px-4 py-3 text-[13px] font-semibold border-b border-neutral-divider">{u.name}</td>
                <td className="px-4 py-3 text-[13px] border-b border-neutral-divider">{u.department}</td>
                <td className="px-4 py-3 border-b border-neutral-divider"><Badge variant={u.role === '관리자' ? 'role-admin' : 'role-user'}>{u.role}</Badge></td>
                <td className="px-4 py-3 border-b border-neutral-divider">
                  <button onClick={() => toggleActive(i)} className={`w-10 h-[22px] rounded-full relative transition ${u.active ? 'bg-success' : 'bg-neutral-border'}`}>
                    <span className={`absolute w-[18px] h-[18px] rounded-full bg-white top-0.5 transition-transform ${u.active ? 'translate-x-[20px]' : 'translate-x-0.5'}`} />
                  </button>
                </td>
                <td className="px-4 py-3 border-b border-neutral-divider"><button className="btn-outline py-1 px-2.5 text-[11px]">수정</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
