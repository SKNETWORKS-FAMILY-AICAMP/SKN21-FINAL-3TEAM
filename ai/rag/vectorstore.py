"""
Vector DB (ChromaDB) 관리 (팀원 B 담당)

Chunk 전략:
  - 규정 문서: 조항 단위
  - 회의록: 문단 단위
"""


class VectorStore:
    """ChromaDB 벡터 저장소"""

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self.client = None
        self.collection = None

    def initialize(self):
        """ChromaDB 초기화"""
        # TODO: 팀원 B 구현
        raise NotImplementedError

    def add_documents(self, documents: list, metadatas: list):
        """문서 청크 + 메타데이터 저장"""
        # TODO: 팀원 B 구현
        raise NotImplementedError

    def search(self, query_embedding: list, top_k: int = 15, filter: dict = None) -> list:
        """벡터 유사도 검색 (scope 필터 지원)"""
        # TODO: 팀원 B 구현
        raise NotImplementedError
