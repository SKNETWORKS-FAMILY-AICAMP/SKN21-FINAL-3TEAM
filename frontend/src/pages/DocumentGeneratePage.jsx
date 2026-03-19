import { useState, useEffect, useMemo, useRef } from 'react';
import { ChevronDown, X } from 'lucide-react';
import useAuthStore from '../store/authStore';
import client from '../api/client';
import TemplateSelector from '../components/documents/TemplateSelector';
import TemplateUploadDialog from '../components/documents/TemplateUploadDialog';
import DocumentPreview from '../components/documents/DocumentPreview';
import MeetingPreview from '../components/meetings/MeetingPreview';
import { generateDocument, downloadDocument, uploadTemplate, listTemplates, getTemplate, fillFields } from '../api/documents';
import DatePicker from '../components/common/DatePicker';
import { toast } from '../store/toastStore';


/**
 * 팀 + 참석자 선택 UI (회의록 전용)
 * — DB에서 전체 멤버를 불러와 팀별 필터링 + 체크박스 선택
 */
function TeamDropdown({ user, value, onChange }) {
  const [allMembers, setAllMembers] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    client.get('/auth/all-members')
      .then(res => setAllMembers(res.data || []))
      .catch(() => setAllMembers([]));
  }, []);

  useEffect(() => {
    const handler = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const teams = useMemo(() => {
    const set = new Set(allMembers.map(m => m.team).filter(Boolean));
    if (user?.team) set.add(user.team);
    return [...set].sort();
  }, [allMembers, user]);

  return (
    <div>
      <label className="block text-[0.8125rem] font-semibold mb-1.5">팀</label>
      <div ref={ref} className="relative">
        <button
          type="button"
          onClick={() => setOpen(v => !v)}
          className={`w-full flex items-center justify-between px-3.5 py-2.5 border rounded-md text-sm transition ${open
            ? 'border-primary-500 bg-primary-50 text-primary-700'
            : 'border-neutral-border bg-surface-card text-neutral-main hover:border-primary-300'
          }`}
        >
          <span className={value ? '' : 'text-neutral-400'}>{value || '팀 선택'}</span>
          <ChevronDown size={14} className={`text-neutral-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
        </button>
        {open && (
          <div className="absolute top-full mt-1 left-0 right-0 z-50 bg-surface-card border border-neutral-border rounded-md shadow-lg overflow-hidden">
            {teams.map(t => (
              <button
                key={t}
                type="button"
                onClick={() => { onChange(t); setOpen(false); }}
                className={`w-full text-left px-3.5 py-2.5 text-sm transition ${t === value
                  ? 'bg-primary-100 text-primary-700 font-semibold'
                  : 'text-neutral-main hover:bg-primary-50'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TeamAttendeePicker({ user, selectedTeam, onTeamChange, selectedAttendees, onAttendeesChange }) {
  const [allMembers, setAllMembers] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [teamOpen, setTeamOpen] = useState(false);
  const teamRef = useRef(null);

  useEffect(() => {
    client.get('/auth/all-members')
      .then(res => {
        const members = res.data || [];
        if (user) {
          const hasSelf = members.some(m => m.id === user.id);
          if (!hasSelf) {
            members.push({ id: user.id, name: user.name, team: user.team, avatar: user.avatar });
          }
        }
        setAllMembers(members);
      })
      .catch(() => setAllMembers([]));
  }, [user]);

  useEffect(() => {
    const handler = (e) => { if (!teamRef.current?.contains(e.target)) setTeamOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const teams = useMemo(() => {
    const set = new Set(allMembers.map(m => m.team).filter(Boolean));
    if (user?.team) set.add(user.team);
    return [...set].sort();
  }, [allMembers, user]);

  const teamMembers = useMemo(() => {
    return allMembers.filter(m => m.team === selectedTeam);
  }, [allMembers, selectedTeam]);

  const toggleAttendee = (name) => {
    const next = selectedAttendees.includes(name)
      ? selectedAttendees.filter(n => n !== name)
      : [...selectedAttendees, name];
    onAttendeesChange(next);
  };

  const removeAttendee = (name) => {
    onAttendeesChange(selectedAttendees.filter(n => n !== name));
  };

  return (
    <div className="grid grid-cols-2 gap-3">
      {/* 팀 선택 */}
      <div>
        <label className="block text-[0.8125rem] font-semibold mb-1.5">팀</label>
        <div ref={teamRef} className="relative">
          <button
            type="button"
            onClick={() => setTeamOpen(v => !v)}
            className={`w-full flex items-center justify-between px-3.5 py-2.5 border rounded-md text-sm transition ${teamOpen
              ? 'border-primary-500 bg-primary-50 text-primary-700'
              : 'border-neutral-border bg-surface-card text-neutral-main hover:border-primary-300'
            }`}
          >
            <span className={selectedTeam ? '' : 'text-neutral-400'}>{selectedTeam || '팀 선택'}</span>
            <ChevronDown size={14} className={`text-neutral-400 transition-transform duration-200 ${teamOpen ? 'rotate-180' : ''}`} />
          </button>
          {teamOpen && (
            <div className="absolute top-full mt-1 left-0 right-0 z-50 bg-surface-card border border-neutral-border rounded-md shadow-lg overflow-hidden">
              {teams.map(t => (
                <button
                  key={t}
                  type="button"
                  onClick={() => { onTeamChange(t); setTeamOpen(false); }}
                  className={`w-full text-left px-3.5 py-2.5 text-sm transition ${t === selectedTeam
                    ? 'bg-primary-100 text-primary-700 font-semibold'
                    : 'text-neutral-main hover:bg-primary-50'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 참석자 선택 */}
      <div>
        <label className="block text-[0.8125rem] font-semibold mb-1.5">참석자</label>
        <div className="relative">
          <div
            onClick={() => setShowDropdown(prev => !prev)}
            className="w-full min-h-[42px] px-3.5 py-2 border border-neutral-border rounded-md text-sm outline-none focus-within:border-primary-500 cursor-pointer flex flex-wrap items-center gap-1.5"
          >
            {selectedAttendees.length > 0 ? (
              selectedAttendees.map(name => (
                <span key={name} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary-50 text-primary-700 text-xs font-medium">
                  {name}
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); removeAttendee(name); }}
                    className="hover:text-primary-900 transition-colors"
                  >
                    <X size={12} />
                  </button>
                </span>
              ))
            ) : (
              <span className="text-neutral-400 text-sm">팀원을 선택하세요</span>
            )}
          </div>

          {showDropdown && (
            <>
              <div className="fixed inset-0 z-10" onClick={(e) => { e.stopPropagation(); setShowDropdown(false); }} />
              <div
                className="absolute top-full left-0 right-0 mt-1 z-20 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 rounded-lg shadow-xl max-h-[200px] overflow-y-auto"
                onClick={(e) => e.stopPropagation()}
              >
                {teamMembers.length > 0 ? (
                  teamMembers.map(m => {
                    const isSelected = selectedAttendees.includes(m.name);
                    return (
                      <div
                        key={m.id}
                        onClick={() => toggleAttendee(m.name)}
                        className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm cursor-pointer hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors ${isSelected ? 'bg-primary-50/50 dark:bg-primary-900/10' : ''}`}
                      >
                        <div className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 transition-all ${isSelected ? 'border-primary-700 bg-primary-700' : 'border-neutral-300 dark:border-neutral-500'}`}>
                          {isSelected && (
                            <svg width="10" height="10" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                          )}
                        </div>
                        <img
                          src={m.avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(m.name)}`}
                          alt={m.name}
                          className="w-7 h-7 rounded-full object-cover bg-neutral-100 dark:bg-neutral-700 flex-shrink-0"
                        />
                        <span className={`${isSelected ? 'font-semibold text-primary-700' : 'text-neutral-700 dark:text-neutral-300'}`}>{m.name}</span>
                      </div>
                    );
                  })
                ) : (
                  <div className="px-4 py-3 text-sm text-neutral-400 text-center">
                    {selectedTeam ? '팀원이 없습니다' : '팀을 먼저 선택하세요'}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}


// 카테고리별 폼에 표시할 필드 키 (form 플래그 없는 커스텀 템플릿용 fallback)
const FORM_KEYS = {
  meeting_minutes: ['title', 'date', 'attendees', 'team', 'content'],
  report: ['title', 'date', 'author', 'department', 'report_to', 'content'],
  proposal: ['title', 'date', 'company', 'manager', 'submit_to', 'content'],
};

// 기본 템플릿 필드 정의 (DB에 layout/type 정보가 없을 때 fallback)
const DEFAULT_TEMPLATE_FIELDS = {
  meeting_minutes: [
    { key: 'title', label: '회의 제목', type: 'text', layout: 'half', form: true, required: true },
    { key: 'date', label: '날짜', type: 'date', layout: 'half', form: true },
    { key: '_team_attendee', label: '팀/참석자', type: 'team_attendee', form: true },
    { key: 'content', label: '회의 내용', type: 'textarea', form: true },
  ],
  report: [
    { key: 'title', label: '보고서 제목', type: 'text', layout: 'half', form: true, required: true },
    { key: 'date', label: '날짜', type: 'date', layout: 'half', form: true },
    { key: 'department', label: '팀', type: 'team_dropdown', layout: 'half', form: true },
    { key: 'author', label: '작성자', type: 'text', layout: 'half', form: true },
    { key: 'report_to', label: '보고 대상', type: 'text', form: true },
    { key: 'content', label: '보고 내용', type: 'textarea', form: true },
  ],
  proposal: [
    { key: 'title', label: '제안서 제목', type: 'text', layout: 'half', form: true, required: true },
    { key: 'date', label: '제출일', type: 'date', layout: 'half', form: true },
    { key: 'company', label: '회사명', type: 'text', layout: 'half', form: true },
    { key: 'manager', label: '담당자', type: 'text', layout: 'half', form: true },
    { key: 'submit_to', label: '제출처', type: 'text', form: true },
    { key: 'content', label: '제안 내용', type: 'textarea', form: true },
  ],
};

/**
 * 동적 폼 렌더링 — parsed_structure.fields 기반
 * attendees/team 필드는 회의록일 때 TeamAttendeePicker로 대체되므로 스킵
 * form: false 필드는 LLM이 생성하므로 UI에 표시하지 않음
 */
function DynamicForm({ fields, formData, onChange, skipKeys = [], category, user, selectedTeam, onTeamChange, selectedAttendees, onAttendeesChange }) {
  if (!fields || fields.length === 0) return null;

  const inputClass = 'w-full px-3.5 py-2.5 border border-neutral-border rounded-md text-sm outline-none focus:border-primary-500';

  const filteredFields = fields
    .filter(f => !skipKeys.includes(f.key))
    .filter(f => {
      if (f.form === false) return false;
      if (f.form === true) return true;
      const formKeys = FORM_KEYS[category] || ['title', 'date', 'content'];
      return formKeys.includes(f.key);
    });
  if (filteredFields.length === 0) return null;

  // layout: 'half' 필드들을 2열 그리드로 묶기
  const rows = [];
  let i = 0;
  while (i < filteredFields.length) {
    const field = filteredFields[i];
    if (field.layout === 'half' && i + 1 < filteredFields.length && filteredFields[i + 1].layout === 'half') {
      rows.push([field, filteredFields[i + 1]]);
      i += 2;
    } else {
      rows.push([field]);
      i += 1;
    }
  }

  const renderField = (field) => {
    const value = formData[field.key] || '';

    // DatePicker
    if (field.type === 'date') {
      return (
        <div key={field.key}>
          <label className="block text-[0.8125rem] font-semibold mb-1.5">
            {field.label}{field.required && <span className="text-red-500 ml-0.5">*</span>}
          </label>
          <DatePicker
            value={value}
            onChange={(v) => onChange(field.key, v)}
            placeholder="날짜 선택"
          />
        </div>
      );
    }

    // 팀 드롭다운
    if (field.type === 'team_dropdown') {
      return (
        <TeamDropdown
          key={field.key}
          user={user}
          value={value}
          onChange={(v) => onChange(field.key, v)}
        />
      );
    }

    // 팀 + 참석자 (회의록 전용)
    if (field.type === 'team_attendee') {
      return (
        <TeamAttendeePicker
          key={field.key}
          user={user}
          selectedTeam={selectedTeam}
          onTeamChange={onTeamChange}
          selectedAttendees={selectedAttendees}
          onAttendeesChange={onAttendeesChange}
        />
      );
    }

    // textarea
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
            rows={10}
            onInput={(e) => { e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 400) + 'px'; }}
            className={`${inputClass} resize-none overflow-y-auto max-h-[400px]`}
          />
        </div>
      );
    }

    // list
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
  };

  return (
    <div className="space-y-4">
      {rows.map((row, idx) =>
        row.length === 2 ? (
          <div key={idx} className="grid grid-cols-2 gap-3">
            {renderField(row[0])}
            {renderField(row[1])}
          </div>
        ) : row[0].type === 'team_attendee' ? (
          renderField(row[0])
        ) : (
          <div key={idx}>{renderField(row[0])}</div>
        )
      )}
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

  // 회의록 전용: 팀 + 참석자
  const [selectedTeam, setSelectedTeam] = useState(user?.team || '');
  const [selectedAttendees, setSelectedAttendees] = useState([]);

  // 커스텀 템플릿: 자연어 입력 + AI 채우기
  const [freeText, setFreeText] = useState('');
  const [filling, setFilling] = useState(false);
  const [filled, setFilled] = useState(false);  // AI가 채웠는지 여부
  const isCustom = !!selectedCustomTemplate;

  const fetchCustomTemplates = () => {
    listTemplates()
      .then(res => setCustomTemplates((res.data || []).filter(t => !t.is_system)))
      .catch(() => setCustomTemplates([]));
  };

  useEffect(() => { fetchCustomTemplates(); }, []);

  // 회의록 카테고리이거나, 양식 필드에 attendees/team이 있으면 팀+참석자 UI 표시
  const hasAttendeeFields = templateFields.some(f => f.key === 'attendees' || f.key === 'team');
  const isMeeting = selectedTemplate === 'meeting_minutes' || hasAttendeeFields;

  // 템플릿 선택 → parsed_structure 로드 → 동적 폼 초기화
  const handleTemplateSelect = async (template, customTpl = null) => {
    // 스크롤 위치 보존
    const scrollY = window.scrollY;
    setSelectedTemplate(template);
    setSelectedCustomTemplate(customTpl);
    setResult(null);
    setMeetingResult(null);
    setFormData({ date: new Date().toISOString().split('T')[0] });
    setTemplateFields([]);
    requestAnimationFrame(() => window.scrollTo(0, scrollY));
    setSelectedTeam(user?.team || '');
    setSelectedAttendees([]);
    setFreeText('');
    setFilled(false);

    const templateId = customTpl?.id;
    setSelectedTemplateId(templateId || null);

    try {
      let tplId = templateId;
      if (!tplId) {
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

          const defaults = { date: new Date().toISOString().split('T')[0] };
          const formKeys = FORM_KEYS[template] || ['title', 'date', 'content'];
          for (const f of (Array.isArray(fields) ? fields : [])) {
            // form: false 필드는 폼 초기값에서 제외 (LLM이 생성)
            if (f.form === false) continue;
            if (f.form !== true && !formKeys.includes(f.key)) continue;
            if (f.key === 'date' || f.key === 'submit_date') defaults[f.key] = new Date().toISOString().split('T')[0];
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

  /** 커스텀 템플릿: AI 필드 채우기 */
  const handleFillFields = async () => {
    if (!selectedTemplateId || !freeText.trim()) return;
    setFilling(true);
    try {
      const response = await fillFields({
        template_id: selectedTemplateId,
        content: freeText,
      });
      const apiData = response.data;
      const data = apiData.data || {};

      // AI가 채운 값을 폼에 반영 (빈 값은 제외, 기존 사용자 입력 보존)
      setFormData(prev => {
        const next = { ...prev };
        for (const [key, val] of Object.entries(data)) {
          if (val && val !== '' && (!Array.isArray(val) || val.length > 0)) {
            next[key] = val;
          }
        }
        return next;
      });

      // AI가 채운 필드가 있으면 templateFields도 업데이트 (fields 정보 포함)
      if (apiData.fields) {
        setTemplateFields(apiData.fields);
      }

      setFilled(true);
      toast.success(`AI가 필드를 채웠습니다. 확인 후 수정할 수 있습니다.`);
    } catch (err) {
      toast.error('AI 채우기 실패: ' + (err.response?.data?.detail || err.message));
    } finally {
      setFilling(false);
    }
  };

  /** 통합 생성 핸들러 */
  const handleGenerate = async () => {
    if (!selectedTemplate) return;
    setLoading(true);
    try {
      // 폼 데이터를 fields_data JSON으로 전달 (서버에서 서술형 변환)
      const fieldsData = { ...formData };
      if (isMeeting) {
        fieldsData.attendees = selectedAttendees;
        fieldsData.team = selectedTeam;
      }

      const payload = {
        template_type: selectedTemplate,
        template_id: selectedTemplateId || null,
        fields_data: fieldsData,
        content: formData.content || '',
      };

      const response = await generateDocument(payload);
      const apiData = response.data;

      const data = apiData.data || {};

      if (isMeeting) {
        setMeetingResult({
          title: data.title || formData.title,
          date: data.date || formData.date,
          attendees: data.attendees?.length > 0
            ? data.attendees
            : fieldsData.attendees || [],
          summary: data.summary || '',
          decisions: data.decisions || [],
          actionItems: data.action_items || [],
          document_id: apiData.document_id,
          model_name: apiData.model_name || '',
        });
      } else {
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
          model_name: apiData.model_name || '',
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

  // 기본 필드 + DB 추가 필드 머지
  const mergedFields = useMemo(() => {
    const defaults = DEFAULT_TEMPLATE_FIELDS[selectedTemplate];
    if (!defaults) return templateFields; // 커스텀 템플릿은 DB 필드 그대로

    const defaultKeys = new Set(defaults.map(f => f.key));
    // 기본 필드와 중복되는 DB 필드 제외 (예: submit_date는 date로 대체됨)
    const skipExtras = new Set([...defaultKeys, 'submit_date']);
    const extras = templateFields.filter(f => !skipExtras.has(f.key) && f.form !== false);
    return [...defaults, ...extras];
  }, [selectedTemplate, templateFields]);

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

        {/* 커스텀 템플릿: 자연어 입력 + AI 채우기 + 편집 폼 */}
        {isCustom && selectedTemplate && templateFields.length > 0 && (
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                {selectedCustomTemplate?.name || '커스텀 문서'} 작성
              </div>
            </div>
            <div className="card-body space-y-5">
              {/* 자연어 입력 영역 */}
              <div>
                <label className="block text-[0.8125rem] font-semibold mb-1.5">내용을 자유롭게 입력하세요</label>
                <textarea
                  value={freeText}
                  onChange={(e) => setFreeText(e.target.value)}
                  placeholder="예: 오늘 오후 3시에 회의실B에서 김철수, 이영희 참석해서 신규 프로젝트 킥오프 회의했어..."
                  rows={5}
                  onInput={(e) => { e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 300) + 'px'; }}
                  className="w-full px-3.5 py-2.5 border border-neutral-border rounded-md text-sm outline-none focus:border-primary-500 resize-none overflow-y-auto max-h-[300px]"
                />
                <div className="flex justify-end mt-2">
                  <button
                    onClick={handleFillFields}
                    disabled={filling || !freeText.trim()}
                    className="btn-primary text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {filling ? 'AI 분석 중...' : 'AI가 필드 채우기'}
                  </button>
                </div>
              </div>

              {/* 구분선 */}
              {filled && (
                <div className="flex items-center gap-3 text-xs text-neutral-muted">
                  <div className="flex-1 border-t border-neutral-divider" />
                  <span>AI가 채운 결과 — 수정 후 문서를 생성하세요</span>
                  <div className="flex-1 border-t border-neutral-divider" />
                </div>
              )}

              {/* 모든 필드 편집 폼 (AI 채움 여부 무관하게 표시) */}
              <div className="space-y-3">
                {templateFields.map((field) => {
                  const value = formData[field.key] ?? '';
                  const isFilled = filled && value !== '' && (!Array.isArray(value) || value.length > 0);
                  const formatValue = (v) => {
                    if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
                      return Object.values(v).filter(Boolean).join(' / ');
                    }
                    return String(v);
                  };
                  const displayValue = Array.isArray(value)
                    ? value.map((v, i) => `${i + 1}. ${formatValue(v)}`).join('\n')
                    : (typeof value === 'object' && value !== null ? formatValue(value) : String(value));

                  return (
                    <div key={field.key}>
                      <label className="block text-[0.8125rem] font-semibold mb-1">
                        {field.label || field.key}
                        {isFilled && <span className="ml-1.5 text-[0.6875rem] font-normal text-primary-600">AI</span>}
                        {!isFilled && filled && <span className="ml-1.5 text-[0.6875rem] font-normal text-neutral-400">직접 입력</span>}
                      </label>
                      {(field.description || '').includes('배열') || (field.description || '').includes('목록') || (field.description || '').includes('문장') || displayValue.length > 80 ? (
                        <textarea
                          value={displayValue}
                          onChange={(e) => handleFieldChange(field.key, e.target.value)}
                          rows={3}
                          onInput={(e) => { e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'; }}
                          className={`w-full px-3.5 py-2.5 border rounded-md text-sm outline-none focus:border-primary-500 resize-none overflow-y-auto max-h-[200px] ${isFilled ? 'border-primary-200 bg-primary-50/30' : 'border-neutral-border'}`}
                        />
                      ) : (
                        <input
                          value={displayValue}
                          onChange={(e) => handleFieldChange(field.key, e.target.value)}
                          placeholder={field.description || `${field.label || field.key}을(를) 입력하세요`}
                          className={`w-full px-3.5 py-2.5 border rounded-md text-sm outline-none focus:border-primary-500 ${isFilled ? 'border-primary-200 bg-primary-50/30' : 'border-neutral-border'}`}
                        />
                      )}
                    </div>
                  );
                })}
              </div>

              {/* 문서 생성 버튼 */}
              <div className="flex justify-end">
                <button
                  onClick={handleGenerate}
                  disabled={loading}
                  className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? 'AI 생성 중...' : '문서 생성'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 시스템 템플릿: 기존 입력 폼 */}
        {!isCustom && selectedTemplate && (isMeeting || templateFields.length > 0) && (
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                {categoryLabel[selectedTemplate] || '문서'} 내용 입력
              </div>
            </div>
            <div className="card-body space-y-4">
              <DynamicForm
                fields={mergedFields}
                formData={formData}
                onChange={handleFieldChange}
                skipKeys={[]}
                category={selectedTemplate}
                user={user}
                selectedTeam={selectedTeam}
                onTeamChange={setSelectedTeam}
                selectedAttendees={selectedAttendees}
                onAttendeesChange={setSelectedAttendees}
              />

              <div className="flex justify-end">
                <button
                  onClick={handleGenerate}
                  disabled={loading}
                  className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? 'AI 생성 중...' : isMeeting ? 'AI 회의록 생성' : 'AI 문서 생성'}
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
