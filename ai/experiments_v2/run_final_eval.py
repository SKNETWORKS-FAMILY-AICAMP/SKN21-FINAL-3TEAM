"""
Stage 4: 최종 평가 — Hold-out test, Adversarial, 전처리 Ablation, 속도 측정

Stage 3에서 확정된 best config로 3개 모델을 최종 학습하고,
다양한 테스트셋 + 전처리 ablation + 추론 속도를 종합 평가한다.

사용법:
    python ai/experiments_v2/run_final_eval.py
    python ai/experiments_v2/run_final_eval.py --model klue/bert-base --skip-ablation
    python ai/experiments_v2/run_final_eval.py --speed-only

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
LEGACY_DIR = BASE_DIR / "data" / "training" / "intent"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR = Path(__file__).resolve().parent / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
FINAL_MODEL_DIR = BASE_DIR / "ai" / "models" / "intent_classifier"

# ── Intent 정의 ──
INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_qa",
]
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}
ID2LABEL = {i: label for i, label in enumerate(INTENT_LABELS)}

# 이전 실험 intent (레거시 호환)
LEGACY_LABELS = [
    "judgment", "doc_search", "doc_generate",
    "meeting_generate", "schedule_add", "schedule_view", "general",
]

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


# ── Best Config 로드 ──

def load_best_config():
    """Stage 3 결과에서 best config 로드"""
    grid_path = RESULTS_DIR / "grid_search_results.json"
    baseline_path = RESULTS_DIR / "baseline_results.json"

    # Grid search 결과가 있으면 사용
    if grid_path.exists():
        with open(grid_path, "r", encoding="utf-8") as f:
            results = json.load(f)
        if results:
            best = max(results, key=lambda r: r["val_f1"])
            return {
                "model": best.get("model"),
                "epochs": best["epochs"],
                "lr": best["lr"],
                "batch_size": best["batch_size"],
            }

    # 없으면 baseline 기본 HP
    return {
        "model": None,
        "epochs": 5,
        "lr": 2e-5,
        "batch_size": 16,
    }


# ── 학습 ──

def train_final_model(model_name, train_data, val_data, config, seed=42):
    """최종 모델 학습"""
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

    output_dir = CHECKPOINT_DIR / f"final_{model_name.split('/')[-1]}_seed{seed}"

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

    # cleanup checkpoint
    if output_dir.exists():
        shutil.rmtree(output_dir)

    return model, tokenizer, train_time


def evaluate_dataset(model, tokenizer, data, label_list=None):
    """데이터셋 평가 → 메트릭 + preds + labels + confidences"""
    if label_list is None:
        label_list = INTENT_LABELS

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
        probs = torch.softmax(outputs.logits, dim=-1)
        pred_id = torch.argmax(probs, dim=-1).item()
        preds.append(ID2LABEL[pred_id])
        confidences.append(probs[0][pred_id].item())

    # 유효 라벨만 필터링
    valid_labels = [l for l in label_list if l in set(labels) | set(preds)]

    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, average="macro", labels=valid_labels, zero_division=0)

    report = classification_report(labels, preds, labels=valid_labels, output_dict=True, zero_division=0)

    return {
        "accuracy": round(acc, 4),
        "f1_macro": round(f1, 4),
        "per_class": {
            l: {"p": round(report[l]["precision"], 4), "r": round(report[l]["recall"], 4),
                "f1": round(report[l]["f1-score"], 4)}
            for l in valid_labels if l in report
        },
        "mean_confidence": round(np.mean(confidences), 4),
    }, preds, labels, confidences


# ── 전처리 Ablation ──

def run_preprocess_ablation(model, tokenizer, test_data):
    """전처리 설정 A~E로 ablation 실험"""
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR))
        from ai.agents.preprocessing import preprocess, ABLATION_CONFIGS
    except ImportError:
        print("  [SKIP] preprocessing 모듈 로드 실패")
        return {}

    results = {}
    for config_name, config in ABLATION_CONFIGS.items():
        processed_data = []
        for d in test_data:
            processed_text = preprocess(d["text"], config)
            processed_data.append({"text": processed_text, "label": d["label"]})

        metrics, _, _, _ = evaluate_dataset(model, tokenizer, processed_data)
        results[config_name] = metrics
        print(f"    Config {config_name}: F1={metrics['f1_macro']:.4f} Acc={metrics['accuracy']:.4f}")

    return results


# ── 추론 속도 측정 ──

def measure_inference_speed(model, tokenizer, n_warmup=100, n_measure=1000):
    """추론 지연시간 측정 (mean, p95)"""
    model.eval()
    model.to(device)

    test_sentences = [
        "내일 3시에 팀미팅 잡아줘",
        "연차 써도 돼?",
        "보고서 작성해줘",
        "이번주 일정 보여줘",
        "이 문서 요약해줘",
        "출장비 규정 찾아줘",
        "안녕하세요",
        "이 보고서에서 예산이 얼마야?",
    ]

    # Warmup
    for i in range(n_warmup):
        text = test_sentences[i % len(test_sentences)]
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=MAX_LENGTH)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            model(**inputs)

    # Measure
    latencies = []
    for i in range(n_measure):
        text = test_sentences[i % len(test_sentences)]
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=MAX_LENGTH)
        inputs = {k: v.to(device) for k, v in inputs.items()}

        start = time.perf_counter()
        with torch.no_grad():
            model(**inputs)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        latencies.append(elapsed)

    # Batch throughput
    batch_texts = test_sentences * 4  # 32개
    inputs = tokenizer(batch_texts, return_tensors="pt", padding=True, truncation=True, max_length=MAX_LENGTH)
    inputs = {k: v.to(device) for k, v in inputs.items()}

    start = time.perf_counter()
    with torch.no_grad():
        model(**inputs)
    batch_time = time.perf_counter() - start
    throughput = len(batch_texts) / batch_time

    return {
        "mean_ms": round(np.mean(latencies), 3),
        "p50_ms": round(np.percentile(latencies, 50), 3),
        "p95_ms": round(np.percentile(latencies, 95), 3),
        "p99_ms": round(np.percentile(latencies, 99), 3),
        "throughput_per_sec": round(throughput, 1),
    }


def measure_model_size(model):
    """모델 크기 측정"""
    param_count = sum(p.numel() for p in model.parameters())
    size_mb = sum(p.numel() * p.element_size() for p in model.parameters()) / 1024 / 1024

    gpu_mem = 0
    if torch.cuda.is_available():
        gpu_mem = torch.cuda.max_memory_allocated() / 1024 / 1024

    return {
        "param_count_m": round(param_count / 1e6, 1),
        "model_size_mb": round(size_mb, 1),
        "gpu_peak_mb": round(gpu_mem, 1),
    }


# ── 통계 검증 ──

def mcnemar_test(labels, preds_a, preds_b, name_a, name_b):
    """McNemar's Test"""
    n01 = sum(1 for l, a, b in zip(labels, preds_a, preds_b) if a == l and b != l)
    n10 = sum(1 for l, a, b in zip(labels, preds_a, preds_b) if a != l and b == l)

    if n01 + n10 == 0:
        return {"chi2": 0, "p_value": 1.0, "significant": False}

    from scipy import stats
    chi2 = (abs(n01 - n10) - 1) ** 2 / (n01 + n10)
    p_value = 1 - stats.chi2.cdf(chi2, df=1)

    return {
        "n01": n01, "n10": n10,
        "chi2": round(chi2, 4),
        "p_value": round(p_value, 6),
        "significant": p_value < 0.05,
        "comparison": f"{name_a} vs {name_b}",
    }


