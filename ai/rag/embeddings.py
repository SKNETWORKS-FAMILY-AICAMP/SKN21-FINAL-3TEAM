"""
임베딩 모델: jhgan/ko-sbert-nli (팀원 B 담당)
"""


class EmbeddingModel:
    """한국어 문장 임베딩"""

    def __init__(self, model_name: str = "jhgan/ko-sbert-nli"):
        self.model_name = model_name
        self.model = None

    def load_model(self):
        """임베딩 모델 로드"""
        # TODO: 팀원 B 구현
        raise NotImplementedError

    def encode(self, texts: list) -> list:
        """텍스트 → 임베딩 벡터"""
        # TODO: 팀원 B 구현
        raise NotImplementedError
