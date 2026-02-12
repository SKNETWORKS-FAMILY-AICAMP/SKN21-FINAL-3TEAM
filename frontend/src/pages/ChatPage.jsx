import { useState, useEffect } from 'react';
import ChatWindow from '../components/chat/ChatWindow';
import MessageBubble from '../components/chat/MessageBubble';
import StreamingMessage from '../components/chat/StreamingMessage';
import AgentIndicator from '../components/chat/AgentIndicator';
import ErrorMessage from '../components/chat/ErrorMessage';
import SuggestedQuestions from '../components/chat/SuggestedQuestions';
import RegulationPanel from '../components/chat/RegulationPanel';
import ChatSessionSidebar from '../components/chat/ChatSessionSidebar';
import useChat from '../hooks/useChat';
import useChatStore from '../store/chatStore';

// 규정 판단 응답 시 우측 패널에 보여줄 mock 규정
const mockRegulations = [
  { name: '근무규정', article: '제12조 (재택근무)', content: '주 2회 이내 재택근무를 허용한다. 단, 수습 기간 중에는 팀장 승인이 필요하다.', relevance: 0.95 },
  { name: '정보보안 규정', article: '제8조 (원격접속)', content: '재택근무 시 반드시 VPN을 통해 사내 시스템에 접속해야 한다.', relevance: 0.82 },
  { name: '인사규정', article: '제5조 (수습기간)', content: '신규 입사자의 수습 기간은 3개월로 한다.', relevance: 0.65 },
];

export default function ChatPage() {
  const { messages, isStreaming, currentIntent, currentStatus, sendMessage } = useChat();
  const { initSession } = useChatStore();
  const [panelOpen, setPanelOpen] = useState(false);
  const [sessionSidebarOpen, setSessionSidebarOpen] = useState(false);
  const [lastError, setLastError] = useState(null);
  const [lastInput, setLastInput] = useState('');

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

  return (
    <div className="-mx-8">
      <header className="flex justify-between items-center py-6 px-8 sticky top-0 bg-surface-main z-10">
        <div>
          <h1 className="text-2xl font-bold">AI 챗봇</h1>
          <p className="text-sm text-neutral-sub mt-1">규정 판단, 문서 분석, 일정 관리를 도와드립니다</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSessionSidebarOpen(!sessionSidebarOpen)}
            className={`btn-outline text-xs ${sessionSidebarOpen ? 'bg-primary-50 border-primary-300' : ''}`}
          >
            💬 대화 목록
          </button>
          <button
            onClick={() => setPanelOpen(!panelOpen)}
            className={`btn-outline text-xs ${panelOpen ? 'bg-primary-50 border-primary-300' : ''}`}
          >
            📖 규정 패널
          </button>
          <div className="flex items-center gap-1.5 text-[0.8125rem] text-success font-medium">
            <span className="w-[7px] h-[7px] rounded-full bg-success" />Mock 모드
          </div>
        </div>
      </header>

      <div className="flex h-[calc(100vh-108px)] -mb-8">
        {/* 좌측 대화 세션 목록 */}
        {sessionSidebarOpen && <ChatSessionSidebar />}

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

              // 스트리밍 중인 AI 응답
              if (isLastAssistant) {
                return (
                  <div key={i}>
                    {currentIntent && <AgentIndicator intent={currentIntent} status={currentStatus} />}
                    <StreamingMessage text={msg.content} status={currentStatus} />
                  </div>
                );
              }

              // 사용자 메시지
              if (msg.role === 'user') {
                return <MessageBubble key={i} type="user">{msg.content}</MessageBubble>;
              }

              // 에러 메시지
              if (msg.error) {
                return <ErrorMessage key={i} message={msg.error} onRetry={handleRetry} />;
              }

              // AI 완료된 응답
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
          regulations={mockRegulations}
          isOpen={panelOpen}
          onClose={() => setPanelOpen(false)}
        />
      </div>
    </div>
  );
}
