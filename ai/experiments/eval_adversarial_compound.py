"""
Phase 2 멀티라벨 BERT — Adversarial 복합 질문 테스트

접속사 없는 복합, false positive, 극단 짧은 문장, 3중 intent 등
자동 생성 테스트에서 검증 불가한 어려운 케이스로 평가.

사용법 (RunPod 등 GPU 환경):
  python -m ai.experiments.eval_adversarial_compound
  python -m ai.experiments.eval_adversarial_compound --model-dir ai/models/intent_multilabel
"""

import argparse
import json
import numpy as np
import torch
from pathlib import Path
from collections import defaultdict
from sklearn.metrics import f1_score
from transformers import AutoTokenizer, AutoModelForSequenceClassification

ROOT = Path(__file__).resolve().parent.parent.parent

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_search",
]
NUM_LABELS = len(INTENT_LABELS)
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}


def labels_to_vector(labels_list):
    vec = [0.0] * NUM_LABELS
    for label in labels_list:
        if label in LABEL2ID:
            vec[LABEL2ID[label]] = 1.0
    return vec


def load_model(model_dir):
    model_dir = Path(model_dir)
    model_info_file = model_dir / "model_info.json"

    with open(model_info_file, "r", encoding="utf-8") as f:
        model_info = json.load(f)

    base_model = model_info.get("base_model", "monologg/koelectra-base-v3-discriminator")
    threshold = model_info.get("threshold", 0.5)

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.eval()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    print(f"모델 로드: {model_dir} (base: {base_model}, threshold: {threshold})")
    return model, tokenizer, threshold, device


