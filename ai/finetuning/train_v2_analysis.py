"""
LoRA v2: 문서 분석 (summary + category + tags) 파인튜닝

DB에 저장된 GPT 분석 결과를 학습 데이터로 사용하여
Kanana-1.5-8B 모델을 문서 분석 태스크에 파인튜닝한다.

사용법:
    # RunPod에서 실행
    python ai/finetuning/train_v2_analysis.py --mode train
    python ai/finetuning/train_v2_analysis.py --mode eval --adapter_path outputs/v2_analysis/kanana-1.5-8b-instruct-2505/final
    python ai/finetuning/train_v2_analysis.py --mode all

환경:
    pip install transformers peft trl bitsandbytes accelerate datasets torch pyyaml
    GPU: A100 40GB (RunPod)
"""

import argparse
import json
import os
import re
from pathlib import Path

os.environ["HF_HUB_TRUST_REMOTE_CODE"] = "1"
os.environ["TRUST_REMOTE_CODE"] = "True"

import torch
import yaml
from datasets import Dataset
from peft import LoraConfig, PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    EarlyStoppingCallback,
)
from trl import SFTConfig, SFTTrainer

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "configs" / "v2_analysis.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_jsonl(path: Path) -> list[dict]:
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
            parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
        return "\n".join(parts)


def load_model(config: dict, for_training: bool = True):
    model_id = config["model"]["base_model"]
    print(f"  모델: {model_id}")

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    if for_training:
        model.config.use_cache = False
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()
        else:
            model.get_input_embeddings().register_forward_hook(
                lambda module, args, output: output.requires_grad_(True)
            )

    vram_gb = torch.cuda.memory_allocated() / 1e9
    print(f"  VRAM: {vram_gb:.1f} GB")
    return tokenizer, model


def train_model(config: dict):
    model_id = config["model"]["base_model"]
    model_short = model_id.split("/")[-1]
    output_base = BASE_DIR / "outputs" / "v2_analysis"
    output_base.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"  LoRA v2_analysis 학습 시작: {model_short}")
    print(f"{'=' * 60}")

    print("\n[1/4] 모델 로드 중...")
    tokenizer, model = load_model(config, for_training=True)

    print("\n[2/4] 데이터 준비 중...")
    data_dir = Path(__file__).resolve().parent / "data"
    train_samples = load_jsonl(data_dir / config["data"]["train_path"].split("/")[-1])
    eval_samples = load_jsonl(data_dir / config["data"]["eval_path"].split("/")[-1])

    train_texts = [{"text": format_chat_sample(tokenizer, s)} for s in train_samples]
    eval_texts = [{"text": format_chat_sample(tokenizer, s)} for s in eval_samples]

    train_dataset = Dataset.from_list(train_texts)
    eval_dataset = Dataset.from_list(eval_texts)
    print(f"  Train: {len(train_dataset)}건 / Eval: {len(eval_dataset)}건")

    lora_cfg = config["lora"]
    lora_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        target_modules=lora_cfg["target_modules"],
        lora_dropout=lora_cfg["lora_dropout"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    print(f"  LoRA: r={lora_cfg['r']}, alpha={lora_cfg['lora_alpha']}")

    train_cfg = config["training"]
    output_dir = str(output_base / model_short / "checkpoints")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    use_bf16 = torch.cuda.is_bf16_supported()
    patience = train_cfg.get("early_stopping_patience", 3)

    training_args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=train_cfg["num_epochs"],
        per_device_train_batch_size=train_cfg["batch_size"],
        gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
        learning_rate=float(train_cfg["learning_rate"]),
        lr_scheduler_type="cosine",
        warmup_steps=max(1, int(len(train_dataset) / train_cfg["batch_size"] / train_cfg["gradient_accumulation_steps"] * train_cfg["warmup_ratio"])),
        logging_steps=5,
        save_strategy="epoch",
        eval_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=use_bf16,
        fp16=not use_bf16,
        gradient_checkpointing=True,
        optim="paged_adamw_8bit",
        report_to="none",
        max_length=train_cfg["max_length"],
    )

    try:
        training_args.dataset_text_field = "text"
    except Exception:
        pass

    print(f"\n[3/4] 학습 시작 (epochs={train_cfg['num_epochs']}, early_stopping={patience})...")
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        peft_config=lora_config,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=patience)],
    )

    trainer.train()

    print("\n[4/4] 어댑터 저장 중...")
    final_path = output_base / model_short / "final"
    final_path.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(final_path))
    tokenizer.save_pretrained(str(final_path))
    print(f"  저장 완료: {final_path}")

    log_path = output_base / model_short / "train_log.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(trainer.state.log_history, f, indent=2)
    print(f"  학습 로그: {log_path}")


