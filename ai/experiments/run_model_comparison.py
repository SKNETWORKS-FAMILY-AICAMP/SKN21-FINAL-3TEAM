"""
실험 5: 다중 모델 × 하이퍼파라미터 전탐색

3개 한국어 사전학습 모델에 대해 체계적으로 하이퍼파라미터를 탐색하고,
최종 모델을 선정한다.

사용법:
    # Step 1+2 전체 실행 (RunPod A100 권장)
    python ai/experiments/run_model_comparison.py

    # Step 1만 실행 (warmup 고정)
    python ai/experiments/run_model_comparison.py --step1-only

    # 특정 모델만 실행
    python ai/experiments/run_model_comparison.py --model klue/roberta-base

실행 환경: RunPod GPU (A100 권장)
사전: pip install transformers datasets accelerate matplotlib seaborn scikit-learn
"""

import argparse
import json
import os
import random
import time
import shutil
import torch
import numpy as np
from pathlib import Path
from collections import Counter
from itertools import product
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
from sklearn.metrics import (
    accuracy_score, f1_score, classification_report, confusion_matrix,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "intent"
MODEL_BASE = BASE_DIR / "ai" / "models"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ── 실험 설정 ──
MODELS = [
    "klue/bert-base",
    "klue/roberta-base",
    "monologg/koelectra-base-v3-discriminator",
]

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate",
    "meeting_generate", "schedule_add", "schedule_view", "general",
]
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}
ID2LABEL = {i: label for i, label in enumerate(INTENT_LABELS)}

# Step 1 그리드
EPOCHS_LIST = [3, 5, 7, 10]
LR_LIST = [1e-5, 2e-5, 3e-5, 5e-5]
BATCH_LIST = [8, 16, 32]
WARMUP_DEFAULT = 0.06

# Step 2 warmup 미세조정
WARMUP_LIST = [0.0, 0.06, 0.1]

MAX_LENGTH = 64
WEIGHT_DECAY = 0.01
SEED = 42

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def set_seed(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ── 데이터 로드 ──

def load_jsonl(path):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def load_all_data():
    """v1.3 데이터 로드 (base + augment v12 + v13)"""
    all_data = []

    # base
    for label in INTENT_LABELS:
        path = DATA_DIR / f"{label}.jsonl"
        if path.exists():
            all_data.extend(load_jsonl(path))

    # augment v12, v13
    for version in ["v12", "v13"]:
        for path in sorted(DATA_DIR.glob(f"augment_{version}_*.jsonl")):
            all_data.extend(load_jsonl(path))

    return all_data


def split_train_eval(data, eval_ratio=0.15, seed=SEED):
    random.seed(seed)
    by_label = {}
    for item in data:
        by_label.setdefault(item["label"], []).append(item)

    train, eval_ = [], []
    for label, items in by_label.items():
        random.shuffle(items)
        n_eval = max(1, int(len(items) * eval_ratio))
        eval_.extend(items[:n_eval])
        train.extend(items[n_eval:])

    random.shuffle(train)
    random.shuffle(eval_)
    return train, eval_


def load_adversarial():
    adv_path = DATA_DIR / "adversarial_test.json"
    with open(adv_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 학습 + 평가 ──

def tokenize(examples, tokenizer):
    return tokenizer(
        examples["text"], padding="max_length", truncation=True, max_length=MAX_LENGTH,
    )


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
    }


def train_and_evaluate(model_name, train_data, eval_data, adv_data,
                       epochs, lr, batch_size, warmup_ratio, output_dir):
    """단일 설정으로 학습 + eval + adversarial 평가"""
    set_seed(SEED)

    train_ds = Dataset.from_list(
        [{"text": d["text"], "label": LABEL2ID[d["label"]]} for d in train_data]
    )
    eval_ds = Dataset.from_list(
        [{"text": d["text"], "label": LABEL2ID[d["label"]]} for d in eval_data]
    )

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=len(INTENT_LABELS),
        id2label=ID2LABEL, label2id=LABEL2ID,
    )

    train_tok = train_ds.map(lambda x: tokenize(x, tokenizer), batched=True)
    eval_tok = eval_ds.map(lambda x: tokenize(x, tokenizer), batched=True)

    args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=lr,
        weight_decay=WEIGHT_DECAY,
        warmup_ratio=warmup_ratio,
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
        model=model, args=args,
        train_dataset=train_tok, eval_dataset=eval_tok,
        compute_metrics=compute_metrics,
    )

    start_time = time.time()
    trainer.train()
    train_time = time.time() - start_time

    eval_results = trainer.evaluate()

    # Adversarial 평가
    adv_texts = [d["text"] for d in adv_data]
    adv_labels = [d["label"] for d in adv_data]

    model.eval()
    model.to(device)
    adv_preds = []
    start_infer = time.time()
    for text in adv_texts:
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=MAX_LENGTH)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
        pred_id = torch.argmax(outputs.logits, dim=-1).item()
        adv_preds.append(ID2LABEL[pred_id])
    infer_time = (time.time() - start_infer) / len(adv_texts) * 1000  # ms per sample

    adv_acc = accuracy_score(adv_labels, adv_preds)
    adv_f1 = f1_score(adv_labels, adv_preds, average="macro", labels=INTENT_LABELS, zero_division=0)

    # cleanup
    if output_dir.exists():
        shutil.rmtree(output_dir)

    return {
        "eval_f1": round(eval_results["eval_f1_macro"], 4),
        "eval_acc": round(eval_results["eval_accuracy"], 4),
        "adv_acc": round(adv_acc, 4),
        "adv_f1": round(adv_f1, 4),
        "train_time": round(train_time, 1),
        "infer_ms": round(infer_time, 2),
    }, tokenizer, model, adv_preds, adv_labels


