import { useState, useEffect } from 'react';
import FilterBar from '../components/common/FilterBar';
import DocumentUpload from '../components/documents/DocumentUpload';
import DocumentList from '../components/documents/DocumentList';
import DocumentDetail from '../components/documents/DocumentDetail';
import { uploadDocument, listDocuments, getDocument, deleteDocument } from '../api/documents';


export default function DocumentsPage() {
  const [activeTab, setActiveTab] = useState('전체');
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [scope, setScope] = useState('company');
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [documentDetail, setDocumentDetail] = useState(null);

  // 문서 목록 로드
  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const response = await listDocuments();
      setDocuments(response.data);
      // 첫 번째 문서를 자동 선택
      if (response.data.length > 0 && !selectedDoc) {
        const firstDoc = response.data[0];
        setSelectedDoc({
          id: firstDoc.id,
          name: firstDoc.title,
          category: firstDoc.file_type === 'pdf' ? 'PDF' : firstDoc.file_type === 'docx' ? 'DOCX' : '문서',
          version: '-',
          status: firstDoc.status === 'completed' ? '완료' : firstDoc.status === 'processing' ? '처리중' : '실패',
          date: new Date(firstDoc.created_at).toLocaleDateString('ko-KR'),
          scope: firstDoc.scope,
          file_type: firstDoc.file_type,
        });
      }
    } catch (error) {
      console.error('Failed to load documents:', error);
    }
  };

  // 파일 업로드 핸들러
  const handleUpload = async (files) => {
    if (!files || files.length === 0) return;

    const file = files[0];
    setLoading(true);

    try {
      const response = await uploadDocument(file, scope);
      const uploadedDoc = response.data;

      // 업로드 응답의 status 확인
      if (uploadedDoc.status === 'failed') {
        alert(`문서 업로드는 되었지만 텍스트 추출에 실패했습니다.\n파일: ${uploadedDoc.title}\n파일 형식을 확인해주세요.`);
      } else if (uploadedDoc.status === 'completed') {
        alert('문서가 성공적으로 업로드되었습니다.');
      } else {
        alert(`문서가 업로드되었습니다. (상태: ${uploadedDoc.status})`);
      }

      loadDocuments(); // 목록 새로고침
    } catch (error) {
      console.error('Upload failed:', error);
      alert('문서 업로드에 실패했습니다: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  // 실제 업로드된 문서를 화면에 표시하기 위해 포맷 변환
  const formattedDocs = documents.map(doc => ({
    id: doc.id,
    name: doc.title,
    category: doc.file_type === 'pdf' ? 'PDF' : doc.file_type === 'docx' ? 'DOCX' : '문서',
    version: '-',
    status: doc.status === 'completed' ? '완료' : doc.status === 'processing' ? '처리중' : '실패',
    date: new Date(doc.created_at).toLocaleDateString('ko-KR'),
    scope: doc.scope,
    file_type: doc.file_type,
    uploaded_by: doc.uploaded_by,
    created_at: doc.created_at,
  }));

  const filteredDocs = formattedDocs.filter((doc) => {
    const matchTab = activeTab === '전체' || doc.category === activeTab;
    const matchSearch = !searchQuery || doc.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchTab && matchSearch;
  });

  // 문서 선택 시 상세 정보 로드
  const handleSelectDoc = async (doc) => {
    setSelectedDoc(doc);

    // 실제 업로드된 문서인 경우 상세 정보 가져오기
    if (doc.id) {
      try {
        const response = await getDocument(doc.id);
        setDocumentDetail(response.data);
      } catch (error) {
        console.error('Failed to load document detail:', error);
        setDocumentDetail(null);
      }
    } else {
      setDocumentDetail(null);
    }
  };

  // 문서 삭제 핸들러
  const handleDeleteDoc = async (docId) => {
    if (!window.confirm('이 문서를 삭제하시겠습니까?')) return;

    try {
      await deleteDocument(docId);
      alert('문서가 삭제되었습니다.');
      loadDocuments();
      setSelectedDoc(null);
      setDocumentDetail(null);
    } catch (error) {
      console.error('Failed to delete document:', error);
      alert('문서 삭제에 실패했습니다: ' + (error.response?.data?.detail || error.message));
    }
  };

  return (
    <div>
      <header className="flex justify-between items-center py-6 sticky top-0 bg-surface-main z-10">
        <div><h1 className="text-2xl font-bold">문서 관리</h1><p className="text-sm text-neutral-sub mt-1">회사 규정 및 문서를 관리합니다</p></div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-surface-card border border-neutral-border rounded-md px-4 py-2 min-w-[280px]"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-neutral-muted flex-shrink-0"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="문서 검색..." className="border-none bg-transparent text-[0.8125rem] w-full outline-none" /></div>
        </div>
      </header>
      <FilterBar tabs={['전체', '규정', '회의록', '보고서']} activeTab={activeTab} onTabChange={setActiveTab}
        filters={<><select className="px-3.5 py-2 rounded-sm border border-neutral-border bg-surface-card text-[0.8125rem]"><option>상태: 전체</option></select><select className="px-3.5 py-2 rounded-sm border border-neutral-border bg-surface-card text-[0.8125rem]"><option>구분: 전체</option></select></>}
        actions={<button className="btn-primary">+ 문서 업로드</button>}
      />
      <DocumentUpload onUpload={handleUpload} onScopeChange={setScope} />
      <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-5">
        <DocumentList documents={filteredDocs} onSelect={handleSelectDoc} searchQuery={searchQuery} />
        <DocumentDetail
          doc={selectedDoc}
          documentDetail={documentDetail}
          searchQuery={searchQuery}
          onDelete={handleDeleteDoc}
        />
      </div>

      {loading && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4"></div>
              <p>업로드 중...</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
