"""
Intent Classification 모델 (팀원 A 담당)

카테고리 (6개):
  - judgment: 규정 기반 판단
  - doc_retrieve: 문서 검색/조회/요약/QA (RAG 파이프라인 → agent 내부에서 세부 분류)
  - doc_generate: 문서 생성 (보고서/회의록/JD/제안서)
  - schedule_add: 일정 추가 (파이프라인/결재도 schedule_agent 내부에서 분기)
  - schedule_view: 일정 조회
  - general: 일반 질문

모델: klue/roberta-large (Fine-tuned, 8-label multi-seed ensemble)
"""

import json
import logging
import os
import re
from pathlib import Path

from ai.agents.config import INTENT_FALLBACK_THRESHOLD

logger = logging.getLogger(__name__)

INTENT_LABELS = [
    "judgment",
    "doc_retrieve",
    "doc_generate",
    "schedule_add",
    "schedule_view",
    "general",
]

# 모델 weights 경로
_MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "intent_classifier"
_ENSEMBLE_DIR = Path(__file__).resolve().parent.parent / "models" / "intent_multilabel_ensemble"
_ONNX_ENSEMBLE_DIR = Path(__file__).resolve().parent.parent / "models" / "intent_ensemble_onnx"

# Singleton 인스턴스
_classifier_instance = None


