"""
v2_generate 내용 품질 평가 — Base vs Fine-tuned

구조 지표(JSON 유효율, 필드 완성도)에서 Base가 이미 높은 성능을 보이므로,
내용 품질 차이를 정량+정성으로 증명한다.

정량 지표 4개:
  1. 빈 필드 정확도 — 할루시네이션 감소 (정답이 빈값이면 모델도 비워야)
  2. ROUGE-L — 표면적 내용 겹침 (단어 순서 유지 매칭)
  3. BERTScore — 의미적 내용 유사도 (klue/roberta-large)
  4. 출력 길이 — 간결성 비교

정성 평가:
  - Before/After 예시 자동 추출 (할루시네이션, 장황함, 품질 차이)

사용법:
    # 1) 먼저 Base/Fine-tuned 모델로 150건 추론 결과를 JSONL로 저장
    #    각 줄: {"pred": "모델 출력 텍스트", "gold": "정답 텍스트"}
    #    (train_v2_document.py의 evaluate 함수에서 predictions를 전체 저장하도록 수정하거나,
    #     별도로 추론 후 저장)

    # 2) 내용 품질 평가 실행
    python ai/finetuning/scripts/eval_content_quality.py \
        --eval_path data/training/v2_generate/eval.jsonl \
        --base_output outputs/v2_generate/base_predictions.jsonl \
        --ft_output outputs/v2_generate/ft_predictions.jsonl \
        --output_dir outputs/v2_generate/content_quality

    # 3) 추론도 함께 실행 (모델 경로 지정 시)
    python ai/finetuning/scripts/eval_content_quality.py \
        --eval_path data/training/v2_generate/eval.jsonl \
        --base_model kakaocorp/kanana-1.5-8b-instruct-2505 \
        --ft_model kakaocorp/kanana-1.5-8b-instruct-2505 \
        --adapter_path outputs/v2_generate/kanana-1.5-8b-instruct-2505/final \
        --output_dir outputs/v2_generate/content_quality

환경:
    pip install bert-score transformers torch
    # BERTScore 모델: klue/roberta-large (한국어 특화)
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# 프로젝트 루트
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


# ── 유틸리티 (evaluate.py에서 재사용) ──


def _safe_parse_json(text: str) -> dict | None:
    """텍스트에서 JSON 추출 (```json 블록, 순수 JSON 등)"""
    if not text:
        return None
    text = text.strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    if not text.startswith("{"):
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _rouge_l(prediction: str, reference: str) -> float:
    """ROUGE-L (LCS 기반) — evaluate.py의 동일 구현"""
    pred_tokens = prediction.split()
    ref_tokens = reference.split()
    if not pred_tokens or not ref_tokens:
        return 0.0

    m, n = len(pred_tokens), len(ref_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if pred_tokens[i - 1] == ref_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs_len = dp[m][n]

    precision = lcs_len / m if m > 0 else 0
    recall = lcs_len / n if n > 0 else 0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def load_jsonl(path: str | Path) -> list[dict]:
    """JSONL 파일 로드"""
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def _is_empty_value(val) -> bool:
    """유연한 빈값 판정 — 빈 문자열, N/A, 없음, 빈 배열 등"""
    if val is None:
        return True
    if isinstance(val, list):
        return len(val) == 0
    if isinstance(val, dict):
        return len(val) == 0
    s = str(val).strip()
    return s == "" or s.lower() in ("n/a", "없음", "null", "none", "-")


def _is_array_field(val) -> bool:
    """배열 필드 여부 판정"""
    return isinstance(val, list)


def _flatten_json_values(obj: dict, prefix: str = "") -> dict[str, str]:
    """JSON 객체의 모든 문자열 값을 평탄화하여 {path: value} 반환"""
    result = {}
    for key, val in obj.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(val, dict):
            result.update(_flatten_json_values(val, full_key))
        elif isinstance(val, list):
            # 배열 필드는 ROUGE-L/BERTScore에서 제외 (구조 비교 대상)
            result[full_key] = json.dumps(val, ensure_ascii=False)
        else:
            result[full_key] = str(val) if val is not None else ""
    return result


# ── 지표 1: 빈 필드 정확도 ──


def eval_empty_fields(gold_json: dict, pred_json: dict) -> dict:
    """정답이 빈값인 필드에 대해 모델도 비웠는지 체크

    Returns:
        {
            "empty_correct": int,    # 정답=빈, 모델=빈 (정확)
            "empty_total": int,      # 정답=빈 필드 수
            "false_fill": int,       # 정답=빈, 모델=채움 (할루시네이션)
            "false_empty": int,      # 정답=있음, 모델=빈 (누락)
            "filled_total": int,     # 정답=있음 필드 수
        }
    """
    empty_correct = 0
    empty_total = 0
    false_fill = 0
    false_empty = 0
    filled_total = 0

    # 정답 JSON의 모든 키에 대해 평가
    for key in gold_json:
        gold_val = gold_json[key]
        pred_val = pred_json.get(key)

        if _is_empty_value(gold_val):
            # 정답이 빈값인 필드
            empty_total += 1
            if _is_empty_value(pred_val):
                empty_correct += 1
            else:
                false_fill += 1  # 할루시네이션: 없는 정보를 지어냄
        else:
            # 정답이 있는 필드
            filled_total += 1
            if _is_empty_value(pred_val):
                false_empty += 1  # 누락: 있는 정보를 비움

    return {
        "empty_correct": empty_correct,
        "empty_total": empty_total,
        "false_fill": false_fill,
        "false_empty": false_empty,
        "filled_total": filled_total,
    }


# ── 지표 2: ROUGE-L (텍스트 필드만) ──


def eval_rouge_l_fields(gold_json: dict, pred_json: dict) -> dict:
    """문자열 텍스트 필드에 대해 ROUGE-L 계산 (배열 필드 제외)

    Returns:
        {"rouge_l_sum": float, "rouge_l_count": int}
    """
    rouge_sum = 0.0
    count = 0

    for key in gold_json:
        gold_val = gold_json[key]
        pred_val = pred_json.get(key)

        # 배열/딕셔너리 필드 제외, 빈값 제외
        if _is_array_field(gold_val) or isinstance(gold_val, dict):
            continue
        if _is_empty_value(gold_val):
            continue

        gold_str = str(gold_val).strip()
        pred_str = str(pred_val).strip() if pred_val is not None else ""

        if not gold_str or not pred_str:
            continue

        rouge_sum += _rouge_l(pred_str, gold_str)
        count += 1

    return {"rouge_l_sum": rouge_sum, "rouge_l_count": count}


# ── 지표 3: BERTScore (텍스트 필드만) ──


def collect_text_pairs(gold_json: dict, pred_json: dict) -> tuple[list[str], list[str]]:
    """ROUGE-L/BERTScore 대상 텍스트 쌍 수집 (배열 필드 제외, 빈값 제외)"""
    preds = []
    refs = []

    for key in gold_json:
        gold_val = gold_json[key]
        pred_val = pred_json.get(key)

        if _is_array_field(gold_val) or isinstance(gold_val, dict):
            continue
        if _is_empty_value(gold_val):
            continue

        gold_str = str(gold_val).strip()
        pred_str = str(pred_val).strip() if pred_val is not None else ""

        if not gold_str or not pred_str:
            continue

        preds.append(pred_str)
        refs.append(gold_str)

    return preds, refs


def compute_bertscore_batch(
    all_preds: list[str], all_refs: list[str], model_type: str = "klue/roberta-large"
) -> float:
    """BERTScore 일괄 계산 — bert_score 라이브러리 사용

    Returns:
        평균 F1 BERTScore
    """
    if not all_preds or not all_refs:
        return 0.0

    try:
        from bert_score import score as bert_score_fn
    except ImportError:
        print("  [WARNING] bert-score 미설치. pip install bert-score")
        return -1.0

    print(f"  BERTScore 계산 중... ({len(all_preds)}건, 모델: {model_type})")

    # klue/roberta-large: 24 레이어, bert-score 내장 매핑에 없으므로 직접 지정
    extra_kwargs = {}
    if "klue" in model_type or model_type not in (
        "bert-base-uncased", "roberta-large", "microsoft/deberta-xlarge-mnli",
    ):
        extra_kwargs["num_layers"] = 24  # roberta-large 계열 기본값

    P, R, F1 = bert_score_fn(
        all_preds,
        all_refs,
        model_type=model_type,
        lang="ko",
        verbose=False,
        batch_size=32,
        **extra_kwargs,
    )
    return F1.mean().item()


# ── 추론 (모델 경로 지정 시) ──


def run_inference(
    eval_samples: list[dict],
    model_id: str,
    adapter_path: str | None = None,
    max_new_tokens: int = 1024,
) -> list[str]:
    """모델로 eval 샘플 추론 → 예측 텍스트 리스트 반환"""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"\n  모델 로드: {model_id}")
    if adapter_path:
        print(f"  어댑터: {adapter_path}")
        from peft import PeftModel

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # H200 143GB — bf16 풀로드 (4-bit 양자화 torch 호환 이슈 회피)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )

    if adapter_path:
        model = PeftModel.from_pretrained(model, adapter_path)

    model.eval()
    torch.cuda.empty_cache()

    predictions = []
    for i, sample in enumerate(eval_samples, 1):
        messages = sample["messages"]
        infer_messages = [m for m in messages if m["role"] != "assistant"]

        try:
            prompt = tokenizer.apply_chat_template(
                infer_messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            prompt = "\n".join(
                f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>"
                for m in infer_messages
            ) + "\n<|im_start|>assistant\n"

        inputs = tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=2560
        ).to(model.device)
        input_len = inputs["input_ids"].shape[1]

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=1.0,
                pad_token_id=tokenizer.eos_token_id,
            )

        pred_text = tokenizer.decode(
            outputs[0][input_len:], skip_special_tokens=True
        ).strip()
        predictions.append(pred_text)

        if i % 20 == 0 or i <= 3:
            print(f"    [{i:03d}/{len(eval_samples)}] 추론 완료")

    # 모델 메모리 해제
    del model
    torch.cuda.empty_cache()

    return predictions


# ── 정성 평가: Before/After 예시 추출 ──


def find_qualitative_examples(
    eval_samples: list[dict],
    base_preds: list[str],
    ft_preds: list[str],
    gold_texts: list[str],
) -> list[dict]:
    """정성 비교 예시를 자동 선별

    기준:
    1. 할루시네이션 예시 — Base가 빈 필드를 채우고, FT는 비운 경우
    2. 장황함 예시 — Base 출력이 FT보다 현저히 긴 경우
    3. ROUGE-L 차이 — FT의 ROUGE-L이 Base보다 높은 경우
    """
    examples = []

    for i in range(len(gold_texts)):
        gold_json = _safe_parse_json(gold_texts[i])
        base_json = _safe_parse_json(base_preds[i])
        ft_json = _safe_parse_json(ft_preds[i])

        if not gold_json or not base_json or not ft_json:
            continue

        # 할루시네이션 차이
        base_empty = eval_empty_fields(gold_json, base_json)
        ft_empty = eval_empty_fields(gold_json, ft_json)

        hallucination_diff = base_empty["false_fill"] - ft_empty["false_fill"]

        # 길이 차이
        base_len = len(base_preds[i])
        ft_len = len(ft_preds[i])
        length_ratio = base_len / max(ft_len, 1)

        # ROUGE-L 차이 (전체 텍스트)
        base_rouge = _rouge_l(base_preds[i], gold_texts[i])
        ft_rouge = _rouge_l(ft_preds[i], gold_texts[i])
        rouge_diff = ft_rouge - base_rouge

        example = {
            "index": i,
            "hallucination_diff": hallucination_diff,
            "base_false_fill": base_empty["false_fill"],
            "ft_false_fill": ft_empty["false_fill"],
            "length_ratio": round(length_ratio, 2),
            "base_len": base_len,
            "ft_len": ft_len,
            "rouge_diff": round(rouge_diff, 4),
            "base_rouge": round(base_rouge, 4),
            "ft_rouge": round(ft_rouge, 4),
        }
        examples.append(example)

    # 각 카테고리에서 최고 예시 선별
    selected = []

    # 1. 할루시네이션 최대 차이
    by_hallucination = sorted(examples, key=lambda x: x["hallucination_diff"], reverse=True)
    if by_hallucination and by_hallucination[0]["hallucination_diff"] > 0:
        ex = by_hallucination[0]
        idx = ex["index"]
        selected.append({
            "category": "할루시네이션 감소",
            "description": f"Base가 빈 필드 {ex['base_false_fill']}개 채움(지어냄) vs FT {ex['ft_false_fill']}개",
            **ex,
            "base_output_preview": base_preds[idx][:500],
            "ft_output_preview": ft_preds[idx][:500],
            "gold_preview": gold_texts[idx][:500],
        })

    # 2. 장황함 최대 차이
    by_length = sorted(examples, key=lambda x: x["length_ratio"], reverse=True)
    if by_length and by_length[0]["length_ratio"] > 1.3:
        ex = by_length[0]
        idx = ex["index"]
        if not any(s["index"] == idx for s in selected):
            selected.append({
                "category": "간결성 향상",
                "description": f"Base {ex['base_len']}자 vs FT {ex['ft_len']}자 (비율 {ex['length_ratio']}x)",
                **ex,
                "base_output_preview": base_preds[idx][:500],
                "ft_output_preview": ft_preds[idx][:500],
                "gold_preview": gold_texts[idx][:500],
            })

    # 3. ROUGE-L 최대 개선
    by_rouge = sorted(examples, key=lambda x: x["rouge_diff"], reverse=True)
    if by_rouge and by_rouge[0]["rouge_diff"] > 0.01:
        ex = by_rouge[0]
        idx = ex["index"]
        if not any(s["index"] == idx for s in selected):
            selected.append({
                "category": "내용 품질 향상",
                "description": f"ROUGE-L: Base {ex['base_rouge']} → FT {ex['ft_rouge']} (+{ex['rouge_diff']})",
                **ex,
                "base_output_preview": base_preds[idx][:500],
                "ft_output_preview": ft_preds[idx][:500],
                "gold_preview": gold_texts[idx][:500],
            })

    return selected


# ── 메인 평가 ──


def evaluate_content_quality(
    eval_samples: list[dict],
    base_preds: list[str],
    ft_preds: list[str],
    bertscore_model: str = "klue/roberta-large",
) -> dict:
    """내용 품질 평가 — 4개 정량 지표 + 정성 예시"""

    total = len(eval_samples)
    gold_texts = [s["messages"][-1]["content"] for s in eval_samples]

    # --- 통계 초기화 ---
    base_stats = {
        "empty_correct": 0, "empty_total": 0,
        "false_fill": 0, "false_empty": 0, "filled_total": 0,
        "rouge_l_sum": 0.0, "rouge_l_count": 0,
        "total_length": 0, "json_valid": 0,
    }
    ft_stats = {
        "empty_correct": 0, "empty_total": 0,
        "false_fill": 0, "false_empty": 0, "filled_total": 0,
        "rouge_l_sum": 0.0, "rouge_l_count": 0,
        "total_length": 0, "json_valid": 0,
    }

    # BERTScore용 텍스트 쌍 수집
    base_bert_preds, base_bert_refs = [], []
    ft_bert_preds, ft_bert_refs = [], []

    for i in range(total):
        gold_json = _safe_parse_json(gold_texts[i])
        base_json = _safe_parse_json(base_preds[i])
        ft_json = _safe_parse_json(ft_preds[i])

        # 출력 길이 (전체 텍스트)
        base_stats["total_length"] += len(base_preds[i])
        ft_stats["total_length"] += len(ft_preds[i])

        if not gold_json:
            continue

        # --- Base 평가 ---
        if base_json:
            base_stats["json_valid"] += 1

            # 빈 필드 정확도
            empty_result = eval_empty_fields(gold_json, base_json)
            for k, v in empty_result.items():
                base_stats[k] += v

            # ROUGE-L (텍스트 필드)
            rouge_result = eval_rouge_l_fields(gold_json, base_json)
            base_stats["rouge_l_sum"] += rouge_result["rouge_l_sum"]
            base_stats["rouge_l_count"] += rouge_result["rouge_l_count"]

            # BERTScore 쌍 수집
            preds, refs = collect_text_pairs(gold_json, base_json)
            base_bert_preds.extend(preds)
            base_bert_refs.extend(refs)

        # --- Fine-tuned 평가 ---
        if ft_json:
            ft_stats["json_valid"] += 1

            empty_result = eval_empty_fields(gold_json, ft_json)
            for k, v in empty_result.items():
                ft_stats[k] += v

            rouge_result = eval_rouge_l_fields(gold_json, ft_json)
            ft_stats["rouge_l_sum"] += rouge_result["rouge_l_sum"]
            ft_stats["rouge_l_count"] += rouge_result["rouge_l_count"]

            preds, refs = collect_text_pairs(gold_json, ft_json)
            ft_bert_preds.extend(preds)
            ft_bert_refs.extend(refs)

    # --- BERTScore 일괄 계산 ---
    print("\n[BERTScore] Base 모델...")
    base_bertscore = compute_bertscore_batch(base_bert_preds, base_bert_refs, bertscore_model)
    print(f"  Base BERTScore F1: {base_bertscore:.4f}")

    print("[BERTScore] Fine-tuned 모델...")
    ft_bertscore = compute_bertscore_batch(ft_bert_preds, ft_bert_refs, bertscore_model)
    print(f"  FT BERTScore F1: {ft_bertscore:.4f}")

    # --- 결과 계산 ---
    def calc_metrics(stats, bertscore_val):
        empty_acc = stats["empty_correct"] / max(stats["empty_total"], 1)
        false_fill_rate = stats["false_fill"] / max(stats["empty_total"], 1)
        false_empty_rate = stats["false_empty"] / max(stats["filled_total"], 1)
        rouge_l = stats["rouge_l_sum"] / max(stats["rouge_l_count"], 1)
        avg_length = stats["total_length"] / max(total, 1)

        return {
            "empty_field_accuracy": round(empty_acc * 100, 2),
            "false_fill_rate": round(false_fill_rate * 100, 2),
            "false_empty_rate": round(false_empty_rate * 100, 2),
            "empty_total": stats["empty_total"],
            "filled_total": stats["filled_total"],
            "rouge_l": round(rouge_l, 4),
            "rouge_l_field_count": stats["rouge_l_count"],
            "bertscore_f1": round(bertscore_val, 4) if bertscore_val >= 0 else "N/A",
            "avg_output_length": round(avg_length, 1),
            "json_valid": stats["json_valid"],
        }

    base_metrics = calc_metrics(base_stats, base_bertscore)
    ft_metrics = calc_metrics(ft_stats, ft_bertscore)

    # --- 정성 예시 ---
    print("\n[정성 평가] Before/After 예시 선별 중...")
    qualitative = find_qualitative_examples(eval_samples, base_preds, ft_preds, gold_texts)

    return {
        "total_samples": total,
        "base": base_metrics,
        "finetuned": ft_metrics,
        "qualitative_examples": qualitative,
    }


def print_comparison_table(results: dict):
    """비교표 콘솔 출력"""
    base = results["base"]
    ft = results["finetuned"]

    print(f"\n{'=' * 70}")
    print(f"  내용 품질 평가 결과 — Base vs Fine-tuned ({results['total_samples']}건)")
    print(f"{'=' * 70}")

    print(f"\n  {'지표':<25} {'Base':>12} {'Fine-tuned':>12} {'의미'}")
    print(f"  {'-' * 65}")

    # 빈 필드 정확도
    print(f"  {'빈 필드 정확도':<22} {base['empty_field_accuracy']:>10}% {ft['empty_field_accuracy']:>10}%   할루시네이션 ↓")
    print(f"  {'  (false fill율)':<22} {base['false_fill_rate']:>10}% {ft['false_fill_rate']:>10}%   지어내기 ↓")
    print(f"  {'  (false empty율)':<22} {base['false_empty_rate']:>10}% {ft['false_empty_rate']:>10}%   누락 ↓")
    print(f"  {'  (빈 필드 수)':<22} {base['empty_total']:>10} {ft['empty_total']:>10}")

    # ROUGE-L
    print(f"  {'ROUGE-L':<22} {base['rouge_l']:>12.4f} {ft['rouge_l']:>12.4f}   내용 일치 ↑")
    print(f"  {'  (필드 수)':<22} {base['rouge_l_field_count']:>10} {ft['rouge_l_field_count']:>10}")

    # BERTScore
    base_bs = f"{base['bertscore_f1']:.4f}" if isinstance(base['bertscore_f1'], float) else base['bertscore_f1']
    ft_bs = f"{ft['bertscore_f1']:.4f}" if isinstance(ft['bertscore_f1'], float) else ft['bertscore_f1']
    print(f"  {'BERTScore F1':<22} {base_bs:>12} {ft_bs:>12}   의미 유사 ↑")

    # 출력 길이
    print(f"  {'평균 출력 길이':<20} {base['avg_output_length']:>10.1f}자 {ft['avg_output_length']:>10.1f}자   간결성 ↑")

    print(f"\n{'=' * 70}")

    # 발표용 마크다운 테이블
    print(f"\n  [발표 슬라이드용 마크다운]")
    print()
    print(f"  | 지표 | Base | Fine-tuned | 의미 |")
    print(f"  |------|------|-----------|------|")
    print(f"  | 빈 필드 정확도 | {base['empty_field_accuracy']}% | {ft['empty_field_accuracy']}% | 할루시네이션 ↓ |")
    print(f"  | ROUGE-L | {base['rouge_l']:.4f} | {ft['rouge_l']:.4f} | 표면적 내용 일치 ↑ |")
    print(f"  | BERTScore F1 | {base_bs} | {ft_bs} | 의미적 내용 유사 ↑ |")
    print(f"  | 평균 출력 길이 | {base['avg_output_length']:.0f}자 | {ft['avg_output_length']:.0f}자 | 간결성 ↑ |")

    # 정성 예시
    if results.get("qualitative_examples"):
        print(f"\n{'=' * 70}")
        print(f"  Before/After 정성 비교 예시")
        print(f"{'=' * 70}")

        for ex in results["qualitative_examples"]:
            print(f"\n  [{ex['category']}] — Sample #{ex['index']}")
            print(f"  {ex['description']}")
            print(f"\n  [Base 출력]")
            print(f"  {ex['base_output_preview'][:300]}...")
            print(f"\n  [Fine-tuned 출력]")
            print(f"  {ex['ft_output_preview'][:300]}...")
            print(f"\n  [정답]")
            print(f"  {ex['gold_preview'][:300]}...")
            print()


def main():
    parser = argparse.ArgumentParser(description="v2_generate 내용 품질 평가")
    parser.add_argument("--eval_path", required=True, help="eval JSONL 경로")
    parser.add_argument("--base_output", default=None, help="Base 모델 출력 JSONL (pred 키)")
    parser.add_argument("--ft_output", default=None, help="Fine-tuned 모델 출력 JSONL (pred 키)")
    parser.add_argument("--base_model", default=None, help="Base 모델 ID (추론 시)")
    parser.add_argument("--ft_model", default=None, help="Fine-tuned 모델 ID (추론 시)")
    parser.add_argument("--adapter_path", default=None, help="LoRA 어댑터 경로 (ft_model과 함께 사용)")
    parser.add_argument("--output_dir", default="outputs/v2_generate/content_quality",
                        help="결과 저장 디렉토리")
    parser.add_argument("--bertscore_model", default="klue/roberta-large",
                        help="BERTScore 모델 (기본: klue/roberta-large)")
    parser.add_argument("--limit", type=int, default=0,
                        help="평가 샘플 수 제한 (0=전체, 소규모 테스트용)")
    args = parser.parse_args()

    # eval 데이터 로드
    eval_path = Path(args.eval_path)
    if not eval_path.is_absolute():
        eval_path = BASE_DIR / eval_path
    eval_samples = load_jsonl(eval_path)
    print(f"  Eval 데이터: {len(eval_samples)}건 로드")

    if args.limit > 0:
        eval_samples = eval_samples[:args.limit]
        print(f"  → {args.limit}건으로 제한 (소규모 테스트)")

    # --- Base 모델 출력 ---
    if args.base_output:
        base_data = load_jsonl(args.base_output)
        base_preds = [d["pred"] for d in base_data]
        print(f"  Base 출력: {len(base_preds)}건 로드 ({args.base_output})")
    elif args.base_model:
        print(f"\n  Base 모델 추론 시작: {args.base_model}")
        base_preds = run_inference(eval_samples, args.base_model)
        # 추론 결과 저장
        output_dir = Path(args.output_dir)
        if not output_dir.is_absolute():
            output_dir = BASE_DIR / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        base_out_path = output_dir / "base_predictions.jsonl"
        with open(base_out_path, "w", encoding="utf-8") as f:
            for pred in base_preds:
                f.write(json.dumps({"pred": pred}, ensure_ascii=False) + "\n")
        print(f"  Base 추론 결과 저장: {base_out_path}")
    else:
        print("ERROR: --base_output 또는 --base_model 중 하나를 지정하세요.")
        sys.exit(1)

    # --- Fine-tuned 모델 출력 ---
    if args.ft_output:
        ft_data = load_jsonl(args.ft_output)
        ft_preds = [d["pred"] for d in ft_data]
        print(f"  FT 출력: {len(ft_preds)}건 로드 ({args.ft_output})")
    elif args.ft_model:
        print(f"\n  Fine-tuned 모델 추론 시작: {args.ft_model}")
        ft_preds = run_inference(eval_samples, args.ft_model, adapter_path=args.adapter_path)
        output_dir = Path(args.output_dir)
        if not output_dir.is_absolute():
            output_dir = BASE_DIR / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        ft_out_path = output_dir / "ft_predictions.jsonl"
        with open(ft_out_path, "w", encoding="utf-8") as f:
            for pred in ft_preds:
                f.write(json.dumps({"pred": pred}, ensure_ascii=False) + "\n")
        print(f"  FT 추론 결과 저장: {ft_out_path}")
    else:
        print("ERROR: --ft_output 또는 --ft_model 중 하나를 지정하세요.")
        sys.exit(1)

    # 길이 확인
    if len(base_preds) != len(eval_samples) or len(ft_preds) != len(eval_samples):
        print(f"  WARNING: eval({len(eval_samples)}) vs base({len(base_preds)}) vs ft({len(ft_preds)}) 길이 불일치")
        min_len = min(len(eval_samples), len(base_preds), len(ft_preds))
        eval_samples = eval_samples[:min_len]
        base_preds = base_preds[:min_len]
        ft_preds = ft_preds[:min_len]
        print(f"  → {min_len}건으로 조정")

    # --- 평가 실행 ---
    print(f"\n{'=' * 70}")
    print(f"  내용 품질 평가 시작 ({len(eval_samples)}건)")
    print(f"{'=' * 70}")

    results = evaluate_content_quality(
        eval_samples, base_preds, ft_preds,
        bertscore_model=args.bertscore_model,
    )

    # --- 결과 출력 ---
    print_comparison_table(results)

    # --- 결과 저장 ---
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = BASE_DIR / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    result_path = output_dir / "content_quality_results.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {result_path}")

    # 마크다운 보고서 저장
    md_path = output_dir / "content_quality_report.md"
    base = results["base"]
    ft = results["finetuned"]
    base_bs = f"{base['bertscore_f1']:.4f}" if isinstance(base['bertscore_f1'], float) else base['bertscore_f1']
    ft_bs = f"{ft['bertscore_f1']:.4f}" if isinstance(ft['bertscore_f1'], float) else ft['bertscore_f1']

    md_content = f"""# v2_generate 내용 품질 평가 결과

> 평가 데이터: {results['total_samples']}건 | BERTScore 모델: {args.bertscore_model}

## 내용 품질 지표

| 지표 | Base | Fine-tuned | 의미 |
|------|------|-----------|------|
| 빈 필드 정확도 | {base['empty_field_accuracy']}% | {ft['empty_field_accuracy']}% | 할루시네이션 ↓ |
| false fill율 | {base['false_fill_rate']}% | {ft['false_fill_rate']}% | 지어내기 ↓ |
| false empty율 | {base['false_empty_rate']}% | {ft['false_empty_rate']}% | 누락 ↓ |
| ROUGE-L | {base['rouge_l']:.4f} | {ft['rouge_l']:.4f} | 표면적 내용 일치 ↑ |
| BERTScore F1 | {base_bs} | {ft_bs} | 의미적 내용 유사 ↑ |
| 평균 출력 길이 | {base['avg_output_length']:.0f}자 | {ft['avg_output_length']:.0f}자 | 간결성 ↑ |

## 세부 통계

| 항목 | Base | Fine-tuned |
|------|------|-----------|
| JSON 파싱 성공 | {base['json_valid']}/{results['total_samples']} | {ft['json_valid']}/{results['total_samples']} |
| 빈 필드 수 | {base['empty_total']} | {ft['empty_total']} |
| 텍스트 필드 수 (ROUGE-L) | {base['rouge_l_field_count']} | {ft['rouge_l_field_count']} |
"""

    # 정성 예시 추가
    if results.get("qualitative_examples"):
        md_content += "\n## Before/After 정성 비교\n"
        for ex in results["qualitative_examples"]:
            md_content += f"\n### {ex['category']} (Sample #{ex['index']})\n\n"
            md_content += f"{ex['description']}\n\n"
            md_content += f"**Base 출력:**\n```json\n{ex['base_output_preview'][:500]}\n```\n\n"
            md_content += f"**Fine-tuned 출력:**\n```json\n{ex['ft_output_preview'][:500]}\n```\n\n"
            md_content += f"**정답:**\n```json\n{ex['gold_preview'][:500]}\n```\n\n"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"  마크다운 보고서: {md_path}")


if __name__ == "__main__":
    main()
