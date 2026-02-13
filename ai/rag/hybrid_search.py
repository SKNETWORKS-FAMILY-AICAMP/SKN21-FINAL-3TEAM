"""
Hybrid Search: BM25 + Vector Search
RRF(Reciprocal Rank Fusion)로 두 검색 결과를 합산한다.
"""
import logging

from rank_bm25 import BM25Okapi

from ai.rag.embeddings import EmbeddingModel
try:
    from ai.rag.vectorstore import VectorStore
except ImportError:
    VectorStore = None
try:
    from ai.rag.qdrant_store import QdrantVectorStore
except ImportError:
    QdrantVectorStore = None

logger = logging.getLogger(__name__)

# 한국어 형태소 분석기 (konlpy + Java 사용 가능 시 Okt, 아니면 공백 분리 fallback)
_okt = None
try:
    from konlpy.tag import Okt
    _okt = Okt()
    logger.info("konlpy Okt 형태소 분석기 로드 완료")
except Exception:
    logger.warning("konlpy를 사용할 수 없습니다 (Java 미설치 등). 공백 기반 토크나이징으로 대체합니다.")


def tokenize(text: str) -> list[str]:
    """한국어 토크나이저: Okt 형태소 분석 (fallback: 공백 분리)"""
    if not text:
        return []
    if _okt is not None:
        return _okt.morphs(text, stem=True)
    return text.split()


class HybridSearcher:
    """BM25 키워드 검색 + 벡터 시멘틱 검색 결합"""

    def __init__(self, vector_store, embedding_model: EmbeddingModel):
        """
        Args:
            vector_store: VectorStore 또는 QdrantVectorStore 인스턴스
            embedding_model: EmbeddingModel 인스턴스
        """
        self.vector_store = vector_store
        self.embedding_model = embedding_model
        self.bm25 = None
        self._corpus_docs = []  # BM25 인덱스 구축에 사용된 문서 목록
        self._corpus_ids = []
        self._corpus_metadatas = []

    def build_bm25_index(self):
        """VectorStore에서 전체 문서를 가져와 BM25 인덱스를 구축한다."""
        all_docs = self.vector_store.get_all_documents()

        self._corpus_docs = all_docs["documents"]
        self._corpus_ids = all_docs["ids"]
        self._corpus_metadatas = all_docs["metadatas"]

        if not self._corpus_docs:
            self.bm25 = None
            return

        tokenized_corpus = [tokenize(doc) for doc in self._corpus_docs]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def _bm25_search(
        self, query: str, user_id: int | None = None, top_k: int = 15
    ) -> list[dict]:
        """BM25 키워드 검색 → Top K (score 정규화 0~1, scope 필터 적용)"""
        if self.bm25 is None or not self._corpus_docs:
            return []

        tokenized_query = tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # score 정규화 (0~1)
        max_score = max(scores) if max(scores) > 0 else 1.0
        normalized_scores = scores / max_score

        # 상위 인덱스 (scope 필터 적용 후 top_k를 자르므로 전체 정렬)
        scored_indices = sorted(
            range(len(scores)),
            key=lambda i: normalized_scores[i],
            reverse=True,
        )

        results = []
        for idx in scored_indices:
            if normalized_scores[idx] <= 0:
                break
            # scope 필터: user_id=None → company만, user_id 있으면 company + 본인 personal
            meta = self._corpus_metadatas[idx]
            scope = meta.get("scope")
            if scope == "personal":
                if user_id is None or str(meta.get("user_id")) != str(user_id):
                    continue
            results.append({
                "content": self._corpus_docs[idx],
                "source": meta.get("source", ""),
                "score": float(normalized_scores[idx]),
                "doc_id": self._corpus_ids[idx],
            })
            if len(results) >= top_k:
                break
        return results

    def _vector_search(
        self, query: str, top_k: int = 15, filter: dict | None = None
    ) -> list[dict]:
        """Vector 시멘틱 검색 → Top K"""
        query_embedding = self.embedding_model.encode([query])[0]
        return self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter=filter,
        )

    def search(
        self, query: str, user_id: int | None = None, top_k: int = 20
    ) -> list[dict]:
        """
        BM25 (Top 15) + Vector (Top 15) → RRF 합산 정렬 → Top K

        Args:
            query: 사용자 질문
            user_id: scope 필터용 사용자 ID (None이면 company 문서만)
            top_k: 최종 반환 수

        Returns:
            list of {"content", "source", "score", "doc_id"}
        """
        # scope 필터 구성: user_id=None → company만, user_id 있으면 company + 본인 personal
        if user_id is not None:
            scope_filter = {
                "$or": [
                    {"scope": "company"},
                    {"$and": [{"scope": "personal"}, {"user_id": str(user_id)}]},
                ]
            }
        else:
            scope_filter = {"scope": "company"}

        # 1. BM25 검색 → Top 15 (scope 필터 포함)
        bm25_results = self._bm25_search(query, user_id=user_id, top_k=15)

        # 2. Vector 검색 → Top 15
        # TODO: Qdrant 필터 형식 수정 필요 (현재는 필터 없이 검색)
        vector_results = self._vector_search(query, top_k=15, filter=None)

        # 3. RRF(Reciprocal Rank Fusion)로 합산
        rrf_scores: dict[str, dict] = {}
        k = 60  # RRF 상수

        for rank, doc in enumerate(bm25_results):
            doc_id = doc["doc_id"]
            rrf_score = 1.0 / (k + rank + 1)
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = {
                    "content": doc["content"],
                    "source": doc["source"],
                    "doc_id": doc_id,
                    "rrf_score": 0.0,
                }
            rrf_scores[doc_id]["rrf_score"] += rrf_score

        for rank, doc in enumerate(vector_results):
            doc_id = doc["doc_id"]
            rrf_score = 1.0 / (k + rank + 1)
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = {
                    "content": doc["content"],
                    "source": doc["source"],
                    "doc_id": doc_id,
                    "rrf_score": 0.0,
                }
            rrf_scores[doc_id]["rrf_score"] += rrf_score

        # RRF score 기준 내림차순 정렬
        sorted_results = sorted(
            rrf_scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )[:top_k]

        return [
            {
                "content": doc["content"],
                "source": doc["source"],
                "score": doc["rrf_score"],
                "doc_id": doc["doc_id"],
            }
            for doc in sorted_results
        ]
