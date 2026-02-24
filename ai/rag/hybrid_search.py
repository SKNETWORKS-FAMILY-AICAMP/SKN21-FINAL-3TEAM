"""
Hybrid Search: BM25 + Vector Search
RRF(Reciprocal Rank Fusion)로 두 검색 결과를 합산한다.

Query Refinement:
  BM25 검색에는 키워드 추출 + 동의어 확장된 쿼리를,
  Vector 검색에는 원본 쿼리(시멘틱 의미 보존)를 사용한다.
"""
import logging

from rank_bm25 import BM25Okapi

from ai.rag.embeddings import EmbeddingModel
from ai.rag.query_refiner import refine_query_for_bm25, refine_query_for_vector
try:
    from ai.rag.vectorstore import VectorStore
except ImportError:
    VectorStore = None
try:
    from ai.rag.qdrant_store import QdrantVectorStore
except ImportError:
    QdrantVectorStore = None

logger = logging.getLogger(__name__)

# 한국어 형태소 분석기 (kiwipiepy 사용, 없으면 공백 분리 fallback)
_kiwi = None
try:
    from kiwipiepy import Kiwi
    _kiwi = Kiwi()
    logger.info("kiwipiepy 형태소 분석기 로드 완료")
except Exception:
    logger.warning("kiwipiepy를 사용할 수 없습니다. 공백 기반 토크나이징으로 대체합니다.")


def _strip_suffixes(token: str) -> str:
    """한국어 조사/어미 간이 제거 (kiwipiepy 없을 때 BM25 토큰 정규화)"""
    _SUFFIXES = [
        "에서는", "으로는", "에서", "으로", "에는", "까지",
        "에게", "한다", "이다", "한다.",
        "은", "는", "이", "가", "을", "를", "의", "에", "도",
        "로", "와", "과", "며", "고",
    ]
    for suf in _SUFFIXES:
        if token.endswith(suf) and len(token) > len(suf):
            return token[: -len(suf)]
    return token.rstrip(".,;:?!)")


def tokenize(text: str) -> list[str]:
    """한국어 토크나이저: kiwipiepy 형태소 분석 (fallback: 공백 분리 + 접미사 제거)"""
    if not text:
        return []
    if _kiwi is not None:
        return [token.form for token in _kiwi.tokenize(text)]
    # fallback: 공백 분리 → 접미사 제거 → 빈 토큰 제거
    tokens = text.split()
    stripped = [_strip_suffixes(t.strip("()[]{}「」")) for t in tokens]
    return [t for t in stripped if t]


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
        self, query: str, user_id: int | None = None, top_k: int = 15,
        filter: dict | None = None,
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
            # 메타데이터 필터 적용 (예: {"source": "regulations"})
            if filter:
                skip = False
                for key, value in filter.items():
                    if meta.get(key) != value:
                        skip = True
                        break
                if skip:
                    continue
            result_item = {
                "content": self._corpus_docs[idx],
                "source": meta.get("source", ""),
                "title": meta.get("title", ""),
                "chapter": meta.get("chapter", ""),
                "article": meta.get("article", ""),
                "score": float(normalized_scores[idx]),
                "doc_id": self._corpus_ids[idx],
            }
            # 추가 메타데이터 전파 (document_id 등)
            if "document_id" in meta:
                result_item["document_id"] = meta["document_id"]
            results.append(result_item)
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
        self, query: str, user_id: int | None = None, top_k: int = 20,
        max_per_source: int = 3, filter: dict | None = None,
    ) -> list[dict]:
        """
        BM25 (Top 15) + Vector (Top 15) → RRF 합산 정렬 → 소스 다양성 적용 → Top K

        Args:
            query: 사용자 질문
            user_id: scope 필터용 사용자 ID (None이면 company 문서만)
            top_k: 최종 반환 수
            max_per_source: 동일 출처 규정의 최대 포함 수 (교차 규정 검색 품질 향상)
            filter: 메타데이터 필터 (예: {"source": "regulations"})

        Returns:
            list of {"content", "source", "score", "doc_id"}
        """
        # scope 필터 구성: user_id=None → company만, user_id 있으면 company + 본인 personal
        # TODO: Qdrant 필터 형식 수정 후 아래 scope_filter를 _vector_search에 전달
        # if user_id is not None:
        #     scope_filter = {
        #         "$or": [
        #             {"scope": "company"},
        #             {"$and": [{"scope": "personal"}, {"user_id": str(user_id)}]},
        #         ]
        #     }
        # else:
        #     scope_filter = {"scope": "company"}

        # Query Refinement: BM25에는 키워드 쿼리, Vector에는 원본 쿼리
        bm25_query = refine_query_for_bm25(query)
        vector_query = refine_query_for_vector(query)

        # 1. BM25 검색 → Top 15 (scope 필터 포함, 키워드+동의어 확장 쿼리)
        bm25_results = self._bm25_search(bm25_query, user_id=user_id, top_k=15, filter=filter)

        # 2. Vector 검색 → Top 15 (원본 쿼리, 시멘틱 의미 보존)
        vector_results = self._vector_search(vector_query, top_k=15, filter=filter)

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
                    "title": doc.get("title", ""),
                    "chapter": doc.get("chapter", ""),
                    "article": doc.get("article", ""),
                    "document_id": doc.get("document_id"),
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
                    "title": doc.get("title", ""),
                    "chapter": doc.get("chapter", ""),
                    "article": doc.get("article", ""),
                    "document_id": doc.get("document_id"),
                    "doc_id": doc_id,
                    "rrf_score": 0.0,
                }
            rrf_scores[doc_id]["rrf_score"] += rrf_score

        # RRF score 기준 내림차순 정렬
        sorted_results = sorted(
            rrf_scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )

        # 소스 다양성 적용: 동일 출처 max_per_source개 제한 → 교차 규정 결과 확보
        diverse_results = []
        source_count: dict[str, int] = {}
        overflow = []  # max_per_source 초과분 (빈자리 채움용)

        for doc in sorted_results:
            src = doc["source"]
            cnt = source_count.get(src, 0)
            if cnt < max_per_source:
                diverse_results.append(doc)
                source_count[src] = cnt + 1
                if len(diverse_results) >= top_k:
                    break
            else:
                overflow.append(doc)

        # top_k 미달이면 초과분에서 채움
        if len(diverse_results) < top_k:
            for doc in overflow:
                diverse_results.append(doc)
                if len(diverse_results) >= top_k:
                    break

        return [
            {
                "content": doc["content"],
                "source": doc["source"],
                "title": doc.get("title", ""),
                "chapter": doc.get("chapter", ""),
                "article": doc.get("article", ""),
                "document_id": doc.get("document_id"),
                "score": doc["rrf_score"],
                "doc_id": doc["doc_id"],
            }
            for doc in diverse_results
        ]
