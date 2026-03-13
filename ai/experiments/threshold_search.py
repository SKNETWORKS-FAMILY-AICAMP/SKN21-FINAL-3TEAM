"""
6-label 앙상블 모델의 per-label threshold grid search.
Held-out 60개에서 최적 threshold 조합을 탐색.

사용법 (RunPod):
  python -m ai.experiments.threshold_search
"""

import json
import numpy as np
import torch
from pathlib import Path
from sklearn.metrics import f1_score
from transformers import AutoTokenizer, AutoModelForSequenceClassification

ROOT = Path(__file__).resolve().parent.parent.parent

INTENT_LABELS = [
    "judgment", "doc_retrieve", "doc_generate",
    "schedule_add", "schedule_view", "general",
]
NUM_LABELS = len(INTENT_LABELS)
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}


def labels_to_vector(labels_list):
    vec = [0.0] * NUM_LABELS
    for label in labels_list:
        if label in LABEL2ID:
            vec[LABEL2ID[label]] = 1.0
    return vec


def load_ensemble(ensemble_dir):
    ensemble_dir = Path(ensemble_dir)
    with open(ensemble_dir / "ensemble_meta.json", "r", encoding="utf-8") as f:
        meta = json.load(f)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    models = []
    tokenizer = None

    for seed in meta["seeds"]:
        seed_dir = ensemble_dir / f"seed_{seed}"
        if not seed_dir.exists():
            continue
        with open(seed_dir / "model_info.json", "r", encoding="utf-8") as f:
            info = json.load(f)
        if tokenizer is None:
            tokenizer = AutoTokenizer.from_pretrained(info["base_model"])
        model = AutoModelForSequenceClassification.from_pretrained(str(seed_dir))
        model.eval().to(device)
        models.append(model)
        print(f"  로드: seed_{seed}")

    print(f"앙상블 {len(models)}개 로드 (device: {device})")
    return models, tokenizer, device


def get_ensemble_probs(models, tokenizer, texts, device):
    all_model_probs = []
    for model in models:
        probs_list = []
        for text in texts:
            inputs = tokenizer(
                text, return_tensors="pt", padding=True,
                truncation=True, max_length=128,
            ).to(device)
            with torch.no_grad():
                logits = model(**inputs).logits
            probs_list.append(torch.sigmoid(logits)[0].cpu().numpy())
        all_model_probs.append(np.array(probs_list))
    return np.mean(all_model_probs, axis=0)


def evaluate_with_thresholds(probs, y_true, thresholds):
    n = len(probs)
    y_pred = np.zeros_like(y_true)
    for i in range(n):
        pred_indices = [j for j in range(NUM_LABELS) if probs[i][j] >= thresholds[j]]
        if not pred_indices:
            pred_indices = [int(np.argmax(probs[i]))]
        for j in pred_indices:
            y_pred[i][j] = 1.0

    exact = np.all(y_pred == y_true, axis=1).mean()
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)

    errors = []
    for i in range(n):
        if not np.array_equal(y_pred[i], y_true[i]):
            true_labels = [INTENT_LABELS[j] for j in range(NUM_LABELS) if y_true[i][j]]
            pred_labels = [INTENT_LABELS[j] for j in range(NUM_LABELS) if y_pred[i][j]]
            errors.append((i, true_labels, pred_labels))

    return exact, macro_f1, errors