def save_best_model(tokenizer, model, model_name):
    """최종 모델 저장"""
    save_dir = MODEL_BASE / "intent_classifier"
    save_dir.mkdir(parents=True, exist_ok=True)

    tokenizer.save_pretrained(str(save_dir))
    model.save_pretrained(str(save_dir))
    label_map = {"id2label": ID2LABEL, "label2id": LABEL2ID}
    with open(save_dir / "label_map.json", "w", encoding="utf-8") as f:
        json.dump(label_map, f, ensure_ascii=False, indent=2)

    # 모델 정보 저장
    with open(save_dir / "model_info.json", "w", encoding="utf-8") as f:
        json.dump({"base_model": model_name, "experiment": "exp5"}, f, ensure_ascii=False, indent=2)

    print(f"  -> Model saved to {save_dir}")


# ── 시각화 ──

def plot_heatmap(model_name, results, filename):
    """lr × epochs 히트맵 (batch_size=best 기준)"""
    # batch_size별 best를 찾아서 가장 좋은 batch_size로 필터링
    best_batch = max(BATCH_LIST, key=lambda b: max(
        (r["adv_f1"] for r in results if r["batch_size"] == b), default=0
    ))

    filtered = [r for r in results if r["batch_size"] == best_batch]

    # 히트맵 데이터 구성
    heatmap_data = np.zeros((len(LR_LIST), len(EPOCHS_LIST)))
    for r in filtered:
        lr_idx = LR_LIST.index(r["lr"])
        ep_idx = EPOCHS_LIST.index(r["epochs"])
        heatmap_data[lr_idx][ep_idx] = r["adv_f1"]

    short_name = model_name.split("/")[-1]

    plt.figure(figsize=(8, 6))
    sns.heatmap(
        heatmap_data, annot=True, fmt=".3f", cmap="YlOrRd",
        xticklabels=EPOCHS_LIST,
        yticklabels=[f"{lr:.0e}" for lr in LR_LIST],
    )
    plt.title(f"{short_name} — Adversarial F1\n(batch={best_batch}, warmup={WARMUP_DEFAULT})")
    plt.xlabel("Epochs")
    plt.ylabel("Learning Rate")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


