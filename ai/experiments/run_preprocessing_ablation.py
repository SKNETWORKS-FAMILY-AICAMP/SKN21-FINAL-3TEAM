"""
실험 6: 전처리 파이프라인 Ablation Study + Seed 안정성 검증

실험 5에서 확정된 최적 모델에 전처리를 적용하여 최종 성능 상한선을 확인한다.
모델 자체는 재학습하지 않고, 추론 시 입력에만 전처리를 적용.

사용법:
    # 기본 실행 (실험 5 best 모델 사용)
    python ai/experiments/run_preprocessing_ablation.py

    # 특정 모델 + config 지정
    python ai/experiments/run_preprocessing_ablation.py \
        --model klue/bert-base --epochs 5 --lr 2e-5 --batch 16 --warmup 0.06

    # seed 반복 없이 빠르게
    python ai/experiments/run_preprocessing_ablation.py --no-seed-repeat

실행 환경: RunPod GPU
사전: pip install transformers datasets accelerate matplotlib seaborn scikit-learn
"""

import argparse
import json
import random
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
    accuracy_score, f1_score, confusion_matrix,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from preprocessing import preprocess, ABLATION_CONFIGS

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "intent"
MODEL_BASE = BASE_DIR / "ai" / "models"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate",
    "meeting_generate", "schedule_add", "schedule_view", "general",
]
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}
ID2LABEL = {i: label for i, label in enumerate(INTENT_LABELS)}

MAX_LENGTH = 64
WEIGHT_DECAY = 0.01
SEEDS = [42, 123, 456]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def set_seed(seed):
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
    all_data = []
    for label in INTENT_LABELS:
        path = DATA_DIR / f"{label}.jsonl"
        if path.exists():
            all_data.extend(load_jsonl(path))
    for version in ["v12", "v13"]:
        for path in sorted(DATA_DIR.glob(f"augment_{version}_*.jsonl")):
            all_data.extend(load_jsonl(path))
    return all_data


def split_train_eval(data, eval_ratio=0.15, seed=42):
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
    with open(DATA_DIR / "adversarial_test.json", "r", encoding="utf-8") as f:
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


def train_model(model_name, train_data, eval_data, epochs, lr, batch_size, warmup_ratio, seed, output_dir):
    """모델 학습 (seed별로 다르게)"""
    set_seed(seed)

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
        train_dataset=train_tok, eval_dataset=eval_tok,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    return tokenizer, model


def evaluate_with_preprocessing(tokenizer, model, test_data, config):
    """전처리 적용 후 평가"""
    model.eval()
    model.to(device)

    texts_orig = [d["text"] for d in test_data]
    labels = [d["label"] for d in test_data]

    # 전처리 적용
    texts = [preprocess(t, config) for t in texts_orig]

    preds = []
    for text in texts:
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=MAX_LENGTH)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
        pred_id = torch.argmax(outputs.logits, dim=-1).item()
        preds.append(ID2LABEL[pred_id])

    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, average="macro", labels=INTENT_LABELS, zero_division=0)

    return {
        "accuracy": round(acc, 4),
        "f1_macro": round(f1, 4),
    }, preds, labels


# ── 시각화 ──

def plot_ablation(results):
    """전처리 단계별 성능 변화 차트"""
    configs = ["A", "B", "C", "D", "E"]
    config_labels = [
        "A: None",
        "B: +P4(clean)",
        "C: +P1(spell)",
        "D: +P2(chosung)",
        "E: +P3(slang)",
    ]

    # seed별 데이터 수집
    eval_f1s = {c: [] for c in configs}
    adv_accs = {c: [] for c in configs}
    adv_f1s = {c: [] for c in configs}

    for entry in results:
        c = entry["config"]
        eval_f1s[c].append(entry["eval_f1"])
        adv_accs[c].append(entry["adv_acc"])
        adv_f1s[c].append(entry["adv_f1"])

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    for ax, data, title in zip(
        axes,
        [eval_f1s, adv_accs, adv_f1s],
        ["Eval F1 (macro)", "Adversarial Accuracy", "Adversarial F1 (macro)"],
    ):
        means = [np.mean(data[c]) for c in configs]
        stds = [np.std(data[c]) for c in configs]

        bars = ax.bar(config_labels, means, yerr=stds, capsize=5,
                       color=["#cccccc", "#a8d8ea", "#6bb3d9", "#3d8eb9", "#1a5276"],
                       edgecolor="black", linewidth=0.5)
        ax.set_title(title)
        ax.set_ylim(min(means) - 0.05, 1.0)
        for bar, mean, std in zip(bars, means, stds):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + std + 0.005,
                    f"{mean:.3f}", ha="center", va="bottom", fontsize=8)
        ax.tick_params(axis='x', rotation=20)

    plt.suptitle("Experiment 6: Preprocessing Ablation Study", fontsize=14)
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "preprocessing_ablation.png", dpi=150)
    plt.close()
    print("  -> preprocessing_ablation.png")


