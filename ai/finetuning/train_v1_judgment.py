"""
LoRA v1: RAG 판단 특화 파인튜닝

베이스 모델: Kanana-1.5-8B-Instruct (벤치마크 #7 선정)
학습 데이터: ~1,500건 (judgment 1,000 + QA 500)
  - 규정 기반 Yes/No/조건부 판단
  - SFTTrainer chat format (messages 배열)
출력 형식: JSON (result, confidence, reasoning, regulations, ...)

사용법:
    # 학습
    python ai/finetuning/train_v1_judgment.py --mode train

    # 평가
    python ai/finetuning/train_v1_judgment.py --mode eval --adapter_path outputs/v1_judgment/final

    # 학습 + 평가
    python ai/finetuning/train_v1_judgment.py --mode all

환경:
    pip install transformers peft trl bitsandbytes accelerate datasets torch pyyaml
    GPU: RunPod A100 40GB 권장
"""

import argparse
import json
import re
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
    TrainingArguments,
)
from trl import SFTTrainer, SFTConfig

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "configs" / "v1_judgment.yaml"
OUTPUT_BASE = BASE_DIR / "outputs" / "v1_judgment"
OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

VALID_RESULTS = {"yes", "no", "conditional", "no_regulation"}


# ── 설정 로드 ──


def load_config(config_path: Path = CONFIG_PATH) -> dict:
    """YAML 설정 파일 로드"""
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── 데이터 로드 ──


def load_jsonl(path: str | Path) -> list[dict]:
    """JSONL 파일 로드"""
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def format_chat_sample(tokenizer, sample: dict) -> str:
    """messages 배열 → chat template 텍스트 변환"""
    messages = sample["messages"]
    try:
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
    except Exception:
        # fallback: 수동 포맷
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
    """train/eval JSONL → Dataset 변환"""
    train_path = BASE_DIR / config["data"]["train_path"]
    eval_path = BASE_DIR / config["data"]["eval_path"]

    train_samples = load_jsonl(train_path)
    eval_samples = load_jsonl(eval_path)

    train_texts = [{"text": format_chat_sample(tokenizer, s)} for s in train_samples]
    eval_texts = [{"text": format_chat_sample(tokenizer, s)} for s in eval_samples]

    train_dataset = Dataset.from_list(train_texts)
    eval_dataset = Dataset.from_list(eval_texts)

    print(f"  Train: {len(train_dataset)}건 / Eval: {len(eval_dataset)}건")
    return train_dataset, eval_dataset


# ── 모델 로드 ──


def load_base_model(config: dict, for_training: bool = True):
    """QLoRA 4-bit 모델 로드"""
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
    output_dir = str(OUTPUT_BASE / "checkpoints")
    training_args = SFTConfig(dataset_text_field="text", max_length=2048,
        output_dir=output_dir,
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
    final_path = OUTPUT_BASE / "final"
    trainer.model.save_pretrained(str(final_path))
    tokenizer.save_pretrained(str(final_path))
    print(f"  저장 완료: {final_path}")


# ── 평가 ──


def parse_judgment_json(text: str) -> dict | None:
    """텍스트에서 judgment JSON 추출"""
    text = text.strip()
    # ```json ... ``` 블록
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    # 첫 { ... } 블록
    if not text.startswith("{"):
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def evaluate(config: dict, adapter_path: str):
    """판단 전용 평가 메트릭: 판단 정확도, JSON 유효율, 카테고리별 정확도"""
    print(f"\n어댑터 로드: {adapter_path}")

    tokenizer, base_model = load_base_model(config, for_training=False)
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.eval()
    torch.cuda.empty_cache()

    eval_path = BASE_DIR / config["data"]["eval_path"]
    eval_samples = load_jsonl(eval_path)
    print(f"평가 시작: {len(eval_samples)}건")

    total = 0
    json_valid = 0
    result_correct = 0
    category_stats: dict[str, dict[str, int]] = {}  # {gold_result: {correct, total}}

    for i, sample in enumerate(eval_samples, 1):
        messages = sample["messages"]
        # gold 라벨 추출
        gold_parsed = parse_judgment_json(messages[2]["content"])
        if not gold_parsed:
            continue
        gold_result = gold_parsed.get("result", "")
        total += 1

        # 카테고리 통계 초기화
        if gold_result not in category_stats:
            category_stats[gold_result] = {"correct": 0, "total": 0}
        category_stats[gold_result]["total"] += 1

        # 추론 (system + user만 전달)
        infer_messages = [messages[0], messages[1]]
        try:
            prompt = tokenizer.apply_chat_template(
                infer_messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            prompt = f"[시스템]\n{messages[0]['content']}\n\n[사용자]\n{messages[1]['content']}\n\n[어시스턴트]\n"

        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
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

        # JSON 유효성
        if pred_parsed is not None:
            json_valid += 1
            pred_result = pred_parsed.get("result", "")

            # 판단 정확도
            if pred_result == gold_result:
                result_correct += 1
                category_stats[gold_result]["correct"] += 1

            if i <= 5 or i % 30 == 0:
                print(
                    f"  [{i:03d}/{len(eval_samples)}] "
                    f"gold={gold_result} pred={pred_result} "
                    f"{'OK' if pred_result == gold_result else 'MISS'}"
                )
        else:
            if i <= 5 or i % 30 == 0:
                print(f"  [{i:03d}/{len(eval_samples)}] gold={gold_result} pred=JSON_FAIL")

    # 결과 출력
    print("\n" + "=" * 60)
    print("  Judgment LoRA v1 평가 결과")
    print("=" * 60)
    print(f"  총 평가 건수:   {total}")
    print(f"  JSON 유효율:    {json_valid}/{total} ({json_valid/total*100:.1f}%)" if total else "")
    print(f"  판단 정확도:    {result_correct}/{total} ({result_correct/total*100:.1f}%)" if total else "")
    print()
    print(f"  {'카테고리':<15} {'정확도':>10} {'건수':>8}")
    print("  " + "-" * 35)
    for cat in sorted(category_stats.keys()):
        stats = category_stats[cat]
        acc = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {cat:<15} {acc:>9.1f}% {stats['total']:>7}건")
    print("=" * 60)

    # 결과 저장
    eval_result = {
        "total": total,
        "json_valid": json_valid,
        "json_valid_rate": round(json_valid / total, 4) if total else 0,
        "result_accuracy": round(result_correct / total, 4) if total else 0,
        "category_stats": category_stats,
    }
    result_path = OUTPUT_BASE / "eval_results.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(eval_result, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {result_path}")


# ── 엔트리포인트 ──


def main():
    parser = argparse.ArgumentParser(description="Kanana-1.5-8B Judgment QLoRA 파인튜닝")
    parser.add_argument("--mode", choices=["train", "eval", "all"], default="all")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="YAML 설정 파일 경로")
    parser.add_argument(
        "--adapter_path",
        default=str(OUTPUT_BASE / "final"),
        help="eval 모드 시 어댑터 경로",
    )
    args = parser.parse_args()

    config = load_config(Path(args.config))
    print(f"설정 로드: {args.config}")
    print(f"  base_model: {config['model']['base_model']}")
    print(f"  LoRA r={config['lora']['r']}, alpha={config['lora']['lora_alpha']}")
    print(f"  epochs={config['training']['num_epochs']}, "
          f"batch={config['training']['batch_size']}, "
          f"lr={config['training']['learning_rate']}")

    if args.mode in ("train", "all"):
        train(config)
    if args.mode in ("eval", "all"):
        evaluate(config, args.adapter_path)


if __name__ == "__main__":
    main()