def plot_confusion(adv_preds, adv_labels, model_name, filename):
    """혼동행렬"""
    cm = confusion_matrix(adv_labels, adv_preds, labels=INTENT_LABELS)
    short_name = model_name.split("/")[-1]

    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=INTENT_LABELS, yticklabels=INTENT_LABELS)
    plt.title(f"Confusion Matrix — {short_name} Best Config\nAdversarial ({len(adv_labels)} samples)")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


def plot_model_comparison(model_results):
    """모델별 비교 차트 (4지표)"""
    models = list(model_results.keys())
    short_names = [m.split("/")[-1] for m in models]
    metrics = ["eval_f1", "eval_acc", "adv_acc", "adv_f1"]
    metric_labels = ["Eval F1", "Eval Acc", "Adv Acc", "Adv F1"]

    fig, axes = plt.subplots(1, 4, figsize=(18, 5))
    colors = ["#4C72B0", "#55A868", "#C44E52"]

    for ax, metric, label in zip(axes, metrics, metric_labels):
        values = [model_results[m]["best_result"][metric] for m in models]
        bars = ax.bar(short_names, values, color=colors[:len(models)])
        ax.set_title(label)
        ax.set_ylim(min(values) - 0.05, 1.0)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                    f"{val:.3f}", ha="center", va="bottom", fontsize=9)
        ax.tick_params(axis='x', rotation=15)

    plt.suptitle("Experiment 5: Model Comparison (Best Config)", fontsize=14)
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "model_comparison.png", dpi=150)
    plt.close()
    print("  -> model_comparison.png")


def plot_inference_speed(model_results):
    """추론 속도 비교"""
    models = list(model_results.keys())
    short_names = [m.split("/")[-1] for m in models]
    speeds = [model_results[m]["best_result"]["infer_ms"] for m in models]
    colors = ["#4C72B0", "#55A868", "#C44E52"]

    plt.figure(figsize=(8, 5))
    bars = plt.bar(short_names, speeds, color=colors[:len(models)])
    for bar, val in zip(bars, speeds):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                 f"{val:.1f}ms", ha="center", va="bottom")
    plt.title("Inference Speed Comparison (ms/sample)")
    plt.ylabel("ms per sample")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "inference_speed.png", dpi=150)
    plt.close()
    print("  -> inference_speed.png")


# ── 메인 ──

def load_existing_results():
    """기존 결과 로드 (resume 모드용)"""
    grid_path = RESULTS_DIR / "grid_search_full.json"
    comp_path = RESULTS_DIR / "model_comparison.json"

    existing_grid = []
    existing_models = {}

    if grid_path.exists():
        with open(grid_path, "r", encoding="utf-8") as f:
            existing_grid = json.load(f)
        print(f"  [Resume] 기존 grid 결과 로드: {len(existing_grid)}건")

    if comp_path.exists():
        with open(comp_path, "r", encoding="utf-8") as f:
            existing_models = json.load(f)
        print(f"  [Resume] 기존 model 결과 로드: {list(existing_models.keys())}")

    return existing_grid, existing_models


def get_completed_models(existing_grid):
    """이미 Step1+Step2 완료된 모델 목록 반환"""
    completed = set()
    for model_name in MODELS:
        step1 = [r for r in existing_grid if r.get("model") == model_name and r.get("step") == 1 and "error" not in r]
        step2 = [r for r in existing_grid if r.get("model") == model_name and r.get("step") == 2 and "error" not in r]
        if len(step1) >= len(EPOCHS_LIST) * len(LR_LIST) * len(BATCH_LIST) and len(step2) >= len(WARMUP_LIST):
            completed.add(model_name)
    return completed


def is_run_completed(existing_grid, model_name, epochs, lr, batch_size, warmup_ratio, step):
    """특정 (model, epochs, lr, batch, warmup, step) 조합이 이미 완료됐는지 확인"""
    for r in existing_grid:
        if (r.get("model") == model_name and r.get("epochs") == epochs
                and r.get("lr") == lr and r.get("batch_size") == batch_size
                and r.get("warmup_ratio") == warmup_ratio and r.get("step") == step
                and "error" not in r):
            return True, r
    return False, None


