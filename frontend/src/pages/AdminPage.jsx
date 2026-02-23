import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import UserManagement from '../components/admin/UserManagement';
import RegulationManagement from '../components/admin/RegulationManagement';
import SystemStats from '../components/admin/SystemStats';
import { listUsers, getSystemStats, getQueryLogs, listRegulations } from '../api/admin';

export default function AdminPage() {
  const { isScrolled } = useOutletContext();
  const [users, setUsers] = useState([]);
  const [regulations, setRegulations] = useState([]);
  const [stats, setStats] = useState({ today_queries: 0, processed_meetings: 0, completed_action_items: 0, risk_alerts: 0 });
  const [queryLogs, setQueryLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [usersRes, regsRes, statsRes, logsRes] = await Promise.all([
        listUsers().catch(() => ({ data: [] })),
        listRegulations().catch(() => ({ data: [] })),
        getSystemStats().catch(() => ({ data: {} })),
        getQueryLogs().catch(() => ({ data: { items: [] } })),
      ]);
      setUsers(usersRes.data || []);
      setRegulations(regsRes.data || []);
      setStats(statsRes.data || {});
      setQueryLogs(logsRes.data?.items || []);
    } catch (e) {
      console.error('Admin data load failed:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  return (
    <div>
      <header className={`sticky top-0 bg-surface-main z-10 transition-all duration-300 ${isScrolled ? 'py-2.5' : 'py-6'}`}>
        <h1 className={`font-bold transition-all duration-300 ${isScrolled ? 'text-lg' : 'text-2xl'}`}>관리자 설정</h1>
        <p className={`text-neutral-sub transition-all duration-300 overflow-hidden ${isScrolled ? 'text-xs mt-0 max-h-0 opacity-0' : 'text-sm mt-1 max-h-6 opacity-100'}`}>시스템 설정 및 사용자를 관리합니다</p>
      </header>

      {loading ? (
        <div className="flex justify-center py-20">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-500" />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
            {[
              { l: '전체 사용자', v: users.length },
              { l: '오늘 질의 수', v: stats.today_queries || 0 },
              { l: '처리된 회의', v: stats.processed_meetings || 0 },
              { l: '등록된 규정', v: regulations.length },
            ].map(({ l, v }) => (
              <div key={l} className="card p-5">
                <div className="text-xs text-neutral-sub">{l}</div>
                <div className="font-display text-[1.75rem] font-bold text-primary-700 mt-1">{v}</div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-5">
            <div className="space-y-5">
              <UserManagement users={users} onRefresh={loadAll} />
              <RegulationManagement regulations={regulations} onRefresh={loadAll} />
            </div>
            <SystemStats queryLogs={queryLogs} />
          </div>
        </>
      )}
    </div>
  );
}