def bootstrap_ci(labels, preds, n_bootstrap=10000, ci=0.95):
    """Bootstrap 95% CI for F1"""
    from scipy import stats as sp_stats

    f1_scores = []
    n = len(labels)
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, n, replace=True)
        sampled_labels = [labels[i] for i in idx]
        sampled_preds = [preds[i] for i in idx]
        f1 = f1_score(sampled_labels, sampled_preds, average="macro",
                       labels=INTENT_LABELS, zero_division=0)
        f1_scores.append(f1)

    alpha = 1 - ci
    lower = np.percentile(f1_scores, 100 * alpha / 2)
    upper = np.percentile(f1_scores, 100 * (1 - alpha / 2))

    return {
        "mean": round(np.mean(f1_scores), 4),
        "ci_lower": round(lower, 4),
        "ci_upper": round(upper, 4),
        "std": round(np.std(f1_scores), 4),
    }


# ── 모델 저장 ──

def save_final_model(model, tokenizer, model_name):
    """최종 모델을 서비스 디렉토리에 저장"""
    FINAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    tokenizer.save_pretrained(str(FINAL_MODEL_DIR))
    model.save_pretrained(str(FINAL_MODEL_DIR))

    label_map = {"id2label": ID2LABEL, "label2id": LABEL2ID}
    with open(FINAL_MODEL_DIR / "label_map.json", "w", encoding="utf-8") as f:
        json.dump(label_map, f, ensure_ascii=False, indent=2)

    with open(FINAL_MODEL_DIR / "model_info.json", "w", encoding="utf-8") as f:
        json.dump({
            "base_model": model_name,
            "experiment": "v2_stage4",
            "intents": INTENT_LABELS,
        }, f, ensure_ascii=False, indent=2)

    print(f"  -> 최종 모델 저장: {FINAL_MODEL_DIR}")


