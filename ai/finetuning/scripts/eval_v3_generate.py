"""
v3_generate 평가 전용 스크립트

평가 항목:
  [구조] JSON 유효율, 필드 완전성, 필드 정확도
  [내용] ROUGE-L, BERTScore F1, 평균 출력 길이
  [할루시네이션] 빈 필드 정확도, False Fill률
  [핵심 필드] decisions, action_items, tasks, issues, next_plan, schedule, budget 채움률
  [정성] 샘플 5건 출력

사용법:
  # Fine-tuned 평가
  python ai/finetuning/scripts/eval_v3_generate.py --adapter outputs/v3_generate/.../checkpoint-170

  # Base 평가
  python ai/finetuning/scripts/eval_v3_generate.py --base

  # 둘 다
  python ai/finetuning/scripts/eval_v3_generate.py --adapter outputs/v3_generate/.../checkpoint-170 --base
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

os.environ["HF_HUB_TRUST_REMOTE_CODE"] = "1"
os.environ["TRUST_REMOTE_CODE"] = "True"

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
MODEL_ID = "kakaocorp/kanana-1.5-8b-instruct-2505"
EVAL_PATH = BASE_DIR / "data" / "training" / "v2_generate" / "eval.jsonl"
OUTPUT_DIR = BASE_DIR / "outputs" / "v3_generate"

KEY_FIELDS = {
    "meeting_minutes": ["decisions", "action_items"],
    "report": ["tasks", "issues", "next_plan"],
    "proposal": ["schedule", "budget", "background", "current_situation"],
}


def load_eval_data():
    samples = []
    with open(EVAL_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    return samples


def detect_doc_type(user_msg):
    if "회의록" in user_msg:
        return "meeting_minutes"
    elif "보고서" in user_msg or "업무보고" in user_msg:
        return "report"
    elif "제안서" in user_msg:
        return "proposal"
    return "unknown"


def parse_field_spec(user_content):
    fields = []
    in_spec = False
    for line in user_content.splitlines():
        stripped = line.strip()
        if "[필드 명세]" in stripped:
            in_spec = True
            continue
        if in_spec:
            if stripped.startswith("[") and "필드" not in stripped:
                break
            if stripped.startswith("- ") and ":" in stripped:
                field_name = stripped[2:].split(":")[0].strip()
                if field_name:
                    fields.append(field_name)
    return fields


def parse_json(text):
    text = text.strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    if not text.startswith("{"):
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def load_model(adapter_path=None):
    print(f"  모델 로드: {MODEL_ID}")
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, quantization_config=bnb, device_map="auto", trust_remote_code=True
    )
    if adapter_path:
        print(f"  어댑터 로드: {adapter_path}")
        model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer, model


def run_inference(tokenizer, model, sample):
    messages = sample["messages"]
    infer_msgs = [m for m in messages if m["role"] != "assistant"]
    try:
        prompt = tokenizer.apply_chat_template(infer_msgs, tokenize=False, add_generation_prompt=True)
    except Exception:
        prompt = "\n".join(
            f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>" for m in infer_msgs
        ) + "\n<|im_start|>assistant\n"

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2560).to(model.device)
    input_len = inputs["input_ids"].shape[1]

    with torch.no_grad():
        outputs = model.generate(
            **inputs, max_new_tokens=1024, do_sample=False, pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True).strip()


def evaluate(tokenizer, model, samples, label):
    print(f"\n{'='*60}")
    print(f"  평가 시작 [{label}] — {len(samples)}건")
    print(f"{'='*60}")

    from rouge_score import rouge_scorer
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)

    stats = {
        "total": 0, "json_valid": 0, "field_complete": 0, "field_accurate": 0,
        "rouge_l_sum": 0.0, "output_len_sum": 0,
        "empty_field_total": 0, "empty_field_correct": 0, "false_fill": 0,
    }
    key_field_stats = {}  # field_name -> {total, filled}
    bertscore_preds = []
    bertscore_refs = []
    qual_samples = []

    start_time = time.time()

    for i, sample in enumerate(samples, 1):
        gold_text = sample["messages"][-1]["content"]
        user_content = sample["messages"][1]["content"]
        doc_type = detect_doc_type(user_content)
        expected_fields = parse_field_spec(user_content)

        # 추론
        pred_text = run_inference(tokenizer, model, sample)
        stats["total"] += 1
        stats["output_len_sum"] += len(pred_text)

        # JSON 파싱
        pred_json = parse_json(pred_text)
        gold_json = parse_json(gold_text)

        if pred_json is None:
            print(f"  [{i:03d}/{len(samples)}] JSON 파싱 실패")
            continue

        stats["json_valid"] += 1
        present_fields = set(pred_json.keys())

        # 필드 완전성 + 정확도
        if expected_fields:
            if all(f in present_fields for f in expected_fields):
                stats["field_complete"] += 1
            expected_set = set(expected_fields)
            if expected_set.issubset(present_fields):
                stats["field_accurate"] += 1

        # ROUGE-L
        rouge_result = scorer.score(gold_text, pred_text)
        rouge_l = rouge_result["rougeL"].fmeasure
        stats["rouge_l_sum"] += rouge_l

        # BERTScore 저장
        bertscore_preds.append(pred_text[:2000])
        bertscore_refs.append(gold_text[:2000])

        # 빈 필드 정확도
        if gold_json and expected_fields:
            for field in expected_fields:
                gold_val = gold_json.get(field)
                pred_val = pred_json.get(field)
                gold_empty = (gold_val is None or gold_val == "" or gold_val == [] or gold_val == {})
                pred_empty = (pred_val is None or pred_val == "" or pred_val == [] or pred_val == {})
                if gold_empty:
                    stats["empty_field_total"] += 1
                    if pred_empty:
                        stats["empty_field_correct"] += 1
                    else:
                        stats["false_fill"] += 1

        # 핵심 필드 채움률
        for key in KEY_FIELDS.get(doc_type, []):
            if not expected_fields or key in expected_fields:
                if key not in key_field_stats:
                    key_field_stats[key] = {"total": 0, "filled": 0}
                key_field_stats[key]["total"] += 1
                pred_val = pred_json.get(key)
                if pred_val and pred_val != [] and pred_val != "" and pred_val != {}:
                    key_field_stats[key]["filled"] += 1

        # 정성 평가 저장
        qual_samples.append({
            "doc_type": doc_type,
            "gold": gold_text[:500],
            "pred": pred_text[:500],
            "rouge_l": round(rouge_l, 4),
        })

        if i % 5 == 0 or i <= 3:
            elapsed = time.time() - start_time
            eta = elapsed / i * (len(samples) - i)
            print(f"  [{i:03d}/{len(samples)}] ROUGE-L={rouge_l:.3f} | ETA {eta:.0f}s")

    elapsed = time.time() - start_time

    # BERTScore 일괄 계산
    bertscore_f1 = 0.0
    if bertscore_preds:
        try:
            from bert_score import score as bert_score_fn
            print(f"\n  BERTScore 계산 중 ({len(bertscore_preds)}건)...")
            P, R, F1 = bert_score_fn(
                bertscore_preds, bertscore_refs,
                model_type="klue/roberta-large", num_layers=24,
                lang="ko", verbose=False, device="cuda",
            )
            bertscore_f1 = F1.mean().item()
        except Exception as e:
            print(f"  BERTScore 실패: {e}")

    # 결과 출력
    total = stats["total"]
    json_rate = stats["json_valid"] / total if total else 0
    field_comp = stats["field_complete"] / total if total else 0
    field_acc = stats["field_accurate"] / max(stats["json_valid"], 1)
    avg_rouge = stats["rouge_l_sum"] / total if total else 0
    avg_len = stats["output_len_sum"] / total if total else 0
    empty_total = stats["empty_field_total"]
    empty_acc = stats["empty_field_correct"] / empty_total if empty_total else 0
    false_fill_rate = stats["false_fill"] / empty_total if empty_total else 0

    print(f"\n{'='*60}")
    print(f"  평가 결과 [{label}] — {total}건 ({elapsed:.0f}초)")
    print(f"{'='*60}")

    print(f"\n  [구조 지표]")
    print(f"    JSON 유효율:     {stats['json_valid']}/{total} ({json_rate*100:.1f}%)")
    print(f"    필드 완전성:     {stats['field_complete']}/{total} ({field_comp*100:.1f}%)")
    print(f"    필드명 정확도:   {stats['field_accurate']}/{stats['json_valid']} ({field_acc*100:.1f}%)")

    print(f"\n  [내용 품질]")
    print(f"    ROUGE-L:         {avg_rouge:.4f}")
    print(f"    BERTScore F1:    {bertscore_f1:.4f}")
    print(f"    평균 출력 길이:  {avg_len:.0f}자")

    print(f"\n  [할루시네이션]")
    print(f"    빈 필드 정확도:  {stats['empty_field_correct']}/{empty_total} ({empty_acc*100:.1f}%)")
    print(f"    False Fill:      {stats['false_fill']}/{empty_total} ({false_fill_rate*100:.1f}%)")

    print(f"\n  [핵심 필드 채움률]")
    kf_results = {}
    for key in ["decisions", "action_items", "tasks", "issues", "next_plan",
                 "schedule", "budget", "background", "current_situation"]:
        if key in key_field_stats:
            ks = key_field_stats[key]
            rate = ks["filled"] / ks["total"] if ks["total"] else 0
            print(f"    {key:25s}: {ks['filled']}/{ks['total']} ({rate*100:.1f}%)")
            kf_results[key] = round(rate, 4)

    # 정성 평가 샘플
    if qual_samples:
        print(f"\n  [정성 평가 — 5건]")
        indices = [0, len(qual_samples)//4, len(qual_samples)//2, len(qual_samples)*3//4, len(qual_samples)-1]
        for idx in sorted(set(indices)):
            if idx < len(qual_samples):
                p = qual_samples[idx]
                print(f"\n    --- [{idx}] {p['doc_type']} | ROUGE-L: {p['rouge_l']:.3f} ---")
                print(f"    Gold: {p['gold'][:150]}")
                print(f"    Pred: {p['pred'][:150]}")

    # 결과 저장
    result = {
        "label": label, "total": total, "elapsed_sec": round(elapsed),
        "json_valid_rate": round(json_rate, 4),
        "field_completeness": round(field_comp, 4),
        "field_accuracy": round(field_acc, 4),
        "rouge_l": round(avg_rouge, 4),
        "bertscore_f1": round(bertscore_f1, 4),
        "avg_output_length": round(avg_len),
        "empty_field_accuracy": round(empty_acc, 4),
        "false_fill_rate": round(false_fill_rate, 4),
        "key_field_fill_rates": kf_results,
    }

    save_dir = OUTPUT_DIR / "eval_results"
    save_dir.mkdir(parents=True, exist_ok=True)
    fname = f"eval_{label.lower().replace(' ', '_')}.json"
    with open(save_dir / fname, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {save_dir / fname}")

    if qual_samples:
        qfname = f"qualitative_{label.lower().replace(' ', '_')}.json"
        with open(save_dir / qfname, "w", encoding="utf-8") as f:
            json.dump(qual_samples, f, ensure_ascii=False, indent=2)
        print(f"  정성 평가 저장: {save_dir / qfname}")

    return result


def main():
    parser = argparse.ArgumentParser(description="v3_generate 평가")
    parser.add_argument("--adapter", type=str, help="Fine-tuned 어댑터 경로")
    parser.add_argument("--base", action="store_true", help="Base 모델 평가")
    args = parser.parse_args()

    if not args.adapter and not args.base:
        print("--adapter 또는 --base 중 하나 이상 지정하세요")
        sys.exit(1)

    samples = load_eval_data()
    print(f"평가 데이터: {len(samples)}건")

    results = {}

    if args.adapter:
        tokenizer, model = load_model(adapter_path=args.adapter)
        results["finetuned"] = evaluate(tokenizer, model, samples, "Fine-tuned")
        del model
        torch.cuda.empty_cache()

    if args.base:
        tokenizer, model = load_model(adapter_path=None)
        results["base"] = evaluate(tokenizer, model, samples, "Base")
        del model
        torch.cuda.empty_cache()

    # 비교 출력
    if "finetuned" in results and "base" in results:
        ft = results["finetuned"]
        bs = results["base"]
        print(f"\n{'='*60}")
        print(f"  Base vs Fine-tuned 비교")
        print(f"{'='*60}")
        for key in ["json_valid_rate", "field_completeness", "rouge_l", "bertscore_f1",
                     "empty_field_accuracy", "false_fill_rate"]:
            bv = bs.get(key, 0)
            fv = ft.get(key, 0)
            diff = fv - bv
            print(f"    {key:25s}: Base={bv:.4f}  FT={fv:.4f}  diff={diff:+.4f}")

        print(f"\n  핵심 필드 채움률 비교:")
        for key in ["decisions", "action_items", "tasks", "issues", "next_plan",
                     "schedule", "budget", "background", "current_situation"]:
            bv = bs.get("key_field_fill_rates", {}).get(key, 0)
            fv = ft.get("key_field_fill_rates", {}).get(key, 0)
            if bv or fv:
                diff = fv - bv
                print(f"    {key:25s}: Base={bv:.2%}  FT={fv:.2%}  diff={diff:+.2%}")

    print(f"\n완료!")


if __name__ == "__main__":
    main()
