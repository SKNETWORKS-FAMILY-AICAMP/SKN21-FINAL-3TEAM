"""
QA 파인튜닝 스크립트: A.X-3.1-Light + QLoRA

베이스라인 실험에서 발견된 약점(복수 엔티티 혼동, 열거 조기 종료, 세부 정보 누락)을
보강하기 위한 합성 데이터(ft_train_data.json) 기반 LoRA 학습.

사용법:
    # 학습
    python ai/finetuning/train_qa_lora.py --mode train

    # 평가 (베이스라인 qa_samples.json 40건 기준)
    python ai/finetuning/train_qa_lora.py --mode eval --adapter_path ai/finetuning/output/final

    # 학습 + 평가 한 번에
    python ai/finetuning/train_qa_lora.py --mode all

환경:
    pip install transformers peft trl bitsandbytes accelerate rouge-score datasets torch
    GPU: Colab L4 (24GB) 이상 권장
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, PeftModel
from rouge_score import rouge_scorer
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from trl import SFTTrainer, SFTConfig

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TRAIN_DATA_PATH = BASE_DIR / "ai" / "data" / "ft_train_data.json"
TEST_DATA_PATH = BASE_DIR / "ai" / "data" / "qa_samples.json"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

MODEL_ID = "skt/A.X-3.1-Light"
MAX_SEQ_LENGTH = 1024


# ── 데이터 포맷 ──

def format_sample(tokenizer, sample: dict) -> str:
    """QA 샘플을 chat template 형식으로 변환 (학습용: 정답 포함)"""
    user_msg = (
        f"다음 글을 읽고 질문에 간결하게 답하세요.\n\n"
        f"[글]\n{sample['context']}\n\n"
        f"[질문]\n{sample['question']}"
    )
    messages = [
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": sample["answer"]},
    ]
    try:
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
    except Exception:
        return f"[지문]\n{sample['context']}\n\n[질문]\n{sample['question']}\n\n[답변]\n{sample['answer']}"


def load_train_dataset(tokenizer) -> tuple[Dataset, Dataset]:
    """ft_train_data.json 로드 후 train(90%) / val(10%) 분할"""
    with open(TRAIN_DATA_PATH, encoding="utf-8") as f:
        samples = json.load(f)

    texts = [{"text": format_sample(tokenizer, s)} for s in samples]
    dataset = Dataset.from_list(texts)
    split = dataset.train_test_split(test_size=0.1, seed=42)

    print(f"  Train: {len(split['train'])}건 / Val: {len(split['test'])}건")
    return split["train"], split["test"]


# ── 모델 로드 ──

def load_base_model(for_training: bool = True):
    """QLoRA 4-bit 로드"""
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
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

def train():
    print("\n[1/4] 모델 로드 중...")
    tokenizer, model = load_base_model(for_training=True)

    print("\n[2/4] 데이터 준비 중...")
    train_dataset, eval_dataset = load_train_dataset(tokenizer)

    use_bf16 = torch.cuda.is_bf16_supported()
    print(f"  bf16 지원: {use_bf16}")

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    sft_config = SFTConfig(
        output_dir=str(OUTPUT_DIR / "checkpoints"),
        num_train_epochs=3,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,      # effective batch size = 16
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_steps=20,
        logging_steps=10,
        save_strategy="epoch",
        eval_strategy="epoch",
        load_best_model_at_end=True,
        bf16=use_bf16,
        fp16=not use_bf16,
        gradient_checkpointing=True,
        optim="paged_adamw_8bit",
        report_to="none",
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_text_field="text",
    )

    print("\n[3/4] 학습 시작...")
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        peft_config=lora_config,
    )

    trainer.train()

    print("\n[4/4] 어댑터 저장 중...")
    final_path = OUTPUT_DIR / "final"
    trainer.model.save_pretrained(str(final_path))
    tokenizer.save_pretrained(str(final_path))
    print(f"  저장 완료: {final_path}")


# ── 평가 ──

def normalize_answer(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s가-힣]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def token_f1(pred: str, gold: str) -> float:
    pred_tokens = normalize_answer(pred).split()
    gold_tokens = normalize_answer(gold).split()
    if not pred_tokens or not gold_tokens:
        return 0.0
    common = sum((Counter(pred_tokens) & Counter(gold_tokens)).values())
    if common == 0:
        return 0.0
    p = common / len(pred_tokens)
    r = common / len(gold_tokens)
    return 2 * p * r / (p + r)


def evaluate(adapter_path: str):
    print(f"\n어댑터 로드: {adapter_path}")

    tokenizer, base_model = load_base_model(for_training=False)
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.eval()
    torch.cuda.empty_cache()

    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)

    with open(TEST_DATA_PATH, encoding="utf-8") as f:
        samples = json.load(f)

    results = []
    print(f"평가 시작: {len(samples)}건")

    for i, sample in enumerate(samples, 1):
        user_msg = (
            f"다음 글을 읽고 질문에 간결하게 답하세요.\n\n"
            f"[글]\n{sample['context']}\n\n"
            f"[질문]\n{sample['question']}"
        )
        messages = [{"role": "user", "content": user_msg}]
        try:
            prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            prompt = f"[지문]\n{sample['context']}\n\n[질문]\n{sample['question']}\n\n[답변]\n"

        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        input_len = inputs["input_ids"].shape[1]

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=128,
                do_sample=False,
                temperature=1.0,
                pad_token_id=tokenizer.eos_token_id,
            )

        pred = tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True).strip()
        tf1 = token_f1(pred, sample["answer"])
        rl = scorer.score(sample["answer"], pred)["rougeL"].fmeasure

        results.append({
            "id": sample["id"],
            "domain": sample["domain"],
            "type": sample.get("type", ""),
            "question": sample["question"],
            "gold_answer": sample["answer"],
            "pred_answer": pred,
            "token_f1": round(tf1, 4),
            "rouge_l": round(rl, 4),
        })
        print(f"  [{i:02d}/{len(samples)}] {sample['id']} TF1={tf1:.3f} RL={rl:.3f} | '{pred[:40]}'")

    # 집계
    def avg(lst, key):
        return round(sum(r[key] for r in lst) / len(lst), 4) if lst else 0.0

    general = [r for r in results if r["domain"] == "general"]
    business = [r for r in results if r["domain"] == "business"]

    print("\n" + "=" * 60)
    print("  파인튜닝 후 평가 결과 vs 베이스라인 A.X-3.1-Light")
    print("=" * 60)
    print(f"  {'지표':<20} {'파인튜닝 후':>12} {'베이스라인':>12}")
    print("  " + "-" * 46)
    print(f"  {'전체 Token F1':<20} {avg(results, 'token_f1'):>12.4f} {'0.7516':>12}")
    print(f"  {'전체 ROUGE-L':<20} {avg(results, 'rouge_l'):>12.4f} {'0.6625':>12}")
    print(f"  {'일반 Token F1':<20} {avg(general, 'token_f1'):>12.4f} {'0.8663':>12}")
    print(f"  {'업무 Token F1':<20} {avg(business, 'token_f1'):>12.4f} {'0.6369':>12}")
    print("=" * 60)

    # 저장
    eval_path = OUTPUT_DIR / "ft_eval_results.json"
    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {eval_path}")


# ── 엔트리포인트 ──

def main():
    parser = argparse.ArgumentParser(description="A.X-3.1-Light QLoRA 파인튜닝")
    parser.add_argument("--mode", choices=["train", "eval", "all"], default="all")
    parser.add_argument(
        "--adapter_path",
        default=str(OUTPUT_DIR / "final"),
        help="eval 모드 시 어댑터 경로",
    )
    args = parser.parse_args()

    if args.mode in ("train", "all"):
        train()
    if args.mode in ("eval", "all"):
        evaluate(args.adapter_path)


if __name__ == "__main__":
    main()
