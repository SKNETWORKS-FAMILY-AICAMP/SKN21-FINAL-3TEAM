import { useState, useRef, useEffect } from 'react';

export default function ChatWindow({ messages, onSend, children }) {
  const [input, setInput] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;
    onSend?.(input.trim());
    setInput('');
  };

  return (
    <div className="flex flex-col h-[calc(100vh-80px)]">
      <div className="flex-1 overflow-y-auto py-4">{children}<div ref={bottomRef} /></div>
      <div className="flex gap-2.5 pt-4 border-t border-neutral-divider">
        <div className="flex-1 flex items-center bg-surface-card rounded-md border border-neutral-border px-4 py-3 transition focus-within:border-primary-300">
          <input
            type="text" value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="질문을 입력하세요..." className="border-none bg-transparent text-sm text-neutral-main w-full outline-none"
          />
        </div>
        <button onClick={handleSend} className="w-11 h-11 rounded-md bg-primary-700 flex items-center justify-center transition hover:bg-primary-900">
          <svg width="18" height="18" viewBox="0 0 18 18"><path d="M2 9L16 2L12 16L9 10L2 9Z" fill="white"/></svg>
        </button>
      </div>
    </div>
  );
}
