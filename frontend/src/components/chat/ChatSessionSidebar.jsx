import useChatStore from '../../store/chatStore';

function formatTime(ts) {
  const d = new Date(ts);
  const now = new Date();
  const diffDays = Math.floor((now - d) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });
  if (diffDays === 1) return '어제';
  if (diffDays < 7) return `${diffDays}일 전`;
  return d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
}

export default function ChatSessionSidebar({ isOpen }) {
  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const createSession = useChatStore((s) => s.createSession);
  const switchSession = useChatStore((s) => s.switchSession);
  const deleteSession = useChatStore((s) => s.deleteSession);

  if (!isOpen) return null;

  return (
    <div className="w-[320px] border-r border-neutral-divider bg-surface-card flex flex-col flex-shrink-0 h-full">
      <div className="px-4 py-3 border-b border-neutral-divider flex items-center justify-between">
        <span className="text-sm font-semibold text-neutral-main">대화 목록</span>
        <button
          onClick={createSession}
          className="text-xs px-2.5 py-1 rounded-md bg-primary-700 text-white hover:bg-primary-900 transition"
        >
          + 새 대화
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <div className="p-4 text-center text-xs text-neutral-muted">
            대화를 시작하면 자동으로 저장됩니다.
          </div>
        ) : (
          sessions.map((session) => (
            <div
              key={session.id}
              onClick={() => switchSession(session.id)}
              className={`group flex items-center gap-2 px-4 py-3 cursor-pointer border-b border-neutral-divider transition ${
                session.id === activeSessionId
                  ? 'bg-primary-50 border-l-2 border-l-primary-700'
                  : 'hover:bg-surface-hover border-l-2 border-l-transparent'
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className={`text-sm truncate ${session.id === activeSessionId ? 'font-semibold text-primary-700' : 'text-neutral-main'}`}>
                  {session.name || '새 대화'}
                </div>
                <div className="text-[0.6875rem] text-neutral-muted mt-0.5">
                  {session.messages?.length || 0}개 메시지 · {formatTime(session.updatedAt)}
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteSession(session.id);
                }}
                className="opacity-0 group-hover:opacity-100 text-neutral-muted hover:text-error transition p-1"
                title="삭제"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
