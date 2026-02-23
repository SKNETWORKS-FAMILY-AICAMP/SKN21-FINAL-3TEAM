"""
Stage 2: Baseline 학습 — 3개 모델 동일 HP 비교

3개 한국어 사전학습 모델을 동일 하이퍼파라미터로 학습하여
Validation Macro F1 기준 순위를 결정한다.

사용법:
    python ai/experiments_v2/run_baseline.py
    python ai/experiments_v2/run_baseline.py --model klue/bert-base
    python ai/experiments_v2/run_baseline.py --seed 123

사전: pip install transformers datasets accelerate scikit-learn matplotlib seaborn
"""

import argparse
import json
import random
import time
import shutil
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
from sklearn.metrics import (
    accuracy_score, f1_score, confusion_matrix, classification_report,
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
MODEL_SAVE_BASE = Path(__file__).resolve().parent / "checkpoints"
MODEL_SAVE_BASE.mkdir(parents=True, exist_ok=True)

# ── 모델 ──
MODELS = [
    "klue/bert-base",
    "monologg/koelectra-base-v3-discriminator",
    "monologg/distilkobert",
]

# ── Intent 정의 (8개) ──
INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_qa",
]
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}
ID2LABEL = {i: label for i, label in enumerate(INTENT_LABELS)}

# ── Baseline 하이퍼파라미터 (고정) ──
BASELINE_HP = {
    "epochs": 5,
    "learning_rate": 2e-5,
    "batch_size": 16,
    "warmup_ratio": 0.06,
    "weight_decay": 0.01,
    "max_length": 64,
}

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ── 데이터 ──

def load_jsonl(path):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def load_splits():
    """Train/Val/Test 분할 데이터 로드"""
    train = load_jsonl(SPLITS_DIR / "train.jsonl")
    val = load_jsonl(SPLITS_DIR / "val.jsonl")
    test = load_jsonl(SPLITS_DIR / "test.jsonl")
    return train, val, test


def load_adversarial():
    """적대적 테스트 데이터 로드"""
    adv_path = DATA_DIR / "adversarial_v2.json"
    if adv_path.exists():
        with open(adv_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# ── 학습 + 평가 ──

def tokenize_fn(examples, tokenizer, max_length):
    return tokenizer(
        examples["text"],
        padding="max_length",
        truncation=True,
        max_length=max_length,
    )


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
    }


def train_model(model_name, train_data, val_data, seed, output_dir):
    """단일 모델 학습 + validation 평가"""
    set_seed(seed)
    hp = BASELINE_HP

    # 데이터셋 변환
    train_ds = Dataset.from_list(
        [{"text": d["text"], "label": LABEL2ID[d["label"]]} for d in train_data]
    )
    val_ds = Dataset.from_list(
        [{"text": d["text"], "label": LABEL2ID[d["label"]]} for d in val_data]
    )

    # 모델 로드
    trust_remote = "distilkobert" in model_name
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=trust_remote)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=len(INTENT_LABELS),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        trust_remote_code=trust_remote,
    )

    # 토크나이즈
    train_tok = train_ds.map(
        lambda x: tokenize_fn(x, tokenizer, hp["max_length"]), batched=True
    )
    val_tok = val_ds.map(
        lambda x: tokenize_fn(x, tokenizer, hp["max_length"]), batched=True
    )

    # 학습 설정
    args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=hp["epochs"],
        per_device_train_batch_size=hp["batch_size"],
        per_device_eval_batch_size=hp["batch_size"],
        learning_rate=hp["learning_rate"],
        weight_decay=hp["weight_decay"],
        warmup_ratio=hp["warmup_ratio"],
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
        model=model,
        args=args,
        train_dataset=train_tok,
        eval_dataset=val_tok,
        compute_metrics=compute_metrics,
    )

    # 학습
    start = time.time()
    train_result = trainer.train()
    train_time = time.time() - start

    # Validation 평가
    eval_results = trainer.evaluate()

    # Training loss history
    log_history = trainer.state.log_history

    return {
        "model": model_name,
        "seed": seed,
        "val_acc": round(eval_results["eval_accuracy"], 4),
        "val_f1": round(eval_results["eval_f1_macro"], 4),
        "train_loss": round(train_result.training_loss, 4),
        "train_time_sec": round(train_time, 1),
        "hp": hp,
    }, tokenizer, model, log_history


