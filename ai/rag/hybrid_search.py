"""
Hybrid Search: BM25 + Vector Search
RRF(Reciprocal Rank Fusion)로 두 검색 결과를 합산한다.

Query Refinement:
  BM25 검색에는 키워드 추출 + 동의어 확장된 쿼리를,
  Vector 검색에는 원본 쿼리(시멘틱 의미 보존)를 사용한다.
"""
import logging
import os

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

    # BM25 인덱스 캐시 경로
    _BM25_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "cache")
    _BM25_CACHE_FILE = os.path.join(_BM25_CACHE_DIR, "bm25_index.pkl")

    def build_bm25_index(self):
        """VectorStore에서 전체 문서를 가져와 BM25 인덱스를 구축한다.

        캐시 전략: pickle로 인덱스 저장 → 문서 수 변경 시에만 재빌드
        """
        all_docs = self.vector_store.get_all_documents()

        self._corpus_docs = all_docs["documents"]
        self._corpus_ids = all_docs["ids"]
        self._corpus_metadatas = all_docs["metadatas"]

        if not self._corpus_docs:
            self.bm25 = None
            return

        doc_count = len(self._corpus_docs)

        # 캐시 로드 시도
        if self._load_bm25_cache(doc_count):
            return

        # 캐시 없거나 문서 수 변경 → 재빌드
        import time
        _t = time.time()
        tokenized_corpus = [tokenize(doc) for doc in self._corpus_docs]
        self.bm25 = BM25Okapi(tokenized_corpus)
        logger.info("[BM25] 인덱스 빌드 완료 (%d개, %.2fs) → 캐시 저장", doc_count, time.time() - _t)

        self._save_bm25_cache(doc_count, tokenized_corpus)

    def _load_bm25_cache(self, expected_count: int) -> bool:
        """pickle 캐시에서 BM25 인덱스 로드. 문서 수 불일치 시 False 반환."""
        import pickle
        try:
            if not os.path.exists(self._BM25_CACHE_FILE):
                return False
            with open(self._BM25_CACHE_FILE, "rb") as f:
                cache = pickle.load(f)
            if cache.get("doc_count") != expected_count:
                logger.info("[BM25] 캐시 문서 수 불일치 (%d → %d) → 재빌드", cache.get("doc_count", 0), expected_count)
                return False
            self.bm25 = cache["bm25"]
            logger.info("[BM25] 캐시 로드 성공 (%d개)", expected_count)
            return True
        except Exception as e:
            logger.warning("[BM25] 캐시 로드 실패: %s → 재빌드", e)
            return False

    def _save_bm25_cache(self, doc_count: int, tokenized_corpus: list):
        """BM25 인덱스를 pickle로 캐시 저장."""
        import pickle
        try:
            os.makedirs(self._BM25_CACHE_DIR, exist_ok=True)
            with open(self._BM25_CACHE_FILE, "wb") as f:
                pickle.dump({"doc_count": doc_count, "bm25": self.bm25}, f)
            logger.info("[BM25] 캐시 저장 완료: %s", self._BM25_CACHE_FILE)
        except Exception as e:
            logger.warning("[BM25] 캐시 저장 실패 (비차단): %s", e)

    def _bm25_search(
        self, query: str, user_id: int | None = None, user_team: str | None = None,
        top_k: int = 15, filter: dict | None = None,
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
            # scope 필터: company=전체공개, team=같은팀만, personal=본인만
            meta = self._corpus_metadatas[idx]
            scope = meta.get("scope")
            if scope == "personal":
                if user_id is None or str(meta.get("user_id")) != str(user_id):
                    continue
            elif scope == "team":
                if not user_team or meta.get("team_name") != user_team:
                    continue
            # 메타데이터 필터 적용 (예: {"source": "documents"} 또는 {"source__nin": [...]})
            if filter:
                skip = False
                for key, value in filter.items():
                    if key.endswith("__nin"):
                        # Not-In 필터: 해당 값 목록에 포함되면 제외
                        actual_key = key[:-5]
                        if meta.get(actual_key) in value:
                            skip = True
                            break
                    elif meta.get(key) != value:
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
                "tags": meta.get("tags", ""),
                "category": meta.get("category", ""),
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
        self, query: str, user_id: int | None = None, user_team: str | None = None,
        top_k: int = 20, max_per_source: int = 3, filter: dict | None = None,
        use_reranker: bool = False, rerank_top_k: int | None = None,
        score_threshold: float | None = None,
    ) -> list[dict]:
        """
        BM25 (Top 15) + Vector (Top 15) → RRF 합산 정렬 → 소스 다양성 적용
        → (선택) Reranker 재정렬 → (선택) Score Threshold 필터링 → Top K

        Args:
            query: 사용자 질문
            user_id: scope 필터용 사용자 ID (None이면 company 문서만)
            top_k: 최종 반환 수
            max_per_source: 동일 출처 규정의 최대 포함 수 (교차 규정 검색 품질 향상)
            filter: 메타데이터 필터 (예: {"source": "regulations"})
            use_reranker: True면 RRF 결과를 Cross-Encoder로 재정렬
            rerank_top_k: Reranker에 넘길 후보 수 (기본값: top_k * 2)
            score_threshold: RRF 정규화 점수 최소 기준 (미달 문서 제거, Reranker 미사용 시)

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
        bm25_results = self._bm25_search(bm25_query, user_id=user_id, user_team=user_team, top_k=15, filter=filter)

        # 2. Vector 검색 → Top 15 (원본 쿼리, 시멘틱 의미 보존)
        vector_results = self._vector_search(vector_query, top_k=15, filter=filter)

        # 3. RRF(Reciprocal Rank Fusion)로 합산
        rrf_scores: dict[str, dict] = {}
        k = 60  # RRF 상수

        def _init_rrf_entry(doc, doc_id):
            return {
                "content": doc["content"],
                "source": doc["source"],
                "title": doc.get("title", ""),
                "chapter": doc.get("chapter", ""),
                "article": doc.get("article", ""),
                "document_id": doc.get("document_id"),
                "tags": doc.get("tags", ""),
                "category": doc.get("category", ""),
                "doc_id": doc_id,
                "rrf_score": 0.0,
            }

        for rank, doc in enumerate(bm25_results):
            doc_id = doc["doc_id"]
            rrf_score = 1.0 / (k + rank + 1)
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = _init_rrf_entry(doc, doc_id)
            rrf_scores[doc_id]["rrf_score"] += rrf_score

        for rank, doc in enumerate(vector_results):
            doc_id = doc["doc_id"]
            rrf_score = 1.0 / (k + rank + 1)
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = _init_rrf_entry(doc, doc_id)
            rrf_scores[doc_id]["rrf_score"] += rrf_score

        # 4. 태그/카테고리 매칭 부스트
        # 쿼리 키워드가 문서의 tags/category에 포함되면 RRF 점수 부스트
        query_keywords = [t.lower() for t in tokenize(query)]
        for doc_id, doc in rrf_scores.items():
            doc_tags = doc.get("tags", "").lower()
            doc_category = doc.get("category", "").lower()
            tag_text = f"{doc_tags} {doc_category}"
            match_count = sum(1 for kw in query_keywords if kw in tag_text)
            if match_count > 0:
                # 태그 매칭 시 RRF 점수에 부스트 (매칭 키워드 수에 비례)
                boost = 0.3 * match_count
                doc["rrf_score"] *= (1.0 + boost)

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

        # Vector 최고 유사도 로깅 (디버깅용, 필터링하지 않음)
        # 관련 없는 문서 필터링은 LLM 프롬프트에서 처리
        if vector_results:
            max_vector_score = max(doc.get("score", 0) for doc in vector_results)
            logger.info(f"[HybridSearch] Vector 최고 유사도: {max_vector_score:.3f}")
        else:
            logger.info("[HybridSearch] Vector 검색 결과 없음")

        # RRF 점수 정규화 (0~1 범위)
        if not diverse_results:
            return []
        rrf_scores_list = [doc["rrf_score"] for doc in diverse_results]
        max_s = max(rrf_scores_list)
        min_s = min(rrf_scores_list)

        normalized_results = []
        for doc in diverse_results:
            # 상대 점수 (0~1) + 바닥 보정으로 시각적 신뢰도 향상
            # 검색 결과에 포함된 문서는 최소 40%의 관련성이 있다고 표시
            relative = doc["rrf_score"] / max_s if max_s > 0 else 1.0
            display_score = 0.4 + 0.6 * relative  # 40%~100% 범위로 매핑

            normalized_results.append({
                "content": doc["content"],
                "source": doc["source"],
                "title": doc.get("title", ""),
                "chapter": doc.get("chapter", ""),
                "article": doc.get("article", ""),
                "document_id": doc.get("document_id"),
                "score": display_score,
                "rrf_score": doc["rrf_score"],
                "doc_id": doc["doc_id"],
            })

        # Score Threshold 필터링 (Reranker 미사용 시 RRF 정규화 점수 기준)
        if score_threshold is not None and not use_reranker:
            before_count = len(normalized_results)
            normalized_results = [
                doc for doc in normalized_results
                if doc["score"] >= score_threshold
            ]
            if len(normalized_results) < before_count:
                logger.info(
                    f"[HybridSearch] Score threshold {score_threshold} 적용: "
                    f"{before_count}개 → {len(normalized_results)}개"
                )

        # Reranker 재정렬 (Cross-Encoder로 관련도 재평가)
        if use_reranker and normalized_results:
            try:
                from ai.rag.reranker import Reranker
                reranker = Reranker()
                # Reranker에 넘길 후보 수 (상위 10개로 제한 — CPU 환경 성능)
                _rerank_candidates = rerank_top_k or min(top_k * 2, 10)
                candidates = normalized_results[:_rerank_candidates]
                reranked = reranker.rerank(
                    query=query,
                    documents=candidates,
                    top_k=top_k,
                    score_threshold=score_threshold if score_threshold is not None else -1.0,
                )
                logger.info(
                    f"[HybridSearch] Reranker 적용: {len(candidates)}개 → {len(reranked)}개"
                )
                return reranked
            except Exception as e:
                logger.warning(f"[HybridSearch] Reranker 실패, RRF 결과 사용: {e}")

        return normalized_results
