"""
Stage 5: 보강 데이터로 재학습 + 재평가

Stage 4 오분류 분석 기반으로 타겟 보강한 데이터를 포함하여 재학습하고,
Stage 4 결과와 비교한다.

사용법:
    python ai/experiments_v2/run_stage5_retrain.py
    python ai/experiments_v2/run_stage5_retrain.py --save-model
    python ai/experiments_v2/run_stage5_retrain.py --no-augment  # 보강 없이 원본만

사전: pip install transformers datasets accelerate scikit-learn matplotlib seaborn scipy
"""

import argparse
import json
import random
import time
import shutil
import torch
import numpy as np
from pathlib import Path
from collections import Counter
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
from sklearn.metrics import (
    accuracy_score, f1_score, classification_report,
    confusion_matrix,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "intent_v2"
SPLITS_DIR = DATA_DIR / "splits"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR = Path(__file__).resolve().parent / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
FINAL_MODEL_DIR = BASE_DIR / "ai" / "models" / "intent_classifier"

AUGMENT_PATH = DATA_DIR / "augmentation_stage5.jsonl"

# ── Intent 정의 ──
INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_qa",
]
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}
ID2LABEL = {i: label for i, label in enumerate(INTENT_LABELS)}

MODEL_NAME = "monologg/koelectra-base-v3-discriminator"
MAX_LENGTH = 64
WEIGHT_DECAY = 0.01

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_jsonl(path):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
    }


def load_best_config():
    """Stage 3 결과에서 best config 로드"""
    grid_path = RESULTS_DIR / "grid_search_results.json"
    if grid_path.exists():
        with open(grid_path, "r", encoding="utf-8") as f:
            results = json.load(f)
        if results:
            best = max(results, key=lambda r: r["val_f1"])
            return {
                "epochs": best["epochs"],
                "lr": best["lr"],
                "batch_size": best["batch_size"],
            }
    return {"epochs": 10, "lr": 3e-5, "batch_size": 16}


def train_model(train_data, val_data, config, seed=42):
    """koelectra 학습"""
    set_seed(seed)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=len(INTENT_LABELS),
        id2label=ID2LABEL, label2id=LABEL2ID,
    )

    train_ds = Dataset.from_list(
        [{"text": d["text"], "label": LABEL2ID[d["label"]]} for d in train_data]
    )
    val_ds = Dataset.from_list(
        [{"text": d["text"], "label": LABEL2ID[d["label"]]} for d in val_data]
    )

    tok_fn = lambda x: tokenizer(x["text"], padding="max_length", truncation=True, max_length=MAX_LENGTH)
    train_tok = train_ds.map(tok_fn, batched=True)
    val_tok = val_ds.map(tok_fn, batched=True)

    output_dir = CHECKPOINT_DIR / f"stage5_seed{seed}"

    args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=config["epochs"],
        per_device_train_batch_size=config["batch_size"],
        per_device_eval_batch_size=config["batch_size"],
        learning_rate=config["lr"],
        weight_decay=WEIGHT_DECAY,
        warmup_ratio=0.06,
        seed=seed,
        data_seed=seed,
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
        model=model, args=args,
        train_dataset=train_tok, eval_dataset=val_tok,
        compute_metrics=compute_metrics,
    )

    start = time.time()
    trainer.train()
    train_time = time.time() - start

    # cleanup
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)

    return model, tokenizer, train_time


def evaluate_dataset(model, tokenizer, data):
    """데이터셋 평가"""
    model.eval()
    model.to(device)

    texts = [d["text"] for d in data]
    labels = [d["label"] for d in data]

    preds = []
    confidences = []
    for text in texts:
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=MAX_LENGTH)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()[0]
        pred_id = np.argmax(probs)
        preds.append(ID2LABEL[pred_id])
        confidences.append(float(probs[pred_id]))

    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, average="macro")

    report = classification_report(labels, preds, labels=INTENT_LABELS, output_dict=True, zero_division=0)
    per_class = {}
    for label in INTENT_LABELS:
        if label in report:
            per_class[label] = {
                "p": round(report[label]["precision"], 4),
                "r": round(report[label]["recall"], 4),
                "f1": round(report[label]["f1-score"], 4),
            }

    return {
        "accuracy": round(acc, 4),
        "f1_macro": round(f1, 4),
        "per_class": per_class,
    }, preds, labels, confidences


