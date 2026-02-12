import { useState } from 'react';
import IntentBadge from './IntentBadge';

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-neutral-100 text-neutral-muted hover:text-neutral-main"
      aria-label="메시지 복사"
      title={copied ? '복사됨!' : '복사'}
    >
      {copied ? (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      )}
    </button>
  );
}

function getPlainText(children) {
  if (typeof children === 'string') return children;
  if (Array.isArray(children)) return children.map(getPlainText).join('');
  if (children?.props?.children) return getPlainText(children.props.children);
  return '';
}

export default function MessageBubble({ type = 'user', children, intent, confidence, confidenceLabel }) {
  const plainText = getPlainText(children);

  if (type === 'user') {
    return (
      <div className="flex justify-end mb-4 group">
        <div className="flex items-start gap-1 max-w-[70%]">
          <CopyButton text={plainText} />
          <div className="bg-primary-700 text-white rounded-2xl rounded-br-sm px-4 py-3 text-sm leading-relaxed">
            {children}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-2.5 mb-5 group">
      <div className="w-8 h-8 rounded-[10px] bg-gradient-to-br from-primary-500 to-accent-500 flex-shrink-0 flex items-center justify-center text-white text-[0.6875rem] font-bold">AI</div>
      <div className="max-w-[70%]">
        {intent && <IntentBadge intent={intent} confidence={confidence} confidenceLabel={confidenceLabel} />}
        <div className="flex items-start gap-1">
          <div>{children}</div>
          <CopyButton text={plainText} />
        </div>
      </div>
    </div>
  );
}
