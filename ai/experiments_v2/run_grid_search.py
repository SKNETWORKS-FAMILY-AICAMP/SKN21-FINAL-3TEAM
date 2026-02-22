"""
Stage 3: HP Grid Search — 최상위 모델 하이퍼파라미터 탐색

Stage 2에서 선정된 최상위 모델에 대해 32-point grid search를 수행하고,
Best config로 3-seed 안정성을 검증한다.

사용법:
    # 전체 실행 (baseline 결과에서 자동 선택)
    python ai/experiments_v2/run_grid_search.py

    # 특정 모델 지정
    python ai/experiments_v2/run_grid_search.py --model klue/bert-base

    # seed 안정성만 실행 (grid search 완료 후)
    python ai/experiments_v2/run_grid_search.py --seed-only

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
from itertools import product
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
from sklearn.metrics import accuracy_score, f1_score

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

# ── Intent 정의 ──
INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_qa",
]
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}
ID2LABEL = {i: label for i, label in enumerate(INTENT_LABELS)}

# ── Grid 범위 ──
EPOCHS_LIST = [3, 5, 7, 10]
LR_LIST = [1e-5, 2e-5, 3e-5, 5e-5]
BATCH_LIST = [16, 32]
WARMUP = 0.06
WEIGHT_DECAY = 0.01
MAX_LENGTH = 64

SEED_LIST = [42, 123, 456]

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


def train_single(model_name, train_data, val_data, epochs, lr, batch_size, seed):
    """단일 설정으로 학습 + 평가"""
    set_seed(seed)

    trust_remote = "distilkobert" in model_name
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=trust_remote)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=len(INTENT_LABELS),
        id2label=ID2LABEL, label2id=LABEL2ID,
        trust_remote_code=trust_remote,
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

    output_dir = CHECKPOINT_DIR / f"grid_{seed}_{epochs}_{lr}_{batch_size}"

    args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=lr,
        weight_decay=WEIGHT_DECAY,
        warmup_ratio=WARMUP,
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

    eval_results = trainer.evaluate()

    # cleanup
    if output_dir.exists():
        shutil.rmtree(output_dir)

    return {
        "epochs": epochs,
        "lr": lr,
        "batch_size": batch_size,
        "seed": seed,
        "val_f1": round(eval_results["eval_f1_macro"], 4),
        "val_acc": round(eval_results["eval_accuracy"], 4),
        "train_time_sec": round(train_time, 1),
    }


def select_best_model():
    """Stage 2 결과에서 최상위 모델 선택"""
    baseline_path = RESULTS_DIR / "baseline_results.json"
    if not baseline_path.exists():
        return None

    with open(baseline_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    best_key = max(results.keys(), key=lambda k: results[k].get("val_f1", 0))
    return results[best_key]["model"]


def run_grid_search(model_name, train_data, val_data):
    """32-point Grid Search"""
    print(f"\n  모델: {model_name}")
    print(f"  Grid: {len(EPOCHS_LIST)} epochs × {len(LR_LIST)} lr × {len(BATCH_LIST)} batch = "
          f"{len(EPOCHS_LIST) * len(LR_LIST) * len(BATCH_LIST)} runs")

    results_path = RESULTS_DIR / "grid_search_results.json"
    existing = []
    if results_path.exists():
        with open(results_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

    # 이미 완료된 설정 식별
    done_keys = set()
    for r in existing:
        done_keys.add(f"{r['epochs']}_{r['lr']}_{r['batch_size']}_{r['seed']}")

    grid = list(product(EPOCHS_LIST, LR_LIST, BATCH_LIST))
    total = len(grid)
    results = list(existing)

    for i, (epochs, lr, batch_size) in enumerate(grid, 1):
        key = f"{epochs}_{lr}_{batch_size}_42"
        if key in done_keys:
            print(f"  [{i}/{total}] ep={epochs} lr={lr:.0e} bs={batch_size} — skip")
            continue

        print(f"\n  [{i}/{total}] ep={epochs} lr={lr:.0e} bs={batch_size}")

        try:
            result = train_single(model_name, train_data, val_data, epochs, lr, batch_size, seed=42)
            result["model"] = model_name
            results.append(result)

            # 즉시 저장 (중단 시 이어쓰기)
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            print(f"    Val F1: {result['val_f1']:.4f}  ({result['train_time_sec']}s)")

        except Exception as e:
            print(f"    [ERROR] {e}")
            continue

    return results


def run_seed_stability(model_name, train_data, val_data, best_config):
    """Best config로 3-seed 안정성 검증"""
    print(f"\n  Best Config: ep={best_config['epochs']} lr={best_config['lr']:.0e} "
          f"bs={best_config['batch_size']}")

    results_path = RESULTS_DIR / "seed_stability_results.json"
    existing = []
    if results_path.exists():
        with open(results_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

    done_seeds = {r["seed"] for r in existing}
    results = list(existing)

    for seed in SEED_LIST:
        if seed in done_seeds:
            print(f"  Seed {seed} — skip")
            continue

        print(f"\n  Seed {seed}...")
        try:
            result = train_single(
                model_name, train_data, val_data,
                best_config["epochs"], best_config["lr"], best_config["batch_size"],
                seed=seed,
            )
            result["model"] = model_name
            results.append(result)

            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            print(f"    Seed {seed}: Val F1 = {result['val_f1']:.4f}")

        except Exception as e:
            print(f"    [ERROR] Seed {seed}: {e}")

    if results:
        f1_scores = [r["val_f1"] for r in results]
        print(f"\n  Seed 안정성: {np.mean(f1_scores):.4f} ± {np.std(f1_scores):.4f}")

    return results


# ── 시각화 ──

def plot_hp_heatmap(results, filename="hp_heatmap.png"):
    """lr × epochs Heatmap (best batch_size 기준)"""
    if not results:
        return

    # seed=42 결과만
    grid_results = [r for r in results if r.get("seed", 42) == 42]
    if not grid_results:
        return

    # best batch_size 찾기
    best_batch = max(BATCH_LIST, key=lambda b: max(
        (r["val_f1"] for r in grid_results if r["batch_size"] == b), default=0
    ))

    for batch_size in BATCH_LIST:
        filtered = [r for r in grid_results if r["batch_size"] == batch_size]
        if not filtered:
            continue

        heatmap = np.zeros((len(LR_LIST), len(EPOCHS_LIST)))
        for r in filtered:
            try:
                lr_idx = LR_LIST.index(r["lr"])
                ep_idx = EPOCHS_LIST.index(r["epochs"])
                heatmap[lr_idx][ep_idx] = r["val_f1"]
            except ValueError:
                continue

        plt.figure(figsize=(8, 6))
        sns.heatmap(
            heatmap, annot=True, fmt=".3f", cmap="YlOrRd",
            xticklabels=EPOCHS_LIST,
            yticklabels=[f"{lr:.0e}" for lr in LR_LIST],
        )
        plt.title(f"HP Grid Search — Val Macro F1\n(batch_size={batch_size})")
        plt.xlabel("Epochs")
        plt.ylabel("Learning Rate")
        plt.tight_layout()

        fname = f"hp_heatmap_bs{batch_size}.png"
        plt.savefig(RESULTS_DIR / fname, dpi=150)
        plt.close()
        print(f"  -> {fname}")


def plot_seed_stability(results, filename="seed_stability.png"):
    """Seed 안정성 Error Bar"""
    if not results:
        return

    seeds = [r["seed"] for r in results]
    f1_scores = [r["val_f1"] for r in results]
    mean_f1 = np.mean(f1_scores)
    std_f1 = np.std(f1_scores)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(range(len(seeds)), f1_scores, color="#4A90D9", alpha=0.7)
    ax.axhline(y=mean_f1, color="red", linestyle="--", label=f"Mean: {mean_f1:.4f}")
    ax.fill_between([-0.5, len(seeds) - 0.5], mean_f1 - std_f1, mean_f1 + std_f1,
                     alpha=0.2, color="red", label=f"±std: {std_f1:.4f}")
    ax.set_xticks(range(len(seeds)))
    ax.set_xticklabels([f"Seed {s}" for s in seeds])
    ax.set_ylabel("Val Macro F1")
    ax.set_title("Seed Stability (Best Config)")
    ax.legend()
    ax.set_ylim(max(0, min(f1_scores) - 0.05), min(1.0, max(f1_scores) + 0.05))
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


# ── 메인 ──

def main():
    parser = argparse.ArgumentParser(description="Stage 3: HP Grid Search")
    parser.add_argument("--model", type=str, default=None, help="모델 지정 (없으면 Stage 2 최상위)")
    parser.add_argument("--seed-only", action="store_true", help="Seed 안정성만 실행")
    parser.add_argument("--skip-plots", action="store_true", help="차트 건너뛰기")
    args = parser.parse_args()

    print("=" * 60)
    print("  Stage 3: HP Grid Search")
    print("=" * 60)
    print(f"  Device: {device}")

    # 모델 선택
    model_name = args.model or select_best_model()
    if not model_name:
        print("\n[ERROR] 모델을 선택할 수 없습니다.")
        print("  --model로 지정하거나 먼저 run_baseline.py를 실행하세요.")
        return

    print(f"  Model: {model_name}")

    # 데이터 로드
    if not (SPLITS_DIR / "train.jsonl").exists():
        print("\n[ERROR] 학습 데이터 없음. generate_data.py --step split 먼저 실행")
        return

    train_data = load_jsonl(SPLITS_DIR / "train.jsonl")
    val_data = load_jsonl(SPLITS_DIR / "val.jsonl")
    print(f"  Train: {len(train_data)}  Val: {len(val_data)}")

    grid_results = []

    if not args.seed_only:
        # Grid Search
        print("\n" + "=" * 60)
        print("  Grid Search (32 runs)")
        print("=" * 60)

        grid_results = run_grid_search(model_name, train_data, val_data)

        # Best config
        if grid_results:
            best = max(grid_results, key=lambda r: r["val_f1"])
            print(f"\n  Best: ep={best['epochs']} lr={best['lr']:.0e} "
                  f"bs={best['batch_size']} → Val F1: {best['val_f1']:.4f}")

    # Best config 결정
    grid_path = RESULTS_DIR / "grid_search_results.json"
    if grid_path.exists():
        with open(grid_path, "r", encoding="utf-8") as f:
            grid_results = json.load(f)

    if not grid_results:
        print("\n[ERROR] Grid search 결과 없음.")
        return

    best = max(grid_results, key=lambda r: r["val_f1"])
    best_config = {"epochs": best["epochs"], "lr": best["lr"], "batch_size": best["batch_size"]}

    # Seed 안정성
    print("\n" + "=" * 60)
    print("  Seed 안정성 검증")
    print("=" * 60)

    seed_results = run_seed_stability(model_name, train_data, val_data, best_config)

    # 차트
    if not args.skip_plots:
        print("\n--- 차트 생성 ---")
        plot_hp_heatmap(grid_results)
        plot_seed_stability(seed_results)

    # 최종 요약
    print("\n" + "=" * 60)
    print("  Stage 3 완료!")
    print(f"  Best Config: ep={best_config['epochs']} lr={best_config['lr']:.0e} bs={best_config['batch_size']}")
    if seed_results:
        f1s = [r["val_f1"] for r in seed_results]
        print(f"  Seed 안정성: {np.mean(f1s):.4f} ± {np.std(f1s):.4f}")
    print(f"  결과: {RESULTS_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
