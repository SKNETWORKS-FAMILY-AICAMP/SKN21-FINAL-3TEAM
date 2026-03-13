"""
Held-out Adversarial 테스트 — 과적합 검증

개발 중 한 번도 사용하지 않은 새 adversarial 60개로 평가.
기존 adversarial 결과와 비교하여 과적합 여부를 판단.

사용법 (RunPod):
  # 단일 모델 평가
  python -m ai.experiments.eval_holdout

  # 앙상블 평가 (여러 seed 모델의 sigmoid 평균)
  python -m ai.experiments.eval_holdout --ensemble-dir ai/models/intent_multilabel_ensemble

  # 앙상블 + threshold 재최적화 (dev adversarial 기반)
  python -m ai.experiments.eval_holdout --ensemble-dir ai/models/intent_multilabel_ensemble --optimize-thresholds
"""

import argparse
import json
import time
import numpy as np
import torch
from pathlib import Path
from collections import defaultdict
from sklearn.metrics import f1_score
from transformers import AutoTokenizer, AutoModelForSequenceClassification

ROOT = Path(__file__).resolve().parent.parent.parent

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
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


def load_ensemble(ensemble_dir):
    """앙상블 디렉토리에서 모든 seed 모델 로드"""
    ensemble_dir = Path(ensemble_dir)
    meta_path = ensemble_dir / "ensemble_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"ensemble_meta.json 없음: {ensemble_dir}")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    seeds = meta["seeds"]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    models = []
    tokenizer = None

    for seed in seeds:
        seed_dir = ensemble_dir / f"seed_{seed}"
        if not seed_dir.exists():
            print(f"  ⚠️  seed_{seed} 디렉토리 없음, 건너뜀")
            continue

        with open(seed_dir / "model_info.json", "r", encoding="utf-8") as f:
            model_info = json.load(f)

        if tokenizer is None:
            base_model = model_info.get("base_model", "monologg/koelectra-base-v3-discriminator")
            tokenizer = AutoTokenizer.from_pretrained(base_model)

        model = AutoModelForSequenceClassification.from_pretrained(str(seed_dir))
        model.eval()
        model.to(device)
        models.append({"seed": seed, "model": model})
        print(f"  앙상블 모델 로드: seed_{seed}")

    print(f"앙상블 모델 {len(models)}개 로드 완료 (device: {device})")
    return models, tokenizer, device, meta


def get_ensemble_probs(models, tokenizer, texts, device):
    """여러 모델의 sigmoid 확률을 평균"""
    all_model_probs = []

    for m_info in models:
        model = m_info["model"]
        model_probs = []
        for text in texts:
            inputs = tokenizer(
                text, return_tensors="pt", padding=True,
                truncation=True, max_length=128,
            ).to(device)
            with torch.no_grad():
                outputs = model(**inputs)
            probs = torch.sigmoid(outputs.logits)[0].cpu().numpy()
            model_probs.append(probs)
        all_model_probs.append(np.array(model_probs))

    # 모든 모델의 확률 평균
    avg_probs = np.mean(all_model_probs, axis=0)
    return avg_probs


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


