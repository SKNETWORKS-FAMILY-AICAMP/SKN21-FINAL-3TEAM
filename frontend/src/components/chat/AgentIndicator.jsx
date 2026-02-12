const agentConfig = {
  judgment: { icon: '⚖️', label: '규정 판단 Agent', color: 'text-primary-700 bg-primary-50' },
  doc_search: { icon: '🔍', label: '문서 검색 Agent', color: 'text-accent-700 bg-accent-50' },
  doc_generate: { icon: '📄', label: '문서 생성 Agent', color: 'text-accent-700 bg-accent-50' },
  meeting_generate: { icon: '📋', label: '회의록 생성 Agent', color: 'text-primary-700 bg-primary-50' },
  schedule_add: { icon: '📅', label: '일정 추가 Agent', color: 'text-success bg-success-bg' },
  schedule_view: { icon: '📅', label: '일정 조회 Agent', color: 'text-success bg-success-bg' },
  general: { icon: '💬', label: '일반 질문 Agent', color: 'text-neutral-sub bg-surface-hover' },
};

export default function AgentIndicator({ intent, status }) {
  const config = agentConfig[intent] || agentConfig.general;

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-2 rounded-sm text-[0.8125rem] font-medium mb-3 ${config.color}`}>
      <span>{config.icon}</span>
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
