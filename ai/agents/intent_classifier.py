"""
Intent Classification 모델 (팀원 A 담당)

카테고리 (7개):
  - judgment: 규정 기반 판단
  - doc_search: 문서 검색
  - doc_summary: 문서 요약
  - doc_generate: 문서 생성
  - meeting_analysis: 회의록 분석
  - schedule_add: 일정 추가
  - schedule_view: 일정 조회

모델: klue/bert-base (Fine-tuned)
학습 데이터: 카테고리별 150~200문장
"""

INTENT_LABELS = [
    "judgment",
    "doc_search",
    "doc_summary",
    "doc_generate",
    "meeting_analysis",
    "schedule_add",
    "schedule_view",
]


class IntentClassifier:
    """Intent 분류기"""

    def __init__(self, model_path: str = "klue/bert-base"):
        self.model_path = model_path
        self.model = None
        self.tokenizer = None

    def load_model(self):
        """모델 로드"""
        # TODO: 팀원 A - Hugging Face transformers 모델 로드
        raise NotImplementedError

    def predict(self, text: str) -> dict:
        """
        Intent 분류 추론

        Returns:
            {"intent": "judgment", "confidence": 0.95}
        """
        # TODO: 팀원 A 구현
        raise NotImplementedError
