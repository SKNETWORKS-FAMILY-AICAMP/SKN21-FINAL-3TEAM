import { Scale, Search, FileText, FileSearch, HelpCircle, CalendarPlus, CalendarDays, MessageCircle } from 'lucide-react';

const agentConfig = {
  judgment: { icon: Scale, label: '규정 판단 Agent', color: 'text-primary-700 bg-primary-50' },
  doc_search: { icon: Search, label: '문서 검색 Agent', color: 'text-accent-700 bg-accent-50' },
  doc_generate: { icon: FileText, label: '문서 생성 Agent', color: 'text-accent-700 bg-accent-50' },
  doc_summary: { icon: FileSearch, label: '문서 요약 Agent', color: 'text-accent-700 bg-accent-50' },
  doc_qa: { icon: HelpCircle, label: '문서 QA Agent', color: 'text-accent-700 bg-accent-50' },
  schedule_add: { icon: CalendarPlus, label: '일정 추가 Agent', color: 'text-success bg-success-bg' },
  schedule_view: { icon: CalendarDays, label: '일정 조회 Agent', color: 'text-success bg-success-bg' },
  general: { icon: MessageCircle, label: '일반 질문 Agent', color: 'text-neutral-sub bg-surface-hover' },
};

export default function AgentIndicator({ intent, status }) {
  const config = agentConfig[intent] || agentConfig.general;
  const Icon = config.icon;

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-2 rounded-sm text-[0.8125rem] font-medium mb-3 ${config.color}`}>
      <Icon size={16} />
      <span>{config.label}</span>
      {status && (
        <>
          <span className="text-neutral-muted">·</span>
          <span className="flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-current" />
            </span>
            {status}
          </span>
        </>
      )}
    </div>
  );
}
