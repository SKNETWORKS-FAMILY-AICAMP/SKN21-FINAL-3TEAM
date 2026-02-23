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
  const [error, setError] = useState(null);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    const results = await Promise.allSettled([
      listUsers(),
      listRegulations(),
      getSystemStats(),
      getQueryLogs(),
    ]);

    const [usersRes, regsRes, statsRes, logsRes] = results;

    // 권한 오류 확인 (403이면 관리자 아님)
    const firstError = results.find((r) => r.status === 'rejected')?.reason;
    if (firstError?.response?.status === 403) {
      setError('관리자 권한이 필요합니다. 관리자 계정으로 로그인해주세요.');
      setLoading(false);
      return;
    }
    if (firstError?.response?.status === 401) {
      setError('로그인이 만료되었습니다. 다시 로그인해주세요.');
      setLoading(false);
      return;
    }

    setUsers(usersRes.status === 'fulfilled' ? (usersRes.value.data || []) : []);
    setRegulations(regsRes.status === 'fulfilled' ? (regsRes.value.data || []) : []);
    setStats(statsRes.status === 'fulfilled' ? (statsRes.value.data || {}) : {});
    setQueryLogs(logsRes.status === 'fulfilled' ? (logsRes.value.data?.items || []) : []);

    // 일부 실패 시 콘솔 로그
    results.forEach((r, i) => {
      if (r.status === 'rejected') {
        console.error(`Admin API call ${i} failed:`, r.reason);
      }
    });

    setLoading(false);
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
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-20">
          <div className="text-error text-lg font-semibold mb-2">{error}</div>
          <button className="btn-primary mt-4" onClick={loadAll}>다시 시도</button>
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
