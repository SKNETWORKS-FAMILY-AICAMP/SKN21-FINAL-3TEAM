"""
Reranker: BAAI/bge-reranker-v2-m3

검색 결과를 한 번 더 정밀하게 재정렬하여 관련도 높은 문서만 선별

변경 이력:
  - 경량 모델(bge-reranker-base) 옵션 추가 → 로딩/추론 속도 개선
  - score_threshold 파라미터 추가 → 관련 없는 문서 자동 제거
  - 메타데이터 전체 보존 → hybrid_search 파이프라인 통합 지원
  - Semaphore(1) 동시성 제어 — zombie thread 누적 방지
"""
import logging
import threading

from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)


class Reranker:
    """Cross-encoder 기반 Reranking (싱글턴)

    동시성 제어:
      CPU 환경에서 Cross-Encoder는 10초+ 소요. 동시 요청이 쌓이면
      스레드 경합으로 10초→200초+ 폭증 (cascade failure).
      Semaphore(1)로 동시 실행을 1개로 제한하고, 대기 중인 요청은
      reranker를 건너뛰고 RRF 결과를 그대로 반환한다.
    """

    _instance = None

    def __new__(cls, model_name: str = "BAAI/bge-reranker-v2-m3"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.model_name = model_name
            cls._instance.model = None
            cls._instance._sem = threading.Semaphore(1)
        return cls._instance

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        pass

    def load_model(self):
        """Reranker 모델 로드 (lazy loading)"""
        if self.model is None:
            logger.info(f"[Reranker] 모델 로드 시작: {self.model_name}")
            self.model = CrossEncoder(self.model_name)
            logger.info("[Reranker] 모델 로드 완료")
        return self.model

    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5,
        score_threshold: float = -1.0,
    ) -> list[dict]:
        """
        (질문, 문서) 쌍의 관련도 점수 산출 후 재정렬

        동시성 제어: 이미 다른 스레드가 rerank 중이면 즉시 포기하고
        입력 documents를 그대로 반환한다 (RRF fallback).

        Args:
            query: 사용자 질문
            documents: 검색 결과 리스트 (각 항목에 "content" 키 필요)
            top_k: 최종 반환 수
            score_threshold: 이 점수 미만인 문서는 제거 (기본값 -1.0 = 제거 안 함)

        Returns:
            재정렬된 상위 K개 문서 (원본 메타데이터 보존 + rerank_score 추가)
        """
        if not documents:
            return []

        # 동시 실행 차단: acquire 실패 시 RRF 결과 그대로 반환
        if not self._sem.acquire(blocking=False):
            logger.warning("[Reranker] 이미 실행 중 — RRF 결과로 fallback (zombie 방지)")
            return documents[:top_k]

        try:
            if self.model is None:
                self.load_model()

            # (query, doc.content) 쌍 구성 — content 1500자 제한
            # Cross-Encoder max_length=512 tokens ≈ 한국어 1500자.
            # 전체(5000자+) 넘기면 토크나이징만 25초+. 1500자면 충분한 문맥 + 빠른 처리.
            pairs = [[query, doc["content"][:1500]] for doc in documents]

            # relevance score 계산
            scores = self.model.predict(pairs)

            # score threshold 이상인 문서만 필터링 + 내림차순 정렬
            scored_docs = sorted(
                [
                    (doc, float(score))
                    for doc, score in zip(documents, scores)
                    if float(score) >= score_threshold
                ],
                key=lambda x: x[1],
                reverse=True,
            )[:top_k]

            logger.info(
                f"[Reranker] {len(documents)}개 → {len(scored_docs)}개 "
                f"(threshold={score_threshold}, top_k={top_k})"
            )

            # 원본 메타데이터 보존 + rerank_score 추가
            # Cross-Encoder raw score(logit)를 sigmoid로 0~1 변환 후 40~100% display 범위로 매핑
            import math
            return [
                {
                    **doc,
                    "rerank_score": score,
                    "score": 0.4 + 0.6 / (1 + math.exp(-score)),  # sigmoid → 40~100%
                }
                for doc, score in scored_docs
            ]
        finally:
            self._sem.release()