def plot_seed_stability(results):
    """seed별 안정성 차트"""
    configs = ["A", "B", "C", "D", "E"]

    # seed별 adv_f1 수집
    seed_data = {}
    for entry in results:
        seed = entry["seed"]
        config = entry["config"]
        if seed not in seed_data:
            seed_data[seed] = {}
        seed_data[seed][config] = entry["adv_f1"]

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(configs))
    width = 0.25
    colors = ["#4C72B0", "#55A868", "#C44E52"]

    for i, (seed, data) in enumerate(sorted(seed_data.items())):
        values = [data.get(c, 0) for c in configs]
        ax.bar(x + i * width, values, width, label=f"seed={seed}", color=colors[i])

    ax.set_xlabel("Config")
    ax.set_ylabel("Adversarial F1")
    ax.set_title("Seed Stability — Adversarial F1 by Config")
    ax.set_xticks(x + width)
    ax.set_xticklabels(configs)
    ax.legend()
    ax.set_ylim(0.8, 1.0)
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "seed_stability.png", dpi=150)
    plt.close()
    print("  -> seed_stability.png")


def plot_final_confusion(preds, labels, config_name):
    """최종 혼동행렬"""
    cm = confusion_matrix(labels, preds, labels=INTENT_LABELS)
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=INTENT_LABELS, yticklabels=INTENT_LABELS)
    plt.title(f"Final Confusion Matrix — Config {config_name} (Full Preprocessing)\n"
              f"Adversarial ({len(labels)} samples)")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "final_confusion_adv.png", dpi=150)
    plt.close()
    print("  -> final_confusion_adv.png")


