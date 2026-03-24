"""
베이스라인 평가: 파인튜닝 전 베이스 모델 성능 측정

베이스 모델(kanana-1.5-8b-instruct)을 LoRA 어댑터 없이 로드하여
동일한 eval.jsonl(328건)로 평가합니다.

사용법 (로컬 CPU):
    python ai/finetuning/eval_baseline.py

사용법 (GPU 있을 때):
    python ai/finetuning/eval_baseline.py --device cuda

옵션:
    --limit N      처음 N건만 평가 (테스트용)
    --device       cpu 또는 cuda (기본: auto)

환경:
    pip install transformers torch datasets pyyaml
"""

import argparse
import json
import re
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_DIR = Path(__file__).resolve().parent.parent.parent
EVAL_PATH = BASE_DIR / "data" / "training" / "v1_judgment" / "eval.jsonl"
OUTPUT_PATH = BASE_DIR / "outputs" / "v1_judgment" / "eval_baseline_results.json"
MODEL_ID = "kakaocorp/kanana-1.5-8b-instruct-2505"

VALID_RESULTS = {"yes", "no", "conditional", "no_regulation"}


def parse_judgment_json(text: str) -> dict | None:
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


def load_jsonl(path: Path) -> list[dict]:
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def main():
    parser = argparse.ArgumentParser(description="베이스라인 평가 (파인튜닝 전)")
    parser.add_argument("--limit", type=int, default=0, help="평가 건수 제한 (0=전체)")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    args = parser.parse_args()

    # 디바이스 결정
    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device

    print(f"디바이스: {device}")
    print(f"모델: {MODEL_ID}")

    # 모델 로드 (CPU: float16, GPU: 4bit)
    print("\n[1/3] 모델 로드 중...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if device == "cuda":
        from transformers import BitsAndBytesConfig
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float16,
            device_map={"": "cpu"},
            trust_remote_code=True,
        )

    model.eval()
    print("  모델 로드 완료")

    # 데이터 로드
    print("\n[2/3] 평가 데이터 로드 중...")
    eval_samples = load_jsonl(EVAL_PATH)
    if args.limit > 0:
        eval_samples = eval_samples[:args.limit]
    print(f"  평가 건수: {len(eval_samples)}건")

    # 평가
    print("\n[3/3] 베이스라인 평가 시작...")
    total = 0
    json_valid = 0
    result_correct = 0
    category_stats: dict[str, dict[str, int]] = {}
    start_time = time.time()

    for i, sample in enumerate(eval_samples, 1):
        messages = sample["messages"]
        gold_parsed = parse_judgment_json(messages[2]["content"])
        if not gold_parsed:
            continue
        gold_result = gold_parsed.get("result", "")
        total += 1

        if gold_result not in category_stats:
            category_stats[gold_result] = {"correct": 0, "total": 0}
        category_stats[gold_result]["total"] += 1

        # system + user만 전달
        infer_messages = [messages[0], messages[1]]
        try:
            prompt = tokenizer.apply_chat_template(
                infer_messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            prompt = (
                f"[시스템]\n{messages[0]['content']}\n\n"
                f"[사용자]\n{messages[1]['content']}\n\n"
                f"[어시스턴트]\n"
            )

        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        input_len = inputs["input_ids"].shape[1]

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,
                temperature=1.0,
                pad_token_id=tokenizer.eos_token_id,
            )

        pred_text = tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True).strip()
        pred_parsed = parse_judgment_json(pred_text)

        if pred_parsed is not None:
            json_valid += 1
            pred_result = pred_parsed.get("result", "")
            if pred_result == gold_result:
                result_correct += 1
                category_stats[gold_result]["correct"] += 1
            status = "OK" if pred_result == gold_result else "MISS"
        else:
            pred_result = "JSON_FAIL"
            status = "JSON_FAIL"

        elapsed = time.time() - start_time
        avg_per_sample = elapsed / i
        remaining = avg_per_sample * (len(eval_samples) - i)

        print(
            f"  [{i:03d}/{len(eval_samples)}] "
            f"gold={gold_result:<15} pred={pred_result:<15} {status} "
            f"({avg_per_sample:.1f}s/건, 남은시간: {remaining/60:.0f}분)"
        )

    # 결과
    elapsed_total = time.time() - start_time
    print("\n" + "=" * 60)
    print("  베이스라인 평가 결과 (파인튜닝 전)")
    print("=" * 60)
    print(f"  모델:           {MODEL_ID}")
    print(f"  디바이스:       {device}")
    print(f"  총 평가 건수:   {total}")
    print(f"  소요 시간:      {elapsed_total/60:.1f}분")
    if total:
        print(f"  JSON 유효율:    {json_valid}/{total} ({json_valid/total*100:.1f}%)")
        print(f"  판단 정확도:    {result_correct}/{total} ({result_correct/total*100:.1f}%)")
    print()
    print(f"  {'카테고리':<15} {'정확도':>10} {'건수':>8}")
    print("  " + "-" * 35)
    for cat in sorted(category_stats.keys()):
        stats = category_stats[cat]
        acc = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {cat:<15} {acc:>9.1f}% {stats['total']:>7}건")
    print("=" * 60)

    # 결과 저장
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    eval_result = {
        "type": "baseline",
        "model": MODEL_ID,
        "device": device,
        "total": total,
        "json_valid": json_valid,
        "json_valid_rate": round(json_valid / total, 4) if total else 0,
        "result_accuracy": round(result_correct / total, 4) if total else 0,
        "category_stats": category_stats,
        "elapsed_minutes": round(elapsed_total / 60, 1),
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(eval_result, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