def save_grid_incremental(all_grid_results):
    """매 실행 후 JSON 즉시 저장 (크래시 방지)"""
    with open(RESULTS_DIR / "grid_search_full.json", "w", encoding="utf-8") as f:
        json.dump(all_grid_results, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step1-only", action="store_true", help="Step 1만 실행")
    parser.add_argument("--model", type=str, default=None, help="특정 모델만 실행")
    parser.add_argument("--resume", action="store_true", help="기존 결과 이어서 실행 (완료된 모델 건너뜀)")
    args = parser.parse_args()

    set_seed(SEED)

    target_models = [args.model] if args.model else MODELS

    print("=" * 70)
    print("  실험 5: 다중 모델 × 하이퍼파라미터 전탐색")
    print(f"  Device: {device}")
    print(f"  Models: {len(target_models)}")
    print(f"  Resume: {args.resume}")
    print(f"  Step 1: {len(EPOCHS_LIST)}×{len(LR_LIST)}×{len(BATCH_LIST)} = {len(EPOCHS_LIST)*len(LR_LIST)*len(BATCH_LIST)} per model")
    if not args.step1_only:
        print(f"  Step 2: {len(WARMUP_LIST)} warmup variations per model")
    print("=" * 70)

    # Resume: 기존 결과 로드
    all_grid_results = []
    model_results = {}
    skip_models = set()

    if args.resume:
        existing_grid, existing_models = load_existing_results()
        all_grid_results = existing_grid
        skip_models = get_completed_models(existing_grid)

        # 기존 완료 모델의 best 결과 복원
        for m_name, m_data in existing_models.items():
            if m_name in skip_models:
                model_results[m_name] = m_data
                print(f"  [Skip] {m_name} — 이미 완료 (Adv F1={m_data['best_result']['adv_f1']})")

    # 데이터 로드
    print("\n[Data] Loading v1.3 dataset...")
    all_data = load_all_data()
    train_data, eval_data = split_train_eval(all_data)
    adv_data = load_adversarial()
    print(f"  Train: {len(train_data)}, Eval: {len(eval_data)}, Adversarial: {len(adv_data)}")

    overall_best_f1 = 0
    overall_best_model = None
    overall_best_tok = None
    overall_best_model_obj = None

    # 기존 결과에서 overall best 초기화
    for m_name, m_data in model_results.items():
        if m_data.get("best_result") and m_data["best_result"]["adv_f1"] > overall_best_f1:
            overall_best_f1 = m_data["best_result"]["adv_f1"]
            overall_best_model = m_name

    for model_idx, model_name in enumerate(target_models):
        # Resume 모드에서 이미 완료된 모델 건너뛰기
        if model_name in skip_models:
            print(f"\n{'='*70}")
            print(f"  [{model_idx+1}/{len(target_models)}] {model_name} — SKIPPED (resume)")
            print(f"{'='*70}")
            continue
        short_name = model_name.split("/")[-1]
        print(f"\n{'='*70}")
        print(f"  [{model_idx+1}/{len(target_models)}] {model_name}")
        print(f"{'='*70}")

        # ── Step 1: 주요 파라미터 탐색 ──
        print(f"\n  [Step 1] Grid Search (warmup={WARMUP_DEFAULT})")
        grid = list(product(EPOCHS_LIST, LR_LIST, BATCH_LIST))
        step1_results = []
        best_f1 = 0
        best_config = None

        skipped_count = 0
        for i, (epochs, lr, batch_size) in enumerate(grid):
            # Resume: 이미 완료된 개별 실행 건너뛰기
            if args.resume:
                done, cached = is_run_completed(all_grid_results, model_name, epochs, lr, batch_size, WARMUP_DEFAULT, 1)
                if done:
                    step1_results.append(cached)
                    if cached["adv_f1"] > best_f1:
                        best_f1 = cached["adv_f1"]
                        best_config = {"epochs": epochs, "lr": lr, "batch_size": batch_size}
                    skipped_count += 1
                    continue

            print(f"\n    [{i+1}/{len(grid)}] epochs={epochs}, lr={lr:.0e}, batch={batch_size}", end=" ")
            output_dir = MODEL_BASE / f"exp5_temp_{short_name}_{i}"
            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                result, tok, model, _, _ = train_and_evaluate(
                    model_name, train_data, eval_data, adv_data,
                    epochs=epochs, lr=lr, batch_size=batch_size,
                    warmup_ratio=WARMUP_DEFAULT, output_dir=output_dir,
                )
                print(f"→ Eval F1={result['eval_f1']}, Adv F1={result['adv_f1']}")

                entry = {
                    "model": model_name,
                    "epochs": epochs, "lr": lr, "batch_size": batch_size,
                    "warmup_ratio": WARMUP_DEFAULT,
                    "step": 1,
                    **result,
                }
                step1_results.append(entry)
                all_grid_results.append(entry)
                save_grid_incremental(all_grid_results)  # 매 실행 후 즉시 저장

                if result["adv_f1"] > best_f1:
                    best_f1 = result["adv_f1"]
                    best_config = {"epochs": epochs, "lr": lr, "batch_size": batch_size}

            except Exception as e:
                print(f"→ ERROR: {e}")
                entry = {
                    "model": model_name,
                    "epochs": epochs, "lr": lr, "batch_size": batch_size,
                    "warmup_ratio": WARMUP_DEFAULT,
                    "step": 1, "error": str(e),
                }
                all_grid_results.append(entry)
                save_grid_incremental(all_grid_results)

        if skipped_count > 0:
            print(f"\n  [Resume] Step 1에서 {skipped_count}건 건너뜀")
        print(f"\n  Step 1 Best: {best_config}, Adv F1={best_f1}")

        # 히트맵
        plot_heatmap(model_name, step1_results, f"heatmap_{short_name}.png")

        # ── Step 2: warmup 미세조정 ──
        final_best_result = None
        final_best_tok = None
        final_best_model = None
        final_best_preds = None
        final_best_labels = None
        final_best_config = {**best_config, "warmup_ratio": WARMUP_DEFAULT} if best_config else None

        if not args.step1_only and best_config:
            print(f"\n  [Step 2] Warmup tuning on best config: {best_config}")
            best_f1_step2 = best_f1

            for warmup in WARMUP_LIST:
                # Resume: 이미 완료된 Step 2 건너뛰기
                if args.resume:
                    done, cached = is_run_completed(
                        all_grid_results, model_name,
                        best_config["epochs"], best_config["lr"], best_config["batch_size"],
                        warmup, 2,
                    )
                    if done:
                        if cached["adv_f1"] >= best_f1_step2:
                            best_f1_step2 = cached["adv_f1"]
                            final_best_config = {**best_config, "warmup_ratio": warmup}
                            final_best_result = cached
                        print(f"\n    warmup={warmup} → SKIPPED (resume, Adv F1={cached['adv_f1']})")
                        continue

                print(f"\n    warmup={warmup}", end=" ")
                output_dir = MODEL_BASE / f"exp5_temp_{short_name}_warmup"
                output_dir.mkdir(parents=True, exist_ok=True)

                try:
                    result, tok, model, adv_preds, adv_labels = train_and_evaluate(
                        model_name, train_data, eval_data, adv_data,
                        epochs=best_config["epochs"], lr=best_config["lr"],
                        batch_size=best_config["batch_size"],
                        warmup_ratio=warmup, output_dir=output_dir,
                    )
                    print(f"→ Eval F1={result['eval_f1']}, Adv F1={result['adv_f1']}")

                    entry = {
                        "model": model_name,
                        **best_config, "warmup_ratio": warmup,
                        "step": 2,
                        **result,
                    }
                    all_grid_results.append(entry)
                    save_grid_incremental(all_grid_results)

                    if result["adv_f1"] >= best_f1_step2:
                        best_f1_step2 = result["adv_f1"]
                        final_best_result = result
                        final_best_tok = tok
                        final_best_model = model
                        final_best_preds = adv_preds
                        final_best_labels = adv_labels
                        final_best_config = {**best_config, "warmup_ratio": warmup}

                except Exception as e:
                    print(f"→ ERROR: {e}")

            print(f"\n  Step 2 Best: warmup={final_best_config['warmup_ratio']}, Adv F1={best_f1_step2}")

        # Step 1 only인 경우 best config로 한 번 더 학습하여 모델 확보
        if final_best_result is None and best_config:
            print(f"\n  Re-training best config for model saving...")
            output_dir = MODEL_BASE / f"exp5_temp_{short_name}_final"
            output_dir.mkdir(parents=True, exist_ok=True)
            final_best_result, final_best_tok, final_best_model, final_best_preds, final_best_labels = (
                train_and_evaluate(
                    model_name, train_data, eval_data, adv_data,
                    epochs=best_config["epochs"], lr=best_config["lr"],
                    batch_size=best_config["batch_size"],
                    warmup_ratio=WARMUP_DEFAULT, output_dir=output_dir,
                )
            )

        # 혼동행렬
        if final_best_preds and final_best_labels:
            plot_confusion(final_best_preds, final_best_labels, model_name,
                           f"confusion_adv_{short_name}_exp5.png")

        model_results[model_name] = {
            "best_config": final_best_config,
            "best_result": final_best_result,
        }

        if final_best_result and final_best_result["adv_f1"] > overall_best_f1:
            overall_best_f1 = final_best_result["adv_f1"]
            overall_best_model = model_name
            overall_best_tok = final_best_tok
            overall_best_model_obj = final_best_model

    # ── 최종 결과 ──
    print(f"\n{'='*70}")
    print("  FINAL RESULTS")
    print(f"{'='*70}")

    for model_name, data in model_results.items():
        short = model_name.split("/")[-1]
        r = data.get("best_result")
        c = data.get("best_config")
        if not r or not c:
            print(f"\n  {short}: ALL FAILED (no successful training)")
            continue
        resumed = " (resumed)" if model_name in skip_models else ""
        print(f"\n  {short}{resumed}:")
        print(f"    Config: epochs={c['epochs']}, lr={c['lr']:.0e}, batch={c['batch_size']}, warmup={c['warmup_ratio']}")
        print(f"    Eval F1={r['eval_f1']}, Adv Acc={r['adv_acc']}, Adv F1={r['adv_f1']}, Speed={r['infer_ms']}ms")

    print(f"\n  OVERALL BEST: {overall_best_model} (Adv F1={overall_best_f1})")

    # 최종 모델 저장 (이번 세션에서 학습한 모델만)
    if overall_best_tok and overall_best_model_obj:
        save_best_model(overall_best_tok, overall_best_model_obj, overall_best_model)
    elif overall_best_model and overall_best_model in skip_models:
        print(f"  -> {overall_best_model}은 이전 세션에서 이미 저장됨 (skip)")

    # 차트 생성
    print("\n[Charts]")
    if len(model_results) > 1:
        plot_model_comparison(model_results)
        plot_inference_speed(model_results)

    # JSON 저장
    with open(RESULTS_DIR / "grid_search_full.json", "w", encoding="utf-8") as f:
        json.dump(all_grid_results, f, ensure_ascii=False, indent=2)
    print("  -> grid_search_full.json")

    # 모델별 best 요약
    summary = {}
    for model_name, data in model_results.items():
        summary[model_name] = {
            "best_config": data["best_config"],
            "best_result": data["best_result"],
        }
    with open(RESULTS_DIR / "model_comparison.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("  -> model_comparison.json")

    print(f"\n{'='*70}")
    print("  실험 5 완료!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
