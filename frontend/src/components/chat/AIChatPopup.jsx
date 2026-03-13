import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, Send, X, Clock, Sparkles, Maximize2, ArrowLeft, Scale, FileText, Search, FileSearch, HelpCircle, CalendarPlus, CalendarDays, MessageCircle, ShieldCheck } from 'lucide-react';
import { SUGGESTED_QUESTIONS } from '../../utils/constants';
import useChatStore from '../../store/chatStore';
import useChat from '../../hooks/useChat';
import MarkdownText from './MarkdownText';

const AGENT_CONFIG = {
  judgment: { icon: Scale, label: '규정 판단', color: 'text-primary-700 bg-primary-50 dark:text-primary-300 dark:bg-primary-900/30' },
  doc_retrieve: { icon: Search, label: '문서 검색/조회', color: 'text-accent-700 bg-accent-50 dark:text-accent-300 dark:bg-accent-900/30' },
  doc_search: { icon: Search, label: '문서 검색/조회', color: 'text-accent-700 bg-accent-50 dark:text-accent-300 dark:bg-accent-900/30' },
  doc_generate: { icon: FileText, label: '문서 생성', color: 'text-accent-700 bg-accent-50 dark:text-accent-300 dark:bg-accent-900/30' },
  doc_summary: { icon: FileSearch, label: '문서 요약', color: 'text-accent-700 bg-accent-50 dark:text-accent-300 dark:bg-accent-900/30' },
  schedule_add: { icon: CalendarPlus, label: '일정 추가', color: 'text-green-700 bg-green-50 dark:text-green-300 dark:bg-green-900/30' },
  schedule_view: { icon: CalendarDays, label: '일정 조회', color: 'text-green-700 bg-green-50 dark:text-green-300 dark:bg-green-900/30' },
  general: { icon: MessageCircle, label: '일반', color: 'text-neutral-500 bg-neutral-100 dark:text-neutral-400 dark:bg-neutral-800' },
};

