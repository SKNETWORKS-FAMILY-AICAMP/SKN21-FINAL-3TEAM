import { Scale, Search, FileText, FileSearch, CalendarPlus, CalendarDays, MessageCircle, Layers } from 'lucide-react';
import MarkdownText from './MarkdownText';
import ScheduleConfirmCard from './ScheduleConfirmCard';

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

export default function CompoundCard({ data }) {
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
