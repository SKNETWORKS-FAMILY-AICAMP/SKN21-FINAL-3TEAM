"""
Phase 2: 멀티라벨 Intent 분류 모델 학습

기존 단일 라벨 학습 (softmax + CrossEntropy) →
멀티라벨 학습 (sigmoid + BCEWithLogitsLoss) 으로 교체.

핵심 변경점:
  - labels: int(단일) → float 벡터 [0,0,1,0,0,1,0,0] (멀티)
  - problem_type: "multi_label_classification"
  - 평가 지표: Subset Accuracy, Hamming Loss, Jaccard, Macro/Micro F1

고급 학습 기법:
  - Focal Loss: easy 샘플 가중치 감소, hard 샘플 집중 (--focal)
  - FGM Adversarial Training: 임베딩 perturbation으로 강건화 (--fgm)
  - Multi-Seed Ensemble: 여러 seed로 학습 후 앙상블 (--ensemble-seeds)

사용법 (RunPod 등 GPU 환경):
  pip install transformers datasets accelerate scikit-learn matplotlib seaborn

  # 기본 학습
  python -m ai.experiments.train_multilabel --model klue/roberta-large

  # Focal Loss + FGM
  python -m ai.experiments.train_multilabel --model klue/roberta-large --focal --fgm

  # 5-Seed 앙상블 (Focal + FGM)
  python -m ai.experiments.train_multilabel --model klue/roberta-large --focal --fgm --ensemble-seeds 42,123,456,789,1337
"""

import argparse
import json
import random
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
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
    "schedule_add", "schedule_view", "general",
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


# ── Focal Loss ────────────────────────────────────────────────────────────────

class FocalBCELoss(nn.Module):
    """
    Focal Loss for multi-label classification.
    easy 샘플(확률 높은)의 loss 가중치를 줄이고, hard 샘플(경계 케이스)에 집중.

    gamma=0 → 일반 BCE와 동일
    gamma=2 → 표준 Focal Loss (추천)
    """
    def __init__(self, gamma=2.0, label_weights=None):
        super().__init__()
        self.gamma = gamma
        self.label_weights = label_weights  # [NUM_LABELS] tensor

    def forward(self, logits, targets):
        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction='none')
        probs = torch.sigmoid(logits)
        pt = targets * probs + (1 - targets) * (1 - probs)
        focal_weight = (1 - pt) ** self.gamma
        loss = focal_weight * bce
        if self.label_weights is not None:
            loss = loss * self.label_weights.to(loss.device)
        return loss.mean()


# ── FGM Adversarial Training ─────────────────────────────────────────────────

class FGM:
    """
    Fast Gradient Method — 학습 중 word embedding에 미세 perturbation 추가.
    임베딩 공간에서 결정 경계를 더 robust하게 만듦.
    """
    def __init__(self, model, epsilon=1.0):
        self.model = model
        self.epsilon = epsilon
        self.backup = {}

    def attack(self):
        for name, param in self.model.named_parameters():
            if param.requires_grad and 'word_embeddings' in name:
                self.backup[name] = param.data.clone()
                if param.grad is not None:
                    norm = torch.norm(param.grad)
                    if norm != 0 and not torch.isnan(norm):
                        r_at = self.epsilon * param.grad / norm
                        param.data.add_(r_at)

    def restore(self):
        for name, param in self.model.named_parameters():
            if name in self.backup:
                param.data = self.backup[name]
        self.backup = {}


# ── Custom Trainer (Focal Loss + FGM) ────────────────────────────────────────

class AdvancedTrainer(Trainer):
    """Focal Loss + FGM 지원 Trainer"""

    def __init__(self, *args, focal_loss=None, fgm=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.focal_loss = focal_loss
        self.fgm = fgm

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)

        if self.focal_loss is not None:
            loss = self.focal_loss(outputs.logits, labels)
        else:
            loss = F.binary_cross_entropy_with_logits(outputs.logits, labels)

        inputs["labels"] = labels
        return (loss, outputs) if return_outputs else loss

    def training_step(self, model, inputs, num_items_in_batch=None):
        model.train()
        inputs = self._prepare_inputs(inputs)

        with self.compute_loss_context_manager():
            loss = self.compute_loss(model, inputs)

        if self.args.n_gpu > 1:
            loss = loss.mean()

        # 정상 backward
        self.accelerator.backward(loss)

        # FGM: 적대적 학습
        if self.fgm is not None:
            self.fgm.attack()
            with self.compute_loss_context_manager():
                loss_adv = self.compute_loss(model, inputs)
            if self.args.n_gpu > 1:
                loss_adv = loss_adv.mean()
            self.accelerator.backward(loss_adv)
            self.fgm.restore()

        return loss.detach() / self.args.gradient_accumulation_steps


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

