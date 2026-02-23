import { Wand2, Scale, FileSearch, CalendarDays, MessageCircle } from 'lucide-react';

const INTENT_CONFIG = {
  judgment: { icon: Scale, color: 'bg-primary-500' },
  doc_search: { icon: FileSearch, color: 'bg-accent-500' },
  schedule: { icon: CalendarDays, color: 'bg-success' },
  general: { icon: MessageCircle, color: 'bg-neutral-500' },
};

export default function StreamingMessage({ text, status, intent = 'general' }) {
  const config = INTENT_CONFIG[intent] || { icon: Wand2, color: 'bg-primary-600' };
  const Icon = config.icon;

  return (
    <div className="flex gap-2.5">
      <div className={`w-8 h-8 rounded-[10px] ${config.color} flex-shrink-0 flex items-center justify-center text-white shadow-sm`}>
        <Icon size={18} />
      </div>
      <div className="max-w-[85%]">
        {status && (
          <div className="flex items-center gap-2 px-3 py-2 bg-primary-50 border border-primary-100 rounded-lg mb-3 text-[11px] font-medium text-primary-700 animate-pulse">
            {status}
          </div>
        )}
        {text ? (
          <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main shadow-sm relative leading-relaxed whitespace-pre-wrap">
            {text}
            <span className="inline-block w-1.5 h-3.5 bg-primary-400 ml-1.5 animate-pulse rounded-full align-middle" />
          </div>
        ) : (
          <div className="flex gap-1.5 py-3 px-4 bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm">
            {[0, 1, 2].map((i) => (
              <span key={i} className="w-1.5 h-1.5 bg-primary-300 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
