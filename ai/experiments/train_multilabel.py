"""
Phase 2: 멀티라벨 Intent 분류 모델 학습

기존 단일 라벨 학습 (softmax + CrossEntropy) →
멀티라벨 학습 (sigmoid + BCEWithLogitsLoss) 으로 교체.

핵심 변경점:
  - labels: int(단일) → float 벡터 [0,0,1,0,0,1,0,0] (멀티)
  - problem_type: "multi_label_classification"
  - 평가 지표: Subset Accuracy, Hamming Loss, Jaccard, Macro/Micro F1

사용법 (RunPod 등 GPU 환경):
  pip install transformers datasets accelerate scikit-learn matplotlib seaborn
  python -m ai.experiments.train_multilabel
  python -m ai.experiments.train_multilabel --model klue/bert-base --epochs 10
"""

import argparse
import json
import random
import time
import torch
import numpy as np
from pathlib import Path
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    EvalPrediction,
)
from sklearn.metrics import f1_score

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# ── 경로 ──────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "intent_multilabel"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_SAVE_DIR = BASE_DIR / "ai" / "models" / "intent_multilabel"
MODEL_SAVE_DIR.mkdir(parents=True, exist_ok=True)

# ── Intent 정의 ──────────────────────────────────────────────────────────────

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_qa",
]
NUM_LABELS = len(INTENT_LABELS)
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}
ID2LABEL = {i: label for i, label in enumerate(INTENT_LABELS)}

# ── 하이퍼파라미터 ───────────────────────────────────────────────────────────

DEFAULT_HP = {
    "epochs": 10,
    "learning_rate": 3e-5,
    "batch_size": 16,
    "warmup_ratio": 0.06,
    "weight_decay": 0.01,
    "max_length": 128,  # 복합 문장이 더 기니까 64→128
    "threshold": 0.5,
}

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ── 데이터 로드 ──────────────────────────────────────────────────────────────

def load_jsonl(path):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def labels_to_vector(labels_list):
    """["doc_search", "judgment"] → [1,1,0,0,0,0,0,0] float vector"""
    vec = [0.0] * NUM_LABELS
    for label in labels_list:
        if label in LABEL2ID:
            vec[LABEL2ID[label]] = 1.0
    return vec


def load_splits():
    train = load_jsonl(DATA_DIR / "train.jsonl")
    val   = load_jsonl(DATA_DIR / "val.jsonl")
    test  = load_jsonl(DATA_DIR / "test.jsonl")

    n_train_compound = sum(1 for d in train if len(d["labels"]) >= 2)
    n_val_compound   = sum(1 for d in val   if len(d["labels"]) >= 2)
    n_test_compound  = sum(1 for d in test  if len(d["labels"]) >= 2)

    print(f"데이터 로드 완료:")
    print(f"  Train: {len(train)} (복합: {n_train_compound})")
    print(f"  Val:   {len(val)}   (복합: {n_val_compound})")
    print(f"  Test:  {len(test)}  (복합: {n_test_compound})")

    return train, val, test


def to_dataset(data, tokenizer, max_length):
    """raw data → HuggingFace Dataset (토큰화 + 멀티라벨 벡터)"""
    texts = [d["text"] for d in data]
    label_vecs = [labels_to_vector(d["labels"]) for d in data]

    ds = Dataset.from_dict({
        "text": texts,
        "labels": label_vecs,
    })

    def tokenize_fn(examples):
        tok = tokenizer(
            examples["text"],
            padding="max_length",
            truncation=True,
            max_length=max_length,
        )
        tok["labels"] = examples["labels"]
        return tok

    ds = ds.map(tokenize_fn, batched=True)
    ds.set_format("torch")
    return ds


# ── 평가 지표 ────────────────────────────────────────────────────────────────

