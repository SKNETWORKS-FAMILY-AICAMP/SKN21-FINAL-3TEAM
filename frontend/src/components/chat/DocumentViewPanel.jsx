import { FileText, X } from 'lucide-react';

export default function DocumentViewPanel({ doc, onClose }) {
  if (!doc) return null;

  return (
    <div className="w-[55%] flex-shrink-0 border-l border-neutral-divider bg-surface-card h-full flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-divider">
        <div className="text-[0.9375rem] font-bold text-neutral-main flex items-center gap-2">
          <FileText size={16} />문서 보기
        </div>
        <button
          aria-label="문서 패널 닫기"
          onClick={onClose}
          className="w-7 h-7 rounded-md flex items-center justify-center text-neutral-muted hover:bg-surface-hover transition"
        >
          <X size={15} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-neutral-main leading-snug">
            {doc.title || doc.name || doc.source}
          </h3>
          {doc.page && (
            <div className="text-xs text-primary-700 font-medium mt-0.5">p.{doc.page}</div>
          )}
        </div>
        {doc.content ? (
          <p className="text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">{doc.content}</p>
        ) : (
          <p className="text-sm text-neutral-muted text-center py-8">내용이 없습니다.</p>
        )}
      </div>
    </div>
  );
}
