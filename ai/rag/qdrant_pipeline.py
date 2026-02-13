"""
Qdrant 기반 RAG 파이프라인

파이프라인:
  사용자 질문
  → BM25 검색 (Top 15) + Vector 검색 (Top 15)
  → 합산 (Top 20)
  → Reranker 관련도 재정렬 (Top 5)
  → AgentState.context에 저장 → Agent가 LLM에 전달
"""
import os
from dotenv import load_dotenv
from ai.rag.embeddings import EmbeddingModel
from ai.rag.hybrid_search import HybridSearcher
from ai.rag.reranker import Reranker
from ai.rag.qdrant_store import QdrantVectorStore

# 싱글턴 인스턴스
_pipeline_instance: "QdrantRAGPipeline | None" = None


class QdrantRAGPipeline:
    """Qdrant 기반 RAG 파이프라인"""

    def __init__(self, qdrant_url: str, qdrant_api_key: str, collection_name: str = "documents"):
        self.qdrant_url = qdrant_url
        self.qdrant_api_key = qdrant_api_key
        self.collection_name = collection_name

        self.embedding_model = EmbeddingModel()
        self.vector_store = QdrantVectorStore(
            url=qdrant_url,
            api_key=qdrant_api_key,
            collection_name=collection_name,
        )
        self.reranker = Reranker()
        self.searcher = HybridSearcher(
            vector_store=self.vector_store,
            embedding_model=self.embedding_model,
        )

    def initialize(self):
        """모델 로드 + Qdrant 초기화 + BM25 인덱스 구축"""
        self.embedding_model.load_model()
        self.reranker.load_model()
        self.vector_store.initialize(vector_size=768)
        self.searcher.build_bm25_index()
        return self

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict],
        batch_size: int = 100,
    ):
        """문서 추가 (임베딩 → Qdrant 저장 → BM25 재구축)

        Args:
            documents: 문서 텍스트 리스트
            metadatas: 메타데이터 리스트 (각 항목에 "source", "scope", "title" 등 포함)
            batch_size: 한 번에 처리할 문서 수 (메모리 관리용)
        """
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i : i + batch_size]
            batch_metas = metadatas[i : i + batch_size]

            # 임베딩 생성
            embeddings = self.embedding_model.encode(batch_docs)

            # Qdrant에 저장
            self.vector_store.add_documents(
                documents=batch_docs,
                embeddings=embeddings,
                metadatas=batch_metas,
            )

        # 전체 저장 완료 후 BM25 인덱스 한 번만 재구축
        self.searcher.build_bm25_index()

    def retrieve(self, query: str, user_id: int | None = None, top_k: int = 5) -> list[dict]:
        """검색 + Reranking

        Args:
            query: 사용자 질문
            user_id: 사용자 ID (scope 필터용)
            top_k: 최종 반환 문서 수

        Returns:
            list of {"content": str, "source": str, "title": str, "score": float, ...}
        """
        # 1. Hybrid Search (BM25 + Vector) → Top 20
        search_results = self.searcher.search(query=query, user_id=user_id, top_k=20)

        if not search_results:
            return []

        # 2. Reranker → Top K
        reranked = self.reranker.rerank(query=query, documents=search_results, top_k=top_k)

        return reranked


def get_qdrant_pipeline() -> QdrantRAGPipeline:
    """Qdrant RAG 파이프라인 싱글턴 인스턴스 반환"""
    global _pipeline_instance
    if _pipeline_instance is None:
        # .env 파일 로드
        load_dotenv()

        # 환경변수에서 Qdrant 설정 로드
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")

        if not qdrant_url or not qdrant_api_key:
            raise ValueError("QDRANT_URL과 QDRANT_API_KEY를 .env에 설정해야 합니다.")

        _pipeline_instance = QdrantRAGPipeline(
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
        )
        _pipeline_instance.initialize()
    return _pipeline_instance


def reset_qdrant_pipeline():
    """Qdrant RAG 파이프라인 싱글턴 인스턴스 초기화 (테스트/재구축용)"""
    global _pipeline_instance
    _pipeline_instance = None