# ── 시각화 ──

def plot_confusion(preds, labels, model_name, dataset_name, filename):
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


def plot_f1_vs_speed(all_model_results, filename="f1_vs_speed.png"):
    """F1 vs 추론속도 vs 모델크기 Scatter"""
    fig, ax = plt.subplots(figsize=(8, 6))

    for model_name, data in all_model_results.items():
        short = model_name.split("/")[-1]
        f1 = data.get("test_f1", data.get("val_f1", 0))
        speed = data.get("speed", {}).get("mean_ms", 0)
        size = data.get("size", {}).get("param_count_m", 10)

        ax.scatter(speed, f1, s=size * 3, alpha=0.7, label=f"{short} ({size}M)")
        ax.annotate(short, (speed, f1), textcoords="offset points", xytext=(5, 5), fontsize=9)

    ax.set_xlabel("Inference Latency (ms)")
    ax.set_ylabel("Test Macro F1")
    ax.set_title("F1 vs Speed vs Model Size")
    ax.legend()
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


def plot_ablation(ablation_results, filename="preprocess_ablation.png"):
    """전처리 Ablation Bar Chart"""
    configs = list(ablation_results.keys())
    f1_scores = [ablation_results[c]["f1_macro"] for c in configs]

    config_labels = {
        "A": "None",
        "B": "+Clean",
        "C": "+Spell",
        "D": "+Chosung",
        "E": "+Slang (All)",
    }

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ["#ccc", "#FFB74D", "#4FC3F7", "#81C784", "#4A90D9"]
    bars = ax.bar(range(len(configs)), f1_scores, color=colors[:len(configs)])

    ax.set_xticks(range(len(configs)))
    ax.set_xticklabels([f"Config {c}\n{config_labels.get(c, '')}" for c in configs])
    ax.set_ylabel("Macro F1")
    ax.set_title("Preprocessing Ablation Study")
    ax.set_ylim(min(f1_scores) - 0.05, max(f1_scores) + 0.03)

    for bar, val in zip(bars, f1_scores):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"{val:.3f}", ha="center", fontsize=10)

    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