def evaluate_model(config: dict, adapter_path: str):
    model_id = config["model"]["base_model"]
    model_short = model_id.split("/")[-1]
    output_base = BASE_DIR / "outputs" / "v2_analysis"

    print(f"\n{'=' * 60}")
    print(f"  LoRA v2_analysis 평가: {model_short}")
    print(f"  어댑터: {adapter_path}")
    print(f"{'=' * 60}")

    tokenizer, base_model = load_model(config, for_training=False)
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.eval()
    torch.cuda.empty_cache()

    data_dir = Path(__file__).resolve().parent / "data"
    eval_samples = load_jsonl(data_dir / config["data"]["eval_path"].split("/")[-1])
    print(f"  평가: {len(eval_samples)}건")

    category_match = 0
    tags_f1_sum = 0.0
    summary_sim_sum = 0.0
    json_valid = 0
    total = 0

    for i, sample in enumerate(eval_samples, 1):
        messages = sample["messages"]
        gold_text = messages[-1]["content"]
        total += 1

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

        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=3072).to(model.device)
        input_len = inputs["input_ids"].shape[1]

        with torch.no_grad():
            outputs = model.generate(
                **inputs, max_new_tokens=512, do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )

        pred_text = tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True).strip()

        # JSON 파싱
        try:
            pred_text_clean = pred_text.strip()
            if pred_text_clean.startswith("```"):
                pred_text_clean = pred_text_clean.split("\n", 1)[1] if "\n" in pred_text_clean else pred_text_clean
                if pred_text_clean.endswith("```"):
                    pred_text_clean = pred_text_clean[:-3]
                pred_text_clean = pred_text_clean.strip()
            pred_json = json.loads(pred_text_clean)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", pred_text, re.DOTALL)
            if match:
                try:
                    pred_json = json.loads(match.group(0))
                except json.JSONDecodeError:
                    print(f"  [{i}] JSON 파싱 실패")
                    continue
            else:
                print(f"  [{i}] JSON 파싱 실패")
                continue

        json_valid += 1
        gold_json = json.loads(gold_text)

        # Category
        if pred_json.get("category", "").strip() == gold_json.get("category", "").strip():
            category_match += 1

        # Tags F1
        gold_tags = set(t.lower() for t in gold_json.get("tags", []))
        pred_tags = set(t.lower() for t in pred_json.get("tags", []))
        if gold_tags and pred_tags:
            tp = len(gold_tags & pred_tags)
            p = tp / len(pred_tags)
            r = tp / len(gold_tags)
            f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
            tags_f1_sum += f1

        # Summary similarity
        gold_words = set(w for w in gold_json.get("summary", "").replace(",", " ").replace(".", " ").split() if len(w) >= 2)
        pred_words = set(w for w in pred_json.get("summary", "").replace(",", " ").replace(".", " ").split() if len(w) >= 2)
        if gold_words:
            summary_sim_sum += len(gold_words & pred_words) / len(gold_words)

        print(f"  [{i}] cat={'✅' if pred_json.get('category','').strip() == gold_json.get('category','').strip() else '❌'} f1={f1:.2f}")

    # 결과 출력
    print(f"\n{'=' * 60}")
    print(f"  평가 결과 ({json_valid}/{total} JSON 유효)")
    print(f"{'=' * 60}")
    if json_valid > 0:
        cat_acc = category_match / json_valid
        avg_f1 = tags_f1_sum / json_valid
        avg_sim = summary_sim_sum / json_valid
        print(f"  Category 일치: {cat_acc:.0%} ({category_match}/{json_valid})")
        print(f"  Tags F1 평균:  {avg_f1:.0%}")
        print(f"  Summary 유사도: {avg_sim:.0%}")

        results = {
            "category_accuracy": round(cat_acc, 4),
            "tags_f1": round(avg_f1, 4),
            "summary_similarity": round(avg_sim, 4),
            "json_valid_rate": round(json_valid / total, 4),
            "total": total,
        }
        result_path = output_base / model_short / "eval_results.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"  결과 저장: {result_path}")


def main():
    parser = argparse.ArgumentParser(description="문서 분석 LoRA 파인튜닝")
    parser.add_argument("--mode", choices=["train", "eval", "all"], default="all")
    parser.add_argument("--adapter_path", default=None)
    args = parser.parse_args()

    config = load_config()
    model_short = config["model"]["base_model"].split("/")[-1]

    if args.mode in ("train", "all"):
        train_model(config)

    if args.mode in ("eval", "all"):
        adapter_path = args.adapter_path or str(
            BASE_DIR / "outputs" / "v2_analysis" / model_short / "final"
        )
        evaluate_model(config, adapter_path)


if __name__ == "__main__":
    main()
