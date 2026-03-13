import { useState } from 'react';
import Badge from '../common/Badge';
import DataTable from '../common/DataTable';
import KeywordHighlight from '../common/KeywordHighlight';
import CustomSelect from '../common/CustomSelect';
import EmptyState from '../common/EmptyState';
import { FileText, List, LayoutList } from 'lucide-react';

const CATEGORY_VARIANT = {
  '회의록': 'document',
  '계약서': 'intent',
  '제안서': 'status-active',
  '보고서': 'status-active',
  '정책문서': 'intent',
  '인사문서': 'status-revising',
  '기타': 'status-revising',
  '보고서': 'document',
  '기타': 'status-revising',
  'PDF': 'status-revising',
  'DOCX': 'status-revising',
  '문서': 'status-revising',
};

export default function DocumentList({ documents = [], onSelect, searchQuery = '', scopeFilter = '전체', onScopeFilterChange }) {
  const [viewMode, setViewMode] = useState('compact'); // 'compact' | 'detailed'

  const compactColumns = [
    {
      key: 'name',
      label: '문서명',
      render: (v, row) => {
        const scopeLabel = row.scope === 'company' ? '회사' : row.scope === 'team' ? '팀' : '개인';
        return (
          <div>
            <div className="font-semibold mb-1"><KeywordHighlight text={v} keyword={searchQuery} /></div>
            <div className="flex items-center gap-1.5 text-[0.6875rem] text-neutral-muted">
              {row.doc_type && row.doc_type !== '-' && (
                <><span>{row.doc_type}</span><span className="text-neutral-border">·</span></>
              )}
              <span>{scopeLabel}</span>
              <span className="text-neutral-border">·</span>
              <span>{row.date}</span>
            </div>
          </div>
        );
      },
    },
    {
      key: 'category',
      label: '분류',
      className: 'whitespace-nowrap',
      render: (v) => v
        ? <Badge variant={CATEGORY_VARIANT[v] || 'status-revising'}>{v}</Badge>
        : <span className="text-neutral-muted text-xs">-</span>,
    },
    {
      key: 'tags',
      label: '태그',
      className: 'min-w-[120px]',
      render: (v) => {
        if (!v || !Array.isArray(v) || v.length === 0) return <span className="text-neutral-muted text-xs">-</span>;
        const display = v.slice(0, 3);
        const remaining = v.length - 3;
        return (
          <div className="flex flex-wrap gap-1">
            {display.map((tag, i) => (
              <span key={i} className="inline-block px-1.5 py-0.5 text-[0.6875rem] rounded bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300 whitespace-nowrap">
                #{tag}
              </span>
            ))}
            {remaining > 0 && (
              <span className="text-[0.6875rem] text-neutral-muted">+{remaining}</span>
            )}
          </div>
        );
      },
    },
  ];

  const detailedColumns = [
    { key: 'name', label: '문서명', render: (v) => <span className="font-semibold"><KeywordHighlight text={v} keyword={searchQuery} /></span> },
    {
      key: 'scope',
      label: '공개\n범위',
      className: 'whitespace-nowrap',
      render: (v) => {
        const label = v === 'company' ? '회사' : v === 'team' ? '팀' : '개인';
        const variant = v === 'company' ? 'status-active' : v === 'team' ? 'intent' : 'status-revising';
        return <Badge variant={variant}>{label}</Badge>;
      },
    },
    { key: 'category', label: '분류', className: 'whitespace-nowrap', render: (v) => <Badge variant={CATEGORY_VARIANT[v] || 'status-revising'}>{v}</Badge> },
    {
      key: 'doc_type',
      label: '타입',
      className: 'whitespace-nowrap',
      render: (v) => v && v !== '-'
        ? <Badge variant={CATEGORY_VARIANT[v] || 'document'}>{v}</Badge>
        : <span className="text-neutral-muted text-xs">-</span>,
    },
    {
      key: 'tags',
      label: '태그',
      className: 'min-w-[140px]',
      render: (v) => {
        if (!v || !Array.isArray(v) || v.length === 0) return <span className="text-neutral-muted text-xs">-</span>;
        const display = v.slice(0, 3);
        const remaining = v.length - 3;
        return (
          <div className="flex flex-wrap gap-1">
            {display.map((tag, i) => (
              <span key={i} className="inline-block px-1.5 py-0.5 text-[0.6875rem] rounded bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300 whitespace-nowrap">
                #{tag}
              </span>
            ))}
            {remaining > 0 && (
              <span className="text-[0.6875rem] text-neutral-muted">+{remaining}</span>
            )}
          </div>
        );
      },
    },
    { key: 'date', label: '수정일', className: 'whitespace-nowrap' },
  ];

  const columns = viewMode === 'compact' ? compactColumns : detailedColumns;

  return (
    <div className="card flex flex-col max-h-[82vh]">
      <div className="card-header shrink-0">
        <div className="flex items-center gap-4">
          <div className="card-title"><FileText size={16} className="text-neutral-sub" />문서 목록</div>
          <CustomSelect
            value={scopeFilter}
            onChange={onScopeFilterChange}
            options={['전체', '회사', '팀']}
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-muted" data-testid="doc-count">총 {documents.length}개</span>
          <div className="flex gap-0.5 bg-surface-hover rounded-md p-0.5">
            <button
              onClick={() => setViewMode('compact')}
              className={`p-1 rounded transition ${viewMode === 'compact' ? 'bg-surface-card shadow-sm text-primary-700' : 'text-neutral-muted hover:text-neutral-sub'}`}
              title="간략히 보기"
            >
              <List size={14} />
            </button>
            <button
              onClick={() => setViewMode('detailed')}
              className={`p-1 rounded transition ${viewMode === 'detailed' ? 'bg-surface-card shadow-sm text-primary-700' : 'text-neutral-muted hover:text-neutral-sub'}`}
              title="상세히 보기"
            >
              <LayoutList size={14} />
            </button>
          </div>
        </div>
      </div>
      <div className={`flex-1 min-h-0 overflow-y-auto ${viewMode === 'detailed' ? 'overflow-x-auto' : ''}`}>
        {documents.length === 0 ? (
          <EmptyState icon={FileText} title="문서가 없습니다" description="문서를 업로드하면 여기에 표시됩니다" />
        ) : (
          <DataTable columns={columns} data={documents} onRowClick={onSelect} />
        )}
      </div>
    </div>
  );
}
