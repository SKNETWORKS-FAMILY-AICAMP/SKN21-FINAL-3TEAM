import { useState, useRef, useEffect } from 'react';
import { MessageSquare } from 'lucide-react';
import useChatStore from '../../store/chatStore';
import EmptyState from '../common/EmptyState';

const KST = 'Asia/Seoul';

function formatTime(isoStr) {
  // 서버가 UTC naive datetime을 반환하므로 Z를 붙여 UTC로 명시
  const utcStr = isoStr.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(isoStr) ? isoStr : isoStr + 'Z';
  const d = new Date(utcStr);
  const now = new Date();
  // KST 기준 날짜 차이 계산
  const toKSTMidnight = (dt) => {
    const kst = new Date(dt.toLocaleString('en-US', { timeZone: KST }));
    kst.setHours(0, 0, 0, 0);
    return kst;
  };
  const diffDays = Math.round((toKSTMidnight(now) - toKSTMidnight(d)) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: KST });
  if (diffDays === 1) return '어제';
  if (diffDays < 7) return `${diffDays}일 전`;
  return d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric', timeZone: KST });
}

export default function ChatSessionSidebar({ isOpen }) {
  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const createSession = useChatStore((s) => s.createSession);
  const switchSession = useChatStore((s) => s.switchSession);
  const deleteSession = useChatStore((s) => s.deleteSession);
  const renameSessionById = useChatStore((s) => s.renameSessionById);

  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState('');
  const inputRef = useRef(null);

  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  const startEdit = (e, session) => {
    e.stopPropagation();
    setEditingId(session.session_id);
    setEditingName(session.name || '새 대화');
  };

  const commitEdit = () => {
    if (editingId) {
      renameSessionById(editingId, editingName);
      setEditingId(null);
    }
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditingName('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') commitEdit();
    if (e.key === 'Escape') cancelEdit();
  };

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
          <EmptyState icon={MessageSquare} title="대화가 없습니다" description="대화를 시작하면 자동으로 저장됩니다" />
        ) : (
          sessions.map((session) => {
            const isActive = session.session_id === activeSessionId;
            const isEditing = editingId === session.session_id;

            return (
              <div
                key={session.session_id}
                onClick={() => !isEditing && switchSession(session.session_id)}
                className={`group flex items-center gap-2 px-4 py-3 cursor-pointer border-b border-neutral-divider transition ${
                  isActive
                    ? 'bg-primary-50 border-l-2 border-l-primary-700'
                    : 'hover:bg-surface-hover border-l-2 border-l-transparent'
                }`}
              >
                <div className="flex-1 min-w-0">
                  {isEditing ? (
                    <input
                      ref={inputRef}
                      value={editingName}
                      onChange={(e) => setEditingName(e.target.value)}
                      onBlur={commitEdit}
                      onKeyDown={handleKeyDown}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full text-sm border border-primary-300 rounded px-1.5 py-0.5 outline-none focus:ring-1 focus:ring-primary-500 bg-white text-neutral-main"
                    />
                  ) : (
                    <>
                      <div className={`text-sm truncate ${isActive ? 'font-semibold text-primary-700' : 'text-neutral-main'}`}>
                        {session.name || '새 대화'}
                      </div>
                      <div className="text-[0.6875rem] text-neutral-muted mt-0.5">
                        {formatTime(session.updated_at)}
                      </div>
                    </>
                  )}
                </div>

                {!isEditing && (
                  <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition">
                    {/* 이름 변경 버튼 */}
                    <button
                      onClick={(e) => startEdit(e, session)}
                      className="text-neutral-muted hover:text-primary-700 transition p-1"
                      title="이름 변경"
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                      </svg>
                    </button>
                    {/* 삭제 버튼 */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteSession(session.session_id);
                      }}
                      className="text-neutral-muted hover:text-error transition p-1"
                      title="삭제"
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      </svg>
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
