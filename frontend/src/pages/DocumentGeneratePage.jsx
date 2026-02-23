import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import TemplateSelector from '../components/documents/TemplateSelector';
import TemplateUploadDialog from '../components/documents/TemplateUploadDialog';
import DocumentPreview from '../components/documents/DocumentPreview';
import MeetingInput from '../components/meetings/MeetingInput';
import MeetingPreview from '../components/meetings/MeetingPreview';
import { generateDocument, downloadDocument } from '../api/documents';

// Mock: 회의록 AI 생성 결과
const mockMeetingResult = {
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

// Mock: 템플릿별 생성 결과
const mockResults = {
  report: {
    title: '2026년 1분기 보안 현황 보고서',
    templateType: 'report',
    fields: [
      { label: '보고 기간', value: '2026년 1월 ~ 3월' },
      { label: '작성 부서', value: '정보보안팀' },
      { label: '요약', value: '1분기 보안 점검 결과, 전반적인 보안 수준이 양호하며 3건의 경미한 위반 사항이 발견되었습니다.' },
      { label: '주요 성과', value: '- 전 직원 보안 교육 완료 (참여율 98%)\n- 보안 취약점 12건 조치 완료\n- 접근 권한 재검토 완료' },
      { label: '개선 필요사항', value: '- 외부 반출 승인 프로세스 간소화\n- 비밀번호 변경 주기 알림 자동화' },
    ],
  },
  jd: {
    title: '정보보안 엔지니어 채용 공고',
    templateType: 'jd',
    fields: [
      { label: '직무명', value: '정보보안 엔지니어' },
      { label: '주요 업무', value: '- 보안 정책 수립 및 관리\n- 취약점 분석 및 대응\n- 보안 교육 기획 및 운영\n- 접근 권한 관리' },
      { label: '자격 요건', value: '- 정보보안 관련 경력 3년 이상\n- ISMS, ISO 27001 인증 경험\n- 네트워크/시스템 보안 이해' },
      { label: '우대 사항', value: '- CISSP, CISA 자격증 보유\n- 클라우드 보안 경험 (AWS/GCP)' },
    ],
  },
  proposal: {
    title: '보안 시스템 고도화 제안서',
    templateType: 'proposal',
    fields: [
      { label: '제안 배경', value: '현행 보안 시스템의 노후화에 따른 고도화 필요성이 대두되었습니다.' },
      { label: '제안 내용', value: '- 차세대 방화벽 도입\n- SIEM 시스템 업그레이드\n- 제로트러스트 아키텍처 적용' },
      { label: '기대 효과', value: '- 보안 사고 대응 시간 50% 단축\n- 이상 탐지 정확도 30% 향상' },
      { label: '예상 일정', value: '2026년 3월 ~ 6월 (4개월)' },
      { label: '예상 비용', value: '총 1.2억원 (하드웨어 8천만, 소프트웨어 4천만)' },
    ],
  },
};

export default function DocumentGeneratePage() {
  const { isScrolled } = useOutletContext();
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [result, setResult] = useState(null);
  const [meetingResult, setMeetingResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const isMeeting = selectedTemplate === 'meeting_minutes';

  const handleTemplateSelect = (template) => {
    setSelectedTemplate(template);
    setResult(null);
    setMeetingResult(null);
    setPrompt('');
  };

  const handleGenerate = () => {
    if (!selectedTemplate) return;
    setLoading(true);
    setTimeout(() => {
      setResult(mockResults[selectedTemplate] || mockResults.report);
      setLoading(false);
    }, 1500);
  };

  const handleMeetingSubmit = async (formData) => {
    setLoading(true);
    try {
      const response = await generateDocument({
        template_type: 'meeting_minutes',
        title: formData.title,
        date: formData.date,
        attendees: formData.attendees,
        content: formData.content,
      });
      const apiData = response.data;
      setMeetingResult({
        title: apiData.title || formData.title,
        date: apiData.date || formData.date,
        attendees: apiData.attendees?.length > 0 ? apiData.attendees : formData.attendees,
        summary: apiData.summary,
        decisions: apiData.decisions || [],
        actionItems: (apiData.action_items || []).map((ai) => ({
          task: ai.content,
          assignee: ai.assignee,
          deadline: ai.due_date,
        })),
        document_id: apiData.document_id,
      });
    } catch (err) {
      alert('회의록 생성 실패: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (format) => {
    if (!meetingResult?.document_id) {
      alert('먼저 회의록을 생성해주세요.');
      return;
    }
    try {
      const response = await downloadDocument(meetingResult.document_id, format);
      const url = URL.createObjectURL(response.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `회의록.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('다운로드 실패: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleUpload = async (data) => {
    alert(`"${data.name}" 템플릿이 업로드되었습니다. (Mock)`);
  };

  return (
    <div>
      <header className={`sticky top-0 bg-surface-main z-10 transition-all duration-300 ${isScrolled ? 'py-2.5' : 'py-6'}`}>
        <h1 className={`font-bold transition-all duration-300 ${isScrolled ? 'text-lg' : 'text-2xl'}`}>문서 생성</h1>
        <p className={`text-neutral-sub transition-all duration-300 overflow-hidden ${isScrolled ? 'text-xs mt-0 max-h-0 opacity-0' : 'text-sm mt-1 max-h-6 opacity-100'}`}>템플릿을 선택하고 AI가 내용을 자동으로 채워줍니다</p>
      </header>

      <div className="space-y-6">
        {/* 템플릿 선택 */}
        <TemplateSelector
          selected={selectedTemplate}
          onSelect={handleTemplateSelect}
          onUploadClick={() => setUploadOpen(true)}
        />

        {/* 회의록 선택 시: 회의 내용 입력 폼 */}
        {isMeeting && (
          <>
            <MeetingInput onSubmit={handleMeetingSubmit} loading={loading} />
            <MeetingPreview data={meetingResult} onDownload={handleDownload} loading={loading} />
          </>
        )}

        {/* 기타 템플릿 선택 시: 추가 지시사항 + 문서 미리보기 */}
        {selectedTemplate && !isMeeting && (
          <>
            <div className="card">
              <div className="card-header">
                <div className="card-title">추가 지시사항</div>
              </div>
              <div className="card-body space-y-4">
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="AI에게 추가 지시사항을 입력하세요 (선택). 예: 보안팀 관점에서 작성해줘"
                  rows={3}
                  className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 resize-y"
                />
                <div className="flex justify-end">
                  <button
                    onClick={handleGenerate}
                    disabled={loading}
                    className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? 'AI 생성 중...' : 'AI 문서 생성'}
                  </button>
                </div>
              </div>
            </div>
            <DocumentPreview data={result} onDownload={handleDownload} loading={loading} />
          </>
        )}

        {/* 업로드 다이얼로그 */}
        <TemplateUploadDialog
          isOpen={uploadOpen}
          onClose={() => setUploadOpen(false)}
          onUpload={handleUpload}
        />
      </div>
    </div>
  );
}
