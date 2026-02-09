"""
Reranker: BAAI/bge-reranker-v2-m3 (팀원 B 담당)

검색 결과를 한 번 더 정밀하게 재정렬하여 관련도 높은 문서만 선별
"""


class Reranker:
    """Cross-encoder 기반 Reranking"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model_name = model_name
        self.model = None

    def load_model(self):
        """Reranker 모델 로드"""
        # TODO: 팀원 B 구현
        raise NotImplementedError

    def rerank(self, query: str, documents: list, top_k: int = 5) -> list:
        """
        (질문, 문서) 쌍의 관련도 점수 산출 후 재정렬

        Args:
            query: 사용자 질문
            documents: 검색 결과 리스트
            top_k: 최종 반환 수

        Returns:
            재정렬된 상위 K개 문서
        """
        # TODO: 팀원 B 구현
        raise NotImplementedError
