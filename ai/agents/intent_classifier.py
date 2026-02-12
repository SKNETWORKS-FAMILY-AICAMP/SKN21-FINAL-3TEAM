"""
Intent Classification 모델 (팀원 A 담당)

카테고리 (7개):
  - judgment: 규정 기반 판단
  - doc_search: 문서 검색
  - doc_generate: 문서 요약 및 생성 (기존 doc_summary 통합)
  - meeting_generate: 회의록 요약 및 생성 (기존 meeting_analysis에서 변경)
  - schedule_add: 일정 추가
  - schedule_view: 일정 조회
  - general: 일반 질문

모델: klue/bert-base (Fine-tuned)
학습 데이터: 카테고리별 150~200문장
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

INTENT_LABELS = [
    "judgment",
    "doc_search",
    "doc_generate",
    "meeting_generate",
    "schedule_add",
    "schedule_view",
    "general",
]

# 모델 weights 경로 (RunPod 학습 후 저장되는 위치)
_MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "intent_classifier"

# Singleton 인스턴스
_classifier_instance = None


class IntentClassifier:
    """Intent 분류기 (Singleton)"""

    def __init__(self, model_path: str = None):
        self.model_path = model_path or str(_MODEL_DIR)
        self.model = None
        self.tokenizer = None
        self.id2label = None
        self._loaded = False

    def load_model(self):
        """모델 로드 — weights 없으면 fallback 모드로 동작"""
        if self._loaded:
            return

        model_dir = Path(self.model_path)
        label_map_file = model_dir / "label_map.json"

        # label_map 로드
        if label_map_file.exists():
            with open(label_map_file, "r", encoding="utf-8") as f:
                label_map = json.load(f)
            self.id2label = {int(k): v for k, v in label_map["id2label"].items()}
        else:
            self.id2label = {i: label for i, label in enumerate(INTENT_LABELS)}

        # weights 파일 확인 (safetensors 또는 bin)
        has_weights = (
            (model_dir / "model.safetensors").exists()
            or (model_dir / "pytorch_model.bin").exists()
        )

        if not has_weights:
            logger.warning(
                "Intent classifier weights not found at %s — running in fallback mode",
                model_dir,
            )
            self._loaded = True
            return

        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification

            self.tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
            self.model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
            self.model.eval()
            logger.info("Intent classifier loaded from %s", model_dir)
        except Exception as e:
            logger.error("Failed to load intent classifier: %s", e)
            self.model = None
            self.tokenizer = None

        self._loaded = True

    def predict(self, text: str) -> dict:
        """
        Intent 분류 추론

        Returns:
            {"intent": "judgment", "confidence": 0.95}
        """
        self.load_model()

        # fallback: 모델 없으면 general 반환
        if self.model is None or self.tokenizer is None:
            return {"intent": "general", "confidence": 0.0}

        # 전처리
        try:
            from ai.experiments.preprocessing import preprocess

            processed = preprocess(text)
        except ImportError:
            processed = text

        # 추론
        import torch

        inputs = self.tokenizer(
            processed,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=128,
        )

        with torch.no_grad():
            outputs = self.model(**inputs)

        probs = torch.softmax(outputs.logits, dim=-1)
        pred_id = torch.argmax(probs, dim=-1).item()
        confidence = probs[0][pred_id].item()

        intent = self.id2label.get(pred_id, "general")

        return {"intent": intent, "confidence": round(confidence, 4)}


def get_classifier() -> IntentClassifier:
    """Singleton IntentClassifier 인스턴스 반환"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
    return _classifier_instance
