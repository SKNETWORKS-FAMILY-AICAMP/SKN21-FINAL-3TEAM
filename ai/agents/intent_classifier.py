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
import os
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

    # 예제 임베딩 캐시 (클래스 변수 - 모든 인스턴스가 공유)
    _example_embeddings_cache = None

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

        # fallback: 모델 없으면 LLM 기반 분류
        if self.model is None or self.tokenizer is None:
            return self._llm_based_predict(text)

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

    def _llm_based_predict(self, text: str) -> dict:
        """LLM 기반 intent 분류 (Solar API)"""
        import time as _time
        _t = _time.time()
        print(f"[IntentClassifier] _llm_based_predict 시작 | text='{text}'")
        api_key = os.getenv("SOLAR_API_KEY")
        print(f"[IntentClassifier] SOLAR_API_KEY 존재: {bool(api_key)}, 값 앞4자: {api_key[:4] if api_key else 'None'}")
        if not api_key:
            print("[IntentClassifier] SOLAR_API_KEY 없음 → 임베딩 fallback")
            return self._embedding_based_predict(text)

        try:
            from openai import OpenAI

            print("[IntentClassifier] Solar API 호출 중...")
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.upstage.ai/v1/solar",
            )

            response = client.chat.completions.create(
                model="solar-1-mini-chat",
                messages=[
                    {"role": "system", "content": """사용자 입력의 의도를 분류하세요.

                카테고리:
                - judgment: 규정/규칙 기반 판단 요청 (예: "이거 규정 위반이야?", "이렇게 해도 돼?")
                - doc_search: 문서 검색, 규정 조회 (예: "연차 규정 알려줘", "회의 내용 찾아줘")
                - doc_generate: 보고서/제안서/JD 작성 (예: "보고서 작성해줘", "제안서 만들어줘")
                - meeting_generate: 회의록 작성/요약 (예: "회의록 작성해줘", "회의록 요약해줘")
                - schedule_add: 일정 추가/등록 (예: "내일 2시 회의 일정 추가해줘", "스케줄 등록해줘")
                - schedule_view: 일정 조회/확인 (예: "오늘 일정 보여줘", "이번 주 스케줄 확인해줘")
                - general: 위 카테고리에 해당하지 않는 일반 질문

                반드시 아래 JSON 형식으로만 응답하세요:
                {"intent": "카테고리명", "confidence": 0.0~1.0}"""},
                                    {"role": "user", "content": text},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            raw_content = response.choices[0].message.content
            print(f"[IntentClassifier] Solar API 응답 원문: {raw_content}")
            result = json.loads(raw_content)
            intent = result.get("intent", "general")

            # 유효하지 않은 intent가 오면 general로 처리
            if intent not in INTENT_LABELS:
                print(f"[IntentClassifier] 유효하지 않은 intent: {intent} → general로 변환")
                intent = "general"

            confidence = float(result.get("confidence", 0.8))
            print(f"[IntentClassifier] 최종 결과: intent={intent}, confidence={confidence:.4f} ({_time.time()-_t:.2f}s)")
            return {"intent": intent, "confidence": round(confidence, 4)}

        except Exception as e:
            print(f"[IntentClassifier] !!! LLM 호출 실패: {e}")
            import traceback
            traceback.print_exc()
            return self._embedding_based_predict(text)

    def _get_example_embeddings(self):
        """예제 임베딩 캐시 가져오기 (한 번만 계산)"""
        if IntentClassifier._example_embeddings_cache is None:
            from ai.rag.embeddings import EmbeddingModel

            logger.info("Building intent example embeddings cache...")

            # 각 intent별 예제 문장들
            intent_examples = {
                "judgment": [
                    "이게 규정 위반인가요?",
                    "이렇게 해도 되나요?",
                    "규정상 허용되나요?",
                    "이건 가능한가요?",
                    "판단해줘",
                ],
                "doc_search": [
                    "연차 휴가 규정 알려줘",
                    "출장비 지급 기준이 뭐야?",
                    "회의에서 어떤 내용이 논의되었나요?",
                    "코드리뷰 회의 내용 찾아줘",
                    "문서 검색해줘",
                    "규정 찾아줘",
                ],
                "doc_generate": [
                    "보고서 작성해줘",
                    "제안서 만들어줘",
                    "문서 생성해줘",
                    "JD 작성해줘",
                ],
                "meeting_generate": [
                    "회의록 작성해줘",
                    "회의록 생성해줘",
                    "회의록 요약해줘",
                ],
                "schedule_add": [
                    "일정 추가해줘",
                    "스케줄 등록해줘",
                    "일정 넣어줘",
                ],
                "schedule_view": [
                    "일정 보여줘",
                    "스케줄 확인해줘",
                    "일정 조회해줘",
                ],
            }

            # 임베딩 모델 로드
            embedding_model = EmbeddingModel()
            embedding_model.load_model()

            # 모든 예제를 한 번에 임베딩
            embeddings_cache = {}
            for intent, examples in intent_examples.items():
                embeddings_cache[intent] = embedding_model.encode(examples)

            IntentClassifier._example_embeddings_cache = {
                "embeddings": embeddings_cache,
                "model": embedding_model,
            }

            logger.info("Intent example embeddings cache built successfully")

        return IntentClassifier._example_embeddings_cache

    def _embedding_based_predict(self, text: str) -> dict:
        """임베딩 기반 intent 분류 (jhgan/ko-sbert-nli 사용)"""
        import numpy as np

        # 캐시된 예제 임베딩 가져오기 (첫 요청 시에만 계산)
        cache = self._get_example_embeddings()
        embedding_model = cache["model"]
        example_embeddings_cache = cache["embeddings"]

        # 사용자 질문만 임베딩 (매 요청마다 1번만!)
        query_embedding = embedding_model.encode([text])[0]

        # 캐시된 예제 임베딩과 비교
        intent_scores = {}
        for intent, example_embeddings in example_embeddings_cache.items():
            # 코사인 유사도 계산
            similarities = []
            for example_emb in example_embeddings:
                similarity = np.dot(query_embedding, example_emb) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(example_emb)
                )
                similarities.append(similarity)

            # 최대 유사도를 해당 intent의 점수로 사용
            intent_scores[intent] = max(similarities)

        # 가장 높은 점수의 intent 선택
        best_intent = max(intent_scores, key=intent_scores.get)
        confidence = float(intent_scores[best_intent])

        logger.info(f"Embedding-based intent: {best_intent} (confidence: {confidence:.4f})")
        logger.debug(f"All intent scores: {intent_scores}")

        # confidence가 너무 낮으면 general로
        if confidence < 0.5:
            return {"intent": "general", "confidence": 0.7}

        return {"intent": best_intent, "confidence": round(confidence, 4)}


def get_classifier() -> IntentClassifier:
    """Singleton IntentClassifier 인스턴스 반환"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
    return _classifier_instance
