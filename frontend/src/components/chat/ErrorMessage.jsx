export default function ErrorMessage({ message, onRetry }) {
  return (
    <div className="flex gap-2.5 mb-5">
      <div className="w-8 h-8 rounded-[10px] bg-error-bg flex-shrink-0 flex items-center justify-center text-error text-sm font-bold">!</div>
      <div className="flex-1">
        <div className="bg-error-bg border border-error/20 rounded-2xl rounded-bl-sm p-4">
          <p className="text-sm text-error font-medium mb-1">요청을 처리하지 못했습니다</p>
          <p className="text-[13px] text-neutral-sub leading-relaxed">{message || '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-surface-card border border-neutral-border text-xs font-semibold text-neutral-main transition hover:bg-surface-hover"
            >
              ↻ 다시 시도
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
