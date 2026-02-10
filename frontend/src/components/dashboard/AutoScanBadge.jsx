const statusConfig = {
  scanning: {
    label: '자동 스캔 중',
    color: 'text-success',
    bg: 'bg-success-bg',
    dot: 'bg-success',
    animate: true,
  },
  completed: {
    label: '스캔 완료',
    color: 'text-primary-700',
    bg: 'bg-primary-50',
    dot: 'bg-primary-500',
    animate: false,
  },
  error: {
    label: '스캔 오류',
    color: 'text-error',
    bg: 'bg-error-bg',
    dot: 'bg-error',
    animate: false,
  },
  idle: {
    label: '대기 중',
    color: 'text-neutral-sub',
    bg: 'bg-surface-hover',
    dot: 'bg-neutral-muted',
    animate: false,
  },
};

export default function AutoScanBadge({ status = 'scanning', lastScan, detectedCount = 0 }) {
  const config = statusConfig[status] || statusConfig.idle;

  return (
    <div className={`inline-flex items-center gap-3 px-4 py-2.5 rounded-md border border-neutral-border ${config.bg}`}>
      <div className="flex items-center gap-1.5">
        <span className={`relative flex h-2.5 w-2.5`}>
          {config.animate && (
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${config.dot} opacity-75`} />
          )}
          <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${config.dot}`} />
        </span>
        <span className={`text-xs font-semibold ${config.color}`}>{config.label}</span>
      </div>
      {detectedCount > 0 && (
        <span className="text-xs font-semibold text-error bg-error-bg px-2 py-0.5 rounded-full">
          {detectedCount}건 감지
        </span>
      )}
      {lastScan && (
        <span className="text-[11px] text-neutral-muted">
          마지막 스캔: {lastScan}
        </span>
      )}
    </div>
  );
}
