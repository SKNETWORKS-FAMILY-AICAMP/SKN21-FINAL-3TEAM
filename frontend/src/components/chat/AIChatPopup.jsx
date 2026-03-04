import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquare, Send, X, Clock, Sparkles } from 'lucide-react';
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

export default function AIChatPopup() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const popupRef = useRef(null);
  const navigate = useNavigate();
  
  const sessions = useChatStore((s) => s.sessions);
  const switchSession = useChatStore((s) => s.switchSession);
  const setPendingQuestion = useChatStore((s) => s.setPendingQuestion);

  const recentSessions = sessions.slice(0, 3);

  const handleSearch = (text) => {
    const q = (text || query).trim();
    if (!q) return;
    setPendingQuestion(q);
    setIsOpen(false);
    navigate('/chat');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSearch();
  };

  const handleSessionClick = (id) => {
    switchSession(id);
    setIsOpen(false);
    navigate('/chat');
  };

  useEffect(() => {
    function handleClickOutside(e) {
      if (popupRef.current && !popupRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    if (isOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  return (
    <div className="fixed bottom-8 right-8 z-50 flex items-end justify-end">
      
      {/* 팝업 창 */}
      {isOpen && (
        <div 
          ref={popupRef}
          className="bg-white/90 dark:bg-gray-800/90 backdrop-blur-md shadow-2xl rounded-2xl border border-neutral-200 w-[380px] mb-4 overflow-hidden animate-fade-in origin-bottom-right"
        >
          {/* Header */}
          <div className="bg-primary-50 px-5 py-4 flex items-center justify-between border-b border-primary-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-primary-500 text-white flex items-center justify-center shadow-inner">
                <Sparkles size={16} />
              </div>
              <span className="font-bold text-primary-900 text-[15px] tracking-tight">AI 어시스턴트</span>
            </div>
            <button 
              onClick={() => setIsOpen(false)}
              className="text-primary-700 hover:bg-primary-200/50 p-1.5 rounded-full transition-colors"
            >
              <X size={18} />
            </button>
          </div>

          {/* Body */}
          <div className="p-5 space-y-5">
            {/* 검색 입력 */}
            <div className="relative flex items-center shadow-sm">
              <input
                type="text"
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="무엇이든 물어보세요..."
                className="w-full pl-4 pr-12 py-3 border border-neutral-200 rounded-xl text-sm outline-none focus:border-primary-400 focus:ring-4 focus:ring-primary-50 transition-all bg-white"
              />
              <button 
                onClick={() => handleSearch()} 
                className="absolute right-2 text-primary-600 hover:text-primary-700 p-1.5 hover:bg-primary-50 rounded-lg transition-colors"
              >
                <Send size={18} />
              </button>
            </div>

            {/* 추천 질문 칩 */}
            <div>
              <p className="text-[11px] font-bold text-neutral-400 mb-2 uppercase tracking-wide px-1">추천 질문</p>
              <div className="flex flex-wrap gap-2">
                {CHIP_QUESTIONS.map((q) => (
                  <button
                    key={q.text}
                    onClick={() => handleSearch(q.text)}
                    className="px-3 py-1.5 rounded-full text-[11px] font-semibold bg-neutral-100 text-neutral-600 border border-neutral-200 transition hover:bg-primary-50 hover:text-primary-700 hover:border-primary-200 shadow-sm"
                  >
                    {q.text}
                  </button>
                ))}
              </div>
            </div>

            {/* 최근 대화 */}
            {recentSessions.length > 0 && (
              <div>
                <div className="text-[11px] font-bold text-neutral-400 mb-2 uppercase tracking-wide flex items-center gap-1.5 px-1">
                  <Clock size={12} /> 최근 대화
                </div>
                <div className="space-y-1">
                  {recentSessions.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => handleSessionClick(s.id)}
                      className="w-full text-left flex items-center gap-3 px-3 py-2.5 rounded-xl transition hover:bg-neutral-50 border border-transparent hover:border-neutral-100"
                    >
                      <div className="bg-neutral-100 p-1.5 rounded-lg text-neutral-500">
                        <MessageSquare size={14} />
                      </div>
                      <span className="text-xs font-semibold text-neutral-700 truncate flex-1">{s.name}</span>
                      <span className="text-[10px] font-medium text-neutral-400 whitespace-nowrap">{formatTime(s.updatedAt)}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 플로팅 버튼 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`w-14 h-14 rounded-full flex items-center justify-center shadow-lg transition-all duration-300 ${isOpen ? 'bg-neutral-200 text-neutral-600 scale-90' : 'bg-primary-600 text-white hover:bg-primary-700 hover:scale-105 hover:shadow-xl'}`}
      >
        {isOpen ? <X size={24} /> : <MessageSquare size={24} />}
      </button>
      
    </div>
  );
}