class IntentClassifier:
    """Intent 분류기 (Singleton) — 5-seed 앙상블 지원"""

    # 예제 임베딩 캐시 (클래스 변수 - 모든 인스턴스가 공유)
    _example_embeddings_cache = None

    def __init__(self, model_path: str = None, ensemble_dir: str = None, onnx_dir: str = None):
        self.model_path = model_path or str(_MODEL_DIR)
        self.ensemble_dir = ensemble_dir or str(_ENSEMBLE_DIR)
        self.onnx_dir = onnx_dir or str(_ONNX_ENSEMBLE_DIR)
        self.model = None
        self.models = []  # 앙상블 모델 리스트 (PyTorch)
        self._onnx_sessions = []  # 앙상블 ONNX 세션 리스트
        self._onnx_tokenizer = None  # tokenizers.Tokenizer
        self.tokenizer = None
        self.id2label = None
        self._loaded = False
        self._is_multilabel = False
        self._is_ensemble = False
        self._is_onnx = False
        self._multilabel_threshold = 0.5
        # 6-label 앙상블 수동 threshold 최적화 결과 (held-out 93.3%)
        self._per_label_thresholds = {
            "judgment": 0.55,       # 과잉 트리거 방지 (0.50→0.55)
            "doc_retrieve": 0.55,   # 과잉 트리거 방지 (0.50→0.55)
            "doc_generate": 0.50,
            "schedule_add": 0.50,
            "schedule_view": 0.50,
            "general": 0.50,
        }

    def load_model(self):
        """모델 로드 — ONNX 앙상블 우선, PyTorch 앙상블, 단일 모델, fallback 순"""
        if self._loaded:
            return

        self.id2label = {i: label for i, label in enumerate(INTENT_LABELS)}

        # 1) ONNX 앙상블 시도 (경량, torch 불필요)
        onnx_dir = Path(self.onnx_dir)
        onnx_meta_path = onnx_dir / "ensemble_meta.json"
        if onnx_meta_path.exists():
            try:
                self._load_onnx_ensemble(onnx_dir, onnx_meta_path)
                self._loaded = True
                return
            except Exception as e:
                logger.error("Failed to load ONNX ensemble: %s — trying PyTorch", e)

        # 2) PyTorch 앙상블 디렉토리 시도
        ensemble_dir = Path(self.ensemble_dir)
        meta_path = ensemble_dir / "ensemble_meta.json"
        if meta_path.exists():
            try:
                self._load_ensemble(ensemble_dir, meta_path)
                self._loaded = True
                return
            except Exception as e:
                logger.error("Failed to load ensemble: %s — falling back to single model", e)

        # 3) 단일 모델 디렉토리 시도
        model_dir = Path(self.model_path)
        self._load_single_model(model_dir)
        self._loaded = True

    def _load_onnx_ensemble(self, onnx_dir: Path, meta_path: Path):
        """ONNX INT8 앙상블 모델 로드 (torch 불필요)"""
        import onnxruntime as ort
        from tokenizers import Tokenizer

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        seeds = meta["seeds"]

        # id2label from meta
        if "id2label" in meta:
            self.id2label = {int(k): v for k, v in meta["id2label"].items()}

        # 토크나이저 로드 (첫 seed에서)
        first_tok_path = onnx_dir / f"seed_{seeds[0]}" / "tokenizer.json"
        self._onnx_tokenizer = Tokenizer.from_file(str(first_tok_path))
        self._onnx_tokenizer.enable_padding(length=128)
        self._onnx_tokenizer.enable_truncation(max_length=128)

        # ONNX 세션 로드
        self._onnx_sessions = []
        for seed in seeds:
            model_path = onnx_dir / f"seed_{seed}" / "model_int8.onnx"
            if not model_path.exists():
                logger.warning("ONNX model not found: %s, skipping", model_path)
                continue
            sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
            self._onnx_sessions.append(sess)
            logger.info("ONNX ensemble model loaded: seed_%s", seed)

        if not self._onnx_sessions:
            raise RuntimeError("No ONNX ensemble models loaded")

        self._is_onnx = True
        self._is_ensemble = True
        self._is_multilabel = True

        logger.info(
            "ONNX INT8 ensemble loaded: %d models from %s",
            len(self._onnx_sessions), onnx_dir,
        )

    def _onnx_predict_probs(self, text: str):
        """ONNX 앙상블 추론 → sigmoid 확률 배열 반환"""
        import numpy as np

        encoded = self._onnx_tokenizer.encode(text)
        input_ids = np.array([encoded.ids], dtype=np.int64)
        attention_mask = np.array([encoded.attention_mask], dtype=np.int64)

        all_logits = []
        for sess in self._onnx_sessions:
            logits = sess.run(None, {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            })[0]
            all_logits.append(logits)

        # 앙상블: sigmoid 확률 평균
        probs = np.mean([1 / (1 + np.exp(-l)) for l in all_logits], axis=0)[0]
        return probs

    def _load_ensemble(self, ensemble_dir: Path, meta_path: Path):
        """5-seed 앙상블 모델 로드"""
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        seeds = meta["seeds"]
        base_model = meta.get("model", "klue/roberta-large")

        self.tokenizer = AutoTokenizer.from_pretrained(base_model)
        self.models = []

        for seed in seeds:
            seed_dir = ensemble_dir / f"seed_{seed}"
            if not seed_dir.exists():
                logger.warning("seed_%s directory not found, skipping", seed)
                continue

            model = AutoModelForSequenceClassification.from_pretrained(str(seed_dir))
            model.eval()
            self.models.append(model)
            logger.info("Ensemble model loaded: seed_%s", seed)

        if not self.models:
            raise RuntimeError("No ensemble models loaded")

        self._is_ensemble = True
        self._is_multilabel = True

        # id2label from first seed's model_info
        first_seed_dir = ensemble_dir / f"seed_{seeds[0]}"
        model_info_file = first_seed_dir / "model_info.json"
        if model_info_file.exists():
            with open(model_info_file, "r", encoding="utf-8") as f:
                model_info = json.load(f)
            if "labels" in model_info:
                self.id2label = {i: label for i, label in enumerate(model_info["labels"])}

        logger.info(
            "Intent ensemble loaded: %d models from %s (base: %s)",
            len(self.models), ensemble_dir, base_model,
        )

    def _load_single_model(self, model_dir: Path):
        """단일 모델 로드 (기존 로직)"""
        label_map_file = model_dir / "label_map.json"
        if label_map_file.exists():
            with open(label_map_file, "r", encoding="utf-8") as f:
                label_map = json.load(f)
            self.id2label = {int(k): v for k, v in label_map["id2label"].items()}

        has_weights = (
            (model_dir / "model.safetensors").exists()
            or (model_dir / "pytorch_model.bin").exists()
        )

        if not has_weights:
            logger.warning(
                "Intent classifier weights not found at %s — running in fallback mode",
                model_dir,
            )
            return

        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification

            base_model = "monologg/koelectra-base-v3-discriminator"
            model_info_file = model_dir / "model_info.json"
            if model_info_file.exists():
                with open(model_info_file, "r", encoding="utf-8") as f:
                    model_info = json.load(f)
                base_model = model_info.get("base_model", base_model)
                problem_type = model_info.get("problem_type", "single_label_classification")
                self._is_multilabel = (problem_type == "multi_label_classification")
                self._multilabel_threshold = model_info.get("threshold", 0.5)

            self.tokenizer = AutoTokenizer.from_pretrained(base_model)
            self.model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
            self.model.eval()
            mode_str = "multi-label" if self._is_multilabel else "single-label"
            logger.info("Intent classifier loaded from %s (tokenizer: %s, mode: %s)", model_dir, base_model, mode_str)
        except Exception as e:
            logger.error("Failed to load intent classifier: %s", e)
            self.model = None
            self.tokenizer = None

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

        # 전처리 (오타 교정 등)
        try:
            from ai.agents.preprocessing import preprocess

            processed = preprocess(text)
        except ImportError:
            processed = text

        # fallback: 모델 없으면 LLM 기반 분류 (전처리된 텍스트 사용)
        if not self._is_onnx and (self.model is None or self.tokenizer is None):
            return self._llm_based_predict(processed, return_candidates=return_candidates)

        # ONNX 추론
        if self._is_onnx:
            import numpy as np
            probs_np = self._onnx_predict_probs(processed)
            pred_id = int(np.argmax(probs_np))
            confidence = float(probs_np[pred_id])

            intent = self.id2label.get(pred_id, "general")
            intent = apply_known_overrides(text, intent)

            result = {"intent": intent, "confidence": round(confidence, 4)}
            if return_candidates:
                sorted_indices = np.argsort(probs_np)[::-1]
                candidates = [
                    {"intent": self.id2label.get(int(idx), "general"), "confidence": round(float(probs_np[idx]), 4)}
                    for idx in sorted_indices[:3]
                ]
                result["candidates"] = candidates
            return result

        # PyTorch 추론
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

    def predict_multilabel(self, text: str) -> dict:
        """
        멀티라벨 Intent 분류 추론 (Phase 2).

        sigmoid + threshold 기반으로 여러 intent를 동시에 반환.
        멀티라벨 모델이 없으면 규칙 기반 detect_compound_query()로 fallback.

        Returns:
            {
                "intents": [
                    {"intent": "doc_retrieve", "confidence": 0.92},
                    {"intent": "judgment", "confidence": 0.87},
                ],
                "is_compound": True,
                "primary_intent": "doc_retrieve",   # 최고 confidence
                "primary_confidence": 0.92,
            }
        """
        self.load_model()

        # 멀티라벨 모델이 없으면 규칙 기반 fallback
        if not self._is_multilabel:
            if not self._is_onnx and not self._is_ensemble and self.model is None:
                return self._fallback_compound_detect(text)
            if not self._is_onnx and self.tokenizer is None:
                return self._fallback_compound_detect(text)

        # 전처리
        try:
            from ai.agents.preprocessing import preprocess
            processed = preprocess(text)
        except ImportError:
            processed = text

        import numpy as np

        # ONNX 추론
        if self._is_onnx:
            probs_np = self._onnx_predict_probs(processed)
        else:
            # PyTorch 추론
            import torch

            inputs = self.tokenizer(
                processed,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=128,
            )

            with torch.no_grad():
                if self._is_ensemble and self.models:
                    all_probs = []
                    for m in self.models:
                        outputs = m(**inputs)
                        all_probs.append(torch.sigmoid(outputs.logits)[0].cpu().numpy())
                    probs_np = np.mean(all_probs, axis=0)
                else:
                    outputs = self.model(**inputs)
                    probs_np = torch.sigmoid(outputs.logits)[0].cpu().numpy()

        # per-label threshold 이상인 intent 수집
        intents = []
        for idx in range(len(self.id2label)):
            conf = float(probs_np[idx])
            label = self.id2label.get(idx, "general")
            threshold = self._per_label_thresholds.get(label, self._multilabel_threshold)
            if conf >= threshold:
                intents.append({
                    "intent": label,
                    "confidence": round(conf, 4),
                })

        # threshold 이상이 하나도 없으면 최고 confidence intent 반환
        if not intents:
            best_idx = int(np.argmax(probs_np))
            intents = [{
                "intent": self.id2label.get(best_idx, "general"),
                "confidence": round(float(probs_np[best_idx]), 4),
            }]

        # 멀티라벨 후처리 규칙
        intents = self._apply_multilabel_rules(processed, intents)

        # confidence 내림차순 정렬
        intents.sort(key=lambda x: x["confidence"], reverse=True)

        # 전체 레이블 sigmoid 확률 (top1/top2 gap 판단용)
        all_probs = {self.id2label[i]: round(float(probs_np[i]), 4) for i in range(len(self.id2label))}

        return {
            "intents": intents,
            "is_compound": len(intents) >= 2,
            "primary_intent": intents[0]["intent"],
            "primary_confidence": intents[0]["confidence"],
            "all_probs": all_probs,
        }

    def _apply_multilabel_rules(self, text: str, intents: list) -> list:
        """멀티라벨 후처리 규칙 — 100건 Held-out 오답 분석 기반"""
        intent_names = [i["intent"] for i in intents]

        # Rule 1: "규정/수당/복리후생" + "분석/확인/정리/알려" → judgment 보장
        if re.search(r"(규정|수당|복리후생|복지|기준)", text):
            if "judgment" not in intent_names:
                # doc_retrieve가 있으면 judgment로 교체
                for i in intents:
                    if i["intent"] == "doc_retrieve":
                        i["intent"] = "judgment"
                        break
                else:
                    intents.append({"intent": "judgment", "confidence": 0.6})

        # Rule 2: connector_trap — "규정 + 분석/정리/알려" 만 있으면 단일 judgment
        if re.search(r"(규정|수당).*(분석|정리|알려|확인|계산)", text) and \
           not re.search(r"(찾아|검색|잡아|등록|만들어|작성|일정)", text):
            return [{"intent": "judgment", "confidence": 0.85}]

        return intents

    def _fallback_compound_detect(self, text: str) -> dict:
        """멀티라벨 모델 없을 때 규칙 기반 fallback"""
        sub_queries = detect_compound_query(text)

        if sub_queries:
            # 복합 감지됨: hint intent 사용
            intents = [
                {"intent": sq["hint"], "confidence": 0.7}
                for sq in sub_queries
            ]
            return {
                "intents": intents,
                "is_compound": True,
                "primary_intent": intents[0]["intent"],
                "primary_confidence": 0.7,
            }

        # 단일: 기존 predict() 결과를 멀티라벨 형식으로 변환
        result = self.predict(text)
        return {
            "intents": [{"intent": result["intent"], "confidence": result["confidence"]}],
            "is_compound": False,
            "primary_intent": result["intent"],
            "primary_confidence": result["confidence"],
        }

    def _llm_based_predict(self, text: str, return_candidates: bool = False) -> dict:
        """LLM 기반 intent 분류 (Solar API)"""
        import time as _time
        _t = _time.time()
        print(f"[IntentClassifier] _llm_based_predict 시작 | text='{text}'")
        api_key = os.getenv("OPENAI_API_KEY")
        print(f"[IntentClassifier] OPENAI_API_KEY 존재: {bool(api_key)}")
        if not api_key:
            print("[IntentClassifier] OPENAI_API_KEY 없음 → 임베딩 fallback")
            return self._embedding_based_predict(text, return_candidates=return_candidates)

        try:
            from openai import OpenAI

            print("[IntentClassifier] GPT API 호출 중...")
            client = OpenAI(api_key=api_key)

            # return_candidates 요청 시 top-3 반환 프롬프트 추가
            _typo_instruction = """
                [중요] 사용자 입력에 오타나 탈자가 있을 수 있습니다. 오타를 자동으로 교정하여 의도를 파악하세요.
                예: "문ㅁ서" → "문서", "일젇" → "일정", "검색해죠" → "검색해줘", "보곶서" → "보고서"
                오타가 있더라도 문맥상 의도가 명확하면 해당 카테고리로 분류하세요."""

            _categories = """
                카테고리:
                - judgment: 규정/규칙 기반 판단 요청 (예: "이거 규정 위반이야?", "이렇게 해도 돼?")
                - doc_retrieve: 문서 검색/조회/요약/QA — 문서 찾기, 내용 질의응답, 문서 요약 (예: "마케팅 문서 찾아줘", "이 문서 요약해줘", "예산 얼마야?")
                - doc_generate: 문서 작성 — 보고서/회의록/JD/제안서 생성 (예: "보고서 작성해줘", "회의록 만들어줘")
                - schedule_add: 일정 추가/등록, 태스크 생성, 결재 요청 (예: "내일 2시 회의 일정 추가해줘", "태스크 만들어줘", "연차 신청해줘")
                - schedule_view: 일정 조회/확인 (예: "오늘 일정 보여줘", "이번 주 스케줄 확인해줘")
                - general: 위 카테고리에 해당하지 않는 일반 질문"""

            if return_candidates:
                system_prompt = f"""사용자 입력의 의도를 분류하세요.
                {_typo_instruction}
                {_categories}

                반드시 아래 JSON 형식으로만 응답하세요:
                {{"intent": "카테고리명", "confidence": 0.0~1.0, "candidates": [{{"intent": "카테고리명", "confidence": 0.0~1.0}}, ...]}}
                candidates에는 가장 가능성 높은 상위 3개를 포함하세요."""
            else:
                system_prompt = f"""사용자 입력의 의도를 분류하세요.
                {_typo_instruction}
                {_categories}

                반드시 아래 JSON 형식으로만 응답하세요:
                {{"intent": "카테고리명", "confidence": 0.0~1.0}}"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            raw_content = response.choices[0].message.content
            print(f"[IntentClassifier] GPT API 응답 원문: {raw_content}")
            result = json.loads(raw_content)
            intent = result.get("intent", "general")

            # deprecated intent 매핑 (Solar LLM이 옛날 라벨 반환할 수 있음)
            _DEPRECATED_INTENT_MAP = {
                "meeting_generate": "doc_generate",
            }
            if intent in _DEPRECATED_INTENT_MAP:
                new_intent = _DEPRECATED_INTENT_MAP[intent]
                print(f"[IntentClassifier] deprecated intent 매핑: {intent} → {new_intent}")
                intent = new_intent

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
                    if c_intent in _DEPRECATED_INTENT_MAP:
                        c_intent = _DEPRECATED_INTENT_MAP[c_intent]
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
                "doc_retrieve": [
                    "연차 휴가 규정 알려줘",
                    "출장비 지급 기준이 뭐야?",
                    "회의에서 어떤 내용이 논의되었나요?",
                    "코드리뷰 회의 내용 찾아줘",
                    "문서 검색해줘",
                    "규정 찾아줘",
                    "이 문서 요약해줘",
                    "핵심만 정리해줘",
                    "문서 내용 요약해줘",
                    "간단히 정리해줘",
                ],
                "doc_generate": [
                    "보고서 작성해줘",
                    "제안서 만들어줘",
                    "문서 생성해줘",
                    "JD 작성해줘",
                    "회의록 작성해줘",
                    "회의록 만들어줘",
                ],
                "schedule_add": [
                    "일정 추가해줘",
                    "스케줄 등록해줘",
                    "일정 넣어줘",
                    "태스크 만들어줘",
                    "결재 올려줘",
                    "연차 신청해줘",
                ],
                "schedule_view": [
                    "일정 보여줘",
                    "스케줄 확인해줘",
                    "일정 조회해줘",
                ],
                # pipeline/approval도 schedule_add에 포함 (schedule_agent 내부에서 분기)
                # "태스크 만들어줘", "결재 올려줘" 등은 schedule_add 예제에 추가
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
    # "X 규정 알려줘" → BERT가 doc_search로 분류하지만 규정 해석은 judgment
    r"(규정|규칙|지침|내규).*(알려|설명|안내)": "judgment",
    # "인사평가 기준 알려줘" → 기준/평가/심사 + 알려줘 패턴도 동일 이슈
    r"(기준|평가|심사|절차).*(알려|설명|안내)": "judgment",
    # "복리후생 뭐 있어" → 제도/수당 관련 질문은 judgment
    r"(복리후생|복지|수당|혜택|지원금|포상).*(뭐|어떤|있어|있나|있습니까)": "judgment",
    # "퇴직금 계산해줘" → 금액 산정 요청은 judgment (doc_generate 아님)
    r"(퇴직금|급여|연봉|월급|수당|상여).*(계산|산정|산출|얼마)": "judgment",
    # "지각하면 어떻게 돼?" → 조건부 결과 질문은 judgment (general 아님)
    r"(지각|결근|조퇴|무단|위반|어기).*(어떻게|불이익|처벌|징계|벌|감봉)": "judgment",
    # doc_retrieve 패턴: "이 문서 요약해줘", "핵심만 정리해줘"
    r"(이 문서|이 파일|업로드한|첨부).*(요약|정리|핵심)": "doc_retrieve",
    r"(요약|정리).*(해줘|해 줘|해주세요|부탁)": "doc_retrieve",
    # doc_retrieve 패턴 (문서 내용 질의 포함): "문서에 뭐라고 써있어?", "결정사항이 뭐야?"
    r"(문서에|보고서에|회의록에).*(뭐라고|어떻게|뭐야|뭐가)": "doc_retrieve",
    r"(결정사항|합의|결론|핵심 이슈).*(뭐야|뭐였|알려|있어)": "doc_retrieve",
    # doc_retrieve 패턴 (검색): "문서 찾아줘", "보고서 검색", "규정 목록"
    r"(문서|보고서|회의록|규정|자료).*(찾아|검색|목록|조회|보여)": "doc_retrieve",
    r"(찾아|검색|목록|조회).*(문서|보고서|회의록|규정|자료)": "doc_retrieve",
    r".*(관련|관한)\s*(문서|자료|보고서|규정).*(찾아|검색|있어|보여|알려)": "doc_retrieve",
    # pipeline/approval → schedule_add로 보내면 schedule_agent 내부에서 _classify_add_type()이 분기
    r"(태스크|task|파이프라인|pipeline|칸반|보드).*(만들|생성|추가|등록)": "schedule_add",
    r"(결재|승인|결재요청|결재 요청).*(올려|신청|등록|만들)": "schedule_add",
    r"(연차|휴가|반차|조퇴|출장).*(신청|올려|결재|요청)": "schedule_add",
}


def apply_known_overrides(text: str, bert_intent: str) -> str:
    """알려진 오분류 패턴이면 강제 전환"""
    for pattern, correct_intent in KNOWN_OVERRIDES.items():
        if re.search(pattern, text):
            logger.info(f"Known override: {bert_intent} → {correct_intent} for '{text}'")
            return correct_intent
    return bert_intent


def get_classifier() -> IntentClassifier:
    """Singleton IntentClassifier 인스턴스 반환"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
    return _classifier_instance


