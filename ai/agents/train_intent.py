"""
Intent Classification 파인튜닝 스크립트 (PM 지용)

klue/bert-base를 7개 intent 카테고리로 파인튜닝합니다.
학습 데이터: data/training/intent/train.jsonl
검증 데이터: data/training/intent/eval.jsonl
목표: F1 90%+

사용법:
    python ai/agents/train_intent.py
"""

import json
import os
import numpy as np
from pathlib import Path

from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
from sklearn.metrics import accuracy_score, f1_score, classification_report

# ── 설정 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "intent"
OUTPUT_DIR = BASE_DIR / "ai" / "models" / "intent_classifier"

MODEL_NAME = "klue/bert-base"
MAX_LENGTH = 64
BATCH_SIZE = 16
EPOCHS = 5
LEARNING_RATE = 2e-5

# 7개 Intent 라벨 (intent_classifier.py와 동일 순서)
INTENT_LABELS = [
    "judgment",
    "doc_search",
    "doc_generate",
    "meeting_generate",
    "schedule_add",
    "schedule_view",
    "general",
]
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}
ID2LABEL = {i: label for i, label in enumerate(INTENT_LABELS)}


def load_jsonl(path: str) -> list[dict]:
    """JSONL 파일 로드"""
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line.strip())
            item["label_id"] = LABEL2ID[item["label"]]
            data.append(item)
    return data


def tokenize_function(examples, tokenizer):
    """토크나이저 적용"""
    return tokenizer(
        examples["text"],
        padding="max_length",
        truncation=True,
        max_length=MAX_LENGTH,
    )


def compute_metrics(eval_pred):
    """평가 지표 계산"""
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    acc = accuracy_score(labels, predictions)
    f1_macro = f1_score(labels, predictions, average="macro")
    f1_weighted = f1_score(labels, predictions, average="weighted")
    return {
        "accuracy": acc,
        "f1_macro": f1_macro,
        "f1_weighted": f1_weighted,
    }


def main():
    print("=" * 50)
    print("Intent Classification 파인튜닝 시작")
    print("=" * 50)

    # 1. 데이터 로드
    print("\n[1/5] 데이터 로드 중...")
    train_data = load_jsonl(DATA_DIR / "train.jsonl")
    eval_data = load_jsonl(DATA_DIR / "eval.jsonl")
    print(f"  Train: {len(train_data)}개")
    print(f"  Eval:  {len(eval_data)}개")

    # Dataset 객체로 변환
    train_dataset = Dataset.from_list(
        [{"text": d["text"], "label": d["label_id"]} for d in train_data]
    )
    eval_dataset = Dataset.from_list(
        [{"text": d["text"], "label": d["label_id"]} for d in eval_data]
    )

    # 2. 토크나이저 & 모델 로드
    print(f"\n[2/5] 모델 로드 중... ({MODEL_NAME})")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(INTENT_LABELS),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )
    print(f"  파라미터: {model.num_parameters():,}개")

    # 3. 토크나이징
    print("\n[3/5] 토크나이징 중...")
    train_tokenized = train_dataset.map(
        lambda x: tokenize_function(x, tokenizer), batched=True
    )
    eval_tokenized = eval_dataset.map(
        lambda x: tokenize_function(x, tokenizer), batched=True
    )

    # 4. 학습
    print(f"\n[4/5] 학습 시작 (epochs={EPOCHS}, batch={BATCH_SIZE}, lr={LEARNING_RATE})")
    print(f"  디바이스: CPU")
    print(f"  저장 경로: {OUTPUT_DIR}")

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        learning_rate=LEARNING_RATE,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        logging_steps=50,
        save_total_limit=2,
        report_to="none",
        fp16=False,  # CPU 학습이므로 fp16 비활성화
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tokenized,
        eval_dataset=eval_tokenized,
        compute_metrics=compute_metrics,
    )

    trainer.train()

    # 5. 최종 평가
    print("\n[5/5] 최종 평가 중...")
    results = trainer.evaluate()
    print(f"\n{'=' * 50}")
    print(f"  Accuracy:    {results['eval_accuracy']:.4f}")
    print(f"  F1 (macro):  {results['eval_f1_macro']:.4f}")
    print(f"  F1 (weighted): {results['eval_f1_weighted']:.4f}")
    print(f"{'=' * 50}")

    # 상세 리포트
    predictions = trainer.predict(eval_tokenized)
    preds = np.argmax(predictions.predictions, axis=-1)
    labels = predictions.label_ids
    report = classification_report(
        labels, preds, target_names=INTENT_LABELS, digits=4
    )
    print(f"\n분류 리포트:\n{report}")

    # 모델 저장
    print(f"\n모델 저장 중... → {OUTPUT_DIR}")
    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))

    # 라벨 매핑 저장
    label_map = {"id2label": ID2LABEL, "label2id": LABEL2ID}
    with open(OUTPUT_DIR / "label_map.json", "w", encoding="utf-8") as f:
        json.dump(label_map, f, ensure_ascii=False, indent=2)

    print("\n파인튜닝 완료!")
    if results["eval_f1_macro"] >= 0.90:
        print(f"  F1 {results['eval_f1_macro']:.4f} >= 0.90 목표 달성!")
    else:
        print(f"  F1 {results['eval_f1_macro']:.4f} < 0.90 — 데이터 증강 필요할 수 있음")


if __name__ == "__main__":
    main()
