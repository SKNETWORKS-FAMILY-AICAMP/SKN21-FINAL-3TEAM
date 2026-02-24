"""
Qdrant 기반 RAG 파이프라인

파이프라인:
  사용자 질문
  → BM25 검색 (Top 15) + Vector 검색 (Top 15)
  → RRF 합산 (Top K)
  → AgentState.context에 저장 → Agent가 LLM에 전달

NOTE: Reranker(Cross-Encoder)는 성능 병목(~15초)으로 비활성화됨.
      BM25+Vector 하이브리드 검색의 RRF 머징으로 충분한 품질 확보.
"""
import logging
import os
import time

from dotenv import load_dotenv

from ai.rag.embeddings import EmbeddingModel
from ai.rag.hybrid_search import HybridSearcher
from ai.rag.qdrant_store import QdrantVectorStore

logger = logging.getLogger(__name__)

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
        self.searcher = HybridSearcher(
            vector_store=self.vector_store,
            embedding_model=self.embedding_model,
        )

    def initialize(self):
        """모델 로드 + Qdrant 초기화 + BM25 인덱스 구축"""
        _t = time.time()
        print("[RAGPipeline] initialize 시작...")

        _t_emb = time.time()
        self.embedding_model.load_model()
        print(f"[RAGPipeline]   임베딩 모델 로드: {time.time()-_t_emb:.2f}s")

        _t_qdrant = time.time()
        self.vector_store.initialize(vector_size=768)
        print(f"[RAGPipeline]   Qdrant 초기화: {time.time()-_t_qdrant:.2f}s")

        _t_bm25 = time.time()
        self.searcher.build_bm25_index()
        print(f"[RAGPipeline]   BM25 인덱스 구축: {time.time()-_t_bm25:.2f}s")

        print(f"[RAGPipeline] initialize 완료: {time.time()-_t:.2f}s")
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

    def retrieve(self, query: str, user_id: int | None = None, top_k: int = 5, filter: dict | None = None) -> list[dict]:
        """하이브리드 검색 (BM25 + Vector → RRF 합산)

        Args:
            query: 사용자 질문
            user_id: 사용자 ID (scope 필터용)
            top_k: 최종 반환 문서 수
            filter: 메타데이터 필터 (예: {"source": "regulations"})

        Returns:
            list of {"content": str, "source": str, "score": float, ...}
        """
        _t = time.time()
        print(f"[RAGPipeline] retrieve 시작 | query='{query[:50]}', top_k={top_k}, filter={filter}")

        # Hybrid Search (BM25 + Vector) → RRF 합산 → Top K
        search_results = self.searcher.search(query=query, user_id=user_id, top_k=top_k, filter=filter)
        print(f"[RAGPipeline] retrieve 완료 ({time.time()-_t:.2f}s) | {len(search_results)}개 문서 검색됨")

        return search_results


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
