"""
임베딩 모델: jhgan/ko-sbert-nli
싱글턴 패턴으로 모델을 한 번만 로드한다.
"""
import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingModel:
    """한국어 문장 임베딩 (싱글턴)"""

    _instance = None

    def __new__(cls, model_name: str = "jhgan/ko-sbert-nli"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.model_name = model_name
            cls._instance.model = None
        return cls._instance

    def __init__(self, model_name: str = "jhgan/ko-sbert-nli"):
        # __new__에서 이미 초기화됨 — 중복 방지
        pass

    def load_model(self):
        """임베딩 모델 로드 (lazy loading)"""
        if self.model is None:
            self.model = SentenceTransformer(self.model_name)
        return self.model

    def encode(self, texts: list[str]) -> list[np.ndarray]:
        """텍스트 리스트 → numpy 벡터 리스트"""
        if self.model is None:
            self.load_model()
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [emb for emb in embeddings]