def save_final_model(model, tokenizer):
    """최종 모델 저장"""
    FINAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(str(FINAL_MODEL_DIR))
    model.save_pretrained(str(FINAL_MODEL_DIR))

    with open(FINAL_MODEL_DIR / "label_map.json", "w", encoding="utf-8") as f:
        json.dump({"id2label": ID2LABEL, "label2id": LABEL2ID}, f, ensure_ascii=False, indent=2)

    with open(FINAL_MODEL_DIR / "model_info.json", "w", encoding="utf-8") as f:
        json.dump({
            "base_model": MODEL_NAME,
            "experiment": "v2_stage5",
            "intents": INTENT_LABELS,
            "augmented": True,
        }, f, ensure_ascii=False, indent=2)

    print(f"  -> 최종 모델 저장: {FINAL_MODEL_DIR}")


def plot_comparison(stage4, stage5, filename="stage5_comparison.png"):
    """Stage 4 vs 5 비교 차트"""
    intents = INTENT_LABELS
    x = np.arange(len(intents))
    width = 0.35

    s4_f1 = [stage4.get(i, {}).get("f1", 0) for i in intents]
    s5_f1 = [stage5.get(i, {}).get("f1", 0) for i in intents]

    fig, ax = plt.subplots(figsize=(12, 6))
    bars1 = ax.bar(x - width/2, s4_f1, width, label="Stage 4", color="#4A90D9", alpha=0.8)
    bars2 = ax.bar(x + width/2, s5_f1, width, label="Stage 5 (augmented)", color="#D96459", alpha=0.8)

    ax.set_ylabel("F1 Score")
    ax.set_title("Stage 4 vs Stage 5: Per-class Adversarial F1")
    ax.set_xticks(x)
    ax.set_xticklabels(intents, rotation=30, ha="right")
    ax.legend()
    ax.set_ylim(0.5, 1.05)

    # 변화량 표시
    for i, (v4, v5) in enumerate(zip(s4_f1, s5_f1)):
        diff = v5 - v4
        color = "green" if diff > 0 else "red" if diff < 0 else "gray"
        ax.text(i + width/2, v5 + 0.01, f"{diff:+.1%}", ha="center", fontsize=8, color=color)

    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


def plot_confusion(preds, labels, filename):
    """혼동행렬"""
    cm = confusion_matrix(labels, preds, labels=INTENT_LABELS)
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=INTENT_LABELS, yticklabels=INTENT_LABELS, ax=ax)
    ax.set_title("Stage 5 — Adversarial Confusion Matrix")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


