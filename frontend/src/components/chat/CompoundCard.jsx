import { Scale, Search, FileText, FileSearch, CalendarPlus, CalendarDays, MessageCircle, Layers, Star } from 'lucide-react';
import MarkdownText from './MarkdownText';
import ScheduleConfirmCard from './ScheduleConfirmCard';
import useChatStore from '../../store/chatStore';

const SUB_CONFIG = {
  judgment:      { icon: Scale,        label: '규정 판단',    border: 'border-l-primary-500', badge: 'bg-primary-50 text-primary-700' },
  doc_retrieve:  { icon: Search,       label: '문서 검색/조회', border: 'border-l-accent-500',   badge: 'bg-accent-50 text-accent-700' },
  doc_search:    { icon: Search,       label: '문서 검색/조회', border: 'border-l-accent-500',   badge: 'bg-accent-50 text-accent-700' },
  doc_generate:  { icon: FileText,     label: '문서 생성',    border: 'border-l-accent-500',   badge: 'bg-accent-50 text-accent-700' },
  doc_summary:   { icon: FileSearch,   label: '문서 요약',    border: 'border-l-accent-500',   badge: 'bg-accent-50 text-accent-700' },
  schedule_add:  { icon: CalendarPlus, label: '일정 추가',    border: 'border-l-success',      badge: 'bg-success-bg text-success' },
  schedule_view: { icon: CalendarDays, label: '일정 조회',    border: 'border-l-success',      badge: 'bg-success-bg text-success' },
  general:       { icon: MessageCircle, label: '일반 질문',   border: 'border-l-neutral-border', badge: 'bg-surface-hover text-neutral-sub' },
};

// schedule_add 관련 응답 타입 (ScheduleConfirmCard로 렌더링)
const SCHEDULE_FORM_TYPES = new Set(['schedule_add', 'schedule_confirm', 'schedule_clarify']);

function TemplatePicker({ templates, templateType, query, onSend }) {
  return (
    <div className="flex flex-col gap-2 max-h-64 overflow-y-auto pr-1">
      {templates.map((tpl, idx) => (
        <button
          key={idx}
          onClick={() => {
            useChatStore.getState().setSelectedTemplate(tpl.template_id, tpl.name, templateType);
            onSend?.(query, { silent: true, forceIntent: 'doc_generate' });
          }}
          className={`p-3 border rounded-xl transition text-left hover:shadow-md hover:border-primary-300 ${tpl.recommended ? 'bg-primary-50/50 border-primary-300' : 'bg-surface-card border-neutral-border hover:bg-primary-50'}`}
        >
          <div className="flex items-center gap-2 mb-1">
            {tpl.is_system ? (
              <Star size={14} className="text-amber-500 fill-amber-500" />
            ) : (
              <FileText size={14} className="text-primary-500" />
            )}
            <span className="font-semibold text-sm text-neutral-main">{tpl.name}</span>
            {tpl.recommended && (
              <span className="px-1.5 py-0.5 text-[10px] bg-amber-100 text-amber-700 rounded font-medium">추천</span>
            )}
            <span className="ml-auto text-[11px] text-neutral-muted">
              {tpl.is_system ? '기본' : '커스텀'}
            </span>
          </div>
          {tpl.field_labels?.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {tpl.field_labels.map((label, i) => (
                <span key={i} className="px-1.5 py-0.5 text-[11px] bg-primary-50 text-primary-700 rounded">
                  {label}
                </span>
              ))}
            </div>
          )}
        </button>
      ))}
    </div>
  );
}

export default function CompoundCard({ data, onSend }) {
  const subResponses = data?.sub_responses || [];

  if (!subResponses.length) return null;

  return (
    <div className="space-y-2.5 mt-1">
      <div className="flex items-center gap-1.5 text-xs text-neutral-sub">
        <Layers size={14} />
        <span>{subResponses.length}개 요청을 처리했습니다</span>
      </div>

      {subResponses.map((sub, i) => {
        const intent = sub.intent || sub.response?.type || 'general';
        const respType = sub.response?.type || '';
        const config = SUB_CONFIG[intent] || SUB_CONFIG.general;
        const Icon = config.icon;
        const message = sub.response?.message || '';

        // schedule_add: 일정 등록 폼(ScheduleConfirmCard) 렌더링
        const isScheduleForm = intent === 'schedule_add' || SCHEDULE_FORM_TYPES.has(respType);
        const scheduleData = sub.response?.schedule;

        // template_pick: 양식 선택 버튼 렌더링
        const isTemplatePick = respType === 'template_pick';
        const templates = sub.response?.templates || [];

        return (
          <div
            key={i}
            className={`bg-surface-sub rounded-lg border-l-[3px] ${config.border} p-3.5`}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold ${config.badge}`}>
                <Icon size={12} />
                {config.label}
              </span>
              <span className="text-[11px] text-neutral-muted truncate">
                &ldquo;{sub.query}&rdquo;
              </span>
            </div>

            {isScheduleForm ? (
              <ScheduleConfirmCard initialData={scheduleData || {}} />
            ) : isTemplatePick ? (
              <div className="space-y-2">
                {message && (
                  <div className="text-sm text-neutral-main">{message}</div>
                )}
                <TemplatePicker
                  templates={templates}
                  templateType={sub.response?.template_type}
                  query={sub.query}
                  onSend={onSend}
                />
              </div>
            ) : message ? (
              <div className="text-sm leading-relaxed text-neutral-main">
                <MarkdownText>{message}</MarkdownText>
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
