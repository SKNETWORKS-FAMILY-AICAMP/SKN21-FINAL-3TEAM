import { useRef, useCallback, useState } from 'react';
import Badge from '../common/Badge';
import KeywordHighlight from '../common/KeywordHighlight';
import { Pencil, Check, X, ShieldCheck } from 'lucide-react';
import { updateDocumentAnalysis, updateDocumentScope, checkDocumentRegulations } from '../../api/documents';

const CATEGORIES = ['회의록', '계약서', '제안서', '보고서', '정책문서', '인사문서', '기타'];

export default function DocumentDetail({ doc, documentDetail, searchQuery = '', onDelete, onAnalysisUpdate }) {
  const printRef = useRef(null);
  const [editing, setEditing] = useState(false);
  const [editCategory, setEditCategory] = useState('');
  const [editTags, setEditTags] = useState('');
  const [editSummary, setEditSummary] = useState('');
  const [saving, setSaving] = useState(false);
  const [editingScope, setEditingScope] = useState(false);
  const [scopeValue, setScopeValue] = useState('');
  const [savingScope, setSavingScope] = useState(false);
  const [regChecking, setRegChecking] = useState(false);
  const [regResult, setRegResult] = useState(null);

  const SCOPE_OPTIONS = [
    { value: 'company', label: '회사' },
    { value: 'team', label: '팀' },
  ];

  const startScopeEdit = () => {
    setScopeValue(doc.scope || documentDetail?.scope || 'company');
    setEditingScope(true);
  };

  const saveScopeEdit = async () => {
    setSavingScope(true);
    try {
      await updateDocumentScope(doc.id, scopeValue);
      onAnalysisUpdate?.({ ...documentDetail, scope: scopeValue });
      setEditingScope(false);
    } catch {
      alert('공개범위 변경에 실패했습니다.');
    } finally {
      setSavingScope(false);
    }
  };

  // 문서 변경 시 규정 결과 초기화
  const docId = doc?.id;
  const [prevDocId, setPrevDocId] = useState(null);
  if (docId !== prevDocId) {
    setPrevDocId(docId);
    setRegResult(null);
  }

  const handleRegCheck = async () => {
    if (!doc?.id) return;
    setRegChecking(true);
    setRegResult(null);
    try {
      const res = await checkDocumentRegulations(doc.id);
      setRegResult(res.data);
    } catch (e) {
      setRegResult({ checked: true, notes: [], error: e.response?.data?.detail || '규정 검증 실패' });
    } finally {
      setRegChecking(false);
    }
  };

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

  if (!doc) return <div className="card p-10 text-center text-neutral-muted text-sm max-h-[82vh]">문서를 선택하세요</div>;

  const isRealDocument = doc.id && documentDetail;
  const content = isRealDocument ? documentDetail.content : doc.analysis;
  const hasAnalysis = isRealDocument;

  return (
    <div className="bg-surface-card rounded-2xl border border-neutral-border p-5 max-h-[82vh] overflow-y-auto" ref={printRef}>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-base font-bold"><KeywordHighlight text={doc.name} keyword={searchQuery} /></h3>
        <Badge variant={doc.status === '적용중' ? 'status-active' : 'status-revising'}>{doc.status}</Badge>
      </div>
      <div className="mb-4">
        <div className="text-[0.8125rem] font-bold text-neutral-main mb-2 flex items-center gap-1.5">기본 정보</div>
        <div className="text-[0.8125rem] text-neutral-sub leading-[1.7]">
          분류: {isRealDocument && documentDetail?.category ? documentDetail.category : doc.category} · 버전: {doc.version} · 수정일: {doc.date}
          <br/>
          <span className="inline-flex items-center gap-1">
            범위:
            {isRealDocument && editingScope ? (
              <>
                <select
                  value={scopeValue}
                  onChange={e => setScopeValue(e.target.value)}
                  className="text-[0.8125rem] px-1.5 py-0.5 rounded border border-neutral-border bg-surface-card ml-1"
                >
                  {SCOPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
                <button onClick={saveScopeEdit} disabled={savingScope} className="text-primary-600 hover:text-primary-800 ml-1"><Check size={14} /></button>
                <button onClick={() => setEditingScope(false)} disabled={savingScope} className="text-neutral-muted hover:text-neutral-main"><X size={14} /></button>
              </>
            ) : (
              <>
                {(() => {
                  const s = isRealDocument ? (documentDetail?.scope || doc.scope) : doc.scope;
                  return s === 'company' ? '회사' : s === 'team' ? '팀' : s === 'personal' ? '개인' : '회사';
                })()}
                {isRealDocument && (
                  <button onClick={startScopeEdit} className="text-primary-600 hover:text-primary-800 ml-1"><Pencil size={12} /></button>
                )}
              </>
            )}
          </span>
          {' '}· 파싱 상태: 완료
        </div>
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

      {/* 규정 검증 — 버튼으로 실행 */}
      {isRealDocument && (
        <div className="mb-4">
          <div className="text-[0.8125rem] font-bold text-neutral-main mb-2 flex items-center gap-1.5 justify-between">
            <span className="flex items-center gap-1.5">
              <ShieldCheck size={14} />
              규정 검증
            </span>
            <button
              onClick={handleRegCheck}
              disabled={regChecking}
              className="text-[0.7rem] px-3 py-1 rounded-full border border-primary-600 bg-primary-50 text-primary-700 hover:bg-primary-700 hover:text-white hover:border-primary-700 flex items-center gap-1 disabled:opacity-50 dark:bg-primary-900/20 dark:text-primary-300 dark:hover:bg-primary-700 dark:hover:text-white transition-colors"
            >
              <ShieldCheck size={11} />
              {regChecking ? '검사 중...' : '규정 검사'}
            </button>
          </div>
          {regChecking && (
            <div className="bg-surface-main p-3 rounded border border-neutral-border text-center">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary-500 mx-auto mb-2"></div>
              <p className="text-[0.75rem] text-neutral-muted">규정 검증 중... (최대 1~2분 소요)</p>
            </div>
          )}
          {regResult?.error && (
            <div className="bg-red-50 dark:bg-red-900/20 p-2.5 rounded-lg border border-red-200 dark:border-red-800">
              <p className="text-[0.75rem] text-red-600 dark:text-red-400">{regResult.error}</p>
            </div>
          )}
          {regResult && !regResult.error && regResult.notes?.length === 0 && (
            regResult.fail_count > 0 ? (
              <div className="bg-amber-50 dark:bg-amber-900/20 p-2.5 rounded-lg border border-amber-200 dark:border-amber-800">
                <p className="text-[0.75rem] text-amber-600 dark:text-amber-400">
                  규정 검색에 실패했습니다 ({regResult.fail_count}/{regResult.total_queries}건). 잠시 후 다시 시도해주세요.
                </p>
              </div>
            ) : (
              <div className="bg-green-50 dark:bg-green-900/20 p-2.5 rounded-lg border border-green-200 dark:border-green-800">
                <p className="text-[0.75rem] text-green-600 dark:text-green-400">규정 위반 사항이 발견되지 않았습니다.</p>
              </div>
            )
          )}
          {regResult?.notes?.length > 0 && (
            <div className="space-y-2">
              {regResult.notes.map((note, idx) => (
                <div
                  key={idx}
                  className={`flex items-start gap-1.5 p-2.5 rounded-lg border ${
                    note.result === 'no'
                      ? 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
                      : 'bg-amber-50 border-amber-200 dark:bg-amber-900/20 dark:border-amber-800'
                  }`}
                >
                  <ShieldCheck size={13} className={`shrink-0 mt-0.5 ${note.result === 'no' ? 'text-red-500' : 'text-amber-500'}`} />
                  <div>
                    <p className={`text-[0.75rem] font-bold ${note.result === 'no' ? 'text-red-600 dark:text-red-400' : 'text-amber-600 dark:text-amber-400'}`}>
                      {note.result === 'no' ? '규정 위반' : '규정 확인 필요'} — {note.topic}
                    </p>
                    <p className="text-[0.6875rem] text-neutral-sub leading-relaxed mt-0.5">{note.reason}</p>
                    {note.regulation && note.regulation !== 'no_regulation' && (
                      <p className="text-[0.6875rem] text-neutral-muted mt-0.5">근거: {note.regulation}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          {!regChecking && !regResult && (
            <p className="text-[0.75rem] text-neutral-muted">버튼을 눌러 문서의 규정 준수 여부를 검사합니다.</p>
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
