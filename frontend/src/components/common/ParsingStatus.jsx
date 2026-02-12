import { PARSING_STATUS, PARSING_STATUS_LABELS } from '../../utils/constants';

const STEPS = [
  PARSING_STATUS.UPLOADING,
  PARSING_STATUS.PARSING,
  PARSING_STATUS.COMPLETED,
];

const statusStyles = {
  uploading: { color: 'text-primary-700', bg: 'bg-primary-50', icon: '↑', spin: true },
  parsing: { color: 'text-warning', bg: 'bg-warning-bg', icon: '⟳', spin: true },
  completed: { color: 'text-success', bg: 'bg-success-bg', icon: '✓', spin: false },
  failed: { color: 'text-error', bg: 'bg-error-bg', icon: '✕', spin: false },
};

export default function ParsingStatus({ status = 'uploading', fileName }) {
  const style = statusStyles[status] || statusStyles.uploading;
  const currentIdx = STEPS.indexOf(status);
  const isFailed = status === PARSING_STATUS.FAILED;

  return (
    <div className={`flex items-center gap-3 px-4 py-3 rounded-md border border-neutral-divider ${style.bg}`}>
      {/* 아이콘 */}
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${style.bg} ${style.color} ${style.spin ? 'animate-spin' : ''}`}>
        {style.icon}
      </div>

      <div className="flex-1 min-w-0">
        {/* 파일명 */}
        {fileName && <p className="text-xs text-neutral-muted truncate mb-1">{fileName}</p>}

        {/* 상태 텍스트 */}
        <p className={`text-sm font-semibold ${style.color}`}>
          {PARSING_STATUS_LABELS[status] || status}
        </p>

        {/* 단계 프로그레스 바 (실패가 아닌 경우) */}
        {!isFailed && (
          <div className="flex gap-1 mt-2">
            {STEPS.map((step, i) => (
              <div
                key={step}
                className={`h-1.5 flex-1 rounded-full transition-all ${
                  i <= currentIdx ? 'bg-primary-500' : 'bg-neutral-divider'
                }`}
              />
            ))}
          </div>
        )}

        {/* 실패 메시지 */}
        {isFailed && (
          <p className="text-xs text-error mt-1">파싱에 실패했습니다. 파일을 다시 업로드해 주세요.</p>
        )}
      </div>
    </div>
  );
}
