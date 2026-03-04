import { Inbox } from 'lucide-react';

export default function EmptyState({
  icon: Icon = Inbox,
  title = '데이터가 없습니다',
  description,
  actionLabel,
  onAction,
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <div className="w-12 h-12 rounded-full bg-neutral-100 dark:bg-neutral-800 flex items-center justify-center mb-4">
        <Icon className="text-neutral-400 dark:text-neutral-500" size={24} />
      </div>
      <h3 className="text-sm font-semibold text-neutral-main mb-1">{title}</h3>
      {description && (
        <p className="text-xs text-neutral-sub max-w-xs">{description}</p>
      )}
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-4 px-4 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 transition-colors"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