# ── 복합 질문 감지 (규칙 기반) ──

# 복합 감지 키워드 (문장 안에 서로 다른 intent 동사가 2개 이상)
_INTENT_VERB_PATTERNS = {
    "judgment": r"(판단|위반|허용|가능한가|되나요|해도 되|해도 돼)",
    "doc_retrieve": r"(찾아|검색|어디|어떤 문서|검토|뭐라고|뭐야|뭐였|결정사항|내용이|요약|정리|핵심만)",
    "doc_generate": r"(작성|생성|만들어|만들고|써 줘|써줘|작성해|만들어 줘)",
    "schedule_add": r"(일정.*(?:추가|등록|잡아|넣어)|(?:추가|등록|잡아|넣어).*일정|회의.*(?:잡아|등록|잡고))",
    "schedule_view": r"(일정.*(?:보여|조회|확인|알려)|(?:보여|조회|확인).*일정|스케줄.*(?:보여|확인))",
}

# 동사 어간 + "하고"/"주고" 패턴 (분리점으로 사용)
_VERB_CONNECTOR_PATTERN = r"((?:추가|등록|잡아|검색|찾아|조회|확인|판단|생성|작성|요약|정리|만들)(?:하고|고)|(?:해|찾아|보여|알려|잡아|확인해|조회해|만들어)(?:줘|주고))\s+"


