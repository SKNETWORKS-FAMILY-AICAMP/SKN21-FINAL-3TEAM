"""
실험 5 최종 모델 배포용 — BERT best config 1회 학습

RunPod에서 실행:
    cd /workspace/SKN21-FINAL-3TEAM
    python ai/experiments/train_best_bert.py
"""

import json
import random
import torch
import numpy as np
from pathlib import Path
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
from sklearn.metrics import accuracy_score, f1_score

# ── 설정 ──
SEED = 42
MODEL_NAME = "klue/bert-base"
EPOCHS = 5
LR = 2e-5
BATCH_SIZE = 16
WARMUP_RATIO = 0.0
MAX_LENGTH = 64
WEIGHT_DECAY = 0.01

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "intent"
SAVE_DIR = BASE_DIR / "ai" / "models" / "intent_classifier"

LABELS = [
    "judgment", "doc_search", "doc_generate",
    "meeting_generate", "schedule_add", "schedule_view", "general",
]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}
ID2LABEL = {i: l for i, l in enumerate(LABELS)}


def set_seed(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_jsonl(path):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def load_all_data():
    """v1.3 데이터 로드 (base + augment v12 + v13)"""
    all_data = []
    for label in LABELS:
        p = DATA_DIR / f"{label}.jsonl"
        if p.exists():
            all_data.extend(load_jsonl(p))
    for ver in ["v12", "v13"]:
        for p in sorted(DATA_DIR.glob(f"augment_{ver}_*.jsonl")):
            all_data.extend(load_jsonl(p))
    return all_data


def split_train_eval(data, eval_ratio=0.15):
    random.seed(SEED)
    by_label = {}
    for d in data:
        by_label.setdefault(d["label"], []).append(d)

    train, eval_ = [], []
    for label, items in by_label.items():
        random.shuffle(items)
        n = max(1, int(len(items) * eval_ratio))
        eval_.extend(items[:n])
        train.extend(items[n:])

    random.shuffle(train)
    random.shuffle(eval_)
    return train, eval_


def compute_metrics(eval_pred):
    preds = np.argmax(eval_pred.predictions, axis=-1)
    return {
        "accuracy": accuracy_score(eval_pred.label_ids, preds),
        "f1_macro": f1_score(eval_pred.label_ids, preds, average="macro"),
    }


def main():
    set_seed()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    # 데이터 로드
    data = load_all_data()
    train_data, eval_data = split_train_eval(data)
    print(f"Train: {len(train_data)}, Eval: {len(eval_data)}")

    # 토크나이저 + 모델
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=len(LABELS), id2label=ID2LABEL, label2id=LABEL2ID,
    )

    # Dataset 생성
    train_ds = Dataset.from_list(
        [{"text": d["text"], "label": LABEL2ID[d["label"]]} for d in train_data]
    )
    eval_ds = Dataset.from_list(
        [{"text": d["text"], "label": LABEL2ID[d["label"]]} for d in eval_data]
    )
    train_ds = train_ds.map(
        lambda x: tokenizer(x["text"], padding="max_length", truncation=True, max_length=MAX_LENGTH),
        batched=True,
    )
    eval_ds = eval_ds.map(
        lambda x: tokenizer(x["text"], padding="max_length", truncation=True, max_length=MAX_LENGTH),
        batched=True,
    )

    # 학습
    args = TrainingArguments(
        output_dir="/tmp/bert_best",
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        learning_rate=LR,
        weight_decay=WEIGHT_DECAY,
        warmup_ratio=WARMUP_RATIO,
        seed=SEED,
        data_seed=SEED,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        logging_steps=50,
        save_total_limit=1,
        report_to="none",
        fp16=torch.cuda.is_available(),
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        compute_metrics=compute_metrics,
    )

    print(f"\n{'='*50}")
    print(f"Training {MODEL_NAME}")
    print(f"Config: epochs={EPOCHS}, lr={LR}, batch={BATCH_SIZE}, warmup={WARMUP_RATIO}")
    print(f"{'='*50}\n")

    trainer.train()

    # 평가
    res = trainer.evaluate()
    print(f"\nEval F1: {res['eval_f1_macro']:.4f}, Acc: {res['eval_accuracy']:.4f}")

    # 저장
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(str(SAVE_DIR))
    model.save_pretrained(str(SAVE_DIR))

    with open(SAVE_DIR / "label_map.json", "w", encoding="utf-8") as f:
        json.dump({"id2label": ID2LABEL, "label2id": LABEL2ID}, f, ensure_ascii=False, indent=2)

    with open(SAVE_DIR / "model_info.json", "w", encoding="utf-8") as f:
        json.dump({"base_model": MODEL_NAME, "experiment": "exp5"}, f, ensure_ascii=False, indent=2)

    print(f"\nModel saved to {SAVE_DIR}")
    print("Done! model.safetensors 파일을 로컬로 다운로드하세요.")


if __name__ == "__main__":
    main()
