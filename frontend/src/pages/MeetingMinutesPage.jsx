import { useState } from 'react';
import MeetingInput from '../components/meetings/MeetingInput';
import MeetingPreview from '../components/meetings/MeetingPreview';

// Mock: AI가 생성한 회의록 결과
const mockResult = {
  title: '보안점검 정기회의',
  date: '2026-02-10',
  attendees: ['김정보', '이개발', '박인사'],
  summary:
    '정보보안 규정 개정 사항을 검토하고 신규 보안 교육 일정을 확정했습니다. ' +
    'AWS 접근 권한 정책 변경에 따른 후속 조치를 논의했습니다.',
  decisions: [
    '정보보안 교육을 2월 말까지 전 직원 대상으로 실시',
    'AWS 프로덕션 접근 권한은 팀장 승인 후 부여',
    '재택근무 시 VPN 필수 사용 규정 재공지',
  ],
  actionItems: [
    { task: '보안 교육 일정 및 강사 섭외', assignee: '김정보', deadline: '2026-02-15' },
    { task: 'AWS 권한 신청 양식 업데이트', assignee: '이개발', deadline: '2026-02-12' },
    { task: 'VPN 사용 가이드 문서 배포', assignee: '박인사', deadline: '2026-02-14' },
  ],
};

export default function MeetingMinutesPage() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (formData) => {
    setLoading(true);
    // Mock: 1.5초 후 결과 표시 (나중에 API 호출로 교체)
    setTimeout(() => {
      setResult({
        ...mockResult,
        title: formData.title || mockResult.title,
        date: formData.date,
        attendees: formData.attendees.length > 0 ? formData.attendees : mockResult.attendees,
      });
      setLoading(false);
    }, 1500);
  };

  const handleDownload = (format) => {
    // Mock: 나중에 API 연동
    alert(`${format.toUpperCase()} 다운로드는 백엔드 연동 후 사용 가능합니다.`);
  };

  return (
    <div>
      <header className="py-6 sticky top-0 bg-surface-main z-10">
        <h1 className="text-2xl font-bold">회의록 생성</h1>
        <p className="text-sm text-neutral-sub mt-1">회의 내용을 입력하면 AI가 회의록을 자동으로 생성합니다</p>
      </header>

      <div className="space-y-6">
        <MeetingInput onSubmit={handleSubmit} loading={loading} />
        <MeetingPreview data={result} onDownload={handleDownload} loading={loading} />
      </div>
    </div>
  );
}
