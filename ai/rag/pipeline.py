"""
RAG 파이프라인 (팀원 B 담당)

파이프라인:
  사용자 질문
  → BM25 검색 (Top 15) + Vector 검색 (Top 15)
  → 합산 (Top 20)
  → Reranker 관련도 재정렬 (Top 5)
  → sLLM에 전달
"""
from ai.rag.hybrid_search import HybridSearcher
from ai.rag.reranker import Reranker


class RAGPipeline:
    """RAG 파이프라인 메인 클래스"""

    def __init__(self):
        self.searcher = HybridSearcher()
        self.reranker = Reranker()

    def retrieve(self, query: str, user_id: int, top_k: int = 5) -> list:
        """
        검색 + Reranking

        Args:
            query: 사용자 질문
            user_id: 사용자 ID (scope 필터용)
            top_k: 최종 반환 문서 수

        Returns:
            list of {"content": str, "source": str, "score": float}
        """
        # TODO: 팀원 B 구현
        # 1. Hybrid Search (BM25 + Vector) → Top 20
        # 2. Reranker → Top 5
        # 3. scope 필터 (company + 본인 personal)
        raise NotImplementedError