def evaluate_on_dataset(model, tokenizer, data, dataset_name="test"):
    """별도 데이터셋으로 평가 (test, adversarial 등)"""
    model.eval()
    model.to(device)

    texts = [d["text"] for d in data]
    labels = [d["label"] for d in data]
    preds = []
    confidences = []

    start = time.time()
    for text in texts:
        inputs = tokenizer(
            text, return_tensors="pt", padding=True,
            truncation=True, max_length=BASELINE_HP["max_length"],
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)
        pred_id = torch.argmax(probs, dim=-1).item()
        preds.append(ID2LABEL[pred_id])
        confidences.append(probs[0][pred_id].item())

    infer_time = (time.time() - start) / len(texts) * 1000 if texts else 0

    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, average="macro", labels=INTENT_LABELS, zero_division=0)

    # Per-class report
    report = classification_report(
        labels, preds, labels=INTENT_LABELS,
        output_dict=True, zero_division=0,
    )

    return {
        f"{dataset_name}_acc": round(acc, 4),
        f"{dataset_name}_f1": round(f1, 4),
        f"{dataset_name}_infer_ms": round(infer_time, 2),
        f"{dataset_name}_per_class": {
            label: {
                "precision": round(report[label]["precision"], 4),
                "recall": round(report[label]["recall"], 4),
                "f1": round(report[label]["f1-score"], 4),
            }
            for label in INTENT_LABELS if label in report
        },
        f"{dataset_name}_mean_confidence": round(np.mean(confidences), 4),
    }, preds, labels, confidences


def measure_model_size(model):
    """모델 파라미터 수 + 메모리 측정"""
    param_count = sum(p.numel() for p in model.parameters())
    size_mb = sum(p.numel() * p.element_size() for p in model.parameters()) / 1024 / 1024

    gpu_mem = 0
    if torch.cuda.is_available():
        gpu_mem = torch.cuda.max_memory_allocated() / 1024 / 1024

    return {
        "param_count": param_count,
        "param_count_m": round(param_count / 1e6, 1),
        "model_size_mb": round(size_mb, 1),
        "gpu_peak_mb": round(gpu_mem, 1),
    }


# ── 시각화 ──

def plot_baseline_comparison(results, filename="baseline_comparison.png"):
    """3모델 Baseline 비교 Grouped Bar Chart"""
    models = [r["model"].split("/")[-1] for r in results]
    val_f1 = [r["val_f1"] for r in results]
    val_acc = [r["val_acc"] for r in results]

    x = np.arange(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width / 2, val_f1, width, label="Val Macro F1", color="#4A90D9")
    bars2 = ax.bar(x + width / 2, val_acc, width, label="Val Accuracy", color="#7BC67E")

    ax.set_ylabel("Score")
    ax.set_title("Stage 2: Baseline Comparison (Same HP)")
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=15)
    ax.legend()
    ax.set_ylim(0.5, 1.0)

    for bar in bars1 + bars2:
        height = bar.get_height()
        ax.annotate(f"{height:.3f}", xy=(bar.get_x() + bar.get_width() / 2, height),
                     xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9)

    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


def plot_confusion_matrix(preds, labels, model_name, dataset_name, filename):
    """혼동행렬"""
    cm = confusion_matrix(labels, preds, labels=INTENT_LABELS)
    short = model_name.split("/")[-1]

    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=INTENT_LABELS, yticklabels=INTENT_LABELS)
    plt.title(f"Confusion Matrix — {short}\n{dataset_name} ({len(labels)} samples)")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


def plot_training_curves(all_histories, filename="training_curves.png"):
    """3모델 Training Loss Curves"""
    fig, axes = plt.subplots(1, len(all_histories), figsize=(5 * len(all_histories), 4), squeeze=False)

    for idx, (model_name, history) in enumerate(all_histories.items()):
        ax = axes[0][idx]
        short = model_name.split("/")[-1]

        # epoch별 train loss + eval loss 추출
        train_losses = [h["loss"] for h in history if "loss" in h and "eval_loss" not in h]
        eval_losses = [h["eval_loss"] for h in history if "eval_loss" in h]
        eval_f1s = [h["eval_f1_macro"] for h in history if "eval_f1_macro" in h]

        if train_losses:
            ax.plot(train_losses, label="Train Loss", color="#D96459")
        if eval_losses:
            epochs_x = np.linspace(0, len(train_losses) - 1, len(eval_losses)) if train_losses else range(len(eval_losses))
            ax.plot(epochs_x, eval_losses, label="Val Loss", color="#4A90D9", marker="o")

        ax.set_title(short)
        ax.set_xlabel("Steps")
        ax.set_ylabel("Loss")
        ax.legend(fontsize=8)

    plt.suptitle("Training Curves", fontsize=14)
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


