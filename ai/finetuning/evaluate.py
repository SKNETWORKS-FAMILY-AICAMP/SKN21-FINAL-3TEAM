"""
모델 평가 모듈 (팀원 B/C 공동)

정량적 평가 지표:
  - Intent 분류: Accuracy, F1-score (팀원 A)
  - 판단 정확도: Yes/No 일치율 (팀원 B)
  - 근거 적합성: 정답 조항 포함 여부 (팀원 B)
  - RAG 검색: MRR, Recall@5 (팀원 B)
  - 문서 요약: ROUGE-L, BERTScore (팀원 C)
  - Action Item 추출: Precision, Recall, F1 (팀원 C)
  - 응답 속도: 평균 응답 시간 (팀원 B)
"""


def evaluate_judgment(predictions: list, labels: list) -> dict:
    """판단 정확도 평가 (팀원 B)"""
    # TODO: 팀원 B 구현
    raise NotImplementedError


def evaluate_rag(retrieved: list, relevant: list) -> dict:
    """RAG 검색 평가 - MRR, Recall@K (팀원 B)"""
    # TODO: 팀원 B 구현
    raise NotImplementedError


def evaluate_summary(predictions: list, references: list) -> dict:
    """요약 평가 - ROUGE-L, BERTScore (팀원 C)"""
    # TODO: 팀원 C 구현
    raise NotImplementedError


def evaluate_action_items(predictions: list, labels: list) -> dict:
    """Action Item 추출 평가 - Precision, Recall, F1 (팀원 C)"""
    # TODO: 팀원 C 구현
    raise NotImplementedError
