import { FileText, X, Copy, ExternalLink, Hash, Bookmark, ChevronDown, ShieldCheck } from 'lucide-react';
import { motion } from 'framer-motion';
import { useState } from 'react';

export default function DocumentViewPanel({ doc, onClose }) {
  const [copied, setCopied] = useState(false);
  const [scoreOpen, setScoreOpen] = useState(false);

  if (!doc) return null;

  const handleCopy = () => {
    if (!doc.content) return;
    navigator.clipboard.writeText(doc.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: 0 }}
      exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      className="w-[55%] flex-shrink-0 border-l border-neutral-divider bg-surface-card h-full flex flex-col z-30 shadow-2xl"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-divider bg-surface-main">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary-50 text-primary-600 flex items-center justify-center">
            <FileText size={20} />
          </div>
          <div>
            <h2 className="text-sm font-bold text-neutral-main leading-tight">문서 상세 보기</h2>
            <p className="text-[10px] text-neutral-muted mt-0.5">Reference Document Preview</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${copied
                ? 'bg-success-50 text-success-600'
                : 'text-neutral-sub hover:bg-neutral-divider hover:text-neutral-main'
              }`}
            title="클립보드에 복사"
          >
            <Copy size={14} />
            {copied ? '복사됨' : '복사'}
          </button>

          <div className="w-px h-4 bg-neutral-divider mx-1" />

          <button
            aria-label="문서 패널 닫기"
            onClick={onClose}
            className="w-8 h-8 rounded-md flex items-center justify-center text-neutral-muted hover:bg-neutral-divider hover:text-neutral-main transition-all"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto px-8 py-6 custom-scrollbar">
        {/* Title & Metadata Section */}
        <div className="mb-8">
          <h1 className="text-xl font-bold text-neutral-main leading-tight mb-4 tracking-tight">
            {doc.title || doc.name || doc.source || '제목 없는 문서'}
          </h1>

          <div className="flex flex-wrap gap-2">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-primary-50 text-primary-700 rounded-full text-xs font-semibold border border-primary-100">
              <Bookmark size={12} />
              {doc.category || '사내규정'}
            </div>

            {(doc.article || doc.article_number) && (
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-accent-50 text-accent-700 rounded-full text-xs font-semibold border border-accent-100">
                <Hash size={12} />
                {doc.article || doc.article_number}
              </div>
            )}

            {doc.page && (
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-neutral-divider text-neutral-sub rounded-full text-xs font-semibold">
                p.{doc.page}
              </div>
            )}

            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-neutral-divider text-neutral-sub rounded-full text-xs font-semibold">
              Source: {doc.source || 'Unknown'}
            </div>
          </div>
        </div>

        {/* Document Body */}
        <div className="relative">
          <div className="absolute -left-4 top-0 bottom-0 w-1 bg-primary-500 rounded-full opacity-20" />

          <div className="bg-white p-6 rounded-xl border border-neutral-divider shadow-sm min-h-[300px]">
            {doc.content ? (
              <div className="text-[0.9375rem] text-neutral-main leading-[1.8] whitespace-pre-wrap font-sans">
                {doc.content}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-neutral-muted">
                <FileText size={48} className="opacity-10 mb-3" />
                <p className="text-sm">문서 내용이 비어 있습니다.</p>
              </div>
            )}
          </div>
        </div>

        {/* 검색 정확도 접이식 */}
        {typeof doc.score === 'number' && (() => {
          const pct = Math.round(doc.score * 100);
          const color = doc.score >= 0.7
            ? { bar: 'bg-green-500', text: 'text-green-600', bg: 'bg-green-50', label: '높음' }
            : doc.score >= 0.4
              ? { bar: 'bg-yellow-500', text: 'text-yellow-600', bg: 'bg-yellow-50', label: '보통' }
              : { bar: 'bg-red-500', text: 'text-red-600', bg: 'bg-red-50', label: '낮음' };
          return (
            <div className="mt-6 border border-neutral-divider rounded-xl overflow-hidden">
              <button
                onClick={() => setScoreOpen(!scoreOpen)}
                className="w-full flex items-center gap-2.5 px-5 py-3 hover:bg-surface-hover transition text-left"
              >
                <ShieldCheck size={16} className={color.text} />
                <span className="text-xs font-semibold text-neutral-main">검색 정확도</span>
                <div className="flex items-center gap-2 ml-auto mr-2">
                  <div className="w-24 h-2 bg-neutral-100 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${color.bar} transition-all duration-300`} style={{ width: `${pct}%` }} />
                  </div>
                  <span className={`text-xs font-bold ${color.text}`}>{pct}%</span>
                </div>
                <ChevronDown size={14} className={`text-neutral-muted transition-transform duration-200 ${scoreOpen ? 'rotate-180' : ''}`} />
              </button>
              {scoreOpen && (
                <div className="px-5 pb-4 space-y-3">
                  <div className="flex items-center gap-3">
                    <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[0.625rem] font-semibold ${color.bg} ${color.text}`}>
                      {color.label}
                    </div>
                    <span className="text-[0.6875rem] text-neutral-sub">
                      RAG 벡터 검색 유사도 점수
                    </span>
                  </div>
                  <div className="text-[0.6875rem] text-neutral-sub leading-relaxed">
                    {doc.score >= 0.7
                      ? '이 문서는 질문과 높은 연관성을 가지고 있습니다. 검색 결과의 신뢰도가 높습니다.'
                      : doc.score >= 0.4
                        ? '이 문서는 질문과 일부 연관성이 있습니다. 내용을 직접 확인하는 것을 권장합니다.'
                        : '이 문서는 질문과의 연관성이 낮습니다. 다른 출처도 함께 참고해 주세요.'}
                  </div>
                </div>
              )}
            </div>
          );
        })()}

        {/* Footer info */}
        <div className="mt-8 pt-6 border-t border-neutral-divider flex items-center justify-between text-[11px] text-neutral-muted">
          <span>AI Chatbot Reference System</span>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1"><ExternalLink size={10} /> 원본 확인 가능</span>
            <span>최종 업데이트: {new Date().toLocaleDateString()}</span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
