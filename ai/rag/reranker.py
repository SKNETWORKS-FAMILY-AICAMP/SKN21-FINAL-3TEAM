"""
Reranker: BAAI/bge-reranker-v2-m3

검색 결과를 한 번 더 정밀하게 재정렬하여 관련도 높은 문서만 선별
"""
from sentence_transformers import CrossEncoder


class Reranker:
    """Cross-encoder 기반 Reranking (싱글턴)"""

    _instance = None

    def __new__(cls, model_name: str = "BAAI/bge-reranker-v2-m3"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.model_name = model_name
            cls._instance.model = None
        return cls._instance

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        pass

    def load_model(self):
        """Reranker 모델 로드 (lazy loading)"""
        if self.model is None:
            self.model = CrossEncoder(self.model_name)
        return self.model

    def rerank(self, query: str, documents: list[dict], top_k: int = 5) -> list[dict]:
        """
        (질문, 문서) 쌍의 관련도 점수 산출 후 재정렬

        Args:
            query: 사용자 질문
            documents: 검색 결과 리스트 (각 항목에 "content" 키 필요)
            top_k: 최종 반환 수

        Returns:
            재정렬된 상위 K개 문서: list of {"content", "source", "score"}
        """
        if self.model is None:
            self.load_model()

        if not documents:
            return []

        # (query, doc.content) 쌍 구성
        pairs = [[query, doc["content"]] for doc in documents]

        # relevance score 계산
        scores = self.model.predict(pairs)

        # score 기준 내림차순 정렬
        scored_docs = sorted(
            zip(documents, scores),
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]

        return [
            {
                "content": doc["content"],
                "source": doc.get("source", ""),
                "score": float(score),
            }
            for doc, score in scored_docs
        ]