def optimize_thresholds(all_probs, y_true):
    """
    Dev adversarial 데이터에서 per-label 최적 threshold를 grid search.
    각 label 독립적으로 F1 최대화 threshold 탐색.
    """
    search_range = np.arange(0.10, 0.90, 0.05)
    best_thresholds = np.array([0.5] * NUM_LABELS)

    print(f"\n{'─'*60}")
    print("  Per-label Threshold 재최적화 (Dev Adversarial 기반)")
    print(f"{'─'*60}")
    print(f"  탐색 범위: {search_range[0]:.2f} ~ {search_range[-1]:.2f} (step 0.05)")

    for i, label in enumerate(INTENT_LABELS):
        true_col = y_true[:, i]
        if true_col.sum() == 0:
            print(f"  {label:<16} → 0.50 (양성 샘플 없음)")
            continue

        best_f1 = 0.0
        best_t = 0.5
        for t in search_range:
            pred_col = (all_probs[:, i] >= t).astype(float)
            f1 = f1_score(true_col, pred_col, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_t = t

        best_thresholds[i] = round(best_t, 2)
        bar = "█" * int(best_f1 * 20)
        print(f"  {label:<16} → {best_t:.2f}  (F1: {best_f1:.4f})  {bar}")

    return best_thresholds


def measure_inference_time(models_or_model, tokenizer, texts, device, is_ensemble=False, n_runs=3):
    """앙상블/단일 모델 추론 시간 측정 (warmup 1회 + n_runs 평균)"""
    sample_text = texts[0] if texts else "테스트 입력입니다."

    def single_inference():
        inputs = tokenizer(
            sample_text, return_tensors="pt", padding=True,
            truncation=True, max_length=128,
        ).to(device)
        if is_ensemble:
            for m_info in models_or_model:
                with torch.no_grad():
                    m_info["model"](**inputs)
        else:
            with torch.no_grad():
                models_or_model(**inputs)

    # warmup
    single_inference()
    if torch.cuda.is_available():
        torch.cuda.synchronize()

    # measure
    times = []
    for _ in range(n_runs):
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        start = time.perf_counter()
        single_inference()
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # ms

    avg_ms = np.mean(times)
    return avg_ms


def evaluate(all_probs, y_true, threshold=0.5, per_label_thresholds=None):
    n = len(all_probs)
    y_pred_vecs = []

    for i in range(n):
        if per_label_thresholds is not None:
            pred = [INTENT_LABELS[j] for j in range(NUM_LABELS)
                    if all_probs[i][j] >= per_label_thresholds[j]]
        else:
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
    parser.add_argument("--ensemble-dir", default=None,
                        help="앙상블 모델 디렉토리 (예: ai/models/intent_multilabel_ensemble)")
    parser.add_argument("--optimize-thresholds", action="store_true",
                        help="Dev adversarial 데이터에서 per-label threshold 재최적화")
    args = parser.parse_args()

    is_ensemble = args.ensemble_dir is not None

    if is_ensemble:
        models, tokenizer, device, ensemble_meta = load_ensemble(args.ensemble_dir)
        print(f"\n앙상블 평가 모드 ({len(models)}개 모델)")
    else:
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

    # ── Per-label Threshold (compare_strategies 결과 로드) ──
    strategy_path = ROOT / "ai" / "experiments" / "results" / "strategy_comparison_results.json"
    opt_thresholds = None
    if strategy_path.exists():
        with open(strategy_path, "r", encoding="utf-8") as f:
            strategy_results = json.load(f)
        th_key = "optimal_thresholds" if "optimal_thresholds" in strategy_results else "strategy1_thresholds"
        if th_key in strategy_results:
            opt_thresholds = np.array([
                strategy_results[th_key].get(label, 0.5)
                for label in INTENT_LABELS
            ])
            print(f"Per-label Threshold 로드: {strategy_path.name}")
            for label, th in zip(INTENT_LABELS, opt_thresholds):
                print(f"  {label:<16}: {th:.2f}")
            print()

    # ── 기존 adversarial 평가 ──
    adv_texts = [item["text"] for item in adv_data]
    adv_y_true = np.array([labels_to_vector(item["labels"]) for item in adv_data])
    if is_ensemble:
        adv_probs = get_ensemble_probs(models, tokenizer, adv_texts, device)
    else:
        adv_probs = get_all_probs(model, tokenizer, adv_texts, device)
    adv_result = evaluate(adv_probs, adv_y_true)

    # ── Held-out 평가 ──
    holdout_texts = [item["text"] for item in holdout_data]
    holdout_y_true = np.array([labels_to_vector(item["labels"]) for item in holdout_data])
    if is_ensemble:
        holdout_probs = get_ensemble_probs(models, tokenizer, holdout_texts, device)
    else:
        holdout_probs = get_all_probs(model, tokenizer, holdout_texts, device)
    holdout_result = evaluate(holdout_probs, holdout_y_true)

    # ── Threshold 재최적화 (--optimize-thresholds) ──
    if args.optimize_thresholds:
        opt_thresholds = optimize_thresholds(adv_probs, adv_y_true)
        print(f"\n  재최적화된 Threshold:")
        for label, th in zip(INTENT_LABELS, opt_thresholds):
            print(f"    {label:<16}: {th:.2f}")

    # ── Per-label Threshold 평가 ──
    adv_result_th = None
    holdout_result_th = None
    if opt_thresholds is not None:
        adv_result_th = evaluate(adv_probs, adv_y_true, per_label_thresholds=opt_thresholds)
        holdout_result_th = evaluate(holdout_probs, holdout_y_true, per_label_thresholds=opt_thresholds)

    # ── 추론 시간 측정 ──
    if is_ensemble:
        infer_ms = measure_inference_time(models, tokenizer, holdout_texts, device, is_ensemble=True)
    else:
        infer_ms = measure_inference_time(model, tokenizer, holdout_texts, device, is_ensemble=False)
    print(f"\n  추론 시간 (1건): {infer_ms:.1f}ms {'✅' if infer_ms < 100 else '⚠️  100ms 초과'}")

    # ── 비교 출력 ──
    sep = "─" * 60

    mode_label = f"앙상블 {len(models)}개 모델" if is_ensemble else "단일 모델"
    print(f"\n{'═'*60}")
    print(f"  과적합 검증 — 기존 vs Held-out 비교 [{mode_label}] (Baseline 0.5)")
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

    # ── Per-label Threshold 비교 ──
    if adv_result_th and holdout_result_th:
        print(f"\n{'═'*60}")
        print("  Per-label Threshold — 기존 vs Held-out 비교")
        print(f"{'═'*60}")
        print(f"\n  {'지표':<24} {'기존 ADV':>12} {'Held-out':>12} {'차이':>10}")
        print(f"  {'─'*24} {'─'*12} {'─'*12} {'─'*10}")

        for name, key in metrics:
            a = adv_result_th[key]
            h = holdout_result_th[key]
            diff = h - a
            sign = "+" if diff >= 0 else ""

            if key == "hamming_loss":
                print(f"  {name:<24} {a:>11.4f} {h:>11.4f} {sign}{diff:>9.4f}")
            elif key in ("over_triggering", "under_triggering"):
                print(f"  {name:<24} {a*100:>10.1f}% {h*100:>10.1f}% {sign}{diff*100:>8.1f}%p")
            else:
                print(f"  {name:<24} {a*100:>10.1f}% {h*100:>10.1f}% {sign}{diff*100:>8.1f}%p")

        # ── Baseline vs Threshold 효과 (Held-out) ──
        print(f"\n{'═'*60}")
        print("  Held-out: Baseline(0.5) vs Per-label Threshold 효과")
        print(f"{'═'*60}")
        print(f"\n  {'지표':<24} {'Baseline':>12} {'Threshold':>12} {'효과':>10}")
        print(f"  {'─'*24} {'─'*12} {'─'*12} {'─'*10}")

        for name, key in metrics:
            b = holdout_result[key]
            t = holdout_result_th[key]
            diff = t - b
            sign = "+" if diff >= 0 else ""

            if key == "hamming_loss":
                print(f"  {name:<24} {b:>11.4f} {t:>11.4f} {sign}{diff:>9.4f}")
            elif key in ("over_triggering", "under_triggering"):
                print(f"  {name:<24} {b*100:>10.1f}% {t*100:>10.1f}% {sign}{diff*100:>8.1f}%p")
            else:
                print(f"  {name:<24} {b*100:>10.1f}% {t*100:>10.1f}% {sign}{diff*100:>8.1f}%p")

    # ── 과적합 판정 (Baseline) ──
    acc_diff = holdout_result["subset_accuracy"] - adv_result["subset_accuracy"]
    print(f"\n{sep}")
    print("  과적합 판정 (Baseline)")
    print(sep)
    if abs(acc_diff) <= 0.05:
        print(f"  ✅ Subset Accuracy 차이 {acc_diff*100:+.1f}%p → 과적합 없음 (±5%p 이내)")
    elif acc_diff < -0.05:
        print(f"  ⚠️  Subset Accuracy 차이 {acc_diff*100:+.1f}%p → 과적합 의심 (Held-out에서 성능 하락)")
    else:
        print(f"  ✅ Subset Accuracy 차이 {acc_diff*100:+.1f}%p → Held-out이 오히려 높음 (과적합 아님)")

    if holdout_result_th:
        acc_diff_th = holdout_result_th["subset_accuracy"] - adv_result_th["subset_accuracy"]
        print(f"\n{sep}")
        print("  과적합 판정 (Per-label Threshold)")
        print(sep)
        if abs(acc_diff_th) <= 0.05:
            print(f"  ✅ Subset Accuracy 차이 {acc_diff_th*100:+.1f}%p → 과적합 없음 (±5%p 이내)")
        elif acc_diff_th < -0.05:
            print(f"  ⚠️  Subset Accuracy 차이 {acc_diff_th*100:+.1f}%p → 과적합 의심 (Held-out에서 성능 하락)")
        else:
            print(f"  ✅ Subset Accuracy 차이 {acc_diff_th*100:+.1f}%p → Held-out이 오히려 높음 (과적합 아님)")

    # ── Held-out 카테고리별 (Threshold 적용) ──
    use_thresholds = opt_thresholds if opt_thresholds is not None else None
    eval_label = "Per-label Threshold" if use_thresholds is not None else "Baseline 0.5"
    print(f"\n{sep}")
    print(f"  Held-out 카테고리별 Exact Match ({eval_label})")
    print(sep)
    cat_stats = defaultdict(lambda: [0, 0])
    errors = []
    for idx, item in enumerate(holdout_data):
        true = sorted(item["labels"])
        if use_thresholds is not None:
            pred_labels = [INTENT_LABELS[j] for j in range(NUM_LABELS)
                           if holdout_probs[idx][j] >= use_thresholds[j]]
        else:
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
    print(f"  Held-out 오답 ({len(errors)}건) [{eval_label}]")
    print(sep)
    for r in errors:
        print(f"  [{r['id']:2d}] [{r['category']}]")
        print(f"       text : {r['text']}")
        print(f"       true : {r['true']}")
        print(f"       pred : {r['pred']}")
        print()

    # ── 결과 저장 ──
    out = {
        "mode": "ensemble" if is_ensemble else "single",
        "dev_adversarial": {k: round(v, 4) if isinstance(v, float) else v for k, v in adv_result.items()},
        "holdout_adversarial": {k: round(v, 4) if isinstance(v, float) else v for k, v in holdout_result.items()},
        "accuracy_diff": round(acc_diff, 4),
        "holdout_errors": errors,
    }
    if is_ensemble:
        out["ensemble_info"] = {
            "n_models": len(models),
            "seeds": [m["seed"] for m in models],
            "features": ensemble_meta.get("features", []),
        }
    if adv_result_th and holdout_result_th:
        out["dev_adversarial_threshold"] = {k: round(v, 4) if isinstance(v, float) else v for k, v in adv_result_th.items()}
        out["holdout_adversarial_threshold"] = {k: round(v, 4) if isinstance(v, float) else v for k, v in holdout_result_th.items()}
        out["accuracy_diff_threshold"] = round(holdout_result_th["subset_accuracy"] - adv_result_th["subset_accuracy"], 4)
        out["optimal_thresholds"] = {label: float(th) for label, th in zip(INTENT_LABELS, opt_thresholds)}
        out["thresholds_optimized"] = bool(args.optimize_thresholds)
    out["inference_time_ms"] = round(infer_ms, 1)
    out_name = "holdout_ensemble_results.json" if is_ensemble else "holdout_evaluation_results.json"
    out_path = ROOT / "ai" / "experiments" / "results" / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
