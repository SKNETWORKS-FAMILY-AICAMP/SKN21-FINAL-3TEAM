"""
Stage 5/6: 보강 데이터로 재학습 + 재평가

Stage 4 오분류 분석 기반으로 타겟 보강한 데이터를 포함하여 재학습하고,
이전 Stage 결과와 비교한다.

사용법:
    python ai/experiments_v2/run_stage5_retrain.py                        # Stage 5
    python ai/experiments_v2/run_stage5_retrain.py --save-model           # + 모델 저장
    python ai/experiments_v2/run_stage5_retrain.py --no-augment           # 보강 없이 원본만
    python ai/experiments_v2/run_stage5_retrain.py --label-smoothing 0.1  # Stage 6

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


def train_model(train_data, val_data, config, seed=42, label_smoothing=0.0):
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
        label_smoothing_factor=label_smoothing,
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


def save_final_model(model, tokenizer, stage="stage5", label_smoothing=0.0):
    """최종 모델 저장"""
    FINAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(str(FINAL_MODEL_DIR))
    model.save_pretrained(str(FINAL_MODEL_DIR))

    with open(FINAL_MODEL_DIR / "label_map.json", "w", encoding="utf-8") as f:
        json.dump({"id2label": ID2LABEL, "label2id": LABEL2ID}, f, ensure_ascii=False, indent=2)

    info = {
        "base_model": MODEL_NAME,
        "experiment": f"v2_{stage}",
        "intents": INTENT_LABELS,
        "augmented": True,
    }
    if label_smoothing > 0:
        info["label_smoothing"] = label_smoothing

    with open(FINAL_MODEL_DIR / "model_info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    print(f"  -> 최종 모델 저장: {FINAL_MODEL_DIR}")


def plot_comparison(prev_pc, cur_pc, filename="stage5_comparison.png"):
    """이전 Stage vs 현재 Stage 비교 차트"""
    intents = INTENT_LABELS
    x = np.arange(len(intents))
    width = 0.35

    # 파일명에서 Stage 번호 추출
    is_s6 = "stage6" in filename
    prev_label = "Stage 5" if is_s6 else "Stage 4"
    cur_label = "Stage 6 (label smoothing)" if is_s6 else "Stage 5 (augmented)"

    prev_f1 = [prev_pc.get(i, {}).get("f1", 0) for i in intents]
    cur_f1 = [cur_pc.get(i, {}).get("f1", 0) for i in intents]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x - width/2, prev_f1, width, label=prev_label, color="#4A90D9", alpha=0.8)
    ax.bar(x + width/2, cur_f1, width, label=cur_label, color="#D96459", alpha=0.8)

    ax.set_ylabel("F1 Score")
    ax.set_title(f"{prev_label} vs {cur_label}: Per-class Adversarial F1")
    ax.set_xticks(x)
    ax.set_xticklabels(intents, rotation=30, ha="right")
    ax.legend()
    ax.set_ylim(0.5, 1.05)

    for i, (vp, vc) in enumerate(zip(prev_f1, cur_f1)):
        diff = vc - vp
        color = "green" if diff > 0 else "red" if diff < 0 else "gray"
        ax.text(i + width/2, vc + 0.01, f"{diff:+.1%}", ha="center", fontsize=8, color=color)

    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


def plot_confusion(preds, labels, filename, title=None):
    """혼동행렬"""
    cm = confusion_matrix(labels, preds, labels=INTENT_LABELS)
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=INTENT_LABELS, yticklabels=INTENT_LABELS, ax=ax)
    ax.set_title(title or "Adversarial Confusion Matrix")
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
    parser.add_argument("--label-smoothing", type=float, default=0.0,
                        help="Label smoothing factor (0.1 권장)")
    args = parser.parse_args()

    is_stage6 = args.label_smoothing > 0
    stage_name = "Stage 6" if is_stage6 else "Stage 5"
    stage_desc = f"Label Smoothing={args.label_smoothing}" if is_stage6 else "보강 데이터 재학습"

    print("=" * 60)
    print(f"  {stage_name}: {stage_desc}")
    print("=" * 60)
    print(f"  Device: {device}")
    print(f"  Model: {MODEL_NAME}")
    if is_stage6:
        print(f"  Label Smoothing: {args.label_smoothing}")

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

    # 이전 Stage 결과 로드 (비교용)
    if is_stage6:
        prev_stage_name = "Stage 5"
        prev_path = RESULTS_DIR / "stage5_results.json"
        prev_results = {}
        if prev_path.exists():
            with open(prev_path, "r", encoding="utf-8") as f:
                prev_all = json.load(f)
            prev_results = {
                "test_f1": prev_all.get("test", {}).get("f1_macro", 0),
                "adv_f1": prev_all.get("adversarial", {}).get("f1_macro", 0),
                "adv_per_class": prev_all.get("adversarial", {}).get("per_class", {}),
            }
        else:
            print(f"  ⚠ {prev_path.name} 없음 — Stage 5 먼저 실행 필요")
    else:
        prev_stage_name = "Stage 4"
        prev_path = RESULTS_DIR / "final_eval_results.json"
        prev_results = {}
        if prev_path.exists():
            with open(prev_path, "r", encoding="utf-8") as f:
                prev_all = json.load(f)
            prev_results = prev_all.get(MODEL_NAME, {})

    # ── 학습 ──
    print(f"\n{'─' * 60}")
    print("  학습 중...")
    model, tokenizer, train_time = train_model(
        train_data, val_data, config, label_smoothing=args.label_smoothing
    )
    print(f"  학습 완료: {train_time:.1f}초")

    results = {
        "model": MODEL_NAME,
        "stage": stage_name,
        "label_smoothing": args.label_smoothing,
        "train_time_sec": round(train_time, 1),
    }

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
        adv_metrics, adv_preds, adv_labels, adv_confs = evaluate_dataset(model, tokenizer, adv_data)
        results["adversarial"] = adv_metrics
        print(f"    Adv F1: {adv_metrics['f1_macro']:.4f}  Acc: {adv_metrics['accuracy']:.4f}")

        cm_filename = "stage6_confusion_adv.png" if is_stage6 else "stage5_confusion_adv.png"
        plot_confusion(adv_preds, adv_labels, cm_filename,
                       title=f"{stage_name} — Adversarial Confusion Matrix")

    # ── 이전 Stage와 비교 ──
    print(f"\n{'=' * 60}")
    print(f"  {prev_stage_name} vs {stage_name} 비교")
    print(f"{'=' * 60}")

    prev_test_f1 = prev_results.get("test_f1", 0)
    prev_adv_f1 = prev_results.get("adv_f1", 0)
    cur_test_f1 = test_metrics["f1_macro"]
    cur_adv_f1 = adv_metrics["f1_macro"] if adv_data else 0

    print(f"\n  {'메트릭':<15} {prev_stage_name:>10} {stage_name:>10} {'변화':>10}")
    print(f"  {'─' * 45}")
    print(f"  {'Test F1':<15} {prev_test_f1:>10.4f} {cur_test_f1:>10.4f} {cur_test_f1 - prev_test_f1:>+10.4f}")
    print(f"  {'Adv F1':<15} {prev_adv_f1:>10.4f} {cur_adv_f1:>10.4f} {cur_adv_f1 - prev_adv_f1:>+10.4f}")

    # 과신뢰 분석 (Stage 6)
    if is_stage6 and adv_data:
        overconf_wrong = sum(1 for p, l, c in zip(adv_preds, adv_labels, adv_confs) if p != l and c > 0.9)
        total_wrong = sum(1 for p, l in zip(adv_preds, adv_labels) if p != l)
        print(f"\n  과신뢰 오류 (conf > 0.90): {overconf_wrong}건 / 오답 {total_wrong}건")
        if total_wrong > 0:
            print(f"  과신뢰 비율: {overconf_wrong/total_wrong:.1%}")
        # 오답 confidence 분포
        wrong_confs = [c for p, l, c in zip(adv_preds, adv_labels, adv_confs) if p != l]
        if wrong_confs:
            print(f"  오답 confidence: mean={np.mean(wrong_confs):.4f} median={np.median(wrong_confs):.4f}")
            print(f"    min={min(wrong_confs):.4f} max={max(wrong_confs):.4f}")
        # 정답 confidence 분포
        right_confs = [c for p, l, c in zip(adv_preds, adv_labels, adv_confs) if p == l]
        if right_confs:
            print(f"  정답 confidence: mean={np.mean(right_confs):.4f} median={np.median(right_confs):.4f}")

    # Per-class 비교
    prev_pc = prev_results.get("adv_per_class", {})
    if adv_data and prev_pc:
        cur_pc = adv_metrics["per_class"]

        prev_label = prev_stage_name.replace("Stage ", "S")
        cur_label = stage_name.replace("Stage ", "S")
        print(f"\n  {'Intent':<18} {prev_label + ' Adv F1':>10} {cur_label + ' Adv F1':>10} {'변화':>10}")
        print(f"  {'─' * 48}")
        for intent in INTENT_LABELS:
            pf = prev_pc.get(intent, {}).get("f1", 0)
            cf = cur_pc.get(intent, {}).get("f1", 0)
            diff = cf - pf
            marker = "+" if diff > 0.01 else "-" if diff < -0.01 else " "
            print(f"  {intent:<18} {pf:>10.4f} {cf:>10.4f} {diff:>+10.4f} {marker}")

        # 비교 차트
        comp_filename = "stage6_comparison.png" if is_stage6 else "stage5_comparison.png"
        plot_comparison(prev_pc, cur_pc, filename=comp_filename)

    # 결과 저장
    results_filename = "stage6_results.json" if is_stage6 else "stage5_results.json"
    results_path = RESULTS_DIR / results_filename
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  -> {results_path.name}")

    # 모델 저장
    if args.save_model:
        save_final_model(model, tokenizer,
                         stage="stage6" if is_stage6 else "stage5",
                         label_smoothing=args.label_smoothing)

    # ── 요약 ──
    print(f"\n{'=' * 60}")
    print(f"  {stage_name} 완료")
    print(f"{'=' * 60}")
    aug_label = "보강 포함" if not args.no_augment else "원본만"
    if is_stage6:
        print(f"  Label Smoothing: {args.label_smoothing}")
    print(f"  데이터: {aug_label} ({len(train_data)}개)")
    print(f"  Test F1: {cur_test_f1:.4f} ({prev_stage_name}: {prev_test_f1:.4f}, {cur_test_f1 - prev_test_f1:+.4f})")
    print(f"  Adv F1:  {cur_adv_f1:.4f} ({prev_stage_name}: {prev_adv_f1:.4f}, {cur_adv_f1 - prev_adv_f1:+.4f})")
    if args.save_model:
        print(f"  모델 저장: {FINAL_MODEL_DIR}")


if __name__ == "__main__":
    main()
