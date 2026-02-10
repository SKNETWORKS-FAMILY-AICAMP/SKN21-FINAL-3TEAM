import IntentBadge from './IntentBadge';

export default function MessageBubble({ type = 'user', children, intent, confidence, confidenceLabel }) {
  if (type === 'user') {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[70%] bg-primary-700 text-white rounded-2xl rounded-br-sm px-4 py-3 text-sm leading-relaxed">
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-2.5 mb-5">
      <div className="w-8 h-8 rounded-[10px] bg-gradient-to-br from-primary-500 to-accent-500 flex-shrink-0 flex items-center justify-center text-white text-[11px] font-bold">AI</div>
      <div className="flex-1">
        {intent && <IntentBadge intent={intent} confidence={confidence} confidenceLabel={confidenceLabel} />}
        {children}
      </div>
    </div>
  );
}