def compute_metrics(eval_pred: EvalPrediction, threshold=0.5):
    """멀티라벨 평가 지표"""
    logits = eval_pred.predictions
    labels = eval_pred.label_ids

    # sigmoid → threshold
    probs = 1 / (1 + np.exp(-logits))
    preds = (probs >= threshold).astype(int)
    labels = labels.astype(int)

    n = len(labels)

    # Subset Accuracy (Exact Match)
    exact_match = np.all(preds == labels, axis=1).mean()

    # Hamming Loss
    hamming = (preds != labels).mean()

    # Jaccard (per-sample, then average)
    jaccard_scores = []
    for i in range(n):
        inter = np.logical_and(preds[i], labels[i]).sum()
        union = np.logical_or(preds[i], labels[i]).sum()
        jaccard_scores.append(inter / union if union > 0 else 1.0)
    jaccard = np.mean(jaccard_scores)

    # Macro F1 / Micro F1 (label-wise)
    macro_f1 = f1_score(labels, preds, average="macro", zero_division=0)
    micro_f1 = f1_score(labels, preds, average="micro", zero_division=0)

    return {
        "subset_accuracy": round(exact_match, 4),
        "hamming_loss": round(hamming, 4),
        "jaccard": round(jaccard, 4),
        "macro_f1": round(macro_f1, 4),
        "micro_f1": round(micro_f1, 4),
    }


# ── 학습 ─────────────────────────────────────────────────────────────────────

def train_model(model_name, train_data, val_data, hp, seed=42):
    """멀티라벨 모델 학습"""
    set_seed(seed)

    print(f"\n{'='*60}")
    print(f"  모델: {model_name}")
    print(f"  HP: epochs={hp['epochs']}, lr={hp['learning_rate']}, bs={hp['batch_size']}")
    print(f"  max_length={hp['max_length']}, threshold={hp['threshold']}")
    print(f"{'='*60}")

    # 토크나이저 + 모델
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        problem_type="multi_label_classification",  # ← 핵심: BCEWithLogitsLoss 자동 사용
    )

    # 데이터셋
    train_ds = to_dataset(train_data, tokenizer, hp["max_length"])
    val_ds   = to_dataset(val_data,   tokenizer, hp["max_length"])

    # 학습 설정
    output_dir = RESULTS_DIR / f"multilabel_{model_name.split('/')[-1]}"
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
        metric_for_best_model="macro_f1",
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
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
    )

    # 학습
    start = time.time()
    train_result = trainer.train()
    train_time = time.time() - start

    # Validation 평가
    eval_results = trainer.evaluate()
    print(f"\n  Val 결과:")
    for k, v in eval_results.items():
        if k.startswith("eval_"):
            print(f"    {k}: {v}")
    print(f"  학습 시간: {train_time:.1f}s")

    return trainer, tokenizer, model, eval_results, train_time


# ── 상세 평가 ────────────────────────────────────────────────────────────────

