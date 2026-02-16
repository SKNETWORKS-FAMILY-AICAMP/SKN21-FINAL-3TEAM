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
import re
from pathlib import Path

from ai.agents.config import INTENT_FALLBACK_THRESHOLD, COMPLEXITY_GAP_THRESHOLD

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

            # 토크나이저는 klue/bert-base 원본 사용 (로컬 저장본과 vocab 불일치 방지)
            self.tokenizer = AutoTokenizer.from_pretrained("klue/bert-base")
            self.model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
            self.model.eval()
            logger.info("Intent classifier loaded from %s (tokenizer: klue/bert-base)", model_dir)
        except Exception as e:
            logger.error("Failed to load intent classifier: %s", e)
            self.model = None
            self.tokenizer = None

        self._loaded = True

    def predict(self, text: str, return_candidates: bool = False) -> dict:
        """
        Intent 분류 추론

        Args:
            text: 사용자 입력 텍스트
            return_candidates: True이면 top-3 후보도 함께 반환

        Returns:
            {"intent": "judgment", "confidence": 0.95}
            return_candidates=True일 때:
            {"intent": "judgment", "confidence": 0.95, "candidates": [{"intent": ..., "confidence": ...}, ...]}
        """
        self.load_model()

        # fallback: 모델 없으면 LLM 기반 분류
        if self.model is None or self.tokenizer is None:
            return self._llm_based_predict(text, return_candidates=return_candidates)

        # 전처리
        try:
            from ai.agents.preprocessing import preprocess

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
            max_length=64,
        )

        with torch.no_grad():
            outputs = self.model(**inputs)

        probs = torch.softmax(outputs.logits, dim=-1)
        pred_id = torch.argmax(probs, dim=-1).item()
        confidence = probs[0][pred_id].item()

        intent = self.id2label.get(pred_id, "general")

        # 알려진 오분류 패턴 보정
        intent = apply_known_overrides(text, intent)

        result = {"intent": intent, "confidence": round(confidence, 4)}

        if return_candidates:
            # top-3 후보 추출
            sorted_indices = torch.argsort(probs[0], descending=True)
            candidates = []
            for idx in sorted_indices[:3]:
                idx_int = idx.item()
                candidates.append({
                    "intent": self.id2label.get(idx_int, "general"),
                    "confidence": round(probs[0][idx_int].item(), 4),
                })
            result["candidates"] = candidates

        return result

    def _llm_based_predict(self, text: str, return_candidates: bool = False) -> dict:
        """LLM 기반 intent 분류 (Solar API)"""
        import time as _time
        _t = _time.time()
        print(f"[IntentClassifier] _llm_based_predict 시작 | text='{text}'")
        api_key = os.getenv("SOLAR_API_KEY")
        print(f"[IntentClassifier] SOLAR_API_KEY 존재: {bool(api_key)}, 값 앞4자: {api_key[:4] if api_key else 'None'}")
        if not api_key:
            print("[IntentClassifier] SOLAR_API_KEY 없음 → 임베딩 fallback")
            return self._embedding_based_predict(text, return_candidates=return_candidates)

        try:
            from openai import OpenAI

            print("[IntentClassifier] Solar API 호출 중...")
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.upstage.ai/v1/solar",
            )

            # return_candidates 요청 시 top-3 반환 프롬프트 추가
            if return_candidates:
                system_prompt = """사용자 입력의 의도를 분류하세요.

                카테고리:
                - judgment: 규정/규칙 기반 판단 요청 (예: "이거 규정 위반이야?", "이렇게 해도 돼?")
                - doc_search: 문서 검색, 규정 조회 (예: "연차 규정 알려줘", "회의 내용 찾아줘")
                - doc_generate: 보고서/제안서/JD 작성 (예: "보고서 작성해줘", "제안서 만들어줘")
                - meeting_generate: 회의록 작성/요약 (예: "회의록 작성해줘", "회의록 요약해줘")
                - schedule_add: 일정 추가/등록 (예: "내일 2시 회의 일정 추가해줘", "스케줄 등록해줘")
                - schedule_view: 일정 조회/확인 (예: "오늘 일정 보여줘", "이번 주 스케줄 확인해줘")
                - general: 위 카테고리에 해당하지 않는 일반 질문

                반드시 아래 JSON 형식으로만 응답하세요:
                {"intent": "카테고리명", "confidence": 0.0~1.0, "candidates": [{"intent": "카테고리명", "confidence": 0.0~1.0}, ...]}
                candidates에는 가장 가능성 높은 상위 3개를 포함하세요."""
            else:
                system_prompt = """사용자 입력의 의도를 분류하세요.

                카테고리:
                - judgment: 규정/규칙 기반 판단 요청 (예: "이거 규정 위반이야?", "이렇게 해도 돼?")
                - doc_search: 문서 검색, 규정 조회 (예: "연차 규정 알려줘", "회의 내용 찾아줘")
                - doc_generate: 보고서/제안서/JD 작성 (예: "보고서 작성해줘", "제안서 만들어줘")
                - meeting_generate: 회의록 작성/요약 (예: "회의록 작성해줘", "회의록 요약해줘")
                - schedule_add: 일정 추가/등록 (예: "내일 2시 회의 일정 추가해줘", "스케줄 등록해줘")
                - schedule_view: 일정 조회/확인 (예: "오늘 일정 보여줘", "이번 주 스케줄 확인해줘")
                - general: 위 카테고리에 해당하지 않는 일반 질문

                반드시 아래 JSON 형식으로만 응답하세요:
                {"intent": "카테고리명", "confidence": 0.0~1.0}"""

            response = client.chat.completions.create(
                model="solar-1-mini-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
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

            # 알려진 오분류 패턴 보정
            intent = apply_known_overrides(text, intent)

            confidence = float(result.get("confidence", 0.8))
            print(f"[IntentClassifier] 최종 결과: intent={intent}, confidence={confidence:.4f} ({_time.time()-_t:.2f}s)")

            output = {"intent": intent, "confidence": round(confidence, 4)}
            if return_candidates:
                candidates = result.get("candidates", [{"intent": intent, "confidence": round(confidence, 4)}])
                # 유효성 검증
                valid_candidates = []
                for c in candidates[:3]:
                    c_intent = c.get("intent", "general")
                    if c_intent not in INTENT_LABELS:
                        c_intent = "general"
                    valid_candidates.append({"intent": c_intent, "confidence": round(float(c.get("confidence", 0.5)), 4)})
                output["candidates"] = valid_candidates
            return output

        except Exception as e:
            print(f"[IntentClassifier] !!! LLM 호출 실패: {e}")
            import traceback
            traceback.print_exc()
            return self._embedding_based_predict(text, return_candidates=return_candidates)

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

    def _embedding_based_predict(self, text: str, return_candidates: bool = False) -> dict:
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
        if confidence < INTENT_FALLBACK_THRESHOLD:
            result = {"intent": "general", "confidence": 0.7}
            if return_candidates:
                result["candidates"] = [{"intent": "general", "confidence": 0.7}]
            return result

        # 알려진 오분류 패턴 보정
        best_intent = apply_known_overrides(text, best_intent)

        result = {"intent": best_intent, "confidence": round(confidence, 4)}

        if return_candidates:
            sorted_scores = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
            candidates = [{"intent": k, "confidence": round(float(v), 4)} for k, v in sorted_scores[:3]]
            result["candidates"] = candidates

        return result


# ── 알려진 오분류 패턴 보정 (실험에서 발견) ──

KNOWN_OVERRIDES = {
    # "인센티브 지급 기준" → BERT가 doc_search로 분류하지만 실제론 judgment
    r"(인센티브|성과급|보너스).*(기준|조건|자격)": "judgment",
    # "남은 공휴일" → BERT가 general로 분류하지만 실제론 schedule_view
    r"(남은|다음|이번).*(공휴일|휴일|쉬는 날)": "schedule_view",
}


def apply_known_overrides(text: str, bert_intent: str) -> str:
    """알려진 오분류 패턴이면 강제 전환"""
    for pattern, correct_intent in KNOWN_OVERRIDES.items():
        if re.search(pattern, text):
            logger.info(f"Known override: {bert_intent} → {correct_intent} for '{text}'")
            return correct_intent
    return bert_intent


# ── 복합 질문 감지 ──

# 접속/순차 키워드 패턴 (넓은 범위)
# V-아/어서: 찾아서, 확인해서, 봐서 등
# V-고: 찾고, 확인하고, 보고 등
# V-면서: 찾으면서, 확인하면서 등
# 순차 표현: ~한 뒤에, ~후에, ~다음에
COMPLEX_PATTERNS = [
    # 기본 접속: ~해서, ~하고, ~그리고
    r"(.+)(하고|해서|후에|다음에|그리고|그런 다음)\s*(.+)(해줘|해주세요|알려줘|만들어줘|찾아줘|보여줘|정리해줘|판단해줘)",
    # V-아/어서: 찾아서, 봐서, 확인해서 등
    r"(.+[아어]서|.+해서)\s*(.+)(해줘|해주세요|알려줘|만들어줘|찾아줘|보여줘|정리해줘|판단해줘)",
    # V-고: 찾고, 확인하고, 조회하고 등
    r"(.+)(하고|찾고|보고|읽고|확인하고|조회하고|검색하고)\s*(.+)(해줘|해주세요|알려줘|만들어줘|찾아줘|보여줘|정리해줘|판단해줘)",
    # 순차: ~한 뒤에, ~한 다음, ~후에
    r"(.+)(한 뒤에|한 다음|을 바탕으로|를 바탕으로|에 따라)\s*(.+)",
    # ~면서: 찾으면서, 확인하면서
    r"(.+)(면서|으면서)\s*(.+)(해줘|해주세요|알려줘|만들어줘)",
    # 조건부: 있으면~없으면
    r"(.+)(있으면|없으면).+(있으면|없으면)",
]

# 동사 어미 패턴
VERB_ENDINGS = re.compile(
    r"(해줘|해주세요|알려줘|만들어줘|찾아줘|확인해줘|작성해줘|추가해줘|보여줘|정리해줘|판단해줘|검색해줘|조회해줘|등록해줘)"
)

# 맥락 의존 패턴 (대명사/지시어)
CONTEXT_DEPENDENT_PATTERNS = [
    r"(그거|그것|그걸|아까|위에|방금|이전에|앞에서|말한|언급한)",
    r"(그|이|저)\s*(문서|보고서|회의|규정|일정|내용)",
    r"(다시|한번 더|또)\s*(해줘|보여줘|알려줘)",
]


def detect_complexity(text: str, candidates: list) -> dict:
    """
    복합 질문 여부 감지 (규칙 기반 + confidence 분석)

    3중 조건 AND 로직: 2개 이상 충족 시에만 복합 판정

    Args:
        text: 사용자 입력 텍스트
        candidates: top-k intent 후보 [{"intent": str, "confidence": float}, ...]

    Returns:
        {"is_complex": bool, "signals": int, "trigger_reasons": list}
    """
    signals = 0
    trigger_reasons = []

    # 조건 1: 접속/순차 키워드 패턴
    has_keyword = any(re.search(p, text) for p in COMPLEX_PATTERNS)
    if has_keyword:
        signals += 1
        trigger_reasons.append("keyword_pattern")

    # 조건 2: top-2 confidence gap이 작음 (두 intent가 경합 중)
    if len(candidates) >= 2:
        gap = candidates[0]["confidence"] - candidates[1]["confidence"]
        if gap < COMPLEXITY_GAP_THRESHOLD:
            signals += 1
            trigger_reasons.append(f"confidence_gap({gap:.2f})")

    # 조건 3: 동사 2개 이상 (행위가 2개)
    verb_endings = VERB_ENDINGS.findall(text)
    if len(verb_endings) >= 2:
        signals += 1
        trigger_reasons.append(f"multi_verb({len(verb_endings)})")

    is_complex = signals >= 2

    return {
        "is_complex": is_complex,
        "signals": signals,
        "trigger_reasons": trigger_reasons,
    }


def is_context_dependent(text: str) -> bool:
    """맥락 의존 쿼리 감지 (대명사/지시어 패턴)"""
    return any(re.search(p, text) for p in CONTEXT_DEPENDENT_PATTERNS)


def get_classifier() -> IntentClassifier:
    """Singleton IntentClassifier 인스턴스 반환"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
    return _classifier_instance