def plot_per_class_f1_radar(all_per_class, filename="per_class_f1_radar.png"):
    """Per-class F1 Radar Chart"""
    labels = INTENT_LABELS
    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    colors = ["#4A90D9", "#D96459", "#7BC67E"]
    for idx, (model_name, per_class) in enumerate(all_per_class.items()):
        values = [per_class.get(label, {}).get("f1", 0) for label in labels]
        values += values[:1]
        short = model_name.split("/")[-1]
        ax.plot(angles, values, "o-", linewidth=2, label=short, color=colors[idx % len(colors)])
        ax.fill(angles, values, alpha=0.1, color=colors[idx % len(colors)])

    ax.set_thetagrids(np.degrees(angles[:-1]), labels, fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_title("Per-class F1 (Validation)")
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


# ── 메인 ──

def main():
    parser = argparse.ArgumentParser(description="Stage 2: Baseline 학습")
    parser.add_argument("--model", type=str, default=None, help="특정 모델만 실행")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--skip-plots", action="store_true", help="차트 생성 건너뛰기")
    args = parser.parse_args()

    print("=" * 60)
    print("  Stage 2: Baseline 학습 (3모델 동일 HP)")
    print("=" * 60)
    print(f"  Device: {device}")
    print(f"  Seed: {args.seed}")
    print(f"  HP: {BASELINE_HP}")

    # 데이터 로드
    if not (SPLITS_DIR / "train.jsonl").exists():
        print("\n[ERROR] 학습 데이터가 없습니다.")
        print("  먼저 실행: python ai/experiments_v2/generate_data.py --step split")
        return

    train_data, val_data, test_data = load_splits()
    adv_data = load_adversarial()

    print(f"\n  Train: {len(train_data)}개")
    print(f"  Val: {len(val_data)}개")
    print(f"  Test: {len(test_data)}개")
    print(f"  Adversarial: {len(adv_data)}개")

    # 결과 파일 (이어쓰기 지원)
    results_path = RESULTS_DIR / "baseline_results.json"
    existing_results = {}
    if results_path.exists():
        with open(results_path, "r", encoding="utf-8") as f:
            existing_results = json.load(f)

    # 모델 학습
    models = [args.model] if args.model else MODELS
    all_results = []
    all_histories = {}
    all_per_class = {}
    all_confusion_data = {}

    for model_name in models:
        short = model_name.split("/")[-1]
        result_key = f"{short}_seed{args.seed}"

        if result_key in existing_results:
            print(f"\n--- {short} (이미 완료 — skip) ---")
            all_results.append(existing_results[result_key])
            continue

        print(f"\n{'=' * 60}")
        print(f"  학습: {model_name}")
        print(f"{'=' * 60}")

        output_dir = MODEL_SAVE_BASE / f"{short}_baseline_seed{args.seed}"

        try:
            # 학습
            metrics, tokenizer, model, log_history = train_model(
                model_name, train_data, val_data, args.seed, output_dir,
            )
            all_histories[model_name] = log_history

            # Val per-class 평가
            val_metrics, val_preds, val_labels, val_conf = evaluate_on_dataset(
                model, tokenizer, val_data, "val",
            )
            metrics.update(val_metrics)
            all_per_class[model_name] = val_metrics.get("val_per_class", {})
            all_confusion_data[model_name] = (val_preds, val_labels)

            # Adversarial 평가 (있으면)
            if adv_data:
                adv_metrics, adv_preds, adv_labels, _ = evaluate_on_dataset(
                    model, tokenizer, adv_data, "adv",
                )
                metrics.update(adv_metrics)

            # 모델 크기 측정
            size_info = measure_model_size(model)
            metrics.update(size_info)

            # 결과 저장
            existing_results[result_key] = metrics
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(existing_results, f, ensure_ascii=False, indent=2)

            all_results.append(metrics)

            print(f"\n  Val F1: {metrics['val_f1']:.4f}  |  Val Acc: {metrics['val_acc']:.4f}")
            if adv_data:
                print(f"  Adv F1: {metrics.get('adv_f1', 'N/A')}  |  Adv Acc: {metrics.get('adv_acc', 'N/A')}")
            print(f"  Params: {size_info['param_count_m']}M  |  Size: {size_info['model_size_mb']}MB")
            print(f"  Train: {metrics['train_time_sec']}s  |  Infer: {metrics.get('val_infer_ms', 'N/A')}ms")

            # 체크포인트 정리
            if output_dir.exists():
                shutil.rmtree(output_dir)

        except Exception as e:
            print(f"  [ERROR] {model_name} 실패: {e}")
            import traceback
            traceback.print_exc()
            continue

    # 결과 요약
    if all_results:
        print("\n" + "=" * 60)
        print("  Baseline 결과 요약")
        print("=" * 60)
        print(f"\n{'모델':<40} {'Val F1':>8} {'Val Acc':>8} {'Params':>8} {'Time':>8}")
        print("-" * 72)

        sorted_results = sorted(all_results, key=lambda x: x["val_f1"], reverse=True)
        for r in sorted_results:
            short = r["model"].split("/")[-1]
            print(f"  {short:<38} {r['val_f1']:>8.4f} {r['val_acc']:>8.4f} "
                  f"{r.get('param_count_m', '?'):>6}M {r['train_time_sec']:>6.1f}s")

        # 최상위 모델
        best = sorted_results[0]
        print(f"\n  => Stage 3 대상: {best['model']} (Val F1: {best['val_f1']:.4f})")

    # 차트 생성
    if not args.skip_plots and all_results:
        print("\n--- 차트 생성 ---")

        if len(all_results) >= 2:
            plot_baseline_comparison(all_results)

        if all_histories:
            plot_training_curves(all_histories)

        if all_per_class:
            plot_per_class_f1_radar(all_per_class)

        for model_name, (preds, labels) in all_confusion_data.items():
            short = model_name.split("/")[-1]
            plot_confusion_matrix(preds, labels, model_name, "Validation",
                                  f"confusion_{short}_val.png")

    print("\n" + "=" * 60)
    print("  Stage 2 완료!")
    print(f"  결과: {results_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