def evaluate_detailed(model, tokenizer, data, hp, dataset_name="test"):
    """상세 평가: per-label F1 + 오답 분석"""
    model.eval()
    threshold = hp["threshold"]

    texts = [d["text"] for d in data]
    true_labels = [d["labels"] for d in data]
    true_vecs = np.array([labels_to_vector(labels) for labels in true_labels])

    # 추론
    all_probs = []
    with torch.no_grad():
        for i in range(0, len(texts), hp["batch_size"]):
            batch_texts = texts[i:i + hp["batch_size"]]
            inputs = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=hp["max_length"],
                return_tensors="pt",
            ).to(model.device)
            outputs = model(**inputs)
            probs = torch.sigmoid(outputs.logits).cpu().numpy()
            all_probs.append(probs)

    all_probs = np.concatenate(all_probs, axis=0)
    pred_vecs = (all_probs >= threshold).astype(int)

    # 전체 지표
    n = len(data)
    exact_match = np.all(pred_vecs == true_vecs, axis=1).mean()
    hamming = (pred_vecs != true_vecs).mean()

    jaccard_scores = []
    for i in range(n):
        inter = np.logical_and(pred_vecs[i], true_vecs[i]).sum()
        union = np.logical_or(pred_vecs[i], true_vecs[i]).sum()
        jaccard_scores.append(inter / union if union > 0 else 1.0)
    jaccard = np.mean(jaccard_scores)

    macro_f1 = f1_score(true_vecs, pred_vecs, average="macro", zero_division=0)
    micro_f1 = f1_score(true_vecs, pred_vecs, average="micro", zero_division=0)

    # Per-label F1
    per_label_f1 = f1_score(true_vecs, pred_vecs, average=None, zero_division=0)

    # Over/Under-triggering (복합 감지 관점)
    true_is_multi = (true_vecs.sum(axis=1) >= 2)
    pred_is_multi = (pred_vecs.sum(axis=1) >= 2)
    n_true_single = (~true_is_multi).sum()
    n_true_multi  = true_is_multi.sum()

    fp_multi = ((~true_is_multi) & pred_is_multi).sum()
    fn_multi = (true_is_multi & (~pred_is_multi)).sum()

    over_trigger  = fp_multi / n_true_single if n_true_single > 0 else 0.0
    under_trigger = fn_multi / n_true_multi  if n_true_multi  > 0 else 0.0

    # 결과 출력
    print(f"\n{'─'*60}")
    print(f"  [{dataset_name}] 상세 평가 결과")
    print(f"{'─'*60}")
    print(f"  Subset Accuracy : {exact_match:.4f} ({exact_match*100:.1f}%)")
    print(f"  Hamming Loss    : {hamming:.4f}")
    print(f"  Jaccard Score   : {jaccard:.4f} ({jaccard*100:.1f}%)")
    print(f"  Macro F1        : {macro_f1:.4f} ({macro_f1*100:.1f}%)")
    print(f"  Micro F1        : {micro_f1:.4f} ({micro_f1*100:.1f}%)")
    print(f"  Over-triggering : {over_trigger:.4f} ({fp_multi}/{n_true_single})")
    print(f"  Under-triggering: {under_trigger:.4f} ({fn_multi}/{n_true_multi})")

    print(f"\n  Intent별 F1:")
    for i, label in enumerate(INTENT_LABELS):
        bar = "█" * int(per_label_f1[i] * 20)
        print(f"    {label:<16} {per_label_f1[i]:.4f}  {bar}")

    # 오답 목록 (최대 20개)
    errors = []
    for i in range(n):
        if not np.array_equal(pred_vecs[i], true_vecs[i]):
            true_set = [INTENT_LABELS[j] for j in range(NUM_LABELS) if true_vecs[i][j]]
            pred_set = [INTENT_LABELS[j] for j in range(NUM_LABELS) if pred_vecs[i][j]]
            errors.append({
                "text": texts[i],
                "true": true_set,
                "pred": pred_set,
            })

    if errors:
        print(f"\n  오답 ({len(errors)}건 중 상위 20건):")
        for err in errors[:20]:
            print(f"    true={err['true']}  pred={err['pred']}")
            print(f"      {err['text'][:80]}")

    return {
        "dataset": dataset_name,
        "n_samples": n,
        "subset_accuracy": round(exact_match, 4),
        "hamming_loss": round(hamming, 4),
        "jaccard": round(jaccard, 4),
        "macro_f1": round(macro_f1, 4),
        "micro_f1": round(micro_f1, 4),
        "over_triggering": round(float(over_trigger), 4),
        "under_triggering": round(float(under_trigger), 4),
        "per_label_f1": {INTENT_LABELS[i]: round(per_label_f1[i], 4) for i in range(NUM_LABELS)},
        "n_errors": len(errors),
    }


# ── 모델 저장 ────────────────────────────────────────────────────────────────

def save_model(model, tokenizer, results, hp):
    """최종 모델 저장"""
    model.save_pretrained(str(MODEL_SAVE_DIR))
    tokenizer.save_pretrained(str(MODEL_SAVE_DIR))

    # label_map 저장
    label_map = {
        "label2id": LABEL2ID,
        "id2label": {str(k): v for k, v in ID2LABEL.items()},
        "problem_type": "multi_label_classification",
    }
    with open(MODEL_SAVE_DIR / "label_map.json", "w", encoding="utf-8") as f:
        json.dump(label_map, f, ensure_ascii=False, indent=2)

    # 모델 정보
    model_info = {
        "base_model": hp.get("model_name", "monologg/koelectra-base-v3-discriminator"),
        "problem_type": "multi_label_classification",
        "num_labels": NUM_LABELS,
        "threshold": hp["threshold"],
        "labels": INTENT_LABELS,
    }
    with open(MODEL_SAVE_DIR / "model_info.json", "w", encoding="utf-8") as f:
        json.dump(model_info, f, ensure_ascii=False, indent=2)

    print(f"\n  모델 저장 완료: {MODEL_SAVE_DIR}")


# ── Phase 1 vs Phase 2 비교표 ────────────────────────────────────────────────

