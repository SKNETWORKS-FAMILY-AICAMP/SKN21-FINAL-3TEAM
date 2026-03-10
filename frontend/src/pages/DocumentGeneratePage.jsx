import { useState, useEffect } from 'react';
import useAuthStore from '../store/authStore';
import TemplateSelector from '../components/documents/TemplateSelector';
import TemplateUploadDialog from '../components/documents/TemplateUploadDialog';
import DocumentPreview from '../components/documents/DocumentPreview';
import MeetingPreview from '../components/meetings/MeetingPreview';
import { generateDocument, downloadDocument, uploadTemplate, listTemplates, getTemplate } from '../api/documents';
import { toast } from '../store/toastStore';


/**
 * 동적 폼 렌더링 — parsed_structure.fields 기반
 */
function DynamicForm({ fields, formData, onChange }) {
  if (!fields || fields.length === 0) return null;

  const inputClass = 'w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500';

  return (
    <div className="space-y-4">
      {fields.map((field) => {
        const value = formData[field.key] || '';

        if (field.type === 'textarea') {
          return (
            <div key={field.key}>
              <label className="block text-[0.8125rem] font-semibold mb-1.5">
                {field.label}{field.required && <span className="text-red-500 ml-0.5">*</span>}
              </label>
              <textarea
                value={value}
                onChange={(e) => onChange(field.key, e.target.value)}
                placeholder={`${field.label}을(를) 입력하세요`}
                rows={4}
                onInput={(e) => { e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'; }}
                className={`${inputClass} resize-none overflow-y-auto max-h-[200px]`}
              />
            </div>
          );
        }

        if (field.type === 'date') {
          return (
            <div key={field.key} className="w-1/2">
              <label className="block text-[0.8125rem] font-semibold mb-1.5">
                {field.label}{field.required && <span className="text-red-500 ml-0.5">*</span>}
              </label>
              <input
                type="date"
                value={value}
                onChange={(e) => onChange(field.key, e.target.value)}
                className={inputClass}
              />
            </div>
          );
        }

        if (field.type === 'list') {
          return (
            <div key={field.key}>
              <label className="block text-[0.8125rem] font-semibold mb-1.5">
                {field.label}{field.required && <span className="text-red-500 ml-0.5">*</span>}
              </label>
              <input
                value={value}
                onChange={(e) => onChange(field.key, e.target.value)}
                placeholder={`${field.label} (쉼표로 구분)`}
                className={inputClass}
              />
            </div>
          );
        }

        // default: text
        return (
          <div key={field.key}>
            <label className="block text-[0.8125rem] font-semibold mb-1.5">
              {field.label}{field.required && <span className="text-red-500 ml-0.5">*</span>}
            </label>
            <input
              value={value}
              onChange={(e) => onChange(field.key, e.target.value)}
              placeholder={`${field.label}을(를) 입력하세요`}
              className={inputClass}
            />
          </div>
        );
      })}
    </div>
  );
}


export default function DocumentGeneratePage() {

  const user = useAuthStore((s) => s.user);
  const [selectedTemplate, setSelectedTemplate] = useState(null);  // category string
  const [selectedTemplateId, setSelectedTemplateId] = useState(null);  // DB id
  const [templateFields, setTemplateFields] = useState([]);  // parsed_structure.fields
  const [uploadOpen, setUploadOpen] = useState(false);
  const [formData, setFormData] = useState({});
  const [result, setResult] = useState(null);          // 보고서/제안서 결과
  const [meetingResult, setMeetingResult] = useState(null);  // 회의록 결과
  const [loading, setLoading] = useState(false);
  const [customTemplates, setCustomTemplates] = useState([]);
  const [selectedCustomTemplate, setSelectedCustomTemplate] = useState(null);

  const fetchCustomTemplates = () => {
    listTemplates()
      .then(res => setCustomTemplates((res.data || []).filter(t => !t.is_system)))
      .catch(() => setCustomTemplates([]));
  };

  useEffect(() => { fetchCustomTemplates(); }, []);

  const isMeeting = selectedTemplate === 'meeting_minutes';

  // 템플릿 선택 → parsed_structure 로드 → 동적 폼 초기화
  const handleTemplateSelect = async (template, customTpl = null) => {
    setSelectedTemplate(template);
    setSelectedCustomTemplate(customTpl);
    setResult(null);
    setMeetingResult(null);
    setFormData({});
    setTemplateFields([]);

    // 템플릿 상세 조회하여 parsed_structure 로드
    const templateId = customTpl?.id;
    setSelectedTemplateId(templateId || null);

    // 시스템 템플릿이든 커스텀이든 DB에서 조회
    try {
      // listTemplates에서 해당 카테고리의 시스템 템플릿 ID를 찾아야 함
      let tplId = templateId;
      if (!tplId) {
        // 시스템 템플릿: listTemplates에서 category + is_system으로 찾기
        const res = await listTemplates({ category: template });
        const systemTpl = (res.data || []).find(t => t.is_system);
        if (systemTpl) tplId = systemTpl.id;
      }

      if (tplId) {
        const res = await getTemplate(tplId);
        const tplData = res.data;
        setSelectedTemplateId(tplId);

        if (tplData.parsed_structure) {
          const ps = typeof tplData.parsed_structure === 'string'
            ? JSON.parse(tplData.parsed_structure)
            : tplData.parsed_structure;
          const fields = ps.fields || ps;
          setTemplateFields(Array.isArray(fields) ? fields : []);

          // 기본값 세팅
          const defaults = {};
          for (const f of (Array.isArray(fields) ? fields : [])) {
            if (f.key === 'date') defaults[f.key] = new Date().toISOString().split('T')[0];
            else if (f.key === 'author' || f.key === 'manager') defaults[f.key] = user?.name || '';
            else if (f.key === 'department') defaults[f.key] = user?.team || '';
            else defaults[f.key] = '';
          }
          setFormData(defaults);
        }
      }
    } catch (err) {
      console.error('[DocumentGeneratePage] 템플릿 조회 실패:', err);
    }
  };

  const handleFieldChange = (key, value) => {
    setFormData(prev => ({ ...prev, [key]: value }));
  };

  const handleGenerate = async () => {
    if (!selectedTemplate) return;
    setLoading(true);
    try {
      // formData를 텍스트로 조립
      const lines = [];
      for (const field of templateFields) {
        const val = formData[field.key] || '';
        if (val) lines.push(`${field.label}: ${val}`);
      }
      const userInput = lines.join('\n');

      const payload = {
        template_type: selectedTemplate,
        template_id: selectedCustomTemplate?.id || null,
        title: formData.title || '',
        date: formData.date || '',
        attendees: formData.attendees
          ? formData.attendees.split(',').map(s => s.trim()).filter(Boolean)
          : [],
        content: formData.content || userInput,
      };

      const response = await generateDocument(payload);
      const apiData = response.data;

      if (isMeeting) {
        setMeetingResult({
          title: apiData.title || formData.title,
          date: apiData.date || formData.date,
          attendees: apiData.attendees?.length > 0
            ? apiData.attendees
            : (formData.attendees || '').split(',').map(s => s.trim()).filter(Boolean),
          summary: apiData.summary || apiData.data?.summary || '',
          decisions: apiData.decisions || apiData.data?.decisions || [],
          actionItems: apiData.action_items || apiData.data?.action_items || [],
          document_id: apiData.document_id,
        });
      } else {
        // 보고서/제안서: data에서 주요 필드 추출
        const data = apiData.data || apiData;
        const displayFields = Object.entries(data)
          .filter(([k]) => !['title', 'date', 'document_id'].includes(k))
          .filter(([, v]) => v && (typeof v === 'string' ? v.trim() : true))
          .slice(0, 5)
          .map(([k, v]) => ({
            label: k,
            value: Array.isArray(v) ? v.map(i => typeof i === 'object' ? JSON.stringify(i) : i).join('\n') : String(v),
          }));

        setResult({
          title: data.title || formData.title,
          templateType: selectedTemplate,
          fields: displayFields.length > 0
            ? displayFields
            : [{ label: '미리보기', value: apiData.preview || '내용 없음' }],
          document_id: apiData.document_id,
        });
      }
    } catch (err) {
      toast.error('문서 생성 실패: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (format) => {
    const documentId = meetingResult?.document_id || result?.document_id;
    if (!documentId) {
      toast.warning('먼저 문서를 생성해주세요.');
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
      toast.error('다운로드 실패: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleUpload = async (data) => {
    const res = await uploadTemplate(data.file, {
      name: data.name,
      category: data.category,
      description: data.description,
    });
    const uploadResult = res.data;
    toast.success(`"${uploadResult.name}" 템플릿 업로드 완료 (${uploadResult.field_count}개 필드 추출)`);
    fetchCustomTemplates();
  };

  const categoryLabel = {
    meeting_minutes: '회의록',
    report: '보고서',
    proposal: '제안서',
  };

  return (
    <div>
      <header className="bg-surface-main flex flex-col justify-center overflow-hidden h-[100px]">
        <h1 className="font-bold text-2xl">문서 생성</h1>
        <p className="text-neutral-sub text-sm mt-1">템플릿을 선택하고 AI가 내용을 자동으로 채워줍니다</p>
      </header>

      <div className="space-y-6">
        {/* 템플릿 선택 */}
        <TemplateSelector
          selected={selectedTemplate}
          selectedCustomId={selectedCustomTemplate?.id}
          onSelect={handleTemplateSelect}
          onUploadClick={() => setUploadOpen(true)}
          customTemplates={customTemplates}
          onDeleteTemplate={async (id) => {
            try {
              const { deleteTemplate } = await import('../api/documents');
              await deleteTemplate(id);
              toast.success('템플릿이 삭제되었습니다.');
              fetchCustomTemplates();
              if (selectedCustomTemplate?.id === id) {
                setSelectedTemplate(null);
                setSelectedCustomTemplate(null);
                setTemplateFields([]);
                setFormData({});
              }
            } catch (err) {
              toast.error('삭제 실패: ' + (err.response?.data?.detail || err.message));
            }
          }}
        />

        {/* 동적 입력 폼 */}
        {selectedTemplate && templateFields.length > 0 && (
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                {selectedCustomTemplate?.name || categoryLabel[selectedTemplate] || '문서'} 내용 입력
              </div>
            </div>
            <div className="card-body space-y-4">
              <DynamicForm
                fields={templateFields}
                formData={formData}
                onChange={handleFieldChange}
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

        {/* 회의록 결과: MeetingPreview (action_items + Pipeline/Google Tasks) */}
        {isMeeting && <MeetingPreview data={meetingResult} onDownload={handleDownload} loading={loading} />}

        {/* 보고서/제안서 결과 */}
        {!isMeeting && <DocumentPreview data={result} onDownload={handleDownload} loading={loading} />}

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
