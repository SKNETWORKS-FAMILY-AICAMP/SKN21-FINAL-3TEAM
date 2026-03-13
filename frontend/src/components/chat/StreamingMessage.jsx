import { Wand2, Scale, FileSearch, CalendarDays, MessageCircle } from 'lucide-react';

const INTENT_CONFIG = {
  judgment: { icon: Scale, color: 'bg-primary-500' },
  doc_retrieve: { icon: FileSearch, color: 'bg-accent-500' },
  doc_search: { icon: FileSearch, color: 'bg-accent-500' },
  doc_summary: { icon: FileSearch, color: 'bg-accent-500' },
  schedule: { icon: CalendarDays, color: 'bg-success' },
  general: { icon: MessageCircle, color: 'bg-neutral-500' },
};

export default function StreamingMessage({ text, status, intent = 'general', isInsideBubble = false }) {
  const config = INTENT_CONFIG[intent] || { icon: Wand2, color: 'bg-primary-600' };
  const Icon = config.icon;
  const trimmedText = (text || '').trimEnd();

  const content = (
    <>
      {trimmedText ? (
        <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main shadow-sm relative leading-relaxed whitespace-pre-wrap">
          {trimmedText}
          <span className="inline-block w-1.5 h-3.5 bg-primary-400 ml-1.5 animate-pulse rounded-full align-middle" />
        </div>
      ) : (
        <div className="flex items-center gap-3 py-3.5 px-4 bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm">
          <span className="text-xs text-neutral-muted">답변을 생성하고 있어요</span>
          <div className="flex gap-1.5">
            {[0, 1, 2].map((i) => (
              <span key={i} className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
            ))}
          </div>
        </div>
      )}
    </>
  );

  // MessageBubble 안에 렌더링될 때는 아이콘 없이 콘텐츠만 반환
  if (isInsideBubble) {
    return <div className="max-w-full">{content}</div>;
  }

  return (
    <div className="flex gap-2.5">
      <div className={`w-8 h-8 rounded-[10px] ${config.color} flex-shrink-0 flex items-center justify-center text-white shadow-sm`}>
        <Icon size={18} />
      </div>
      <div className="max-w-[85%]">
        {content}
      </div>
    </div>
  );
}
