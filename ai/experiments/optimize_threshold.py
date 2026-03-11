"""
Per-label Threshold 최적화

validation set에서 intent별 최적 threshold를 자동 탐색한 뒤,
adversarial 테스트에서 uniform(0.5) vs optimized 성능을 비교.

사용법 (RunPod 등 GPU 환경):
  python -m ai.experiments.optimize_threshold
  python -m ai.experiments.optimize_threshold --model-dir ai/models/intent_multilabel
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
    model_info_file = model_dir / "model_info.json"

    with open(model_info_file, "r", encoding="utf-8") as f:
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
    """모든 텍스트에 대해 확률 벡터 반환"""
    all_probs = []
    for text in texts:
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
        all_probs.append(probs)

    return np.array(all_probs)


def predict_with_thresholds(probs, thresholds):
    """Per-label threshold로 예측"""
    pred_labels = [
        INTENT_LABELS[i] for i in range(NUM_LABELS)
        if probs[i] >= thresholds[i]
    ]
    if not pred_labels:
        best_idx = np.argmax(probs)
        pred_labels = [INTENT_LABELS[best_idx]]
    return sorted(pred_labels)


# ── Threshold 최적화 ─────────────────────────────────────────────────────────

def optimize_per_label_threshold(all_probs, y_true, search_range=None):
    """
    validation set에서 intent별 최적 threshold 탐색.
    각 label에 대해 F1을 최대화하는 threshold를 독립적으로 찾음.
    """
    if search_range is None:
        search_range = np.arange(0.15, 0.85, 0.05)

    best_thresholds = [0.5] * NUM_LABELS

    print(f"\n{'─'*60}")
    print("[ Per-label Threshold 최적화 ]")
    print(f"{'─'*60}")
    print(f"  탐색 범위: {search_range[0]:.2f} ~ {search_range[-1]:.2f} (step {search_range[1]-search_range[0]:.2f})")
    print(f"  Validation 샘플: {len(all_probs)}개\n")

    for i, label in enumerate(INTENT_LABELS):
        true_col = y_true[:, i]

        # 이 label이 validation에 없으면 스킵
        if true_col.sum() == 0:
            print(f"  {label:<16} → 0.50 (validation에 양성 샘플 없음)")
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


# ── 평가 함수 ────────────────────────────────────────────────────────────────

def evaluate(all_probs, y_true, thresholds, title=""):
    """주어진 threshold로 전체 지표 계산"""
    n = len(all_probs)
    y_pred_vecs = []

    for i in range(n):
        pred_labels = predict_with_thresholds(all_probs[i], thresholds)
        y_pred_vecs.append(labels_to_vector(pred_labels))

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

    # Over/Under-triggering
    true_is_multi = (y_true.sum(axis=1) >= 2)
    pred_is_multi = (y_pred.sum(axis=1) >= 2)
    n_true_single = (~true_is_multi).sum()
    n_true_multi = true_is_multi.sum()
    fp = ((~true_is_multi) & pred_is_multi).sum()
    fn = (true_is_multi & (~pred_is_multi)).sum()
    over_trigger = fp / n_true_single if n_true_single > 0 else 0.0
    under_trigger = fn / n_true_multi if n_true_multi > 0 else 0.0

    return {
        "title": title,
        "subset_accuracy": exact_match,
        "hamming_loss": hamming,
        "jaccard": jaccard,
        "macro_f1": macro_f1,
        "micro_f1": micro_f1,
        "over_triggering": over_trigger,
        "under_triggering": under_trigger,
        "n_over": int(fp),
        "n_under": int(fn),
        "n_single": int(n_true_single),
        "n_multi": int(n_true_multi),
    }


def print_comparison(results_list):
    """여러 threshold 설정 결과 비교 출력"""
    sep = "─" * 60

    print(f"\n{sep}")
    print("[ Threshold 비교 결과 ]")
    print(sep)

    # 헤더
    header = f"  {'지표':<24}"
    for r in results_list:
        header += f" {r['title']:>14}"
    print(header)
    print(f"  {'─'*24}" + " ─" * 14 * len(results_list))

    rows = [
        ("Subset Accuracy", "subset_accuracy", True),
        ("Hamming Loss", "hamming_loss", False),
        ("Jaccard Score", "jaccard", True),
        ("Macro F1", "macro_f1", True),
        ("Micro F1", "micro_f1", True),
        ("Over-triggering", "over_triggering", False),
        ("Under-triggering", "under_triggering", False),
    ]

    for name, key, higher_is_better in rows:
        line = f"  {name:<24}"
        values = [r[key] for r in results_list]
        best_val = max(values) if higher_is_better else min(values)

        for r in results_list:
            val = r[key]
            if key in ("over_triggering", "under_triggering"):
                n_key = "n_over" if key == "over_triggering" else "n_under"
                d_key = "n_single" if key == "over_triggering" else "n_multi"
                s = f"{val*100:.1f}% ({r[n_key]}/{r[d_key]})"
            else:
                s = f"{val*100:.1f}%" if key != "hamming_loss" else f"{val:.4f}"

            if val == best_val and len(results_list) > 1:
                s = f"*{s}"
            line += f" {s:>14}"
        print(line)


def print_adversarial_detail(all_probs, y_true, thresholds, samples, title=""):
    """카테고리별 Exact Match + 오답 목록"""
    sep = "─" * 60
    detail_rows = []

    for idx, item in enumerate(samples):
        true_labels = sorted(item["labels"])
        pred_labels = predict_with_thresholds(all_probs[idx], thresholds)
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

    # 카테고리별
    cat_stats = defaultdict(lambda: [0, 0])
    for row in detail_rows:
        cat = row["category"]
        cat_stats[cat][1] += 1
        if row["correct"]:
            cat_stats[cat][0] += 1

    print(f"\n{sep}")
    print(f"[ 카테고리별 Exact Match — {title} ]")
    print(sep)
    for cat, (ok, total) in sorted(cat_stats.items()):
        pct = ok / total * 100
        bar = "█" * int(pct / 5)
        print(f"  {cat:<30} {ok:2d}/{total:2d}  ({pct:5.1f}%)  {bar}")

    # 오답
    errors = [r for r in detail_rows if not r["correct"]]
    print(f"\n{sep}")
    print(f"[ 오답 목록 — {title} ({len(errors)}건) ]")
    print(sep)
    for r in errors:
        print(f"  [{r['id']:2d}] [{r['category']}]")
        print(f"       text : {r['text']}")
        print(f"       true : {r['true']}")
        print(f"       pred : {r['pred']}")
        print(f"       note : {r['note']}")
        print()


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default=str(ROOT / "ai" / "models" / "intent_multilabel"))
    args = parser.parse_args()

    # 1. 모델 로드
    model, tokenizer, device = load_model(args.model_dir)

    # 2. Validation 데이터 로드
    val_path = ROOT / "data" / "training" / "intent_multilabel" / "val.jsonl"
    val_items = []
    with open(val_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                val_items.append(json.loads(line))
    print(f"\nValidation 데이터: {len(val_items)}개")

    val_texts = [item["text"] for item in val_items]
    val_y_true = np.array([labels_to_vector(item["labels"]) for item in val_items])

    # 3. Validation 확률 계산
    print("Validation 확률 계산 중...")
    val_probs = get_all_probs(model, tokenizer, val_texts, device)

    # 4. Per-label Threshold 최적화
    best_thresholds = optimize_per_label_threshold(val_probs, val_y_true)

    print(f"\n  최적 Threshold: {{")
    for i, label in enumerate(INTENT_LABELS):
        print(f"    {label:<16}: {best_thresholds[i]}")
    print(f"  }}")

    # 5. Validation에서 비교
    uniform_thresholds = [0.5] * NUM_LABELS
    val_uniform = evaluate(val_probs, val_y_true, uniform_thresholds, "Uniform(0.5)")
    val_optimized = evaluate(val_probs, val_y_true, best_thresholds, "Optimized")

    print(f"\n{'═'*60}")
    print("  VALIDATION 결과")
    print(f"{'═'*60}")
    print_comparison([val_uniform, val_optimized])

    # 6. Adversarial 테스트 로드 및 평가
    adv_path = ROOT / "data" / "training" / "intent_multilabel" / "adversarial_compound_test.json"
    with open(adv_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    adv_samples = raw["data"]
    print(f"\n\nAdversarial 테스트: {len(adv_samples)}개")

    adv_texts = [item["text"] for item in adv_samples]
    adv_y_true = np.array([labels_to_vector(item["labels"]) for item in adv_samples])

    print("Adversarial 확률 계산 중...")
    adv_probs = get_all_probs(model, tokenizer, adv_texts, device)

    adv_uniform = evaluate(adv_probs, adv_y_true, uniform_thresholds, "Uniform(0.5)")
    adv_optimized = evaluate(adv_probs, adv_y_true, best_thresholds, "Optimized")

    print(f"\n{'═'*60}")
    print("  ADVERSARIAL 결과")
    print(f"{'═'*60}")
    print_comparison([adv_uniform, adv_optimized])

    # 7. Adversarial 카테고리별 비교
    print_adversarial_detail(adv_probs, adv_y_true, uniform_thresholds, adv_samples, "Uniform(0.5)")
    print_adversarial_detail(adv_probs, adv_y_true, best_thresholds, adv_samples, "Optimized")

    # 8. 결과 저장
    model_dir = Path(args.model_dir)
    model_info_file = model_dir / "model_info.json"

    with open(model_info_file, "r", encoding="utf-8") as f:
        model_info = json.load(f)

    model_info["per_label_thresholds"] = {
        INTENT_LABELS[i]: best_thresholds[i] for i in range(NUM_LABELS)
    }

    with open(model_info_file, "w", encoding="utf-8") as f:
        json.dump(model_info, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Per-label thresholds → {model_info_file} 에 저장 완료")

    # 결과 JSON 저장
    result = {
        "per_label_thresholds": {INTENT_LABELS[i]: best_thresholds[i] for i in range(NUM_LABELS)},
        "validation": {
            "uniform": {k: round(v, 4) if isinstance(v, float) else v for k, v in val_uniform.items()},
            "optimized": {k: round(v, 4) if isinstance(v, float) else v for k, v in val_optimized.items()},
        },
        "adversarial": {
            "uniform": {k: round(v, 4) if isinstance(v, float) else v for k, v in adv_uniform.items()},
            "optimized": {k: round(v, 4) if isinstance(v, float) else v for k, v in adv_optimized.items()},
        },
    }

    out_path = ROOT / "ai" / "experiments" / "results" / "threshold_optimization_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"📊 전체 결과 → {out_path}")


if __name__ == "__main__":
    main()
