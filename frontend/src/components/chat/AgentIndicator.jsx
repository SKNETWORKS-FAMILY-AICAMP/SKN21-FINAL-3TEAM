import { Scale, Search, FileText, FileSearch, HelpCircle, CalendarPlus, CalendarDays, MessageCircle } from 'lucide-react';

const agentConfig = {
  judgment: { icon: Scale, label: '규정 판단 Agent', color: 'text-primary-700 bg-primary-50' },
  doc_retrieve: { icon: Search, label: '문서 검색/조회 Agent', color: 'text-accent-700 bg-accent-50' },
  doc_search: { icon: Search, label: '문서 검색/조회 Agent', color: 'text-accent-700 bg-accent-50' },
  doc_generate: { icon: FileText, label: '문서 생성 Agent', color: 'text-accent-700 bg-accent-50' },
  doc_summary: { icon: FileSearch, label: '문서 요약 Agent', color: 'text-accent-700 bg-accent-50' },
  schedule_add: { icon: CalendarPlus, label: '일정 추가 Agent', color: 'text-success bg-success-bg' },
  schedule_view: { icon: CalendarDays, label: '일정 조회 Agent', color: 'text-success bg-success-bg' },
  general: { icon: MessageCircle, label: '일반 질문 Agent', color: 'text-neutral-sub bg-surface-hover' },
};

// 모델명을 사용자 친화적 이름으로 변환
const formatModelName = (name) => {
  if (!name) return null;
  const lower = name.toLowerCase();
  if (lower.includes('kanana') || lower.includes('v1_judgment') || lower.includes('v2_')) return 'Kanana-1.5-8B';
  if (lower.includes('gpt-4o-mini')) return 'GPT-4o-mini';
  if (lower.includes('gpt-4o')) return 'GPT-4o';
  if (lower.includes('gpt')) return name;
  return name;
};

// sLLM 여부 판별
const isSllmModel = (name) => {
  if (!name) return false;
  const lower = name.toLowerCase();
  return lower.includes('kanana') || lower.includes('v1_') || lower.includes('v2_');
};

export default function AgentIndicator({ intent, status, modelName }) {
  const config = agentConfig[intent] || agentConfig.general;
  const Icon = config.icon;
  const displayName = formatModelName(modelName);
  const isFallback = modelName && modelName.includes('(fallback)');
  const sllm = isSllmModel(modelName);

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-2 rounded-sm text-[0.8125rem] font-medium mb-3 ${config.color}`}>
      <Icon size={16} />
      <span>{config.label}</span>
      {displayName && (
        <>
          <span className="text-neutral-muted">·</span>
          <span className={`text-[0.6875rem] font-normal px-1.5 py-0.5 rounded-full ${
            sllm ? 'bg-emerald-100 text-emerald-700' : isFallback ? 'bg-amber-100 text-amber-700' : 'opacity-70'
          }`}>
            {displayName}{isFallback ? ' (fallback)' : ''}
          </span>
        </>
      )}
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
