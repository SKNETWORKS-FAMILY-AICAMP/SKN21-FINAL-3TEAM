import { useState, useEffect, useMemo, useRef } from 'react';
import { MessageSquarePlus, Menu } from 'lucide-react';
import ChatWindow from '../components/chat/ChatWindow';
import MessageBubble from '../components/chat/MessageBubble';
import StreamingMessage from '../components/chat/StreamingMessage';

import ErrorMessage from '../components/chat/ErrorMessage';
import SuggestedQuestions from '../components/chat/SuggestedQuestions';
import RegulationPanel from '../components/chat/RegulationPanel';
import ChatSessionSidebar from '../components/chat/ChatSessionSidebar';
import JudgmentCard from '../components/chat/JudgmentCard';
import ScheduleCard from '../components/chat/ScheduleCard';
import useChat from '../hooks/useChat';
import useChatStore from '../store/chatStore';
import { listRegulations } from '../api/regulations';
import { listDocuments } from '../api/documents';

function exportChat(messages) {
  if (messages.length === 0) return;

  const now = new Date();
  const dateStr = now.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\. /g, '-').replace('.', '');
  const timeStr = now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });

  const lines = [`AI 챗봇 대화 기록`, `내보낸 시각: ${dateStr} ${timeStr}`, `총 ${messages.length}개 메시지`, '─'.repeat(40), ''];

  messages.forEach((msg) => {
    const role = msg.role === 'user' ? '[나]' : '[AI]';
    lines.push(`${role}:`);
    lines.push(msg.content);
    lines.push('');
  });

  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `chat-export-${dateStr}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

const RESULT_MAP = { yes: '가능', no: '불가', conditional: '조건부 가능', no_regulation: 'No regulation' };
const RESULT_ICON = { yes: '', no: '', conditional: '', no_regulation: '' };

function renderCardMessage(msg, onSelectClarify, messages = [], index = -1) {
  const { resultIntent, agentResponse, content } = msg;
  const data = agentResponse || {};

  switch (resultIntent) {
    case 'judgment': {
      // 사용자의 질문 내용 확인 (이전 메시지)
      const userMsg = index > 0 ? messages[index - 1]?.content || '' : '';
      // '규정', '알려줘', '설명'만 있는 경우는 정보 조회로 간주 (의문형/판단형 키워드가 없을 때)
      const isJudgmentRequest = /가능|요건|조건|되나요|있나요|수 있|있습니|허용|금지|위반|처벌|준수/.test(userMsg);

      // 'none'이나 판단 결과가 명확하지 않거나, 단순 정보 조회인 경우 배지 숨김
      const isInformational = !data.result || data.result === 'none' || data.result === 'info' || (data.result === 'yes' && !isJudgmentRequest);

      const resultLabel = isInformational ? null : (RESULT_MAP[data.result] || data.result || '판단 완료');
      const resultIcon = isInformational ? null : (Object.prototype.hasOwnProperty.call(RESULT_ICON, data.result) ? RESULT_ICON[data.result] : '📋');

      const regType = data.result === 'no' ? 'deny' : data.result === 'conditional' ? 'conditional' : 'ref';
      const regulations = (data.regulations || []).map((r) => ({
        name: `${r.name || ''} ${r.article || ''}`.trim(),
        type: regType,
        verdict: r.content || '',
      }));
      return (
        <>
          <JudgmentCard result={resultLabel} resultIcon={resultIcon} summary={data.reasoning || content} regulations={regulations} />
          {content && data.reasoning && content !== data.reasoning && (
            <div className="mt-2 bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-wrap shadow-sm">
              {content}
            </div>
          )}
        </>
      );
    }

    case 'doc_search': {
      const sources = data.sources || data.references || [];
      return (
        <div className="bg-surface-card rounded-[14px] border border-neutral-border overflow-hidden">
          <div className="px-4 py-3 border-b border-neutral-divider flex items-center gap-2 font-bold text-sm text-primary-700">
            문서 검색 결과
          </div>
          <div className="p-4">
            {content && <p className="text-[0.8125rem] text-neutral-main leading-[1.7] mb-3.5 whitespace-pre-wrap">{content}</p>}
            {sources.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-neutral-sub mb-2">출처 ({sources.length}건)</div>
                {sources.map((s, idx) => (
                  <div key={idx} className="px-3 py-2 bg-surface-hover rounded-lg mb-1.5 border-l-[3px] border-l-accent-300">
                    <div className="text-xs font-semibold text-neutral-main">
                      {s.title || s.name || s.source || `출처 ${idx + 1}`}
                      {s.page && <span className="text-neutral-muted font-normal ml-1">p.{s.page}</span>}
                    </div>
                    {s.content && <div className="text-[0.6875rem] text-neutral-sub mt-0.5">{s.content}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      );
    }

    case 'schedule_add': {
      return (
        <div>
          <ScheduleCard
            title={data.title || data.summary || '일정 등록'}
            date={data.date || ''}
            time={data.time || ''}
            synced={data.synced || data.google_synced || false}
          />
          {content && (
            <div className="mt-2 bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">
              {content}
            </div>
          )}
        </div>
      );
    }

    case 'clarify': {
      const candidates = data.candidates || [];
      return (
        <div>
          <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">
            {content || data.message || '질문을 명확히 해주세요.'}
          </div>
          {candidates.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {candidates.map((c, idx) => (
                <button
                  key={idx}
                  onClick={() => onSelectClarify?.(typeof c === 'string' ? c : c.query || c.label)}
                  className="px-3 py-1.5 text-xs bg-primary-50 text-primary-700 rounded-full border border-primary-200 hover:bg-primary-100 transition"
                >
                  {typeof c === 'string' ? c : c.label || c.query}
                </button>
              ))}
            </div>
          )}
        </div>
      );
    }

    default:
      return (
        <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">
          {content}
        </div>
      );
  }
}

export default function ChatPage() {
  const { messages, isStreaming, currentIntent, currentStatus, sendMessage } = useChat();
  const clearMessages = useChatStore((s) => s.clearMessages);
  const initSession = useChatStore((s) => s.initSession);
  const createSession = useChatStore((s) => s.createSession);
  const pendingQuestion = useChatStore((s) => s.pendingQuestion);
  const clearPendingQuestion = useChatStore((s) => s.clearPendingQuestion);
  const selectedDocumentId = useChatStore((s) => s.selectedDocumentId);
  const selectedDocumentName = useChatStore((s) => s.selectedDocumentName);
  const setSelectedDocument = useChatStore((s) => s.setSelectedDocument);
  const clearSelectedDocument = useChatStore((s) => s.clearSelectedDocument);
  const [panelOpen, setPanelOpen] = useState(false);
  const [sessionSidebarOpen, setSessionSidebarOpen] = useState(false);
  const [lastError, setLastError] = useState(null);
  const [lastInput, setLastInput] = useState('');
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [dbRegulations, setDbRegulations] = useState([]);
  const [docPickerOpen, setDocPickerOpen] = useState(false);
  const [docList, setDocList] = useState([]);
  const [docSearch, setDocSearch] = useState('');

  const mountedRef = useRef(false);

  useEffect(() => {
    if (mountedRef.current) return;
    mountedRef.current = true;

    const q = useChatStore.getState().pendingQuestion;
    if (q) {
      // 대시보드에서 질문 클릭 → 새 세션 시작 후 자동 전송
      clearPendingQuestion();
      createSession();
      setLastInput(q);
      sendMessage(q);
    } else {
      initSession();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    listRegulations()
      .then((res) => setDbRegulations(res.data || []))
      .catch((err) => console.warn('[ChatPage] 규정 로드 실패:', err));
  }, []);

  useEffect(() => {
    if (!docPickerOpen) return;
    listDocuments()
      .then((res) => setDocList(res.data?.documents || res.data || []))
      .catch((err) => console.warn('[ChatPage] 문서 로드 실패:', err));
  }, [docPickerOpen]);

  const handleSend = (text) => {
    setLastError(null);
    setLastInput(text);
    sendMessage(text);
  };

  const handleRetry = () => {
    if (lastInput) {
      setLastError(null);
      sendMessage(lastInput);
    }
  };

  const handleClear = () => {
    if (messages.length === 0) return;
    setShowClearConfirm(true);
  };

  const confirmClear = () => {
    clearMessages();
    setLastError(null);
    setLastInput('');
    setShowClearConfirm(false);
  };

  // 메시지에서 마지막 judgment 응답의 regulations 추출 (DB 원문 우선 병합)
  const regulationsFromMessages = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.resultIntent === 'judgment' && msg.agentResponse?.regulations) {
        return msg.agentResponse.regulations.map((r) => {
          const articleKey = (r.article || r.name || '').match(/제\d+조/)?.[0];
          const dbReg = articleKey
            ? dbRegulations.find((db) => db.article_number === articleKey)
            : null;
          return {
            name: r.name || dbReg?.title || '',
            article: r.article || dbReg?.article_number || '',
            content: dbReg?.content || r.content || '',
            relevance: r.relevance || r.score || null,
          };
        });
      }
    }
    return [];
  }, [messages, dbRegulations]);

  return (
    <div className="-ml-8 -mb-8 flex flex-col h-[calc(100vh-4rem-2rem)]">
      <header className="flex justify-between items-center py-4 pl-8 bg-surface-main z-10 flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold">나에게 물어봐</h1>
          <p className="text-sm text-neutral-sub mt-1">규정 판단, 문서 분석, 일정 관리를 도와드립니다</p>
        </div>
        <div className="flex items-center gap-2">
          {/* 대화 내보내기 */}
          <button
            onClick={() => exportChat(messages)}
            disabled={messages.length === 0}
            className="btn-outline text-xs disabled:opacity-40 disabled:cursor-not-allowed"
            title="대화 내보내기"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            내보내기
          </button>
          {/* 대화 초기화 */}
          <button
            onClick={handleClear}
            disabled={messages.length === 0}
            className="btn-outline text-xs disabled:opacity-40 disabled:cursor-not-allowed text-red-500 border-red-200 hover:bg-red-50"
            title="대화 초기화"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
            초기화
          </button>
          <button
            onClick={() => setDocPickerOpen(true)}
            className={`btn-outline text-xs ${selectedDocumentId ? 'bg-accent-50 border-accent-300 text-accent-700' : ''}`}
            title="요약할 문서 선택"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            {selectedDocumentId ? '문서 선택됨' : '문서 선택'}
          </button>
          <button
            onClick={() => setPanelOpen(!panelOpen)}
            className={`btn-outline text-xs ${panelOpen ? 'bg-primary-50 border-primary-300' : ''}`}
          >
            규정 패널
          </button>
        </div>
      </header>

      {/* 문서 선택 피커 */}
      {docPickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => { setDocPickerOpen(false); setDocSearch(''); }}>
          <div className="bg-surface-card rounded-xl shadow-xl w-[28rem] max-w-[90vw] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-divider">
              <h3 className="text-sm font-semibold text-neutral-main">요약할 문서 선택</h3>
              <button onClick={() => { setDocPickerOpen(false); setDocSearch(''); }} className="text-neutral-muted hover:text-neutral-main transition">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="px-4 py-3 border-b border-neutral-divider">
              <input
                autoFocus
                value={docSearch}
                onChange={(e) => setDocSearch(e.target.value)}
                placeholder="문서 검색..."
                className="w-full px-3 py-2 text-sm border border-neutral-border rounded-md bg-surface-main outline-none focus:border-primary-300 text-neutral-main placeholder:text-neutral-muted"
              />
            </div>
            <div className="max-h-64 overflow-y-auto py-1">
              {docList.filter(d => !docSearch || d.title?.includes(docSearch) || d.original_filename?.includes(docSearch)).length === 0 ? (
                <div className="py-8 text-center text-sm text-neutral-muted">
                  {docList.length === 0 ? '등록된 문서가 없습니다' : '검색 결과 없음'}
                </div>
              ) : (
                docList
                  .filter(d => !docSearch || d.title?.includes(docSearch) || d.original_filename?.includes(docSearch))
                  .map((doc) => (
                    <button
                      key={doc.id}
                      onClick={() => { setSelectedDocument(doc.id, doc.title || doc.original_filename); setDocPickerOpen(false); setDocSearch(''); }}
                      className={`w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-hover transition text-sm ${selectedDocumentId === doc.id ? 'bg-accent-50 text-accent-700' : 'text-neutral-main'}`}
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0 text-neutral-muted">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                      </svg>
                      <span className="truncate">{doc.title || doc.original_filename}</span>
                    </button>
                  ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* 초기화 확인 다이얼로그 */}
      {showClearConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-surface-card rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="text-base font-semibold mb-2">대화 기록을 초기화할까요?</h3>
            <p className="text-sm text-neutral-sub mb-5">모든 대화 내용이 삭제됩니다. 이 작업은 되돌릴 수 없습니다.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowClearConfirm(false)} className="btn-outline text-sm px-4 py-2">취소</button>
              <button onClick={confirmClear} className="bg-red-500 hover:bg-red-600 text-white text-sm px-4 py-2 rounded-md transition">삭제</button>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-1 min-h-0 -mb-8">
        {/* 왼쪽 아이콘 레일 + 세션 사이드바 */}
        <div className="flex flex-shrink-0 h-full">
          <div className="w-11 bg-surface-card border-r border-neutral-divider flex flex-col items-center py-2 gap-2">
            <button
              onClick={() => setSessionSidebarOpen(!sessionSidebarOpen)}
              title={sessionSidebarOpen ? '대화 목록 닫기' : '대화 목록'}
              className={`w-8 h-8 flex items-center justify-center rounded-md transition ${sessionSidebarOpen
                ? 'text-primary-700 bg-primary-50'
                : 'text-neutral-sub hover:text-primary-700 hover:bg-primary-50'
                }`}
            >
              <Menu size={18} />
            </button>
            <button
              onClick={() => { createSession(); setSessionSidebarOpen(true); }}
              title="새 대화"
              className="w-8 h-8 flex items-center justify-center rounded-md text-neutral-sub hover:text-primary-700 hover:bg-primary-50 transition"
            >
              <MessageSquarePlus size={18} />
            </button>
          </div>
          <ChatSessionSidebar isOpen={sessionSidebarOpen} />
        </div>

        {/* 챗 영역 */}
        <div className="flex-1 min-w-0">
          <ChatWindow onSend={handleSend} messages={messages} selectedDocumentName={selectedDocumentName} onClearDocument={clearSelectedDocument} activeIntent={currentIntent || messages.filter(m => m.role === 'assistant').at(-1)?.resultIntent || messages.filter(m => m.role === 'assistant').at(-1)?.intent} isStreaming={isStreaming}>
            {/* 메시지가 없을 때 — 추천 질문 */}
            {messages.length === 0 && (
              <SuggestedQuestions onSelect={handleSend} />
            )}

            {/* 메시지 렌더링 */}
            {messages.map((msg, i) => {
              const isLastAssistant = msg.role === 'assistant' && i === messages.length - 1 && isStreaming;

              // 사용자 메시지
              if (msg.role === 'user') {
                return <MessageBubble key={i} type="user">{msg.content}</MessageBubble>;
              }

              // 에러 메시지
              if (msg.error) {
                return <ErrorMessage key={i} message={msg.error} onRetry={handleRetry} />;
              }

              // 스트리밍 중인 AI 응답 (데이터가 미리 왔더라도 텍스트 출력을 우선으로 보여줌)
              if (isLastAssistant) {
                const intent = currentIntent || msg.resultIntent || msg.intent || 'general';
                return (
                  <MessageBubble key={i} type="bot" intent={intent}>
                    <StreamingMessage
                      text={msg.content}
                      status={currentStatus}
                      intent={intent}
                      isInsideBubble
                    />
                  </MessageBubble>
                );
              }

              // AI 완료 — agentResponse 카드 렌더링
              if (msg.agentResponse && msg.resultIntent) {
                return (
                  <MessageBubble key={i} type="bot" intent={msg.resultIntent || msg.intent}>
                    {renderCardMessage(msg, handleSend, messages, i)}
                  </MessageBubble>
                );
              }

              // AI 완료 — 기본 텍스트 버블
              return (
                <MessageBubble key={i} type="bot" intent={msg.intent}>
                  <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">
                    {msg.content}
                  </div>
                </MessageBubble>
              );
            })}

            {/* 에러 표시 */}
            {lastError && <ErrorMessage message={lastError} onRetry={handleRetry} />}
          </ChatWindow>
        </div>

        {/* 우측 규정 패널 */}
        <RegulationPanel
          regulations={regulationsFromMessages}
          isOpen={panelOpen}
          onClose={() => setPanelOpen(false)}
        />
      </div>
    </div>
  );
}
