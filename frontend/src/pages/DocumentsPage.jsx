import { useState } from 'react';
import FilterBar from '../components/common/FilterBar';
import DocumentUpload from '../components/documents/DocumentUpload';
import DocumentList from '../components/documents/DocumentList';
import DocumentDetail from '../components/documents/DocumentDetail';

const mockDocs = [
  { name: '정보보안 지침', category: '규정', version: 'v2.3', status: '적용중', date: '2026-02-05', riskLevel: 'low', analysis: '총 42개 조항 파싱 완료. 주요 변경: 3.2조 외부 접근 권한 강화, 5.1조 테스트 환경 분리 기준 추가.' },
  { name: '인사규정 매뉴얼', category: '규정', version: 'v1.8', status: '개정중', date: '2026-01-28', riskLevel: 'medium' },
  { name: '개발 가이드라인', category: '규정', version: 'v3.1', status: '적용중', date: '2026-01-20', riskLevel: 'low' },
  { name: '2025 보안점검 회의록', category: '회의록', version: '-', status: '완료', date: '2026-02-03' },
  { name: 'Q4 예산 보고서', category: '보고서', version: 'v1.0', status: '검토중', date: '2026-01-15' },
];

export default function DocumentsPage() {
  const [activeTab, setActiveTab] = useState('전체');
  const [selectedDoc, setSelectedDoc] = useState(mockDocs[0]);
  const [searchQuery, setSearchQuery] = useState('');

  const filteredDocs = mockDocs.filter((doc) => {
    const matchTab = activeTab === '전체' || doc.category === activeTab;
    const matchSearch = !searchQuery || doc.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchTab && matchSearch;
  });

  return (
    <div>
      <header className="flex justify-between items-center py-6 sticky top-0 bg-surface-main z-10">
        <div><h1 className="text-2xl font-bold">문서 관리</h1><p className="text-sm text-neutral-sub mt-1">회사 규정 및 문서를 관리합니다</p></div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-surface-card border border-neutral-border rounded-md px-4 py-2 min-w-[280px]"><span>🔍</span><input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="문서 검색..." className="border-none bg-transparent text-[13px] w-full outline-none" /></div>
        </div>
      </header>
      <FilterBar tabs={['전체', '규정', '회의록', '보고서']} activeTab={activeTab} onTabChange={setActiveTab}
        filters={<><select className="px-3.5 py-2 rounded-sm border border-neutral-border bg-surface-card text-[13px]"><option>상태: 전체</option></select><select className="px-3.5 py-2 rounded-sm border border-neutral-border bg-surface-card text-[13px]"><option>구분: 전체</option></select></>}
        actions={<button className="btn-primary">+ 문서 업로드</button>}
      />
      <DocumentUpload />
      <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-5">
        <DocumentList documents={filteredDocs} onSelect={setSelectedDoc} searchQuery={searchQuery} />
        <DocumentDetail doc={selectedDoc} searchQuery={searchQuery} />
      </div>
    </div>
  );
}