# "~해서/~어서" 순차 연결 패턴
_SEQUENTIAL_CONNECTOR_PATTERN = r"((?:찾아|검색해|확인해|정리해|검토해|조회해)서)\s+"

# "~보고", "바탕으로", "한 다음" 등 순차 패턴
_SEQUENTIAL_PHRASE_PATTERNS = [
    r"(.+?(?:찾아|검색해|확인해)보고)\s+(.+)",      # "찾아보고 ~해줘"
    r"(.+?)\s*(?:바탕으로|기반으로|토대로)\s+(.+)",   # "규정을 바탕으로 JD 작성해줘"
    r"(.+?(?:요약|정리|확인|검색)한\s*(?:다음|후에?))\s+(.+)",  # "요약한 다음 ~해줘"
    r"(.+?)\s*있으면\s*(.+?)\s*없으면\s*(.+)",        # "있으면 ~ 없으면 ~"
]


def _split_compound_text(text: str) -> list[str]:
    """복합 질문 텍스트를 서브쿼리 파트로 분리 (3step 이상 지원)"""
    # 1. "그리고" / 쉼표로 분리
    if "그리고" in text:
        return [p.strip() for p in text.split("그리고") if p.strip()]
    if ", " in text or "," in text:
        parts = [p.strip() for p in re.split(r",\s*", text) if p.strip()]
        if len(parts) >= 2:
            return parts

    # 2. 동사 연결 + 순차 연결 통합 패턴 (verb "~하고/~주고" + seq "~해서")
    combined = (
        r"("
        r"(?:추가|등록|잡아|잡|검색|찾아|조회|확인|판단|생성|작성|요약|정리|만들|보)(?:하고|고)"
        r"|(?:해|찾아|보여|알려|잡아|확인해|조회해|만들어)(?:줘|주고)"
        r"|(?:찾아|검색해|확인해|정리해|검토해|조회해)서"
        r")\s+"
    )
    segments = re.split(combined, text)
    if len(segments) >= 3:
        parts = []
        for i in range(0, len(segments) - 1, 2):
            part = (segments[i] + segments[i + 1]).strip()
            if part:
                parts.append(part)
        if len(segments) % 2 == 1 and segments[-1].strip():
            parts.append(segments[-1].strip())
        if len(parts) >= 2:
            return parts

    # 3. "~보고", "바탕으로", "한 다음" 등 순차 구문
    for pattern in _SEQUENTIAL_PHRASE_PATTERNS:
        m = re.match(pattern, text)
        if m:
            parts = [p.strip() for p in m.groups() if p and p.strip()]
            if len(parts) >= 2:
                return parts

    return []