def plot_confidence_distribution(confidences, model_name, filename="confidence_dist.png"):
    """Confidence 분포 Histogram"""
    plt.figure(figsize=(8, 5))
    plt.hist(confidences, bins=50, color="#4A90D9", alpha=0.7, edgecolor="black")
    plt.axvline(np.mean(confidences), color="red", linestyle="--",
                label=f"Mean: {np.mean(confidences):.3f}")
    plt.xlabel("Confidence")
    plt.ylabel("Count")
    plt.title(f"Confidence Distribution — {model_name.split('/')[-1]}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


def plot_speed_comparison(all_speed, filename="speed_comparison.png"):
    """추론 속도 비교 Bar Chart"""
    models = list(all_speed.keys())
    means = [all_speed[m]["mean_ms"] for m in models]
    p95s = [all_speed[m]["p95_ms"] for m in models]

    x = np.arange(len(models))
    width = 0.35
    short_names = [m.split("/")[-1] for m in models]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - width / 2, means, width, label="Mean", color="#4A90D9")
    ax.bar(x + width / 2, p95s, width, label="P95", color="#D96459")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Inference Latency Comparison")
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, rotation=15)
    ax.legend()
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


# ── 메인 ──

MODELS = [
    "klue/bert-base",
    "monologg/koelectra-base-v3-discriminator",
    "monologg/distilkobert",
]


