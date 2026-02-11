import StatCard from '../components/dashboard/StatCard';
import RiskAlert from '../components/dashboard/RiskAlert';
import ActivityTimeline from '../components/dashboard/ActivityTimeline';
import ActionItemList from '../components/dashboard/ActionItemList';
import CalendarWidget from '../components/dashboard/CalendarWidget';
import TodayMeetings from '../components/dashboard/TodayMeetings';
import RecentDocs from '../components/dashboard/RecentDocs';
import TopQueries from '../components/dashboard/TopQueries';
import QuickSearch from '../components/dashboard/QuickSearch';
import AutoScanBadge from '../components/dashboard/AutoScanBadge';
import FilterBar from '../components/common/FilterBar';
import { useState } from 'react';

const mockActivities = [
  { type: 'doc', icon: '📄', title: '정보보안 지침 v2.3 업로드', description: '새 문서가 업로드되어 파싱 완료되었습니다.', time: '5분 전', to: '/documents' },
  { type: 'query', icon: '❓', title: '질의응답: "외부 반출 승인 절차"', description: 'AI가 Yes/No 판단과 근거를 제공했습니다.', time: '12분 전', to: '/chat' },
  { type: 'meeting', icon: '📅', title: '보안점검 회의록 분석 완료', description: '5개 결정사항, 8개 Action Item 추출됨', time: '1시간 전', to: '/meetings' },
  { type: 'schedule', icon: '📆', title: '일정 변경: 인사규정 검토회의', description: '2월 7일 → 2월 10일로 변경되었습니다.', time: '2시간 전', to: '/schedules' },
];

const mockActions = [
  { title: '정보보안 교육 계획서 제출', assignee: '김정보', deadline: 'D-1', priority: 'high' },
  { title: '개인정보 접근 권한 검토', assignee: '이개발', deadline: 'D-3', priority: 'medium' },
  { title: '신규 입사자 보안 서약서 수집', assignee: '박인사', deadline: 'D-7', priority: 'low' },
];

const mockTopQueries = {
  '월간': [
    { question: '재택근무 관련 규정이 어떻게 되나요?', type: '판단', count: 128 },
    { question: '출장비 정산 절차를 알려주세요', type: '문서', count: 95 },
    { question: '연차 사용 기준은?', type: '판단', count: 87 },
    { question: '보안 점검 체크리스트 있나요?', type: '문서', count: 64 },
    { question: '신규 입사자 온보딩 절차는?', type: '일반', count: 52 },
  ],
  '주간': [
    { question: '외부 반출 승인 절차가 어떻게 되나요?', type: '판단', count: 32 },
    { question: '휴가 신청 기한은 언제까지인가요?', type: '문서', count: 28 },
    { question: '코드 리뷰 필수 참여자는?', type: '판단', count: 21 },
    { question: 'AWS 접근 권한 신청 방법은?', type: '일반', count: 15 },
  ],
  '일간': [
    { question: '오늘 회의 일정 알려줘', type: '일정', count: 8 },
    { question: '인사규정 검토회의 자료 어디있어?', type: '문서', count: 5 },
    { question: '재택근무 VPN 접속 방법은?', type: '판단', count: 3 },
  ],
};

const mockMeetings = [
  { time: '10:00', period: 'AM', title: '보안점검 정기회의', location: '회의실 A', attendees: 5 },
  { time: '2:00', period: 'PM', title: '인사규정 개정 검토', location: '온라인', attendees: 8 },
];

const mockDocs = [
  { name: '정보보안 지침 v2.3', version: 'v2.3', date: '2026-02-05', status: '적용중' },
  { name: '인사규정 매뉴얼', version: 'v1.8', date: '2026-01-28', status: '개정중' },
];

const calEvents = { 3: 'meeting', 6: 'deadline', 10: 'meeting' };

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];
const formatToday = () => {
  const d = new Date();
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 (${WEEKDAYS[d.getDay()]})`;
};

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState('전체');

  return (
    <div>
      <header className="flex justify-between items-center py-6 sticky top-0 bg-surface-main z-10">
        <div>
          <h1 className="text-2xl font-bold">대시보드</h1>
          <p className="text-sm text-neutral-sub mt-1">{formatToday()} — 오늘의 현황을 확인하세요.</p>
        </div>
        <div className="flex items-center gap-3">
          <AutoScanBadge status="scanning" lastScan="2분 전" detectedCount={2} />
          <button aria-label="알림" className="w-10 h-10 rounded-sm border border-neutral-border bg-surface-card flex items-center justify-center relative">
            <span>🔔</span>
            <span className="absolute top-2 right-2 w-2 h-2 bg-error rounded-full border-2 border-surface-card" />
          </button>
        </div>
      </header>

      <FilterBar tabs={['전체', '정보보안', '인사', '개발']} activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        <StatCard icon="💬" iconColor="blue" value="24" label="오늘의 질의응답" trend="↑ 12%" to="/chat" />
        <StatCard icon="📋" iconColor="purple" value="8" label="처리된 회의록" trend="↑ 3건" to="/meetings" />
        <StatCard icon="✓" iconColor="green" value="15" label="완료된 Action Item" trend="↑ 5건" to="/schedules" />
        <StatCard icon="⚠️" iconColor="red" value="3" label="리스크 알림" />
      </div>

      <div className="mb-5">
        <QuickSearch />
      </div>

      <RiskAlert title="높음 리스크 감지 - 2건" description="정보보안 규정 위반 가능성이 감지되었습니다. 즉시 확인이 필요합니다." />

      <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-5">
        <div className="space-y-6">
          <TopQueries data={mockTopQueries} />
          <ActivityTimeline activities={mockActivities} />
          <ActionItemList items={mockActions} tabs={['마감 임박', '우선순위']} />
        </div>
        <div className="space-y-6">
          <CalendarWidget events={calEvents} />
          <TodayMeetings meetings={mockMeetings} />
          <RecentDocs docs={mockDocs} />
        </div>
      </div>
    </div>
  );
}
