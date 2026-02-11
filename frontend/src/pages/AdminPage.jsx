import UserManagement from '../components/admin/UserManagement';
import RegulationManagement from '../components/admin/RegulationManagement';
import SystemStats from '../components/admin/SystemStats';

const mockUsers = [
  { name: '김정보', department: '정보보안팀', role: '관리자', active: true },
  { name: '이개발', department: '개발팀', role: '일반', active: true },
  { name: '박인사', department: '인사팀', role: '일반', active: true },
  { name: '최보안', department: '정보보안팀', role: '일반', active: false },
];

const mockRegs = [
  { name: '정보보안 지침', count: 42, status: '적용중' },
  { name: '인사규정 매뉴얼', count: 38, status: '개정중' },
  { name: '개발 가이드라인', count: 31, status: '적용중' },
];

const mockStats = [
  { label: '판단 질의', percent: 72, color: '#6E87A0' },
  { label: '문서 분석', percent: 18, color: '#A89580' },
  { label: '일정 관리', percent: 10, color: '#5B9A6F' },
];

const mockLogs = [
  { type: 'query', icon: '❓', title: '외부 반출 승인 절차', description: '김정보 · 판단 Agent · 응답 2.3초', time: '5분 전' },
  { type: 'doc', icon: '📄', title: 'Q4 예산 보고서 요약 요청', description: '이개발 · 문서 Agent · 응답 4.1초', time: '12분 전' },
  { type: 'schedule', icon: '📆', title: '회의 일정 등록', description: '박인사 · 일정 Agent · 응답 1.2초', time: '30분 전' },
];

export default function AdminPage() {
  return (
    <div>
      <header className="py-6 sticky top-0 bg-surface-main z-10">
        <h1 className="text-2xl font-bold">관리자 설정</h1>
        <p className="text-sm text-neutral-sub mt-1">시스템 설정 및 사용자를 관리합니다</p>
      </header>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        {[{ l: '전체 사용자', v: '24' }, { l: '이번 달 질의 수', v: '847' }, { l: '등록된 규정', v: '6' }].map(({ l, v }) => (
          <div key={l} className="card p-5"><div className="text-xs text-neutral-sub">{l}</div><div className="font-display text-[28px] font-bold text-primary-700 mt-1">{v}</div></div>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-5">
        <div className="space-y-5">
          <UserManagement users={mockUsers} />
          <RegulationManagement regulations={mockRegs} />
        </div>
        <SystemStats stats={mockStats} queryLogs={mockLogs} />
      </div>
    </div>
  );
}
