"""
LoRA Task Planner 파인튜닝 (v3)

베이스 모델: Kanana-1.5-8B-Instruct (v3.1 비교 평가 선정)
학습 데이터: 합성 planner 데이터 (800건)
  - 사용자 요청 → 실행 계획 JSON (intent 순서 + 의존성)
  - SFTTrainer chat format (messages 배열)
출력 형식: JSON {"plan": [{"step_id", "intent", "query", "depends_on"}]}

사용법:
    # 학습 + 평가
    python ai/finetuning/train_v3_planner.py --mode all

    # 학습만
    python ai/finetuning/train_v3_planner.py --mode train

    # 평가만 (기존 어댑터)
    python ai/finetuning/train_v3_planner.py --mode eval --adapter_path outputs/v3_planner/final

환경:
    pip install transformers peft trl bitsandbytes accelerate datasets torch pyyaml
    GPU: RunPod A100 40GB 권장
"""

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import torch
import yaml
from datasets import Dataset
from peft import LoraConfig, PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from trl import SFTTrainer, SFTConfig

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "configs" / "v3_planner.yaml"

VALID_INTENTS = {"judgment", "doc_retrieve", "doc_generate",
                 "schedule_add", "schedule_view", "general"}


def get_output_base(config: dict) -> Path:
    output_dir = config.get("output", {}).get("output_dir", "outputs/v3_planner")
    output_base = BASE_DIR / output_dir
    output_base.mkdir(parents=True, exist_ok=True)
    return output_base


# ── 설정/데이터 로드 ──

def load_config(config_path: Path = CONFIG_PATH) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_jsonl(path: str | Path) -> list[dict]:
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def format_chat_sample(tokenizer, sample: dict) -> str:
    messages = sample["messages"]
    try:
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
    except Exception:
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                parts.append(f"[시스템]\n{content}")
            elif role == "user":
                parts.append(f"[사용자]\n{content}")
            elif role == "assistant":
                parts.append(f"[어시스턴트]\n{content}")
        return "\n\n".join(parts)


def load_train_eval_datasets(
    tokenizer, config: dict
) -> tuple[Dataset, Dataset]:
    train_path = BASE_DIR / config["data"]["train_path"]
    eval_path = BASE_DIR / config["data"]["eval_path"]

    train_samples = load_jsonl(train_path)
    eval_samples = load_jsonl(eval_path)

    train_texts = [{"text": format_chat_sample(tokenizer, s)}
                   for s in train_samples]
    eval_texts = [{"text": format_chat_sample(tokenizer, s)}
                  for s in eval_samples]

    train_dataset = Dataset.from_list(train_texts)
    eval_dataset = Dataset.from_list(eval_texts)

    print(f"  Train: {len(train_dataset)}건 / Eval: {len(eval_dataset)}건")
    return train_dataset, eval_dataset


# ── 모델 로드 ──

def load_base_model(config: dict, for_training: bool = True):
    model_id = config["model"]["base_model"]
    print(f"  모델: {model_id}")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    if for_training:
        model.config.use_cache = False
        model.enable_input_require_grads()

    print(f"  VRAM - Allocated: {torch.cuda.memory_allocated()/1e9:.1f} GB")
    return tokenizer, model


# ── 학습 ──

def train(config: dict):
    output_base = get_output_base(config)

    print("\n[1/4] 모델 로드 중...")
    tokenizer, model = load_base_model(config, for_training=True)

    print("\n[2/4] 데이터 준비 중...")
    train_dataset, eval_dataset = load_train_eval_datasets(tokenizer, config)

    use_bf16 = torch.cuda.is_bf16_supported()
    print(f"  bf16 지원: {use_bf16}")

    lora_cfg = config["lora"]
    lora_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        target_modules=lora_cfg["target_modules"],
        lora_dropout=lora_cfg["lora_dropout"],
        bias="none",
        task_type="CAUSAL_LM",
    )

    train_cfg = config["training"]
    max_length = train_cfg.get("max_length", 1024)
    checkpoint_dir = str(output_base / "checkpoints")

    training_args = SFTConfig(
        dataset_text_field="text",
        max_seq_length=max_length,
        output_dir=checkpoint_dir,
        num_train_epochs=train_cfg["num_epochs"],
        per_device_train_batch_size=train_cfg["batch_size"],
        gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
        learning_rate=float(train_cfg["learning_rate"]),
        lr_scheduler_type="cosine",
        warmup_ratio=train_cfg["warmup_ratio"],
        logging_steps=10,
        save_strategy="epoch",
        eval_strategy="epoch",
        load_best_model_at_end=True,
        bf16=use_bf16,
        fp16=not use_bf16,
        gradient_checkpointing=True,
        optim="paged_adamw_8bit",
        report_to="none",
    )

    print("\n[3/4] 학습 시작...")
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        peft_config=lora_config,
    )

    trainer.train()

    print("\n[4/4] 어댑터 저장 중...")
    final_path = output_base / "final"
    trainer.model.save_pretrained(str(final_path))
    tokenizer.save_pretrained(str(final_path))
    print(f"  저장 완료: {final_path}")


