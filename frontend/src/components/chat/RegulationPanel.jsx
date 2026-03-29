import { useState, useEffect } from 'react';
import KeywordHighlight from '../common/KeywordHighlight';
import { BookOpen, X, FileText } from 'lucide-react';

function RegulationModal({ reg, onClose }) {
  const [fullContent, setFullContent] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  useEffect(() => {
    const articleStr = reg.article_number || reg.article || '';
    const articleMatch = articleStr.match(/제\d+조/) || reg.name?.match(/제\d+조/);
    if (articleMatch) {
      setLoading(true);
      // 규정명(reg.name)을 title 힌트로 전달하여 정확한 조항 조회
      const titleHint = reg.name || reg.title || '';
      import('../../api/regulations').then(({ getRegulationByArticle }) => {
        getRegulationByArticle(articleMatch[0], titleHint)
          .then((res) => setFullContent(res.data?.content || res.content || null))
          .catch(() => setFullContent(null))
          .finally(() => setLoading(false));
      });
    }
  }, [reg]);

  const displayContent = fullContent || reg.content;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] flex flex-col border border-white/40 dark:border-white/10"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-neutral-divider">
          <div className="flex items-center gap-2 pr-4">
            <FileText size={16} className="text-primary-600 flex-shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-bold text-neutral-main leading-snug">{reg.name}</div>
              {reg.article && (
                <div className="text-xs text-primary-700 font-medium mt-0.5">{reg.article}</div>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-md flex items-center justify-center text-neutral-muted hover:bg-surface-hover transition flex-shrink-0"
          >
            <X size={15} />
          </button>
        </div>

        {/* 본문 */}
        <div className="overflow-y-auto px-5 py-4 flex-1">
          {loading ? (
            <p className="text-sm text-neutral-muted text-center py-8">규정 원문을 불러오는 중...</p>
          ) : displayContent ? (
            <p className="text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">{displayContent}</p>
          ) : (
            <p className="text-sm text-neutral-muted text-center py-8">내용이 없습니다.</p>
          )}
        </div>

        {/* 푸터 */}
        <div className="px-5 py-3 border-t border-neutral-divider flex justify-end">
          <button
            onClick={onClose}
            className="btn-outline text-xs px-4 py-1.5"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}

export default function RegulationPanel({ regulations = [], isOpen, onClose, searchQuery = '' }) {
  const [selectedReg, setSelectedReg] = useState(null);

  if (!isOpen) return null;

  return (
    <>
      <div className="w-[320px] flex-shrink-0 border-l border-neutral-divider bg-surface-card h-full overflow-y-auto ml-5">
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
            <button
              key={i}
              onClick={() => setSelectedReg(reg)}
              className="w-full text-left p-3 rounded-sm border border-neutral-divider hover:border-primary-300 hover:bg-surface-hover transition cursor-pointer"
            >
              <div className="text-[0.8125rem] font-semibold text-neutral-main mb-1">
                <KeywordHighlight text={reg.name} keyword={searchQuery} />
              </div>
              {reg.article && (
                <div className="text-xs text-primary-700 font-medium mb-1.5">
                  <KeywordHighlight text={reg.article} keyword={searchQuery} />
                </div>
              )}
              {reg.content && (
                <p className="text-xs text-neutral-sub leading-relaxed line-clamp-2">
                  <KeywordHighlight text={reg.content} keyword={searchQuery} />
                </p>
              )}
              {typeof reg.relevance === 'number' && !isNaN(reg.relevance) && (
                <div className="mt-2 flex items-center gap-1 text-[0.6875rem] text-neutral-muted">
                  <span>신뢰도</span>
                  <div className="flex-1 h-1.5 bg-neutral-divider rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary-500 rounded-full"
                      style={{ width: `${Math.round(reg.relevance * 100)}%` }}
                    />
                  </div>
                  <span>{Math.round(reg.relevance * 100)}%</span>
                </div>
              )}
              <div className="mt-2 text-[0.6875rem] text-primary-600 font-medium">전체 보기 →</div>
            </button>
          ))}
        </div>
      </div>

      {selectedReg && (
        <RegulationModal reg={selectedReg} onClose={() => setSelectedReg(null)} />
      )}
    </>
  );
}