def main():
    parser = argparse.ArgumentParser(description="Stage 4: 최종 평가")
    parser.add_argument("--model", type=str, default=None, help="특정 모델만")
    parser.add_argument("--skip-ablation", action="store_true")
    parser.add_argument("--skip-stats", action="store_true")
    parser.add_argument("--speed-only", action="store_true")
    parser.add_argument("--save-model", action="store_true", help="최종 모델 서비스 디렉토리에 저장")
    args = parser.parse_args()

    print("=" * 60)
    print("  Stage 4: 최종 평가")
    print("=" * 60)
    print(f"  Device: {device}")

    # Best config 로드
    config = load_best_config()
    print(f"  Config: ep={config['epochs']} lr={config['lr']:.0e} bs={config['batch_size']}")

    # 데이터 로드
    train_data = load_jsonl(SPLITS_DIR / "train.jsonl")
    val_data = load_jsonl(SPLITS_DIR / "val.jsonl")
    test_data = load_jsonl(SPLITS_DIR / "test.jsonl")

    adv_path = DATA_DIR / "adversarial_v2.json"
    adv_data = []
    if adv_path.exists():
        with open(adv_path, "r", encoding="utf-8") as f:
            adv_data = json.load(f)

    print(f"  Train: {len(train_data)} | Val: {len(val_data)} | Test: {len(test_data)} | Adv: {len(adv_data)}")

    # 결과 저장
    final_results = {}
    all_test_preds = {}
    all_speed = {}
    models = [args.model] if args.model else MODELS

    for model_name in models:
        short = model_name.split("/")[-1]
        print(f"\n{'=' * 60}")
        print(f"  {model_name}")
        print(f"{'=' * 60}")

        if args.speed_only:
            # 속도만 측정 (모델 로드 후 바로)
            trust_remote = "distilkobert" in model_name
            tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=trust_remote)
            model = AutoModelForSequenceClassification.from_pretrained(
                model_name, num_labels=len(INTENT_LABELS),
                id2label=ID2LABEL, label2id=LABEL2ID,
                trust_remote_code=trust_remote,
            )
            speed = measure_inference_speed(model, tokenizer)
            all_speed[model_name] = speed
            print(f"  Speed: mean={speed['mean_ms']}ms p95={speed['p95_ms']}ms")
            continue

        # 최종 학습
        print("\n  학습 중...")
        model, tokenizer, train_time = train_final_model(
            model_name, train_data, val_data, config,
        )

        model_results = {"model": model_name, "train_time_sec": round(train_time, 1)}

        # 4.1 Hold-out Test (최초 1회)
        print("  Hold-out Test 평가...")
        test_metrics, test_preds, test_labels, test_conf = evaluate_dataset(model, tokenizer, test_data)
        model_results["test_f1"] = test_metrics["f1_macro"]
        model_results["test_acc"] = test_metrics["accuracy"]
        model_results["test_per_class"] = test_metrics["per_class"]
        all_test_preds[model_name] = (test_preds, test_labels)
        print(f"    Test F1: {test_metrics['f1_macro']:.4f}  Acc: {test_metrics['accuracy']:.4f}")

        # 4.2 Adversarial 평가
        if adv_data:
            print("  Adversarial 평가...")
            adv_metrics, adv_preds, adv_labels, _ = evaluate_dataset(model, tokenizer, adv_data)
            model_results["adv_f1"] = adv_metrics["f1_macro"]
            model_results["adv_acc"] = adv_metrics["accuracy"]
            model_results["adv_per_class"] = adv_metrics["per_class"]
            print(f"    Adv F1: {adv_metrics['f1_macro']:.4f}  Acc: {adv_metrics['accuracy']:.4f}")

            # Confusion matrix
            plot_confusion(adv_preds, adv_labels, model_name, "Adversarial",
                           f"confusion_{short}_adv.png")

        # 4.4 전처리 Ablation
        if not args.skip_ablation:
            print("  전처리 Ablation...")
            ablation = run_preprocess_ablation(model, tokenizer, test_data)
            model_results["preprocess_ablation"] = ablation
            if ablation:
                plot_ablation(ablation, f"ablation_{short}.png")

        # 4.5 속도 + 크기
        print("  속도 측정...")
        speed = measure_inference_speed(model, tokenizer)
        size = measure_model_size(model)
        model_results["speed"] = speed
        model_results["size"] = size
        all_speed[model_name] = speed
        print(f"    Speed: mean={speed['mean_ms']}ms p95={speed['p95_ms']}ms")
        print(f"    Size: {size['param_count_m']}M params, {size['model_size_mb']}MB")

        # Bootstrap CI
        if not args.skip_stats:
            print("  Bootstrap CI...")
            ci = bootstrap_ci(test_labels, test_preds)
            model_results["bootstrap_ci"] = ci
            print(f"    F1: {ci['mean']:.4f} [{ci['ci_lower']:.4f}, {ci['ci_upper']:.4f}]")

        # Confidence 분포
        plot_confidence_distribution(test_conf, model_name, f"confidence_{short}.png")

        final_results[model_name] = model_results

        # 최종 모델 저장
        if args.save_model:
            save_final_model(model, tokenizer, model_name)

    # 4.6 모델간 통계 비교 (McNemar)
    if not args.skip_stats and len(all_test_preds) >= 2:
        print("\n--- McNemar's Test ---")
        model_names = list(all_test_preds.keys())
        mcnemar_results = []
        for i in range(len(model_names)):
            for j in range(i + 1, len(model_names)):
                preds_a, labels_a = all_test_preds[model_names[i]]
                preds_b, _ = all_test_preds[model_names[j]]
                result = mcnemar_test(labels_a, preds_a, preds_b,
                                      model_names[i].split("/")[-1],
                                      model_names[j].split("/")[-1])
                mcnemar_results.append(result)
                sig = "***" if result["significant"] else "n.s."
                print(f"  {result['comparison']}: chi2={result['chi2']:.4f} p={result['p_value']:.6f} {sig}")

        final_results["mcnemar"] = mcnemar_results

    # 차트
    if all_speed and len(all_speed) >= 2:
        plot_speed_comparison(all_speed)
    if final_results and len(final_results) >= 2:
        plot_f1_vs_speed(final_results)

    # 결과 저장
    results_path = RESULTS_DIR / "final_eval_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  결과 저장: {results_path}")

    # 최종 요약
    if final_results:
        print("\n" + "=" * 60)
        print("  최종 결과 요약")
        print("=" * 60)
        print(f"\n{'모델':<35} {'Test F1':>8} {'Adv F1':>8} {'Speed':>8} {'Params':>8}")
        print("-" * 67)

        for name, data in sorted(final_results.items(), key=lambda x: x[1].get("test_f1", 0), reverse=True):
            if name == "mcnemar":
                continue
            short = name.split("/")[-1]
            tf1 = data.get("test_f1", "-")
            af1 = data.get("adv_f1", "-")
            spd = data.get("speed", {}).get("mean_ms", "-")
            prm = data.get("size", {}).get("param_count_m", "-")
            print(f"  {short:<33} {tf1:>8} {af1:>8} {spd:>6}ms {prm:>6}M")

    print("\n" + "=" * 60)
    print("  Stage 4 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
