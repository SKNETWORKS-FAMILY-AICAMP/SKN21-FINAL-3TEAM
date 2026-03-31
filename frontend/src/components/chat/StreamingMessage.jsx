import { useRef, useEffect, useState } from 'react';
import { Wand2, Scale, FileSearch, CalendarDays, MessageCircle } from 'lucide-react';
import MarkdownText from './MarkdownText';

const INTENT_CONFIG = {
  judgment: { icon: Scale, color: 'bg-primary-500' },
  doc_retrieve: { icon: FileSearch, color: 'bg-accent-500' },
  doc_search: { icon: FileSearch, color: 'bg-accent-500' },
  doc_summary: { icon: FileSearch, color: 'bg-accent-500' },
  schedule: { icon: CalendarDays, color: 'bg-success' },
  general: { icon: MessageCircle, color: 'bg-neutral-500' },
};

export default function StreamingMessage({ text, status, intent = 'general', isInsideBubble = false, isStreaming = true }) {
  const config = INTENT_CONFIG[intent] || { icon: Wand2, color: 'bg-primary-600' };
  const Icon = config.icon;
  const trimmedText = (text || '').trimEnd();
  const containerRef = useRef(null);
  const [minHeight, setMinHeight] = useState(0);
  const prevStreamingRef = useRef(isStreaming);

  // 스트리밍 → 완료 전환 시 min-height 고정하여 레이아웃 점프 방지
  useEffect(() => {
    if (prevStreamingRef.current && !isStreaming && containerRef.current) {
      setMinHeight(containerRef.current.offsetHeight);
      // 마크다운 렌더링 후 min-height 해제 (전환 완료)
      const timer = setTimeout(() => setMinHeight(0), 300);
      return () => clearTimeout(timer);
    }
    prevStreamingRef.current = isStreaming;
  }, [isStreaming]);

  const content = (
    <>
      {trimmedText ? (
        <div
          ref={containerRef}
          className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main shadow-sm relative leading-relaxed"
          style={{ wordBreak: 'keep-all', overflowWrap: 'break-word', minHeight: minHeight || undefined }}
        >
          <div className={isStreaming ? '' : 'transition-opacity duration-150'}>
            {isStreaming ? (
              <div className="whitespace-pre-wrap">{trimmedText}</div>
            ) : (
              <MarkdownText>{trimmedText}</MarkdownText>
            )}
          </div>
          {isStreaming && (
            <span className="inline-block w-1.5 h-3.5 bg-primary-400 ml-0.5 animate-pulse rounded-full align-middle" />
          )}
        </div>
      ) : (
        <div className="flex items-center gap-3 py-3.5 px-4 bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm">
          <span className="text-xs text-neutral-muted">{status || '답변을 생성하고 있어요'}</span>
          <div className="flex gap-1.5">
            {[0, 1, 2].map((i) => (
              <span key={i} className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
            ))}
          </div>
        </div>
      )}
    </>
  );

  if (isInsideBubble) {
    return <div className="max-w-full">{content}</div>;
  }

  return (
    <div className="flex gap-2.5">
      <div className={`w-8 h-8 rounded-md ${config.color} flex-shrink-0 flex items-center justify-center text-white shadow-sm`}>
        <Icon size={18} />
      </div>
      <div className="max-w-[85%]">
        {content}
      </div>
    </div>
  );
}
