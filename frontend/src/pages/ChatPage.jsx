import ChatWindow from '../components/chat/ChatWindow';
import MessageBubble from '../components/chat/MessageBubble';
import StreamingMessage from '../components/chat/StreamingMessage';
import useChat from '../hooks/useChat';
import { SUGGESTED_QUESTIONS } from '../utils/constants';

export default function ChatPage() {
  const { messages, isStreaming, currentIntent, currentStatus, sendMessage } = useChat();

  return (
    <div>
      <header className="flex justify-between items-center py-6 sticky top-0 bg-surface-main z-10">
        <div>
          <h1 className="text-2xl font-bold">AI 챗봇</h1>
          <p className="text-sm text-neutral-sub mt-1">규정 판단, 문서 분석, 일정 관리를 도와드립니다</p>
        </div>
        <div className="flex items-center gap-1.5 text-[13px] text-success font-medium">
          <span className="w-[7px] h-[7px] rounded-full bg-success" />Mock 모드
        </div>
      </header>
      <ChatWindow onSend={sendMessage} messages={messages}>
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-6 py-20">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center text-white text-xl font-bold">AI</div>
            <p className="text-neutral-sub text-sm">무엇을 도와드릴까요?</p>
            <div className="flex flex-wrap gap-2 justify-center max-w-md">
              {SUGGESTED_QUESTIONS.map((q, i) => (
                <button key={i} onClick={() => sendMessage(q.text)}
                  className="px-3.5 py-2 rounded-full border border-neutral-border text-sm text-neutral-main hover:bg-primary-50 hover:border-primary-300 transition">
                  {q.text}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg, i) => {
          const isLastAssistant = msg.role === 'assistant' && i === messages.length - 1 && isStreaming;

          if (isLastAssistant) {
            return <StreamingMessage key={i} text={msg.content} status={currentStatus} />;
          }

          if (msg.role === 'user') {
            return <MessageBubble key={i} type="user">{msg.content}</MessageBubble>;
          }

          return (
            <MessageBubble key={i} type="bot" intent={msg.intent}>
              <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">
                {msg.content}
              </div>
            </MessageBubble>
          );
        })}
      </ChatWindow>
    </div>
  );
}
