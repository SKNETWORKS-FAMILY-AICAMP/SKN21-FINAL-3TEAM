import { useRef, useCallback, useState } from 'react';
import Badge from '../common/Badge';
import KeywordHighlight from '../common/KeywordHighlight';
import { Pencil, Check, X } from 'lucide-react';
import { updateDocumentAnalysis } from '../../api/documents';

const CATEGORIES = ['회의록', '계약서', '제안서', '보고서', '정책문서', '인사문서', '공지사항', '이메일', '기타'];

export default function DocumentDetail({ doc, documentDetail, searchQuery = '', onDelete, onAnalysisUpdate }) {
  const printRef = useRef(null);
  const [editing, setEditing] = useState(false);
  const [editCategory, setEditCategory] = useState('');
  const [editTags, setEditTags] = useState('');
  const [editSummary, setEditSummary] = useState('');
  const [saving, setSaving] = useState(false);

  const handlePrint = useCallback(() => {
    if (!printRef.current) return;
    printRef.current.classList.add('print-area');
    window.print();
    const cleanup = () => {
      printRef.current?.classList.remove('print-area');
      window.removeEventListener('afterprint', cleanup);
    };
    window.addEventListener('afterprint', cleanup);
  }, []);

  const startEdit = () => {
    setEditCategory(documentDetail?.category || '');
    setEditTags((documentDetail?.tags || []).join(', '));
    setEditSummary(documentDetail?.summary || '');
    setEditing(true);
  };

  const cancelEdit = () => setEditing(false);

  const saveEdit = async () => {
    setSaving(true);
    try {
      const tags = editTags.split(/[,，]/).map(t => t.trim()).filter(Boolean);
      const res = await updateDocumentAnalysis(doc.id, {
        category: editCategory || null,
        tags,
        summary: editSummary || null,
      });
      onAnalysisUpdate?.(res.data);
      setEditing(false);
    } catch {
      alert('저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  if (!doc) return <div className="card p-10 text-center text-neutral-muted text-sm">문서를 선택하세요</div>;

  const isRealDocument = doc.id && documentDetail;
  const content = isRealDocument ? documentDetail.content : doc.analysis;
  const hasAnalysis = isRealDocument;

  return (
    <div className="bg-surface-card rounded-md border border-neutral-border p-5" ref={printRef}>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-base font-bold"><KeywordHighlight text={doc.name} keyword={searchQuery} /></h3>
        <Badge variant={doc.status === '적용중' ? 'status-active' : 'status-revising'}>{doc.status}</Badge>
      </div>
      <div className="mb-4">
        <div className="text-[0.8125rem] font-bold text-neutral-main mb-2 flex items-center gap-1.5">기본 정보</div>
        <div className="text-[0.8125rem] text-neutral-sub leading-[1.7]">분류: {isRealDocument && documentDetail?.category ? documentDetail.category : doc.category} · 버전: {doc.version} · 수정일: {doc.date}<br/>범위: 회사 문서 · 파싱 상태: 완료</div>
      </div>

      {/* AI 분석 섹션 — 항상 표시 (분석 결과 없으면 수정 버튼만) */}
      {isRealDocument && (
        <div className="mb-4">
          <div className="text-[0.8125rem] font-bold text-neutral-main mb-2 flex items-center gap-1.5 justify-between">
            <span className="flex items-center gap-1.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a4 4 0 0 1 4 4c0 1.95-1.4 3.26-2.06 3.7L12 11l-1.94-1.3C9.4 9.26 8 7.95 8 6a4 4 0 0 1 4-4z"/><path d="M12 11v11"/><path d="m4.93 15.5 2.83-2.83"/><path d="m16.24 12.67 2.83 2.83"/><path d="m7.76 12.67-2.83 2.83"/><path d="m19.07 15.5-2.83-2.83"/></svg>
              AI 자동 분석
            </span>
            {!editing && (
              <button onClick={startEdit} className="text-[0.75rem] text-primary-600 hover:text-primary-800 flex items-center gap-1 font-normal">
                <Pencil size={12} /> 수정
              </button>
            )}
          </div>

          {editing ? (
            <div className="bg-surface-main p-3 rounded border border-primary-300 space-y-3">
              <div>
                <label className="text-[0.75rem] text-neutral-muted block mb-1">카테고리</label>
                <select
                  value={editCategory}
                  onChange={e => setEditCategory(e.target.value)}
                  className="w-full text-[0.8125rem] px-2 py-1.5 rounded border border-neutral-border bg-surface-card"
                >
                  <option value="">선택 안함</option>
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[0.75rem] text-neutral-muted block mb-1">태그 (쉼표로 구분)</label>
                <input
                  type="text"
                  value={editTags}
                  onChange={e => setEditTags(e.target.value)}
                  placeholder="태그1, 태그2, 태그3"
                  className="w-full text-[0.8125rem] px-2 py-1.5 rounded border border-neutral-border bg-surface-card"
                />
              </div>
              <div>
                <label className="text-[0.75rem] text-neutral-muted block mb-1">요약</label>
                <textarea
                  value={editSummary}
                  onChange={e => setEditSummary(e.target.value)}
                  rows={3}
                  className="w-full text-[0.8125rem] px-2 py-1.5 rounded border border-neutral-border bg-surface-card resize-none"
                />
              </div>
              <div className="flex gap-2 justify-end">
                <button onClick={cancelEdit} disabled={saving} className="text-[0.75rem] px-3 py-1 rounded border border-neutral-border text-neutral-muted hover:bg-surface-hover flex items-center gap-1">
                  <X size={12} /> 취소
                </button>
                <button onClick={saveEdit} disabled={saving} className="text-[0.75rem] px-3 py-1 rounded border border-primary-600 bg-primary-50 text-primary-700 hover:bg-primary-700 hover:text-white hover:border-primary-700 flex items-center gap-1 disabled:opacity-50 dark:bg-primary-900/20 dark:text-primary-300 dark:hover:bg-primary-700 dark:hover:text-white">
                  <Check size={12} /> {saving ? '저장 중...' : '저장'}
                </button>
              </div>
            </div>
          ) : hasAnalysis ? (
            <div className="bg-surface-main p-3 rounded border border-neutral-border space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-[0.75rem] text-neutral-muted">타입:</span>
                <Badge variant="document">{documentDetail.category || '미분류'}</Badge>
              </div>
              {documentDetail.tags?.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[0.75rem] text-neutral-muted">태그:</span>
                  {documentDetail.tags.map((tag, i) => (
                    <span key={i} className="inline-block px-2 py-0.5 text-[0.75rem] rounded-full bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300">
                      #{tag}
                    </span>
                  ))}
                </div>
              )}
              {documentDetail.summary && (
                <div>
                  <span className="text-[0.75rem] text-neutral-muted">요약:</span>
                  <p className="text-[0.8125rem] text-neutral-sub leading-[1.7] mt-1">{documentDetail.summary}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-surface-main p-3 rounded border border-neutral-border text-center">
              <p className="text-[0.8125rem] text-neutral-muted">분석 결과가 없습니다</p>
              <button onClick={startEdit} className="text-[0.75rem] text-primary-600 hover:text-primary-800 mt-1">
                직접 입력하기
              </button>
            </div>
          )}
        </div>
      )}

      {isRealDocument && content && (
        <div className="mb-4">
          <div className="text-[0.8125rem] font-bold text-neutral-main mb-2 flex items-center gap-1.5">문서 내용</div>
          <div className="bg-surface-main p-4 rounded border border-neutral-border max-h-96 overflow-y-auto">
            <pre className="text-[0.8125rem] text-neutral-sub leading-[1.7] whitespace-pre-wrap font-sans">
              <KeywordHighlight text={content} keyword={searchQuery} />
            </pre>
          </div>
        </div>
      )}
      {doc.riskLevel && !isRealDocument && (
        <div className="mb-4">
          <div className="text-[0.8125rem] font-bold text-neutral-main mb-2 flex items-center gap-1.5">AI 분석 결과</div>
          <Badge variant={`risk-${doc.riskLevel}`} className="mb-2">리스크: {doc.riskLevel === 'low' ? '낮음' : doc.riskLevel === 'medium' ? '중간' : '높음'}</Badge>
          {doc.analysis && <div className="text-[0.8125rem] text-neutral-sub leading-[1.7]"><KeywordHighlight text={doc.analysis} keyword={searchQuery} /></div>}
        </div>
      )}
      <div className="flex gap-2 mt-4 no-print">
        {isRealDocument ? (
          <>
            <button onClick={handlePrint} className="btn-primary">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
                <polyline points="6 9 6 2 18 2 18 9" />
                <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                <rect x="6" y="14" width="12" height="8" />
              </svg>
              인쇄
            </button>
            <button onClick={() => onDelete?.(doc.id)} className="btn-outline text-red-600 hover:bg-red-50 hover:border-red-300">
              삭제
            </button>
          </>
        ) : (
          <>
            <button className="btn-primary">원문 보기</button>
            <button className="btn-outline">다운로드</button>
            <button onClick={handlePrint} className="btn-outline">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
                <polyline points="6 9 6 2 18 2 18 9" />
                <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                <rect x="6" y="14" width="12" height="8" />
              </svg>
              인쇄
            </button>
          </>
        )}
      </div>
    </div>
  );
}
