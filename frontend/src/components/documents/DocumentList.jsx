import { useState } from 'react';
import Badge from '../common/Badge';
import DataTable from '../common/DataTable';
import KeywordHighlight from '../common/KeywordHighlight';
import CustomSelect from '../common/CustomSelect';
import EmptyState from '../common/EmptyState';
import { FileText } from 'lucide-react';

const DOC_CATEGORIES = ['전체', '회의록', '계약서', '제안서', '보고서', '정책문서', '인사문서', '기타'];

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
  const [categoryFilter, setCategoryFilter] = useState('전체');

  const filteredByCategory = categoryFilter === '전체'
    ? documents
    : documents.filter(d => d.doc_type === categoryFilter);

  const columns = [
    {
      key: 'name',
      label: '문서명',
      render: (v, row) => {
        const scopeLabel = row.scope === 'company' ? '회사' : row.scope === 'team' ? '팀' : '개인';
        return (
          <div>
            <div className="font-semibold mb-1"><KeywordHighlight text={v} keyword={searchQuery} /></div>
            <div className="flex items-center gap-1.5 text-[0.6875rem] text-neutral-muted">
              {row.category && (
                <><span>{row.category}</span><span className="text-neutral-border">·</span></>
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
      key: 'doc_type',
      label: '분류',
      className: 'whitespace-nowrap',
      render: (v) => v && v !== '-'
        ? <Badge variant={CATEGORY_VARIANT[v] || 'document'}>{v}</Badge>
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

  return (
    <div className="card flex flex-col max-h-[82vh]">
      <div className="shrink-0">
        <div className="card-header !border-b-0 !pb-2">
          <div className="flex items-center gap-4">
            <div className="card-title"><FileText size={16} className="text-neutral-sub" />문서 목록</div>
            <CustomSelect
              value={scopeFilter}
              onChange={onScopeFilterChange}
              options={['전체', '회사', '팀']}
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-neutral-muted" data-testid="doc-count">총 {filteredByCategory.length}개</span>
          </div>
        </div>
        {/* 카테고리 필터 */}
        <div className="px-4 pt-1 pb-3 border-b border-neutral-divider">
          <div className="flex flex-wrap gap-1.5">
            {DOC_CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={`px-2.5 py-1 text-[0.75rem] rounded-full border transition whitespace-nowrap ${
                  categoryFilter === cat
                    ? 'bg-primary-100 text-primary-900 border-primary-400 font-semibold dark:bg-primary-900/40 dark:text-primary-200 dark:border-primary-500'
                    : 'bg-surface-card text-neutral-muted border-neutral-border hover:border-primary-300 hover:text-primary-700 dark:hover:border-primary-600 dark:hover:text-primary-300'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto">
        {filteredByCategory.length === 0 ? (
          <EmptyState icon={FileText} title={categoryFilter !== '전체' ? `"${categoryFilter}" 문서가 없습니다` : '문서가 없습니다'} description={categoryFilter !== '전체' ? '다른 분류를 선택해보세요' : '문서를 업로드하면 여기에 표시됩니다'} />
        ) : (
          <DataTable columns={columns} data={filteredByCategory} onRowClick={onSelect} />
        )}
      </div>
    </div>
  );
}
