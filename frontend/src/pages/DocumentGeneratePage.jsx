import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import useAuthStore from '../store/authStore';
import TemplateSelector from '../components/documents/TemplateSelector';
import TemplateUploadDialog from '../components/documents/TemplateUploadDialog';
import DocumentPreview from '../components/documents/DocumentPreview';
import MeetingInput from '../components/meetings/MeetingInput';
import MeetingPreview from '../components/meetings/MeetingPreview';
import { generateDocument, downloadDocument } from '../api/documents';


export default function DocumentGeneratePage() {
  const { isScrolled } = useOutletContext();
  const user = useAuthStore((s) => s.user);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [result, setResult] = useState(null);
  const [meetingResult, setMeetingResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reportForm, setReportForm] = useState({ title: '', date: new Date().toISOString().split('T')[0], author: user?.name ?? '', department: '', content: '' });
  const [proposalForm, setProposalForm] = useState({ title: '', date: new Date().toISOString().split('T')[0], company: '', manager: user?.name ?? '', phone: '', content: '' });

  const isMeeting = selectedTemplate === 'meeting_minutes';
  const isReport = selectedTemplate === 'report';
  const isProposal = selectedTemplate === 'proposal';

  const handleTemplateSelect = (template) => {
    setSelectedTemplate(template);
    setResult(null);
    setMeetingResult(null);
    setPrompt('');
    setReportForm({ title: '', date: new Date().toISOString().split('T')[0], author: user?.name ?? '', department: '', content: '' });
    setProposalForm({ title: '', date: new Date().toISOString().split('T')[0], company: '', manager: user?.name ?? '', phone: '', content: '' });
  };

  const handleGenerate = async () => {
    if (!selectedTemplate) return;
    setLoading(true);
    try {
      let payload = { template_type: selectedTemplate };

      if (isReport) {
        payload = {
          ...payload,
          title: reportForm.title,
          date: reportForm.date,
          content: [
            reportForm.author && `작성자: ${reportForm.author}`,
            reportForm.department && `부서: ${reportForm.department}`,
            reportForm.content,
          ].filter(Boolean).join('\n'),
        };
      } else if (isProposal) {
        payload = {
          ...payload,
          title: proposalForm.title,
          date: proposalForm.date,
          content: [
            proposalForm.company && `제안사: ${proposalForm.company}`,
            proposalForm.manager && `담당자: ${proposalForm.manager}`,
            proposalForm.phone && `연락처: ${proposalForm.phone}`,
            proposalForm.content,
          ].filter(Boolean).join('\n'),
        };
      } else {
        payload = { ...payload, content: prompt };
      }

      const response = await generateDocument(payload);
      const apiData = response.data;

      const fieldsMap = {
        report: [
          { label: '보고 개요', value: apiData.overview },
          { label: '주요 내용', value: apiData.main_content },
          { label: '향후 계획', value: apiData.next_plan },
        ],
        proposal: [
          { label: '제안 배경', value: apiData.background },
          { label: '제안 내용', value: apiData.content },
          { label: '기대 효과', value: apiData.expected_effect },
        ],
      };

      setResult({
        title: apiData.title,
        templateType: selectedTemplate,
        fields: fieldsMap[selectedTemplate] || [{ label: '내용', value: apiData.preview }],
        document_id: apiData.document_id,
      });
    } catch (err) {
      alert('문서 생성 실패: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
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
    const documentId = meetingResult?.document_id || result?.document_id;
    if (!documentId) {
      alert('먼저 문서를 생성해주세요.');
      return;
    }
    const filenameMap = {
      meeting_minutes: '회의록',
      report: '업무보고서',
      proposal: '제안서',
    };
    const filename = filenameMap[selectedTemplate] || '문서';
    try {
      const response = await downloadDocument(documentId, format);
      const url = URL.createObjectURL(response.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${filename}.${format}`;
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
      <header className={`sticky top-0 bg-surface-main z-10 flex flex-col justify-center overflow-hidden transition-all duration-300 ${isScrolled ? 'h-[56px]' : 'h-[100px]'}`}>
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

        {/* 보고서 입력 폼 */}
        {isReport && (
          <>
            <div className="card">
              <div className="card-header">
                <div className="card-title">보고서 내용 입력</div>
              </div>
              <div className="card-body space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[0.8125rem] font-semibold mb-1.5">제목</label>
                    <input
                      value={reportForm.title}
                      onChange={(e) => setReportForm({ ...reportForm, title: e.target.value })}
                      placeholder="예: 2026년 1분기 보안 현황 보고서"
                      className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[0.8125rem] font-semibold mb-1.5">날짜</label>
                    <input
                      type="date"
                      value={reportForm.date}
                      onChange={(e) => setReportForm({ ...reportForm, date: e.target.value })}
                      className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[0.8125rem] font-semibold mb-1.5">작성자</label>
                    <input
                      value={reportForm.author}
                      onChange={(e) => setReportForm({ ...reportForm, author: e.target.value })}
                      placeholder="예: 김정보"
                      className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[0.8125rem] font-semibold mb-1.5">부서</label>
                    <input
                      value={reportForm.department}
                      onChange={(e) => setReportForm({ ...reportForm, department: e.target.value })}
                      placeholder="예: 정보보안팀"
                      className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-[0.8125rem] font-semibold mb-1.5">회의 내용</label>
                  <textarea
                    value={reportForm.content}
                    onChange={(e) => setReportForm({ ...reportForm, content: e.target.value })}
                    placeholder="보고서에 포함할 회의 내용을 입력하세요."
                    rows={4}
                    onInput={(e) => { e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 130) + 'px'; }}
                    className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 resize-none overflow-y-auto max-h-[130px]"
                  />
                </div>
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

        {/* 제안서 입력 폼 */}
        {isProposal && (
          <>
            <div className="card">
              <div className="card-header">
                <div className="card-title">제안서 내용 입력</div>
              </div>
              <div className="card-body space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[0.8125rem] font-semibold mb-1.5">제목</label>
                    <input
                      value={proposalForm.title}
                      onChange={(e) => setProposalForm({ ...proposalForm, title: e.target.value })}
                      placeholder="예: 보안 시스템 고도화 제안서"
                      className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[0.8125rem] font-semibold mb-1.5">날짜</label>
                    <input
                      type="date"
                      value={proposalForm.date}
                      onChange={(e) => setProposalForm({ ...proposalForm, date: e.target.value })}
                      className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-[0.8125rem] font-semibold mb-1.5">제안사</label>
                    <input
                      value={proposalForm.company}
                      onChange={(e) => setProposalForm({ ...proposalForm, company: e.target.value })}
                      placeholder="예: (주)보안솔루션"
                      className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[0.8125rem] font-semibold mb-1.5">담당자</label>
                    <input
                      value={proposalForm.manager}
                      onChange={(e) => setProposalForm({ ...proposalForm, manager: e.target.value })}
                      placeholder="예: 이담당"
                      className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[0.8125rem] font-semibold mb-1.5">연락처</label>
                    <input
                      value={proposalForm.phone}
                      onChange={(e) => setProposalForm({ ...proposalForm, phone: e.target.value })}
                      placeholder="예: 010-1234-5678"
                      className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-[0.8125rem] font-semibold mb-1.5">회의내용</label>
                  <textarea
                    value={proposalForm.content}
                    onChange={(e) => setProposalForm({ ...proposalForm, content: e.target.value })}
                    placeholder="제안서에 포함할 회의 내용을 입력하세요."
                    rows={4}
                    onInput={(e) => { e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 130) + 'px'; }}
                    className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 resize-none overflow-y-auto max-h-[130px]"
                  />
                </div>
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

        {/* 기타 템플릿 선택 시: 추가 지시사항 + 문서 미리보기 */}
        {selectedTemplate && !isMeeting && !isReport && !isProposal && (
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