def main():
    ensemble_dir = ROOT / "ai" / "models" / "intent_multilabel_ensemble"
    models, tokenizer, device = load_ensemble(ensemble_dir)

    # Held-out 로드
    holdout_path = ROOT / "data" / "training" / "intent_multilabel" / "adversarial_holdout_test.json"
    with open(holdout_path, "r", encoding="utf-8") as f:
        holdout_data = json.load(f)["data"]

    texts = [item["text"] for item in holdout_data]
    y_true = np.array([labels_to_vector(item["labels"]) for item in holdout_data])

    print(f"\nHeld-out: {len(holdout_data)}개")
    print("앙상블 확률 계산 중...")
    probs = get_ensemble_probs(models, tokenizer, texts, device)

    # ── 오답별 확률 분포 ──
    print(f"\n{'='*60}")
    print("  Baseline(0.5) 오답별 확률 분포")
    print(f"{'='*60}")
    baseline_th = np.array([0.5] * NUM_LABELS)
    _, _, baseline_errors = evaluate_with_thresholds(probs, y_true, baseline_th)

    for idx, true_labels, pred_labels in baseline_errors:
        item = holdout_data[idx]
        print(f"\n  [{item['id']}] {item['text'][:50]}")
        print(f"       true={true_labels}  pred={pred_labels}")
        for j, label in enumerate(INTENT_LABELS):
            prob = probs[idx][j]
            marker = ""
            if label in true_labels and label not in pred_labels:
                marker = " ← 누락 (threshold↓)"
            elif label not in true_labels and label in pred_labels:
                marker = " ← 과다 (threshold↑)"
            if prob > 0.05 or marker:
                print(f"       {label:<16}: {prob:.4f}{marker}")

    # ── Grid Search (doc_retrieve × judgment) ──
    print(f"\n{'='*60}")
    print("  Threshold Grid Search (doc_retrieve × judgment)")
    print(f"{'='*60}")

    search_range = np.arange(0.25, 0.80, 0.05)
    results = []

    for dr_th in search_range:
        for jdg_th in search_range:
            thresholds = np.array([0.5] * NUM_LABELS)
            thresholds[LABEL2ID["doc_retrieve"]] = dr_th
            thresholds[LABEL2ID["judgment"]] = jdg_th

            acc, f1, errors = evaluate_with_thresholds(probs, y_true, thresholds)
            results.append({
                "doc_retrieve": round(float(dr_th), 2),
                "judgment": round(float(jdg_th), 2),
                "accuracy": round(float(acc), 4),
                "macro_f1": round(float(f1), 4),
                "n_errors": len(errors),
            })

    results.sort(key=lambda x: (-x["accuracy"], -x["macro_f1"]))

    print(f"\n  Top 15 threshold 조합:")
    print(f"  {'doc_retrieve':>12} {'judgment':>10} {'Accuracy':>10} {'Macro F1':>10} {'Errors':>8}")
    print(f"  {'─'*12} {'─'*10} {'─'*10} {'─'*10} {'─'*8}")
    for r in results[:15]:
        marker = " ◀ BEST" if r == results[0] else ""
        print(f"  {r['doc_retrieve']:>12.2f} {r['judgment']:>10.2f} "
              f"{r['accuracy']*100:>9.1f}% {r['macro_f1']*100:>9.1f}% "
              f"{r['n_errors']:>8}{marker}")

    # ── 최적 결과 상세 ──
    best = results[0]
    print(f"\n{'─'*60}")
    print(f"  최적: doc_retrieve={best['doc_retrieve']}, judgment={best['judgment']}")
    print(f"  → Accuracy: {best['accuracy']*100:.1f}% ({best['n_errors']}건 오답)")
    print(f"{'─'*60}")

    thresholds = np.array([0.5] * NUM_LABELS)
    thresholds[LABEL2ID["doc_retrieve"]] = best["doc_retrieve"]
    thresholds[LABEL2ID["judgment"]] = best["judgment"]
    _, _, best_errors = evaluate_with_thresholds(probs, y_true, thresholds)

    if best_errors:
        print(f"\n  최적 threshold 잔여 오답 ({len(best_errors)}건):")
        for idx, true_labels, pred_labels in best_errors:
            item = holdout_data[idx]
            print(f"    [{item['id']}] true={true_labels} pred={pred_labels}")
            print(f"         {item['text'][:60]}")
    else:
        print("\n  오답 0건!")

    # ── 확장 grid search (judgment × doc_retrieve × doc_generate) ──
    print(f"\n{'='*60}")
    print("  확장 Grid Search (judgment × doc_retrieve × doc_generate)")
    print(f"{'='*60}")

    jdg_range = np.arange(0.35, 0.65, 0.05)
    dg_range = np.arange(0.35, 0.65, 0.05)
    ext_results = []

    for jdg_th in jdg_range:
        for dr_th in search_range:
            for dg_th in dg_range:
                thresholds = np.array([0.5] * NUM_LABELS)
                thresholds[LABEL2ID["judgment"]] = jdg_th
                thresholds[LABEL2ID["doc_retrieve"]] = dr_th
                thresholds[LABEL2ID["doc_generate"]] = dg_th

                acc, f1, errors = evaluate_with_thresholds(probs, y_true, thresholds)
                ext_results.append({
                    "judgment": round(float(jdg_th), 2),
                    "doc_retrieve": round(float(dr_th), 2),
                    "doc_generate": round(float(dg_th), 2),
                    "accuracy": round(float(acc), 4),
                    "macro_f1": round(float(f1), 4),
                    "n_errors": len(errors),
                })

    ext_results.sort(key=lambda x: (-x["accuracy"], -x["macro_f1"]))

    print(f"\n  Top 10 확장 threshold 조합:")
    print(f"  {'judgment':>8} {'doc_retrieve':>12} {'doc_generate':>12} {'Accuracy':>10} {'Macro F1':>10} {'Errors':>8}")
    print(f"  {'─'*8} {'─'*12} {'─'*12} {'─'*10} {'─'*10} {'─'*8}")
    for r in ext_results[:10]:
        print(f"  {r['judgment']:>8.2f} {r['doc_retrieve']:>12.2f} {r['doc_generate']:>12.2f} "
              f"{r['accuracy']*100:>9.1f}% {r['macro_f1']*100:>9.1f}% "
              f"{r['n_errors']:>8}")

    # 결과 저장
    out = {
        "best_2d": best,
        "best_3d": ext_results[0],
        "top_10_2d": results[:10],
        "top_10_3d": ext_results[:10],
    }
    out_path = ROOT / "ai" / "experiments" / "results" / "threshold_grid_search.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