def main():
    parser = argparse.ArgumentParser(description="Stage 5: 보강 재학습")
    parser.add_argument("--save-model", action="store_true", help="최종 모델 서비스 디렉토리에 저장")
    parser.add_argument("--no-augment", action="store_true", help="보강 없이 원본만 학습 (비교용)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Stage 5: 보강 데이터 재학습 + 재평가")
    print("=" * 60)
    print(f"  Device: {device}")
    print(f"  Model: {MODEL_NAME}")

    # Best config 로드
    config = load_best_config()
    print(f"  Config: ep={config['epochs']} lr={config['lr']:.0e} bs={config['batch_size']}")

    # 데이터 로드
    train_data = load_jsonl(SPLITS_DIR / "train.jsonl")
    val_data = load_jsonl(SPLITS_DIR / "val.jsonl")
    test_data = load_jsonl(SPLITS_DIR / "test.jsonl")

    print(f"  원본 Train: {len(train_data)}")

    # 보강 데이터 추가
    if not args.no_augment and AUGMENT_PATH.exists():
        aug_data = load_jsonl(AUGMENT_PATH)
        train_data = train_data + aug_data

        aug_counts = Counter(d["label"] for d in aug_data)
        print(f"  보강 데이터: +{len(aug_data)}개")
        for label, count in sorted(aug_counts.items(), key=lambda x: -x[1]):
            print(f"    {label}: +{count}")
    else:
        print("  보강 없음 (원본만)")

    print(f"  최종 Train: {len(train_data)}")

    # Adversarial 로드
    adv_path = DATA_DIR / "adversarial_v2.json"
    adv_data = []
    if adv_path.exists():
        with open(adv_path, "r", encoding="utf-8") as f:
            adv_data = json.load(f)

    print(f"  Val: {len(val_data)} | Test: {len(test_data)} | Adv: {len(adv_data)}")

    # Stage 4 결과 로드 (비교용)
    stage4_path = RESULTS_DIR / "final_eval_results.json"
    stage4_results = {}
    if stage4_path.exists():
        with open(stage4_path, "r", encoding="utf-8") as f:
            stage4_all = json.load(f)
        stage4_results = stage4_all.get(MODEL_NAME, {})

    # ── 학습 ──
    print(f"\n{'─' * 60}")
    print("  학습 중...")
    model, tokenizer, train_time = train_model(train_data, val_data, config)
    print(f"  학습 완료: {train_time:.1f}초")

    results = {"model": MODEL_NAME, "train_time_sec": round(train_time, 1)}

    # ── Val 평가 ──
    print("\n  Val 평가...")
    val_metrics, _, _, _ = evaluate_dataset(model, tokenizer, val_data)
    results["val"] = val_metrics
    print(f"    Val F1: {val_metrics['f1_macro']:.4f}  Acc: {val_metrics['accuracy']:.4f}")

    # ── Test 평가 ──
    print("  Test 평가...")
    test_metrics, test_preds, test_labels, _ = evaluate_dataset(model, tokenizer, test_data)
    results["test"] = test_metrics
    print(f"    Test F1: {test_metrics['f1_macro']:.4f}  Acc: {test_metrics['accuracy']:.4f}")

    # ── Adversarial 평가 ──
    if adv_data:
        print("  Adversarial 평가...")
        adv_metrics, adv_preds, adv_labels, _ = evaluate_dataset(model, tokenizer, adv_data)
        results["adversarial"] = adv_metrics
        print(f"    Adv F1: {adv_metrics['f1_macro']:.4f}  Acc: {adv_metrics['accuracy']:.4f}")

        plot_confusion(adv_preds, adv_labels, "stage5_confusion_adv.png")

    # ── Stage 4 vs 5 비교 ──
    print(f"\n{'=' * 60}")
    print("  Stage 4 vs Stage 5 비교")
    print(f"{'=' * 60}")

    s4_test_f1 = stage4_results.get("test_f1", 0)
    s4_adv_f1 = stage4_results.get("adv_f1", 0)
    s5_test_f1 = test_metrics["f1_macro"]
    s5_adv_f1 = adv_metrics["f1_macro"] if adv_data else 0

    print(f"\n  {'메트릭':<15} {'Stage 4':>10} {'Stage 5':>10} {'변화':>10}")
    print(f"  {'─' * 45}")
    print(f"  {'Test F1':<15} {s4_test_f1:>10.4f} {s5_test_f1:>10.4f} {s5_test_f1 - s4_test_f1:>+10.4f}")
    print(f"  {'Adv F1':<15} {s4_adv_f1:>10.4f} {s5_adv_f1:>10.4f} {s5_adv_f1 - s4_adv_f1:>+10.4f}")

    # Per-class 비교
    if adv_data and stage4_results.get("adv_per_class"):
        s4_pc = stage4_results["adv_per_class"]
        s5_pc = adv_metrics["per_class"]

        print(f"\n  {'Intent':<18} {'S4 Adv F1':>10} {'S5 Adv F1':>10} {'변화':>10}")
        print(f"  {'─' * 48}")
        for intent in INTENT_LABELS:
            s4_f = s4_pc.get(intent, {}).get("f1", 0)
            s5_f = s5_pc.get(intent, {}).get("f1", 0)
            diff = s5_f - s4_f
            marker = "⬆" if diff > 0.01 else "⬇" if diff < -0.01 else " "
            print(f"  {intent:<18} {s4_f:>10.4f} {s5_f:>10.4f} {diff:>+10.4f} {marker}")

        # 비교 차트
        plot_comparison(s4_pc, s5_pc)

    # 결과 저장
    results_path = RESULTS_DIR / "stage5_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  -> {results_path.name}")

    # 모델 저장
    if args.save_model:
        save_final_model(model, tokenizer)

    # ── 요약 ──
    print(f"\n{'=' * 60}")
    print("  Stage 5 완료")
    print(f"{'=' * 60}")
    aug_label = "보강 포함" if not args.no_augment else "원본만"
    print(f"  데이터: {aug_label} ({len(train_data)}개)")
    print(f"  Test F1: {s5_test_f1:.4f} (Stage 4: {s4_test_f1:.4f}, {s5_test_f1 - s4_test_f1:+.4f})")
    print(f"  Adv F1:  {s5_adv_f1:.4f} (Stage 4: {s4_adv_f1:.4f}, {s5_adv_f1 - s4_adv_f1:+.4f})")
    if args.save_model:
        print(f"  모델 저장: {FINAL_MODEL_DIR}")


if __name__ == "__main__":
    main()