def predict_multilabel(model, tokenizer, text, threshold, device):
    inputs = tokenizer(
        text,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=128,
    ).to(device)

    with torch.no_grad():
        outputs = model(**inputs)

    probs = torch.sigmoid(outputs.logits)[0].cpu().numpy()
    pred_labels = [INTENT_LABELS[i] for i in range(NUM_LABELS) if probs[i] >= threshold]

    if not pred_labels:
        best_idx = np.argmax(probs)
        pred_labels = [INTENT_LABELS[best_idx]]

    return sorted(pred_labels), probs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default=str(ROOT / "ai" / "models" / "intent_multilabel"))
    args = parser.parse_args()

    # 데이터 로드
    test_path = ROOT / "data" / "training" / "intent_multilabel" / "adversarial_compound_test.json"
    with open(test_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    samples = raw["data"]
    print(f"Adversarial 테스트 데이터: {len(samples)}개")
    print(f"카테고리: {raw['categories']}\n")

    # 모델 로드
    model, tokenizer, threshold, device = load_model(args.model_dir)

    # 예측
    y_true_vecs = []
    y_pred_vecs = []
    detail_rows = []

    for item in samples:
        true_labels = sorted(item["labels"])
        pred_labels, probs = predict_multilabel(model, tokenizer, item["text"], threshold, device)

        true_vec = labels_to_vector(true_labels)
        pred_vec = labels_to_vector(pred_labels)
        y_true_vecs.append(true_vec)
        y_pred_vecs.append(pred_vec)

        correct = (true_labels == pred_labels)
        detail_rows.append({
            "id": item["id"],
            "category": item["category"],
            "text": item["text"],
            "true": true_labels,
            "pred": pred_labels,
            "correct": correct,
            "note": item.get("note", ""),
        })

    y_true = np.array(y_true_vecs)
    y_pred = np.array(y_pred_vecs)
    n = len(samples)

    # ── 전체 지표 ──
    exact_match = np.all(y_pred == y_true, axis=1).mean()
    hamming = (y_pred != y_true).mean()

    jaccard_scores = []
    for i in range(n):
        inter = np.logical_and(y_pred[i], y_true[i]).sum()
        union = np.logical_or(y_pred[i], y_true[i]).sum()
        jaccard_scores.append(inter / union if union > 0 else 1.0)
    jaccard = np.mean(jaccard_scores)

    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    micro_f1 = f1_score(y_true, y_pred, average="micro", zero_division=0)
    per_label_f1 = f1_score(y_true, y_pred, average=None, zero_division=0)

    # Over/Under-triggering
    true_is_multi = (y_true.sum(axis=1) >= 2)
    pred_is_multi = (y_pred.sum(axis=1) >= 2)
    n_true_single = (~true_is_multi).sum()
    n_true_multi = true_is_multi.sum()
    fp = ((~true_is_multi) & pred_is_multi).sum()
    fn = (true_is_multi & (~pred_is_multi)).sum()
    over_trigger = fp / n_true_single if n_true_single > 0 else 0.0
    under_trigger = fn / n_true_multi if n_true_multi > 0 else 0.0

    sep = "─" * 60

    print(sep)
    print("[ Adversarial 전체 결과 ]")
    print(sep)
    print(f"  Subset Accuracy : {exact_match:.4f} ({exact_match*100:.1f}%)")
    print(f"  Hamming Loss    : {hamming:.4f}")
    print(f"  Jaccard Score   : {jaccard:.4f} ({jaccard*100:.1f}%)")
    print(f"  Macro F1        : {macro_f1:.4f} ({macro_f1*100:.1f}%)")
    print(f"  Micro F1        : {micro_f1:.4f} ({micro_f1*100:.1f}%)")
    print(f"  Over-triggering : {over_trigger:.4f} ({fp}/{n_true_single})")
    print(f"  Under-triggering: {under_trigger:.4f} ({fn}/{n_true_multi})")

    print(f"\n  Intent별 F1:")
    for i, label in enumerate(INTENT_LABELS):
        bar = "█" * int(per_label_f1[i] * 20)
        print(f"    {label:<16} {per_label_f1[i]:.4f}  {bar}")

    # ── 카테고리별 결과 ──
    print(f"\n{sep}")
    print("[ 카테고리별 Exact Match ]")
    print(sep)
    cat_stats = defaultdict(lambda: [0, 0])
    for row in detail_rows:
        cat = row["category"]
        cat_stats[cat][1] += 1
        if row["correct"]:
            cat_stats[cat][0] += 1

    for cat, (ok, total) in sorted(cat_stats.items()):
        pct = ok / total * 100
        bar = "█" * int(pct / 5)
        print(f"  {cat:<30} {ok:2d}/{total:2d}  ({pct:5.1f}%)  {bar}")

    # ── 오답 목록 ──
    errors = [r for r in detail_rows if not r["correct"]]
    print(f"\n{sep}")
    print(f"[ 오답 목록 ({len(errors)}건) ]")
    print(sep)
    for r in errors:
        print(f"  [{r['id']:2d}] [{r['category']}]")
        print(f"       text : {r['text']}")
        print(f"       true : {r['true']}")
        print(f"       pred : {r['pred']}")
        print(f"       note : {r['note']}")
        print()

    # ── 3단계 비교표 ──
    print(sep)
    print("[ Phase 1 vs Phase 2 (자동생성) vs Phase 2 (Adversarial) ]")
    print(sep)
    print(f"  {'지표':<24} {'Phase1':>10} {'자동생성':>10} {'Adversarial':>12}")
    print(f"  {'─'*24} {'─'*10} {'─'*10} {'─'*12}")
    rows = [
        ("Subset Accuracy", "41.7%", "99.9%", f"{exact_match*100:.1f}%"),
        ("Hamming Loss", "0.1146", "0.0002", f"{hamming:.4f}"),
        ("Jaccard Score", "52.8%", "100.0%", f"{jaccard*100:.1f}%"),
        ("Macro F1", "49.3%", "87.5%", f"{macro_f1*100:.1f}%"),
        ("Micro F1", "70.3%", "100.0%", f"{micro_f1*100:.1f}%"),
        ("Over-triggering", "5.6%", "0.0%", f"{over_trigger*100:.1f}%"),
        ("Under-triggering", "33.3%", "0.0%", f"{under_trigger*100:.1f}%"),
    ]
    for name, p1, auto, adv in rows:
        print(f"  {name:<24} {p1:>10} {auto:>10} {adv:>12}")

    # ── 결과 저장 ──
    results = {
        "subset_accuracy": round(exact_match, 4),
        "hamming_loss": round(hamming, 4),
        "jaccard": round(jaccard, 4),
        "macro_f1": round(macro_f1, 4),
        "micro_f1": round(micro_f1, 4),
        "over_triggering": round(float(over_trigger), 4),
        "under_triggering": round(float(under_trigger), 4),
        "per_label_f1": {INTENT_LABELS[i]: round(per_label_f1[i], 4) for i in range(NUM_LABELS)},
        "category_accuracy": {cat: {"correct": ok, "total": total} for cat, (ok, total) in cat_stats.items()},
        "n_errors": len(errors),
        "errors": errors,
    }

    out_path = ROOT / "ai" / "experiments" / "results" / "adversarial_compound_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