# ── 평가 ──

def extract_plan_json(text: str) -> dict | None:
    """텍스트에서 plan JSON 추출"""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _lcs_length(a: list, b: list) -> int:
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return 0
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]


def evaluate_single(gold_plan: list[dict], pred_plan: list[dict]) -> dict:
    """단일 케이스 planning 평가 (v3.1 지표)"""
    gold_intents = [s["intent"] for s in gold_plan]
    pred_intents = [s.get("intent", "") for s in pred_plan]

    # Intent Recall
    ca, cb = Counter(pred_intents), Counter(gold_intents)
    matched = sum((ca & cb).values())
    recall = matched / len(gold_intents) if gold_intents else (
        1.0 if not pred_intents else 0.0)

    # Order Accuracy (LCS)
    if gold_intents:
        lcs = _lcs_length(pred_intents, gold_intents)
        order = lcs / len(gold_intents)
    else:
        order = 1.0 if not pred_intents else 0.0

    # Precision
    precision = matched / len(pred_intents) if pred_intents else (
        1.0 if not gold_intents else 0.0)

    # Dep Correctness
    min_len = min(len(pred_plan), len(gold_plan))
    max_len = max(len(pred_plan), len(gold_plan))
    dep_matches = 0
    for i in range(min_len):
        gold_deps = set(gold_plan[i].get("depends_on", []))
        pred_deps_raw = pred_plan[i].get("depends_on", [])
        pred_deps = set(pred_deps_raw) if isinstance(pred_deps_raw, list) else set()
        if gold_deps == pred_deps:
            dep_matches += 1
    dep_corr = dep_matches / max_len if max_len > 0 else 1.0

    # Efficiency
    diff = abs(len(pred_plan) - len(gold_plan))
    efficiency = max(0.0, 1.0 - diff * 0.3)

    # Weighted score
    score = (recall * 0.30 + order * 0.25 + precision * 0.20 +
             dep_corr * 0.15 + efficiency * 0.10)

    return {
        "recall": recall, "order": order, "precision": precision,
        "dep_correctness": dep_corr, "efficiency": efficiency,
        "score": score,
        "hallucinated": [i for i in pred_intents if i not in VALID_INTENTS],
    }


