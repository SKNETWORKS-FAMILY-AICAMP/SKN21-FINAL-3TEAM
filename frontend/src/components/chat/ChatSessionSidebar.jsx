import useChatStore from '../../store/chatStore';

export default function ChatSessionSidebar() {
  const { sessions, activeSessionId, switchSession, deleteSession, clearMessages } = useChatStore();

  const handleNewChat = () => {
    clearMessages();
  };

  const formatTime = (isoString) => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return '방금 전';
    if (diffMins < 60) return `${diffMins}분 전`;
    if (diffHours < 24) return `${diffHours}시간 전`;
    return `${diffDays}일 전`;
  };

  return (
    <div className="w-64 border-r border-neutral-divider bg-surface-card flex flex-col h-full">
      <div className="p-4 border-b border-neutral-divider">
        <button
          onClick={handleNewChat}
          className="w-full btn-primary text-sm"
        >
          ➕ 새 대화
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {sessions.length === 0 && (
          <div className="text-center text-neutral-muted text-xs mt-8">
            대화 기록이 없습니다
          </div>
        )}
        {sessions.map((session) => (
          <div
            key={session.id}
            className={`
              p-3 rounded-md cursor-pointer transition border
              ${activeSessionId === session.id
                ? 'bg-primary-50 border-primary-300'
                : 'bg-surface-hover border-transparent hover:border-neutral-border'
              }
            `}
            onClick={() => switchSession(session.id)}
          >
            <div className="flex justify-between items-start mb-1">
              <div className="text-[0.8125rem] font-semibold text-neutral-main line-clamp-1 flex-1">
                {session.name}
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteSession(session.id);
                }}
                className="text-neutral-muted hover:text-error text-xs ml-2"
                aria-label="삭제"
              >
                ✕
              </button>
            </div>
            <div className="flex items-center gap-2 text-xs text-neutral-sub">
              <span>💬 {session.messages.length}개</span>
              <span>•</span>
              <span>{formatTime(session.createdAt)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
