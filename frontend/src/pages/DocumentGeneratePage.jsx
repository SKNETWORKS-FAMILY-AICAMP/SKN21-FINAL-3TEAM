import { useState } from 'react';
import TemplateSelector from '../components/documents/TemplateSelector';
import TemplateUploadDialog from '../components/documents/TemplateUploadDialog';
import DocumentPreview from '../components/documents/DocumentPreview';

// Mock: 템플릿별 생성 결과
const mockResults = {
  meeting_minutes: {
    title: '2026년 2월 보안점검 회의록',
    templateType: 'meeting_minutes',
    fields: [
      { label: '회의 일시', value: '2026년 2월 10일 (화) 14:00-15:30' },
      { label: '참석자', value: '김정보, 이개발, 박인사, 최보안' },
      { label: '회의 목적', value: '정보보안 규정 개정 사항 검토 및 교육 일정 확정' },
      { label: '주요 논의사항', value: '1. 정보보안 교육 일정 확정\n2. AWS 접근 권한 정책 변경\n3. 재택근무 VPN 사용 규정 재공지' },
      { label: '결정사항', value: '- 보안 교육: 2월 말까지 전 직원 대상 실시\n- AWS 권한: 팀장 승인 후 부여\n- VPN: 재택 시 필수 사용 재공지' },
    ],
  },
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
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleGenerate = () => {
    if (!selectedTemplate) return;
    setLoading(true);
    // Mock: 1.5초 후 결과 표시
    setTimeout(() => {
      setResult(mockResults[selectedTemplate] || mockResults.report);
      setLoading(false);
    }, 1500);
  };

  const handleDownload = (format) => {
    alert(`${format.toUpperCase()} 다운로드는 백엔드 연동 후 사용 가능합니다.`);
  };

  const handleUpload = async (data) => {
    // Mock: 나중에 API 연동
    alert(`"${data.name}" 템플릿이 업로드되었습니다. (Mock)`);
  };

  return (
    <div>
      <header className="py-6 sticky top-0 bg-surface-main z-10">
        <h1 className="text-2xl font-bold">문서 생성</h1>
        <p className="text-sm text-neutral-sub mt-1">템플릿을 선택하고 AI가 내용을 자동으로 채워줍니다</p>
      </header>

      <div className="space-y-6">
        {/* 템플릿 선택 */}
        <TemplateSelector
          selected={selectedTemplate}
          onSelect={setSelectedTemplate}
          onUploadClick={() => setUploadOpen(true)}
        />

        {/* 추가 지시사항 + 생성 버튼 */}
        {selectedTemplate && (
          <div className="card">
            <div className="card-header">
              <div className="card-title"><span>✏️</span>추가 지시사항</div>
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
        )}

        {/* 결과 미리보기 */}
        <DocumentPreview data={result} onDownload={handleDownload} loading={loading} />

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
