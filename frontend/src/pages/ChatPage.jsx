import { useState, useEffect, useMemo } from 'react';
import ChatWindow from '../components/chat/ChatWindow';
import MessageBubble from '../components/chat/MessageBubble';
import StreamingMessage from '../components/chat/StreamingMessage';
import AgentIndicator from '../components/chat/AgentIndicator';
import ErrorMessage from '../components/chat/ErrorMessage';
import SuggestedQuestions from '../components/chat/SuggestedQuestions';
import RegulationPanel from '../components/chat/RegulationPanel';
import ChatSessionSidebar from '../components/chat/ChatSessionSidebar';
import JudgmentCard from '../components/chat/JudgmentCard';
import ScheduleCard from '../components/chat/ScheduleCard';
import useChat from '../hooks/useChat';
import useChatStore from '../store/chatStore';

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

const RESULT_MAP = { yes: '가능', no: '불가', conditional: '조건부 가능' };
const RESULT_ICON = { yes: '✅', no: '❌', conditional: '⚠️' };

function renderCardMessage(msg, onSelectClarify) {
  const { resultIntent, agentResponse, content } = msg;
  const data = agentResponse || {};

  switch (resultIntent) {
    case 'judgment': {
      const resultLabel = RESULT_MAP[data.result] || data.result || '판단 완료';
      const resultIcon = RESULT_ICON[data.result] || '📋';
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
            <div className="mt-2 bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">
              {content}
            </div>
          )}
        </>
      );
    }

    case 'doc_search': {
      const sources = data.sources || data.references || [];
      return (
        <div>
          <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">
            {content}
          </div>
          {sources.length > 0 && (
            <div className="mt-2 px-3 py-2 bg-surface-hover rounded-lg">
              <div className="text-xs font-semibold text-neutral-sub mb-1">출처 ({sources.length}건)</div>
              {sources.map((s, idx) => (
                <div key={idx} className="text-xs text-neutral-main py-1 border-b border-neutral-divider last:border-0">
                  {s.title || s.name || s.source || `출처 ${idx + 1}`}
                  {s.page && <span className="text-neutral-muted ml-1">p.{s.page}</span>}
                </div>
              ))}
            </div>
          )}
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
  const [panelOpen, setPanelOpen] = useState(false);
  const [sessionSidebarOpen, setSessionSidebarOpen] = useState(false);
  const [lastError, setLastError] = useState(null);
  const [lastInput, setLastInput] = useState('');
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  useEffect(() => {
    initSession();
  }, [initSession]);

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

  // 메시지에서 마지막 judgment 응답의 regulations 추출
  const regulationsFromMessages = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.resultIntent === 'judgment' && msg.agentResponse?.regulations) {
        return msg.agentResponse.regulations.map((r) => ({
          name: r.name,
          article: r.article,
          content: r.content,
        }));
      }
    }
    return [];
  }, [messages]);

  return (
    <div className="-ml-8">
      <header className="flex justify-between items-center py-6 pl-8 sticky top-0 bg-surface-main z-10">
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
            onClick={() => setSessionSidebarOpen(!sessionSidebarOpen)}
            className={`btn-outline text-xs ${sessionSidebarOpen ? 'bg-primary-50 border-primary-300' : ''}`}
          >
            대화 목록
          </button>
          <button
            onClick={() => setPanelOpen(!panelOpen)}
            className={`btn-outline text-xs ${panelOpen ? 'bg-primary-50 border-primary-300' : ''}`}
          >
            규정 패널
          </button>
        </div>
      </header>

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

      <div className="flex h-[calc(100vh-108px)] -mb-8">
        {/* 세션 사이드바 */}
        <ChatSessionSidebar isOpen={sessionSidebarOpen} />

        {/* 챗 영역 */}
        <div className="flex-1 min-w-0">
          <ChatWindow onSend={handleSend} messages={messages}>
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

              // AI 완료 — agentResponse 카드 렌더링 (스트리밍 중이어도 result가 오면 카드 우선)
              if (msg.agentResponse && msg.resultIntent) {
                return (
                  <MessageBubble key={i} type="bot" intent={msg.resultIntent || msg.intent}>
                    {(msg.resultIntent || msg.intent) && <AgentIndicator intent={msg.resultIntent || msg.intent} />}
                    {renderCardMessage(msg, handleSend)}
                  </MessageBubble>
                );
              }

              // 스트리밍 중인 AI 응답
              if (isLastAssistant) {
                return (
                  <div key={i}>
                    {currentIntent && <AgentIndicator intent={currentIntent} status={currentStatus} />}
                    <StreamingMessage text={msg.content} status={currentStatus} />
                  </div>
                );
              }

              // AI 완료 — 기본 텍스트 버블
              return (
                <MessageBubble key={i} type="bot" intent={msg.intent}>
                  {msg.intent && <AgentIndicator intent={msg.intent} />}
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
