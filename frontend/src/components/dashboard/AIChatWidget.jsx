import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquare, Send, Clock } from 'lucide-react';
import { SUGGESTED_QUESTIONS } from '../../utils/constants';
import useChatStore from '../../store/chatStore';

const CHIP_QUESTIONS = SUGGESTED_QUESTIONS.slice(0, 4);

function formatTime(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  const now = new Date();
  const diff = now - d;
  if (diff < 60000) return '방금 전';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}분 전`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}시간 전`;
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export default function AIChatWidget() {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();
  const sessions = useChatStore((s) => s.sessions);
  const switchSession = useChatStore((s) => s.switchSession);

  const recentSessions = sessions.slice(0, 3);

  const handleSearch = (text) => {
    const q = (text || query).trim();
    if (!q) return;
    navigate(`/chat?q=${encodeURIComponent(q)}`);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSearch();
  };

  const handleSessionClick = (id) => {
    switchSession(id);
    navigate('/chat');
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><MessageSquare size={16} className="text-neutral-sub" />AI 어시스턴트</div>
      </div>
      <div className="card-body space-y-4">
        {/* 검색 입력 */}
        <div className="flex items-center gap-2">
          <div className="flex-1 relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="무엇이든 물어보세요..."
              className="w-full pl-3.5 pr-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] placeholder:text-neutral-muted"
            />
          </div>
          <button onClick={() => handleSearch()} className="btn-primary px-4 flex items-center gap-1.5">
            <Send size={14} />
            질문
          </button>
        </div>

        {/* 추천 질문 칩 */}
        <div className="flex flex-wrap gap-2">
          {CHIP_QUESTIONS.map((q) => (
            <button
              key={q.text}
              onClick={() => handleSearch(q.text)}
              className="px-3 py-1.5 rounded-full text-xs font-medium bg-primary-50 text-primary-700 border border-primary-100 transition hover:bg-primary-100"
            >
              {q.text}
            </button>
          ))}
        </div>

        {/* 최근 대화 */}
        {recentSessions.length > 0 && (
          <div>
            <div className="text-xs font-semibold text-neutral-sub mb-2 flex items-center gap-1">
              <Clock size={12} />최근 대화
            </div>
            <div className="space-y-1">
              {recentSessions.map((s) => (
                <button
                  key={s.id}
                  onClick={() => handleSessionClick(s.id)}
                  className="w-full text-left flex items-center gap-2 px-3 py-2 rounded-sm transition hover:bg-surface-hover"
                >
                  <MessageSquare size={14} className="text-neutral-muted flex-shrink-0" />
                  <span className="text-[0.8125rem] text-neutral-main truncate flex-1">{s.name}</span>
                  <span className="text-[0.6875rem] text-neutral-muted whitespace-nowrap">{formatTime(s.updatedAt)}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
