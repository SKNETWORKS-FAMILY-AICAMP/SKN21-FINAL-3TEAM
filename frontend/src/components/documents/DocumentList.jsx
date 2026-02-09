import Badge from '../common/Badge';
import DataTable from '../common/DataTable';

export default function DocumentList({ documents = [], onSelect }) {
  const columns = [
    { key: 'name', label: '문서명', render: (v) => <span className="font-semibold">{v}</span> },
    { key: 'category', label: '분류', render: (v) => <Badge variant={v === '규정' ? 'intent' : v === '회의록' ? 'document' : 'status-revising'}>{v}</Badge> },
    { key: 'version', label: '버전' },
    { key: 'status', label: '상태', render: (v) => <Badge variant={v === '적용중' || v === '완료' ? 'status-active' : 'status-revising'}>{v}</Badge> },
    { key: 'date', label: '수정일' },
  ];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><span>📄</span>문서 목록</div>
        <span className="text-xs text-neutral-muted">총 {documents.length}개 문서</span>
      </div>
      <div className="overflow-x-auto">
        <DataTable columns={columns} data={documents} onRowClick={onSelect} />
      </div>
    </div>
  );
}
