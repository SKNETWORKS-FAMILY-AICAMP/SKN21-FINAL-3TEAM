import Badge from '../common/Badge';
import DataTable from '../common/DataTable';
import KeywordHighlight from '../common/KeywordHighlight';
import CustomSelect from '../common/CustomSelect';
import { FileText } from 'lucide-react';

export default function DocumentList({ documents = [], onSelect, searchQuery = '', scopeFilter = '전체', onScopeFilterChange }) {
  const columns = [
    { key: 'name', label: '문서명', render: (v) => <span className="font-semibold"><KeywordHighlight text={v} keyword={searchQuery} /></span> },
    { key: 'category', label: '분류', render: (v) => <Badge variant={v === '규정' ? 'intent' : v === '회의록' ? 'document' : 'status-revising'}>{v}</Badge> },
    { key: 'version', label: '버전' },
    { key: 'status', label: '상태', render: (v) => <Badge variant={v === '적용중' || v === '완료' ? 'status-active' : 'status-revising'}>{v}</Badge> },
    { key: 'date', label: '수정일' },
  ];

  return (
    <div className="card">
      <div className="card-header">
        <div className="flex items-center gap-4">
          <div className="card-title"><FileText size={16} className="text-neutral-sub" />문서 목록</div>
          <CustomSelect
            value={scopeFilter}
            onChange={onScopeFilterChange}
            options={['전체', '회사', '팀']}
          />
        </div>
        <span className="text-xs text-neutral-muted" data-testid="doc-count">총 {documents.length}개 문서</span>
      </div>
      <div className="overflow-x-auto">
        <DataTable columns={columns} data={documents} onRowClick={onSelect} />
      </div>
    </div>
  );
}
