import { useState } from 'react';
import FilterBar from '../components/common/FilterBar';
import MeetingList from '../components/meetings/MeetingList';
import MeetingDetail from '../components/meetings/MeetingDetail';

const mockMeetings = [
  { id: 1, dateShort: '02/03', dayOfWeek: '월', title: '보안점검 정기회의', attendeeCount: 5, duration: '1시간 20분', analyzed: true, riskLevel: 'medium',
    info: '일시: 2026-02-03 10:00~11:20\n참석자: 김정보, 이개발, 박인사, 최보안, 정관리\n장소: 회의실 A',
    decisions: [{ title: '외부 접근 권한 정책 강화', assignee: '김정보' }, { title: '보안 교육 분기별 실시', assignee: '전원' }],
    actionItems: [
      { title: '정보보안 교육 계획서 제출', assignee: '김정보', deadline: 'D-1 (2026-02-06)', priority: 'high' },
      { title: '개인정보 접근 권한 검토', assignee: '이개발', deadline: 'D-3 (2026-02-08)', priority: 'medium' },
      { title: '신규 입사자 보안 서약서 수집', assignee: '박인사', deadline: 'D-7 (2026-02-12)', priority: 'low' },
    ],
  },
  { id: 2, dateShort: '01/28', dayOfWeek: '화', title: '인사규정 개정 검토회의', attendeeCount: 8, duration: '55분', analyzed: true },
  { id: 3, dateShort: '01/20', dayOfWeek: '월', title: 'Q4 예산 검토 회의', attendeeCount: 6, duration: '45분', analyzed: false },
];

export default function MeetingsPage() {
  const [activeTab, setActiveTab] = useState('전체');
  const [selected, setSelected] = useState(mockMeetings[0]);

  return (
    <div>
      <header className="flex justify-between items-center py-6 sticky top-0 bg-surface-main z-10">
        <div><h1 className="text-2xl font-bold">회의 관리</h1><p className="text-sm text-neutral-sub mt-1">회의록을 업로드하면 AI가 자동으로 분석합니다</p></div>
        <button className="btn-primary">+ 회의록 업로드</button>
      </header>
      <FilterBar tabs={['전체', '분석완료', '분석중']} activeTab={activeTab} onTabChange={setActiveTab} />
      <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-5">
        <MeetingList meetings={mockMeetings} selected={selected} onSelect={setSelected} />
        <MeetingDetail meeting={selected} />
      </div>
    </div>
  );
}