# ── 메인 ──

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default=None, help="모델 이름 (미지정시 실험5 결과에서 로드)")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--warmup", type=float, default=None)
    parser.add_argument("--no-seed-repeat", action="store_true", help="seed 반복 없이 42만 사용")
    args = parser.parse_args()

    # 실험 5 결과에서 best config 로드
    model_comp_path = RESULTS_DIR / "model_comparison.json"
    if args.model and args.epochs and args.lr and args.batch and args.warmup is not None:
        model_name = args.model
        best_config = {
            "epochs": args.epochs, "lr": args.lr,
            "batch_size": args.batch, "warmup_ratio": args.warmup,
        }
    elif model_comp_path.exists():
        with open(model_comp_path, "r", encoding="utf-8") as f:
            model_comp = json.load(f)
        # Adv F1 기준 best 모델 찾기
        best_entry = max(model_comp.items(), key=lambda x: x[1]["best_result"]["adv_f1"])
        model_name = best_entry[0]
        best_config = best_entry[1]["best_config"]
        print(f"  실험 5 결과에서 best 모델 로드: {model_name}")
    else:
        # 기본값 (실험 5 미실행 시)
        model_name = "klue/bert-base"
        best_config = {"epochs": 5, "lr": 2e-5, "batch_size": 16, "warmup_ratio": 0.06}
        print(f"  실험 5 결과 없음 → 기본값 사용: {model_name}")

    seeds = [42] if args.no_seed_repeat else SEEDS

    print("=" * 70)
    print("  실험 6: 전처리 Ablation Study + Seed 안정성 검증")
    print(f"  Device: {device}")
    print(f"  Model: {model_name}")
    print(f"  Config: epochs={best_config['epochs']}, lr={best_config['lr']}, "
          f"batch={best_config['batch_size']}, warmup={best_config['warmup_ratio']}")
    print(f"  Seeds: {seeds}")
    print("  Configs: A(none), B(P4), C(P4+P1), D(P4+P1+P2), E(all)")
    print("=" * 70)

    # 데이터 로드
    print("\n[Data] Loading v1.3 dataset...")
    all_data = load_all_data()
    adv_data = load_adversarial()

    all_results = []
    final_best_preds = None
    final_best_labels = None

    for seed_idx, seed in enumerate(seeds):
        print(f"\n{'='*50}")
        print(f"  Seed {seed} [{seed_idx+1}/{len(seeds)}]")
        print(f"{'='*50}")

        # seed별 train/eval 분할 + 학습
        train_data, eval_data = split_train_eval(all_data, seed=seed)
        print(f"  Train: {len(train_data)}, Eval: {len(eval_data)}")

        output_dir = MODEL_BASE / f"exp6_temp_seed{seed}"
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"  Training model (seed={seed})...")
        tokenizer, model = train_model(
            model_name, train_data, eval_data,
            epochs=best_config["epochs"], lr=best_config["lr"],
            batch_size=best_config["batch_size"], warmup_ratio=best_config["warmup_ratio"],
            seed=seed, output_dir=output_dir,
        )

        # cleanup training artifacts
        if output_dir.exists():
            shutil.rmtree(output_dir)

        # 각 전처리 config로 평가
        for config_name, config in ABLATION_CONFIGS.items():
            print(f"\n  Config {config_name}: ", end="")

            # Eval
            eval_result, _, _ = evaluate_with_preprocessing(tokenizer, model, eval_data, config)

            # Adversarial
            adv_result, adv_preds, adv_labels = evaluate_with_preprocessing(tokenizer, model, adv_data, config)

            entry = {
                "seed": seed,
                "config": config_name,
                "eval_f1": eval_result["f1_macro"],
                "eval_acc": eval_result["accuracy"],
                "adv_acc": adv_result["accuracy"],
                "adv_f1": adv_result["f1_macro"],
            }
            all_results.append(entry)
            print(f"Eval F1={eval_result['f1_macro']}, Adv Acc={adv_result['accuracy']}, Adv F1={adv_result['f1_macro']}")

            # 최종 (Config E, seed=42)용 저장
            if config_name == "E" and seed == 42:
                final_best_preds = adv_preds
                final_best_labels = adv_labels

    # ── 결과 요약 ──
    print(f"\n{'='*70}")
    print("  RESULTS SUMMARY")
    print(f"{'='*70}")

    configs = ["A", "B", "C", "D", "E"]
    config_desc = {
        "A": "None (baseline)",
        "B": "+P4 (clean)",
        "C": "+P4+P1 (spell)",
        "D": "+P4+P1+P2 (chosung)",
        "E": "Full (all)",
    }

    print(f"\n  {'Config':<25} {'Eval F1':>10} {'Adv Acc':>10} {'Adv F1':>10}")
    print(f"  {'-'*55}")

    for c in configs:
        entries = [r for r in all_results if r["config"] == c]
        eval_f1s = [r["eval_f1"] for r in entries]
        adv_accs = [r["adv_acc"] for r in entries]
        adv_f1s = [r["adv_f1"] for r in entries]

        if len(seeds) > 1:
            eval_str = f"{np.mean(eval_f1s):.4f}±{np.std(eval_f1s):.4f}"
            adv_acc_str = f"{np.mean(adv_accs):.4f}±{np.std(adv_accs):.4f}"
            adv_f1_str = f"{np.mean(adv_f1s):.4f}±{np.std(adv_f1s):.4f}"
        else:
            eval_str = f"{eval_f1s[0]:.4f}"
            adv_acc_str = f"{adv_accs[0]:.4f}"
            adv_f1_str = f"{adv_f1s[0]:.4f}"

        print(f"  {c}: {config_desc[c]:<20} {eval_str:>10} {adv_acc_str:>10} {adv_f1_str:>10}")

    # ── 차트 ──
    print("\n[Charts]")
    plot_ablation(all_results)
    if len(seeds) > 1:
        plot_seed_stability(all_results)
    if final_best_preds and final_best_labels:
        plot_final_confusion(final_best_preds, final_best_labels, "E")

    # ── JSON 저장 ──
    with open(RESULTS_DIR / "preprocessing_ablation.json", "w", encoding="utf-8") as f:
        json.dump({
            "model": model_name,
            "config": best_config,
            "seeds": seeds,
            "results": all_results,
        }, f, ensure_ascii=False, indent=2)
    print("  -> preprocessing_ablation.json")

    print(f"\n{'='*70}")
    print("  실험 6 완료!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