def print_comparison(phase2_results):
    """Phase 1 규칙 기반 vs Phase 2 BERT 비교"""
    # Phase 1 결과 (eval_compound_phase1.py 실행 결과 하드코딩)
    phase1 = {
        "복합감지 F1": 76.2,
        "Over-triggering": 5.6,
        "Under-triggering": 33.3,
        "Subset Accuracy": 41.7,
        "Hamming Loss": 0.1146,
        "Jaccard Score": 52.8,
        "Macro F1": 49.3,
        "Micro F1": 70.3,
    }

    print(f"\n{'='*60}")
    print("  Phase 1 (규칙) vs Phase 2 (멀티라벨 BERT) 비교")
    print(f"{'='*60}")
    print(f"  {'지표':<24} {'Phase1':>10} {'Phase2':>10} {'차이':>10}")
    print(f"  {'─'*24} {'─'*10} {'─'*10} {'─'*10}")

    comparisons = [
        ("Subset Accuracy", phase1["Subset Accuracy"], phase2_results["subset_accuracy"] * 100),
        ("Hamming Loss", phase1["Hamming Loss"], phase2_results["hamming_loss"]),
        ("Jaccard Score", phase1["Jaccard Score"], phase2_results["jaccard"] * 100),
        ("Macro F1", phase1["Macro F1"], phase2_results["macro_f1"] * 100),
        ("Micro F1", phase1["Micro F1"], phase2_results["micro_f1"] * 100),
        ("Over-triggering", phase1["Over-triggering"], phase2_results["over_triggering"] * 100),
        ("Under-triggering", phase1["Under-triggering"], phase2_results["under_triggering"] * 100),
    ]

    for name, p1, p2 in comparisons:
        if "Loss" in name or "triggering" in name:
            diff = p1 - p2
            arrow = "↓" if diff > 0 else "↑"
        else:
            diff = p2 - p1
            arrow = "↑" if diff > 0 else "↓"

        if "Loss" in name:
            print(f"  {name:<24} {p1:>10.4f} {p2:>10.4f} {arrow}{abs(diff):>8.4f}")
        else:
            print(f"  {name:<24} {p1:>9.1f}% {p2:>9.1f}% {arrow}{abs(diff):>7.1f}%p")


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Phase 2 멀티라벨 Intent 학습")
    parser.add_argument("--model", default="monologg/koelectra-base-v3-discriminator")
    parser.add_argument("--epochs", type=int, default=DEFAULT_HP["epochs"])
    parser.add_argument("--lr", type=float, default=DEFAULT_HP["learning_rate"])
    parser.add_argument("--batch-size", type=int, default=DEFAULT_HP["batch_size"])
    parser.add_argument("--max-length", type=int, default=DEFAULT_HP["max_length"])
    parser.add_argument("--threshold", type=float, default=DEFAULT_HP["threshold"])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    hp = {
        "model_name": args.model,
        "epochs": args.epochs,
        "learning_rate": args.lr,
        "batch_size": args.batch_size,
        "max_length": args.max_length,
        "threshold": args.threshold,
        "warmup_ratio": DEFAULT_HP["warmup_ratio"],
        "weight_decay": DEFAULT_HP["weight_decay"],
    }

    print("Phase 2: 멀티라벨 Intent 분류 모델 학습")
    print(f"모델: {args.model}")
    print(f"디바이스: {device}")

    # 데이터 로드
    train_data, val_data, test_data = load_splits()

    # 학습
    trainer, tokenizer, model, eval_results, train_time = train_model(
        args.model, train_data, val_data, hp, args.seed,
    )

    # Test 평가
    test_results = evaluate_detailed(model, tokenizer, test_data, hp, "Test")

    # 복합 데이터만 별도 평가
    compound_path = DATA_DIR / "compound_only.jsonl"
    if compound_path.exists():
        compound_data = load_jsonl(compound_path)
        compound_results = evaluate_detailed(model, tokenizer, compound_data, hp, "Compound-Only")
    else:
        compound_results = None

    # Phase 1 vs Phase 2 비교
    if compound_results:
        print_comparison(compound_results)

    # 모델 저장
    save_model(model, tokenizer, test_results, hp)

    # 전체 결과 JSON 저장
    all_results = {
        "model": args.model,
        "hp": hp,
        "train_time_sec": round(train_time, 1),
        "val": {k.replace("eval_", ""): v for k, v in eval_results.items()},
        "test": test_results,
        "compound": compound_results,
    }
    results_path = RESULTS_DIR / "multilabel_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {results_path}")


if __name__ == "__main__":
    main()
