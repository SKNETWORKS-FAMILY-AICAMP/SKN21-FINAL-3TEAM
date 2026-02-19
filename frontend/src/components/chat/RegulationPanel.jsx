import KeywordHighlight from '../common/KeywordHighlight';
import { BookOpen } from 'lucide-react';

export default function RegulationPanel({ regulations = [], isOpen, onClose, searchQuery = '' }) {
  if (!isOpen) return null;

  return (
    <div className="w-[320px] flex-shrink-0 border-l border-neutral-divider bg-surface-card h-full overflow-y-auto ml-5 -mr-8">
      <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-divider">
        <div className="text-[0.9375rem] font-bold text-neutral-main flex items-center gap-2">
          <BookOpen size={16} />관련 규정
        </div>
        <button
          aria-label="규정 패널 닫기"
          onClick={onClose}
          className="w-7 h-7 rounded-md flex items-center justify-center text-neutral-muted hover:bg-surface-hover transition"
        >
          ✕
        </button>
      </div>
      <div className="p-4 space-y-3">
        {regulations.length === 0 && (
          <p className="text-sm text-neutral-muted text-center py-8">관련 규정이 없습니다</p>
        )}
        {regulations.map((reg, i) => (
          <div key={i} className="p-3 rounded-sm border border-neutral-divider hover:border-primary-300 transition">
            <div className="text-[0.8125rem] font-semibold text-neutral-main mb-1">
              <KeywordHighlight text={reg.name} keyword={searchQuery} />
            </div>
            {reg.article && (
              <div className="text-xs text-primary-700 font-medium mb-1.5">
                <KeywordHighlight text={reg.article} keyword={searchQuery} />
              </div>
            )}
            {reg.content && (
              <p className="text-xs text-neutral-sub leading-relaxed">
                <KeywordHighlight text={reg.content} keyword={searchQuery} />
              </p>
            )}
            {reg.relevance && (
              <div className="mt-2 flex items-center gap-1 text-[0.6875rem] text-neutral-muted">
                <span>관련도</span>
                <div className="flex-1 h-1.5 bg-neutral-divider rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary-500 rounded-full"
                    style={{ width: `${Math.round(reg.relevance * 100)}%` }}
                  />
                </div>
                <span>{Math.round(reg.relevance * 100)}%</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