function MiniAgentBadge({ intent }) {
  const config = AGENT_CONFIG[intent] || AGENT_CONFIG.general;
  const Icon = config.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${config.color}`}>
      <Icon size={10} />
      {config.label}
    </span>
  );
}

function getConfidenceColor(value) {
  if (value >= 0.7) return { bar: 'bg-green-500', text: 'text-green-600' };
  if (value >= 0.4) return { bar: 'bg-yellow-500', text: 'text-yellow-600' };
  return { bar: 'bg-red-500', text: 'text-red-600' };
}

function AgentResultCard({ msg }) {
  const { agentResponse: data, resultIntent } = msg;
  if (!data) return null;

  // ── Judgment Agent ──
  if (resultIntent === 'judgment') {
    const regs = (data.regulations || []).map((r) => ({
      name: `${r.name || ''} ${r.article || ''}`.trim(),
      verdict: r.content || '',
    }));
    const confidence = data.confidence_breakdown?.final ?? data.confidence;
    const hasScore = typeof confidence === 'number';
    const scoreColor = hasScore ? getConfidenceColor(confidence) : null;

    return (
      <div className="mt-2 bg-white/60 dark:bg-neutral-800/60 rounded-xl border border-neutral-200/50 dark:border-white/10 overflow-hidden text-xs">
        {/* 관련 규정 */}
        {regs.length > 0 && (
          <div className="p-3">
            <div className="font-semibold text-neutral-500 dark:text-neutral-400 mb-1.5">관련 규정 ({regs.length}건)</div>
            {regs.map((r, i) => (
              <div key={i} className="px-2.5 py-2 bg-neutral-50/80 dark:bg-neutral-700/50 rounded-lg mb-1 border-l-2 border-l-primary-400">
                <div className="font-bold text-neutral-800 dark:text-neutral-200">{r.name}</div>
                {r.verdict && <div className="text-[10px] text-neutral-500 dark:text-neutral-400 mt-0.5 line-clamp-2">{r.verdict}</div>}
              </div>
            ))}
          </div>
        )}
        {/* 신뢰도 */}
        {hasScore && (
          <div className="flex items-center gap-2 px-3 py-2.5 border-t border-neutral-200/50 dark:border-white/10">
            <ShieldCheck size={12} className={scoreColor.text} />
            <span className="font-semibold text-neutral-600 dark:text-neutral-300">신뢰도 분석</span>
            <div className="flex items-center gap-1.5 ml-auto">
              <div className="w-16 h-1.5 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${scoreColor.bar}`} style={{ width: `${Math.min(confidence * 100, 100)}%` }} />
              </div>
              <span className={`font-black ${scoreColor.text}`}>{(confidence * 100).toFixed(1)}%</span>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── Document Generate Agent ──
  if (resultIntent === 'doc_generate') {
    const TEMPLATE_NAMES = { meeting_minutes: '회의록', report: '업무보고서', proposal: '제안서' };
    const templateName = data.template_name || TEMPLATE_NAMES[data.template_type] || '문서';
    return (
      <div className="mt-2 bg-white/60 dark:bg-neutral-800/60 rounded-xl border border-neutral-200/50 dark:border-white/10 overflow-hidden text-xs">
        <div className="flex items-center gap-2 p-3">
          <FileText size={14} className="text-accent-600" />
          <span className="font-bold text-neutral-700 dark:text-neutral-200">{templateName} 생성 완료</span>
        </div>
      </div>
    );
  }

  // ── Document Search/Retrieve Agent ──
  if (resultIntent === 'doc_search' || resultIntent === 'doc_retrieve') {
    const sources = data.sources || data.references || [];
    if (sources.length === 0) return null;
    return (
      <div className="mt-2 bg-white/60 dark:bg-neutral-800/60 rounded-xl border border-neutral-200/50 dark:border-white/10 overflow-hidden text-xs">
        <div className="p-3">
          <div className="font-semibold text-neutral-500 dark:text-neutral-400 mb-1.5">출처 ({sources.length}건)</div>
          {sources.slice(0, 3).map((s, i) => (
            <div key={i} className="px-2.5 py-1.5 bg-neutral-50/80 dark:bg-neutral-700/50 rounded-lg mb-1">
              <div className="font-bold text-neutral-800 dark:text-neutral-200">{s.name || s.title || `문서 ${i + 1}`}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ── Schedule Agent ──
  if (resultIntent === 'schedule_add' || resultIntent === 'schedule_view') {
    return (
      <div className="mt-2 bg-white/60 dark:bg-neutral-800/60 rounded-xl border border-neutral-200/50 dark:border-white/10 overflow-hidden text-xs">
        <div className="flex items-center gap-2 p-3">
          <CalendarDays size={14} className="text-green-600" />
          <span className="font-bold text-neutral-700 dark:text-neutral-200">
            {resultIntent === 'schedule_add' ? '일정 등록 완료' : '일정 조회 결과'}
          </span>
        </div>
      </div>
    );
  }

  return null;
}

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

export default function AIChatPopup({ isOpen: externalOpen, onClose }) {
  const [internalOpen, setInternalOpen] = useState(false);
  const isOpen = externalOpen !== undefined ? externalOpen : internalOpen;
  const setIsOpen = onClose || setInternalOpen;

  const [mode, setMode] = useState('home'); // 'home' or 'chat'
  const [query, setQuery] = useState('');
  const popupRef = useRef(null);
  const messagesEndRef = useRef(null);
  const navigate = useNavigate();

  const { messages, isStreaming, currentIntent, sendMessage } = useChat();
  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const switchSession = useChatStore((s) => s.switchSession);
  const startNewSession = useChatStore((s) => s.startNewSession);

  const recentSessions = sessions.slice(0, 3);

  const handleSearch = async (text) => {
    const q = (text || query).trim();
    if (!q) return;

    setMode('chat');
    setQuery('');
    await sendMessage(q);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSearch();
  };

  const handleSessionClick = (id) => {
    switchSession(id);
    setMode('chat');
  };

  const handleExpand = () => {
    setIsOpen(false);
    navigate(activeSessionId ? `/chat?session=${activeSessionId}` : '/chat');
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (mode === 'chat') {
      scrollToBottom();
    }
  }, [messages, mode]);

  useEffect(() => {
    function handleClickOutside(e) {
      if (popupRef.current && !popupRef.current.contains(e.target) && !e.target.closest('.sidebar-trigger')) {
        setIsOpen(false);
      }
    }
    if (isOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, setIsOpen]);

  return (
    <div className="fixed bottom-[5.5rem] right-24 z-50 flex items-end justify-end pointer-events-none">

      {/* 팝업 창 */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            ref={popupRef}
            initial={{ opacity: 0, x: 20, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 20, scale: 0.95 }}
            className="bg-white/40 dark:bg-neutral-900/40 backdrop-blur-xl shadow-[0_32px_64px_-16px_rgba(0,0,0,0.12)] rounded-[2rem] border border-white/30 dark:border-white/10 w-[400px] max-h-[calc(100vh-10rem)] mb-4 overflow-hidden pointer-events-auto origin-right flex flex-col"
          >
            {/* Header */}
            <div className="px-6 py-5 flex items-center justify-between border-b border-neutral-200/30 dark:border-white/10 flex-shrink-0 bg-white/50 dark:bg-black/20">
              <div className="flex items-center gap-3">
                {mode === 'chat' && (
                  <button onClick={() => setMode('home')} className="p-1.5 rounded-full hover:bg-neutral-100 dark:hover:bg-white/10 text-neutral-500 transition-colors">
                    <ArrowLeft size={18} />
                  </button>
                )}
                <div className="w-9 h-9 rounded-2xl bg-primary-500 text-white flex items-center justify-center shadow-lg shadow-primary-500/20">
                  <Sparkles size={18} />
                </div>
                <div className="flex flex-col">
                  <span className="font-black text-neutral-900 dark:text-white text-[15px] tracking-tight">AI 어시스턴트</span>
                  {mode === 'chat' && <span className="text-[10px] font-bold text-primary-500 uppercase tracking-widest">대화 중...</span>}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={handleExpand}
                  title="전체 화면으로 보기"
                  className="text-neutral-400 hover:text-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/20 p-2 rounded-xl transition-all"
                >
                  <Maximize2 size={18} />
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  className="text-neutral-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 p-2 rounded-xl transition-all"
                >
                  <X size={20} />
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              <AnimatePresence mode="wait">
                {mode === 'home' ? (
                  <motion.div
                    key="home"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="p-6 space-y-6"
                  >
                    {/* 추천 질문 칩 */}
                    <div>
                      <p className="text-[11px] font-black text-neutral-400 mb-3 uppercase tracking-[0.2em] px-1">추천 질문</p>
                      <div className="flex flex-col gap-2">
                        {CHIP_QUESTIONS.map((q) => (
                          <button
                            key={q.text}
                            onClick={() => handleSearch(q.text)}
                            className="w-full text-left px-4 py-3.5 rounded-2xl text-xs font-bold bg-surface-card text-neutral-sub border border-neutral-divider transition-all hover:border-primary-300 hover:bg-primary-50 dark:hover:bg-primary-900/20 hover:text-primary-700 dark:hover:text-primary-300 shadow-sm"
                          >
                            {q.text}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* 최근 대화 */}
                    {recentSessions.length > 0 && (
                      <div>
                        <div className="text-[11px] font-black text-neutral-400 mb-3 uppercase tracking-[0.2em] flex items-center gap-1.5 px-1">
                          <Clock size={12} /> 최근 대화
                        </div>
                        <div className="space-y-2">
                          {recentSessions.map((s) => (
                            <button
                              key={s.session_id}
                              onClick={() => handleSessionClick(s.session_id)}
                              className="w-full text-left flex items-center gap-3 px-4 py-3 rounded-2xl transition-all hover:bg-surface-card border border-transparent hover:border-neutral-divider group"
                            >
                              <div className="bg-neutral-100 dark:bg-neutral-800 p-2 rounded-xl text-neutral-400 group-hover:text-primary-500 transition-colors">
                                <MessageSquare size={14} />
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="text-xs font-bold text-neutral-700 dark:text-neutral-300 truncate">{s.name}</div>
                                <div className="text-[10px] font-medium text-neutral-400">{formatTime(s.updated_at)}</div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </motion.div>
                ) : (
                  <motion.div
                    key="chat"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="p-6 space-y-4"
                  >
                    {messages.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-12 text-center">
                        <div className="w-12 h-12 rounded-2xl bg-primary-50 dark:bg-primary-900/20 text-primary-500 flex items-center justify-center mb-4">
                          <MessageSquare size={24} />
                        </div>
                        <p className="text-sm font-bold text-neutral-400">새로운 대화를 시작하세요</p>
                      </div>
                    ) : (
                      messages.map((msg, i) => (
                        <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                          <div className={`max-w-[85%] ${msg.role === 'user' ? '' : ''}`}>
                            {msg.role === 'assistant' && (msg.intent || msg.resultIntent || (i === messages.length - 1 && isStreaming && currentIntent)) && (
                              <div className="mb-1">
                                <MiniAgentBadge intent={msg.intent || msg.resultIntent || currentIntent} />
                              </div>
                            )}
                            <div className={`px-4 py-3 rounded-2xl text-sm ${msg.role === 'user'
                                ? 'bg-primary-500 text-white rounded-br-none shadow-lg shadow-primary-500/20'
                                : 'bg-surface-card/80 text-neutral-main rounded-bl-none border border-neutral-divider'
                              }`}>
                              <MarkdownText>{msg.content}</MarkdownText>
                              {msg.role === 'assistant' && !msg.content && i === messages.length - 1 && isStreaming && (
                                <div className="flex gap-1 mt-1">
                                  <span className="w-1.5 h-1.5 bg-primary-300 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                  <span className="w-1.5 h-1.5 bg-primary-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                  <span className="w-1.5 h-1.5 bg-primary-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                </div>
                              )}
                              {msg.role === 'assistant' && msg.agentResponse && (
                                <AgentResultCard msg={msg} />
                              )}
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                    <div ref={messagesEndRef} />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Footer / Input */}
            <div className="p-6 border-t border-neutral-200/30 dark:border-white/10 flex-shrink-0 bg-white/50 dark:bg-black/20">
              <div className="relative flex items-center group">
                <input
                  type="text"
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="메시지를 입력하세요..."
                  disabled={isStreaming}
                  className="w-full pl-5 pr-14 py-4 bg-surface-card border border-neutral-border rounded-[1.25rem] text-sm text-neutral-main outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/10 transition-all shadow-sm placeholder:text-neutral-muted disabled:opacity-50"
                />
                <button
                  onClick={() => handleSearch()}
                  disabled={isStreaming || !query.trim()}
                  className="absolute right-2.5 w-10 h-10 bg-primary-700 text-white rounded-xl flex items-center justify-center transition-all hover:bg-primary-900 hover:scale-105 active:scale-95 disabled:opacity-30 disabled:hover:scale-100"
                >
                  <Send size={18} />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