def evaluate(config: dict, adapter_path: str):
    """Planner LoRA 평가"""
    output_base = get_output_base(config)

    print(f"\n어댑터 로드: {adapter_path}")
    tokenizer, base_model = load_base_model(config, for_training=False)
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.eval()
    torch.cuda.empty_cache()

    eval_path = BASE_DIR / config["data"]["eval_path"]
    eval_samples = load_jsonl(eval_path)
    print(f"평가 시작: {len(eval_samples)}건\n")

    total = 0
    usable = 0
    scores = []
    metric_sums = {"recall": 0, "order": 0, "precision": 0,
                   "dep_correctness": 0, "efficiency": 0, "score": 0}

    for i, sample in enumerate(eval_samples, 1):
        messages = sample["messages"]
        gold_output = json.loads(messages[2]["content"])
        gold_plan = gold_output["plan"]
        total += 1

        # 추론
        infer_messages = [messages[0], messages[1]]
        try:
            prompt = tokenizer.apply_chat_template(
                infer_messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            prompt = (f"[시스템]\n{messages[0]['content']}\n\n"
                      f"[사용자]\n{messages[1]['content']}\n\n[어시스턴트]\n")

        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        input_len = inputs["input_ids"].shape[1]

        t0 = time.time()
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
                temperature=1.0,
                pad_token_id=tokenizer.eos_token_id,
            )
        latency = (time.time() - t0) * 1000

        pred_text = tokenizer.decode(
            outputs[0][input_len:], skip_special_tokens=True).strip()

        # JSON 파싱
        parsed = extract_plan_json(pred_text)
        if parsed is None or "plan" not in parsed:
            if i <= 5 or i % 20 == 0:
                print(f"  [{i:03d}] JSON_FAIL | latency={latency:.0f}ms")
            continue

        pred_plan = parsed["plan"]
        if not isinstance(pred_plan, list) or len(pred_plan) == 0:
            if i <= 5 or i % 20 == 0:
                print(f"  [{i:03d}] EMPTY_PLAN | latency={latency:.0f}ms")
            continue

        usable += 1
        metrics = evaluate_single(gold_plan, pred_plan)
        scores.append(metrics["score"])
        for k in metric_sums:
            metric_sums[k] += metrics[k]

        gold_intents = [s["intent"] for s in gold_plan]
        pred_intents = [s.get("intent", "") for s in pred_plan]

        if i <= 5 or i % 20 == 0:
            match = "OK" if metrics["score"] >= 0.99 else f"{metrics['score']:.3f}"
            print(f"  [{i:03d}] {match} | "
                  f"gold={gold_intents} pred={pred_intents} | "
                  f"{latency:.0f}ms")

    # 결과 출력
    print("\n" + "=" * 60)
    print("  Planner LoRA 평가 결과 (v3.1 지표)")
    print("=" * 60)
    print(f"  총 평가:        {total}건")
    print(f"  유효 응답:      {usable}/{total} "
          f"({usable/total*100:.1f}%)" if total else "")

    if usable > 0:
        for k in metric_sums:
            metric_sums[k] /= usable
        print(f"\n  [Planning 능력] — 유효 {usable}건 기준")
        print(f"    Intent Recall:     {metric_sums['recall']:.3f}")
        print(f"    Order Accuracy:    {metric_sums['order']:.3f}")
        print(f"    Intent Precision:  {metric_sums['precision']:.3f}")
        print(f"    Dep Correctness:   {metric_sums['dep_correctness']:.3f}")
        print(f"    Efficiency:        {metric_sums['efficiency']:.3f}")
        print(f"    ─────────────────────")
        print(f"    Weighted Score:    {metric_sums['score']:.3f}")
        perfect = sum(1 for s in scores if s >= 0.99)
        print(f"\n    Perfect Score:     {perfect}/{usable} "
              f"({perfect/usable*100:.1f}%)")

    print("=" * 60)

    # 결과 저장
    eval_result = {
        "total": total,
        "usable": usable,
        "usable_rate": round(usable / total, 4) if total else 0,
        "metrics": {k: round(v, 4) for k, v in metric_sums.items()},
        "perfect_rate": round(
            sum(1 for s in scores if s >= 0.99) / usable, 4) if usable else 0,
    }
    result_path = output_base / "eval_results.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(eval_result, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {result_path}")


# ── 엔트리포인트 ──

def main():
    parser = argparse.ArgumentParser(
        description="Kanana-1.5-8B Planner QLoRA 파인튜닝")
    parser.add_argument("--mode", choices=["train", "eval", "all"],
                        default="all")
    parser.add_argument("--config", default=str(CONFIG_PATH),
                        help="YAML 설정 파일 경로")
    parser.add_argument("--adapter_path", default=None,
                        help="eval 시 어댑터 경로 (미지정 시 output_dir/final)")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    output_base = get_output_base(config)

    if args.adapter_path is None:
        args.adapter_path = str(output_base / "final")

    print(f"설정 로드: {args.config}")
    print(f"  base_model: {config['model']['base_model']}")
    print(f"  LoRA r={config['lora']['r']}, alpha={config['lora']['lora_alpha']}")
    print(f"  epochs={config['training']['num_epochs']}, "
          f"batch={config['training']['batch_size']}, "
          f"lr={config['training']['learning_rate']}")
    print(f"  output: {output_base}")

    if args.mode in ("train", "all"):
        train(config)
    if args.mode in ("eval", "all"):
        evaluate(config, args.adapter_path)


if __name__ == "__main__":
    main()