def train_model(model_name, train_data, val_data, hp, seed=42,
                use_focal=False, focal_gamma=2.0, label_weights=None,
                use_fgm=False, fgm_epsilon=1.0,
                save_dir=None):
    """멀티라벨 모델 학습 (Focal Loss + FGM 지원)"""
    set_seed(seed)

    features = []
    if use_focal:
        features.append(f"Focal(γ={focal_gamma})")
    if use_fgm:
        features.append(f"FGM(ε={fgm_epsilon})")
    feat_str = " + ".join(features) if features else "Baseline(BCE)"

    print(f"\n{'='*60}")
    print(f"  모델: {model_name}")
    print(f"  학습 기법: {feat_str}")
    print(f"  HP: epochs={hp['epochs']}, lr={hp['learning_rate']}, bs={hp['batch_size']}, seed={seed}")
    print(f"  max_length={hp['max_length']}, threshold={hp['threshold']}")
    if label_weights:
        print(f"  Label Weights: {label_weights}")
    print(f"{'='*60}")

    # 토크나이저 + 모델
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        problem_type="multi_label_classification",
    )

    # 데이터셋
    train_ds = to_dataset(train_data, tokenizer, hp["max_length"])
    val_ds   = to_dataset(val_data,   tokenizer, hp["max_length"])

    # Focal Loss 설정
    focal_loss_fn = None
    if use_focal:
        lw_tensor = None
        if label_weights:
            lw_tensor = torch.tensor(
                [label_weights.get(label, 1.0) for label in INTENT_LABELS],
                dtype=torch.float32,
            )
        focal_loss_fn = FocalBCELoss(gamma=focal_gamma, label_weights=lw_tensor)
        print(f"  ✓ Focal Loss 활성화 (gamma={focal_gamma})")

    # FGM 설정
    fgm = None
    if use_fgm:
        fgm = FGM(model, epsilon=fgm_epsilon)
        print(f"  ✓ FGM Adversarial Training 활성화 (epsilon={fgm_epsilon})")

    # 학습 설정
    output_dir = RESULTS_DIR / f"multilabel_{model_name.split('/')[-1]}_seed{seed}"
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=hp["epochs"],
        per_device_train_batch_size=hp["batch_size"],
        per_device_eval_batch_size=hp["batch_size"],
        learning_rate=hp["learning_rate"],
        weight_decay=hp["weight_decay"],
        warmup_ratio=hp["warmup_ratio"],
        gradient_accumulation_steps=hp.get("grad_accum", 1),
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
        fp16=torch.cuda.is_available() and "deberta" not in model_name.lower(),
        bf16=torch.cuda.is_available() and "deberta" in model_name.lower(),
    )

    # Trainer 선택 (Focal/FGM 사용 시 AdvancedTrainer)
    if use_focal or use_fgm:
        trainer = AdvancedTrainer(
            model=model,
            args=training_args,
            train_dataset=train_ds,
            eval_dataset=val_ds,
            compute_metrics=compute_metrics,
            focal_loss=focal_loss_fn,
            fgm=fgm,
        )
    else:
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_ds,
            eval_dataset=val_ds,
            compute_metrics=compute_metrics,
        )

    # 학습
    start = time.time()
    trainer.train()
    train_time = time.time() - start

    # Validation 평가
    eval_results = trainer.evaluate()
    print(f"\n  Val 결과:")
    for k, v in eval_results.items():
        if k.startswith("eval_"):
            print(f"    {k}: {v}")
    print(f"  학습 시간: {train_time:.1f}s")

    # 모델 저장 (save_dir 지정 시)
    if save_dir:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(str(save_dir))
        tokenizer.save_pretrained(str(save_dir))
        model_info = {
            "base_model": model_name,
            "problem_type": "multi_label_classification",
            "num_labels": NUM_LABELS,
            "threshold": hp["threshold"],
            "labels": INTENT_LABELS,
            "seed": seed,
            "features": feat_str,
        }
        with open(save_dir / "model_info.json", "w", encoding="utf-8") as f:
            json.dump(model_info, f, ensure_ascii=False, indent=2)
        print(f"  모델 저장: {save_dir}")

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
    parser.add_argument("--grad-accum", type=int, default=1,
                        help="Gradient accumulation steps (effective batch = batch_size * grad_accum)")

    # Focal Loss
    parser.add_argument("--focal", action="store_true", help="Focal Loss 사용")
    parser.add_argument("--focal-gamma", type=float, default=2.0, help="Focal Loss gamma (default: 2.0)")
    parser.add_argument("--label-weights", action="store_true",
                        help="오답 빈도 기반 label weight 적용 (doc_summary:2.0, judgment:1.5, ...)")

    # FGM
    parser.add_argument("--fgm", action="store_true", help="FGM Adversarial Training 사용")
    parser.add_argument("--fgm-epsilon", type=float, default=1.0, help="FGM epsilon (default: 1.0)")

    # 앙상블
    parser.add_argument("--ensemble-seeds", type=str, default=None,
                        help="앙상블 학습용 seed 리스트 (콤마 구분, 예: 42,123,456,789,1337)")

    args = parser.parse_args()

    # Label weights (오답 분석 기반)
    lw = None
    if args.label_weights:
        lw = {
            "doc_summary": 2.0,
            "judgment": 1.5,
            "doc_generate": 1.5,
            "doc_search": 1.3,
        }

    hp = {
        "model_name": args.model,
        "epochs": args.epochs,
        "learning_rate": args.lr,
        "batch_size": args.batch_size,
        "max_length": args.max_length,
        "threshold": args.threshold,
        "warmup_ratio": DEFAULT_HP["warmup_ratio"],
        "weight_decay": DEFAULT_HP["weight_decay"],
        "grad_accum": args.grad_accum,
    }

    print("Phase 2: 멀티라벨 Intent 분류 모델 학습")
    print(f"모델: {args.model}")
    print(f"디바이스: {device}")

    # 데이터 로드
    train_data, val_data, test_data = load_splits()

    # ── 앙상블 모드 ──
    if args.ensemble_seeds:
        seeds = [int(s.strip()) for s in args.ensemble_seeds.split(",")]
        print(f"\n{'▶'*3} 앙상블 모드: {len(seeds)}개 seed {seeds}")

        ensemble_dir = MODEL_SAVE_DIR.parent / "intent_multilabel_ensemble"
        ensemble_dir.mkdir(parents=True, exist_ok=True)
        ensemble_results = []

        for i, seed in enumerate(seeds):
            print(f"\n{'━'*60}")
            print(f"  앙상블 [{i+1}/{len(seeds)}] seed={seed}")
            print(f"{'━'*60}")

            seed_save_dir = ensemble_dir / f"seed_{seed}"
            trainer, tokenizer, model, eval_results, train_time = train_model(
                args.model, train_data, val_data, hp, seed,
                use_focal=args.focal, focal_gamma=args.focal_gamma, label_weights=lw,
                use_fgm=args.fgm, fgm_epsilon=args.fgm_epsilon,
                save_dir=str(seed_save_dir),
            )

            test_results = evaluate_detailed(model, tokenizer, test_data, hp, f"Test(seed={seed})")
            ensemble_results.append({
                "seed": seed,
                "train_time": round(train_time, 1),
                "val": {k.replace("eval_", ""): v for k, v in eval_results.items()},
                "test": test_results,
            })

            # GPU 메모리 해제
            del model, trainer
            torch.cuda.empty_cache()

        # 앙상블 메타 저장
        meta = {
            "model": args.model,
            "seeds": seeds,
            "features": [],
            "hp": hp,
            "results": ensemble_results,
        }
        if args.focal:
            meta["features"].append(f"FocalLoss(gamma={args.focal_gamma})")
        if args.fgm:
            meta["features"].append(f"FGM(epsilon={args.fgm_epsilon})")
        if lw:
            meta["features"].append(f"LabelWeights({lw})")

        with open(ensemble_dir / "ensemble_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"  앙상블 학습 완료! {len(seeds)}개 모델 저장: {ensemble_dir}")
        print(f"  → eval_holdout.py --ensemble-dir {ensemble_dir} 로 앙상블 평가")
        print(f"{'='*60}")
        return

    # ── 단일 모델 학습 ──
    trainer, tokenizer, model, eval_results, train_time = train_model(
        args.model, train_data, val_data, hp, args.seed,
        use_focal=args.focal, focal_gamma=args.focal_gamma, label_weights=lw,
        use_fgm=args.fgm, fgm_epsilon=args.fgm_epsilon,
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
        "features": [],
        "train_time_sec": round(train_time, 1),
        "val": {k.replace("eval_", ""): v for k, v in eval_results.items()},
        "test": test_results,
        "compound": compound_results,
    }
    if args.focal:
        all_results["features"].append(f"FocalLoss(gamma={args.focal_gamma})")
    if args.fgm:
        all_results["features"].append(f"FGM(epsilon={args.fgm_epsilon})")
    if lw:
        all_results["features"].append(f"LabelWeights({lw})")

    results_path = RESULTS_DIR / "multilabel_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {results_path}")


if __name__ == "__main__":
    main()
