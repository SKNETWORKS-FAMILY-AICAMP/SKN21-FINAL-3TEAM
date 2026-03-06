import { useEffect } from 'react';
import { X, CheckCircle, XCircle, Info, AlertTriangle } from 'lucide-react';
import useToastStore from '../../store/toastStore';

const configs = {
  success: {
    icon: CheckCircle,
    bg: 'bg-success-bg border-success/30',
    text: 'text-success',
    bar: 'bg-success',
  },
  error: {
    icon: XCircle,
    bg: 'bg-error-bg border-error/30',
    text: 'text-error',
    bar: 'bg-error',
  },
  info: {
    icon: Info,
    bg: 'bg-info-bg border-info/30',
    text: 'text-info',
    bar: 'bg-info',
  },
  warning: {
    icon: AlertTriangle,
    bg: 'bg-warning-bg border-warning/30',
    text: 'text-warning',
    bar: 'bg-warning',
  },
};

function ToastItem({ item, onRemove }) {
  const { icon: Icon, bg, text, bar } = configs[item.type] || configs.info;

  return (
    <div className={`flex items-start gap-3 pl-4 pr-3 py-3 rounded-xl border shadow-md min-w-[260px] max-w-sm overflow-hidden relative ${bg}`}>
      <div className={`absolute left-0 top-0 bottom-0 w-1 rounded-l-xl ${bar}`} />
      <Icon size={17} className={`${text} flex-shrink-0 mt-0.5`} />
      <p className={`text-sm font-medium flex-1 leading-snug text-neutral-main`}>{item.message}</p>
      <button
        onClick={() => onRemove(item.id)}
        className="text-neutral-muted hover:text-neutral-main transition flex-shrink-0 mt-0.5"
      >
        <X size={14} />
      </button>
    </div>
  );
}

function ConfirmModal({ message, onConfirm, onCancel }) {
  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 z-[9998] flex items-center justify-center bg-black/50"
      onClick={onCancel}
    >
      <div
        className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-xl shadow-2xl w-full max-w-sm mx-4 p-6 border border-white/40 dark:border-white/10"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-sm text-neutral-main leading-relaxed mb-6 whitespace-pre-wrap">{message}</p>
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel} className="btn-outline text-sm px-5 py-2">
            취소
          </button>
          <button onClick={onConfirm} className="btn-primary text-sm px-5 py-2">
            확인
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Toast() {
  const toasts = useToastStore((s) => s.toasts);
  const confirmState = useToastStore((s) => s.confirm);
  const removeToast = useToastStore((s) => s.removeToast);
  const resolveConfirm = useToastStore((s) => s.resolveConfirm);

  return (
    <>
      <div className="fixed top-5 right-5 z-[9999] flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div key={t.id} className="pointer-events-auto">
            <ToastItem item={t} onRemove={removeToast} />
          </div>
        ))}
      </div>

      {confirmState && (
        <ConfirmModal
          message={confirmState.message}
          onConfirm={() => resolveConfirm(true)}
          onCancel={() => resolveConfirm(false)}
        />
      )}
    </>
  );
}
