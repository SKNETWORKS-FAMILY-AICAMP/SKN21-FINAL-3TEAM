"""
Hybrid Search: BM25 + Vector Search (팀원 B 담당)
"""


class HybridSearcher:
    """BM25 키워드 검색 + 벡터 시멘틱 검색 결합"""

    def __init__(self):
        self.bm25 = None  # rank_bm25
        self.vector_store = None  # ChromaDB

    def search(self, query: str, top_k: int = 20) -> list:
        """
        BM25 (Top 15) + Vector (Top 15) → 합산 정렬 (Top K)

        Returns:
            list of {"content": str, "source": str, "bm25_score": float, "vector_score": float}
        """
        # TODO: 팀원 B 구현
        raise NotImplementedError
