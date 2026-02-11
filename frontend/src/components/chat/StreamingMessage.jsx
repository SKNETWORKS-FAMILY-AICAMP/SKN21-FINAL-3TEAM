export default function StreamingMessage({ text, status }) {
  return (
    <div className="flex gap-2.5">
      <div className="w-8 h-8 rounded-[10px] bg-gradient-to-br from-primary-500 to-accent-500 flex-shrink-0 flex items-center justify-center text-white text-[0.6875rem] font-bold">AI</div>
      <div className="flex-1">
        {status && (
          <div className="flex items-center gap-2 px-4 py-2.5 bg-primary-50 rounded-sm mb-3 text-[0.8125rem] text-primary-700">
            📄 {status}
          </div>
        )}
        {text ? (
          <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">
            {text}<span className="inline-block w-0.5 h-4 bg-primary-500 ml-0.5 animate-pulse" />
          </div>
        ) : (
          <div className="flex gap-1 py-2">
            {[0, 1, 2].map((i) => (
              <span key={i} className="w-1.5 h-1.5 bg-primary-300 rounded-full" style={{ animation: `bounce 1.4s infinite ease-in-out ${i * 0.2}s` }} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
