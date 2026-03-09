"""
Qdrant 기반 RAG 파이프라인

파이프라인:
  사용자 질문
  → (선택) LLM 쿼리 재작성 (HyDE)
  → BM25 검색 (Top 15) + Vector 검색 (Top 15)
  → RRF 합산
  → (선택) Cross-Encoder Reranker 재정렬
  → (선택) Score Threshold 필터링
  → Top K → AgentState.context에 저장

검색 품질 개선 옵션 (retrieve 호출 시 선택):
  - use_reranker=True: Cross-Encoder로 관련도 재평가 (정밀도 ↑, 지연 +2~5초)
  - score_threshold=0.1: 관련 없는 문서 자동 제거
  - use_hyde=True: LLM으로 가상 정답 문서 생성 → 벡터 검색 품질 향상
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

    def retrieve(
        self,
        query: str,
        user_id: int | None = None,
        top_k: int = 5,
        filter: dict | None = None,
        use_reranker: bool = False,
        score_threshold: float | None = None,
        use_hyde: bool = False,
    ) -> list[dict]:
        """하이브리드 검색 (BM25 + Vector → RRF 합산 → Reranker → Threshold)

        Args:
            query: 사용자 질문
            user_id: 사용자 ID (scope 필터용)
            top_k: 최종 반환 문서 수
            filter: 메타데이터 필터 (예: {"source": "regulations"})
            use_reranker: Cross-Encoder 재정렬 사용 여부
            score_threshold: 최소 점수 기준 (미달 문서 제거)
            use_hyde: HyDE (Hypothetical Document Embeddings) 사용 여부

        Returns:
            list of {"content": str, "source": str, "score": float, ...}
        """
        _t = time.time()
        search_query = query

        # HyDE: LLM으로 가상 정답 문서 생성 → 벡터 검색에 사용
        if use_hyde:
            try:
                from ai.rag.query_refiner import generate_hyde_document
                hyde_doc = generate_hyde_document(query)
                if hyde_doc:
                    search_query = hyde_doc
                    logger.info(f"[RAGPipeline] HyDE 적용: '{query[:40]}' → '{hyde_doc[:60]}'")
            except Exception as e:
                logger.warning(f"[RAGPipeline] HyDE 실패, 원본 쿼리 사용: {e}")

        print(f"[RAGPipeline] retrieve 시작 | query='{query[:50]}', top_k={top_k}, "
              f"reranker={use_reranker}, threshold={score_threshold}, hyde={use_hyde}")

        # Hybrid Search (BM25 + Vector) → RRF 합산 → (Reranker) → Top K
        search_results = self.searcher.search(
            query=search_query,
            user_id=user_id,
            top_k=top_k,
            filter=filter,
            use_reranker=use_reranker,
            score_threshold=score_threshold,
        )
        print(f"[RAGPipeline] retrieve 완료 ({time.time()-_t:.2f}s) | {len(search_results)}개 문서 검색됨")

        return search_results

    def list_documents(self, source: str = "documents", user_id: int = None) -> list[dict]:
        """source 필터로 저장된 문서 목록 반환 (title + document_id)"""
        return self.vector_store.list_documents_by_source(source=source, user_id=user_id)

    def get_document_content(self, document_id: int) -> str:
        """document_id로 Qdrant 청크 전체 합산 → 전체 content 반환 (DB 없을 때 fallback용)"""
        chunks = self.vector_store.get_chunks_by_document_id(document_id)
        return "\n\n".join(chunks) if chunks else ""


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
