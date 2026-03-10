"""
Held-out Adversarial 테스트 — 과적합 검증

개발 중 한 번도 사용하지 않은 새 adversarial 60개로 평가.
기존 adversarial 결과와 비교하여 과적합 여부를 판단.

사용법 (RunPod):
  python -m ai.experiments.eval_holdout
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
    "schedule_add", "schedule_view", "general", "doc_qa",
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
    with open(model_dir / "model_info.json", "r", encoding="utf-8") as f:
        model_info = json.load(f)

    base_model = model_info.get("base_model", "monologg/koelectra-base-v3-discriminator")
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.eval()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"모델 로드: {model_dir} (base: {base_model})")
    return model, tokenizer, device


def get_all_probs(model, tokenizer, texts, device):
    all_probs = []
    for text in texts:
        inputs = tokenizer(
            text, return_tensors="pt", padding=True,
            truncation=True, max_length=128,
        ).to(device)
        with torch.no_grad():
            outputs = model(**inputs)
        probs = torch.sigmoid(outputs.logits)[0].cpu().numpy()
        all_probs.append(probs)
    return np.array(all_probs)


def evaluate(all_probs, y_true, threshold=0.5):
    n = len(all_probs)
    y_pred_vecs = []

    for i in range(n):
        pred = [INTENT_LABELS[j] for j in range(NUM_LABELS) if all_probs[i][j] >= threshold]
        if not pred:
            pred = [INTENT_LABELS[np.argmax(all_probs[i])]]
        y_pred_vecs.append(labels_to_vector(sorted(pred)))

    y_pred = np.array(y_pred_vecs)

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

    true_multi = (y_true.sum(axis=1) >= 2)
    pred_multi = (y_pred.sum(axis=1) >= 2)
    n_single = (~true_multi).sum()
    n_multi = true_multi.sum()
    fp = ((~true_multi) & pred_multi).sum()
    fn = (true_multi & (~pred_multi)).sum()
    over = fp / n_single if n_single > 0 else 0.0
    under = fn / n_multi if n_multi > 0 else 0.0

    return {
        "subset_accuracy": exact_match,
        "hamming_loss": hamming,
        "jaccard": jaccard,
        "macro_f1": macro_f1,
        "micro_f1": micro_f1,
        "over_triggering": over,
        "under_triggering": under,
        "fp": int(fp), "fn": int(fn),
        "n_single": int(n_single), "n_multi": int(n_multi),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default=str(ROOT / "ai" / "models" / "intent_multilabel"))
    args = parser.parse_args()

    model, tokenizer, device = load_model(args.model_dir)

    # ── 1) 기존 adversarial (개발용) ──
    adv_path = ROOT / "data" / "training" / "intent_multilabel" / "adversarial_compound_test.json"
    with open(adv_path, "r", encoding="utf-8") as f:
        adv_data = json.load(f)["data"]

    # ── 2) Held-out adversarial (과적합 검증용) ──
    holdout_path = ROOT / "data" / "training" / "intent_multilabel" / "adversarial_holdout_test.json"
    with open(holdout_path, "r", encoding="utf-8") as f:
        holdout_data = json.load(f)["data"]

    print(f"기존 adversarial: {len(adv_data)}개")
    print(f"Held-out (신규): {len(holdout_data)}개\n")

    # ── 기존 adversarial 평가 ──
    adv_texts = [item["text"] for item in adv_data]
    adv_y_true = np.array([labels_to_vector(item["labels"]) for item in adv_data])
    adv_probs = get_all_probs(model, tokenizer, adv_texts, device)
    adv_result = evaluate(adv_probs, adv_y_true)

    # ── Held-out 평가 ──
    holdout_texts = [item["text"] for item in holdout_data]
    holdout_y_true = np.array([labels_to_vector(item["labels"]) for item in holdout_data])
    holdout_probs = get_all_probs(model, tokenizer, holdout_texts, device)
    holdout_result = evaluate(holdout_probs, holdout_y_true)

    # ── 비교 출력 ──
    sep = "─" * 60

    print(f"\n{'═'*60}")
    print("  과적합 검증 — 기존 vs Held-out 비교")
    print(f"{'═'*60}")
    print(f"\n  {'지표':<24} {'기존 ADV':>12} {'Held-out':>12} {'차이':>10}")
    print(f"  {'─'*24} {'─'*12} {'─'*12} {'─'*10}")

    metrics = [
        ("Subset Accuracy", "subset_accuracy"),
        ("Hamming Loss", "hamming_loss"),
        ("Jaccard Score", "jaccard"),
        ("Macro F1", "macro_f1"),
        ("Micro F1", "micro_f1"),
        ("Over-triggering", "over_triggering"),
        ("Under-triggering", "under_triggering"),
    ]

    for name, key in metrics:
        a = adv_result[key]
        h = holdout_result[key]
        diff = h - a
        sign = "+" if diff >= 0 else ""

        if key == "hamming_loss":
            print(f"  {name:<24} {a:>11.4f} {h:>11.4f} {sign}{diff:>9.4f}")
        elif key in ("over_triggering", "under_triggering"):
            print(f"  {name:<24} {a*100:>10.1f}% {h*100:>10.1f}% {sign}{diff*100:>8.1f}%p")
        else:
            print(f"  {name:<24} {a*100:>10.1f}% {h*100:>10.1f}% {sign}{diff*100:>8.1f}%p")

    # ── 과적합 판정 ──
    acc_diff = holdout_result["subset_accuracy"] - adv_result["subset_accuracy"]
    print(f"\n{sep}")
    print("  과적합 판정")
    print(sep)
    if abs(acc_diff) <= 0.05:
        print(f"  ✅ Subset Accuracy 차이 {acc_diff*100:+.1f}%p → 과적합 없음 (±5%p 이내)")
    elif acc_diff < -0.05:
        print(f"  ⚠️  Subset Accuracy 차이 {acc_diff*100:+.1f}%p → 과적합 의심 (Held-out에서 성능 하락)")
    else:
        print(f"  ✅ Subset Accuracy 차이 {acc_diff*100:+.1f}%p → Held-out이 오히려 높음 (과적합 아님)")

    # ── Held-out 카테고리별 ──
    print(f"\n{sep}")
    print("  Held-out 카테고리별 Exact Match")
    print(sep)
    cat_stats = defaultdict(lambda: [0, 0])
    errors = []
    for idx, item in enumerate(holdout_data):
        true = sorted(item["labels"])
        pred_labels = [INTENT_LABELS[j] for j in range(NUM_LABELS) if holdout_probs[idx][j] >= 0.5]
        if not pred_labels:
            pred_labels = [INTENT_LABELS[np.argmax(holdout_probs[idx])]]
        pred = sorted(pred_labels)

        cat = item["category"]
        cat_stats[cat][1] += 1
        if true == pred:
            cat_stats[cat][0] += 1
        else:
            errors.append({
                "id": item["id"], "category": cat,
                "text": item["text"], "true": true, "pred": pred,
                "note": item.get("note", ""),
            })

    for cat, (ok, total) in sorted(cat_stats.items()):
        pct = ok / total * 100
        bar = "█" * int(pct / 5)
        print(f"  {cat:<30} {ok:2d}/{total:2d}  ({pct:5.1f}%)  {bar}")

    # ── Held-out 오답 ──
    print(f"\n{sep}")
    print(f"  Held-out 오답 ({len(errors)}건)")
    print(sep)
    for r in errors:
        print(f"  [{r['id']:2d}] [{r['category']}]")
        print(f"       text : {r['text']}")
        print(f"       true : {r['true']}")
        print(f"       pred : {r['pred']}")
        print()

    # ── 결과 저장 ──
    out = {
        "dev_adversarial": {k: round(v, 4) if isinstance(v, float) else v for k, v in adv_result.items()},
        "holdout_adversarial": {k: round(v, 4) if isinstance(v, float) else v for k, v in holdout_result.items()},
        "accuracy_diff": round(acc_diff, 4),
        "holdout_errors": errors,
    }
    out_path = ROOT / "ai" / "experiments" / "results" / "holdout_evaluation_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