def detect_compound_query(text: str) -> list[dict]:
    """
    규칙 기반 복합 질문 감지 + 분리.

    Returns:
        복합이면: [{"query": "일정 추가해줘", "hint": "schedule_add"}, ...]
        단일이면: []
    """
    # 1단계: intent 동사 패턴으로 2개 이상 intent 감지
    matched_intents = []
    for intent, pattern in _INTENT_VERB_PATTERNS.items():
        if re.search(pattern, text):
            matched_intents.append(intent)

    if len(matched_intents) < 2:
        return []

    # 2단계: 명확한 구분자로 문장 분리
    parts = _split_compound_text(text)

    if len(parts) < 2:
        return []

    # 3단계: 각 part에 intent hint 매칭
    sub_queries = []
    for part in parts:
        hint = "general"
        for intent, pattern in _INTENT_VERB_PATTERNS.items():
            if re.search(pattern, part):
                hint = intent
                break
        sub_queries.append({"query": part, "hint": hint})

    # 모든 sub_query가 같은 intent면 복합이 아님
    hints = set(sq["hint"] for sq in sub_queries)
    if len(hints) < 2:
        return []

    logger.info(
        "Compound query detected: '%s' → %s",
        text,
        [sq["hint"] for sq in sub_queries],
    )
    return sub_queries
