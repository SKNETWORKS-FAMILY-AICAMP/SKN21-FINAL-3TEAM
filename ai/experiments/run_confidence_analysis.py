"""
Confidence Threshold 분석 (제안 2)

기존 배포 모델의 confidence 값을 분석하여 최적 threshold를 실험적으로 결정.
- threshold별 precision / recall / coverage
- overconfident error 비율
- false rejection 비율

사용법:
    python ai/experiments/run_confidence_analysis.py
"""

import json
import sys
import torch
import numpy as np
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data" / "training" / "intent"
MODEL_DIR = BASE_DIR / "ai" / "models" / "intent_classifier"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate",
    "meeting_generate", "schedule_add", "schedule_view", "general",
]


def load_test_data():
    """adversarial + blind 테스트셋 모두 로드"""
    all_data = []

    adv_path = DATA_DIR / "adversarial_test.json"
    if adv_path.exists():
        with open(adv_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for d in data:
            d["source"] = "adversarial"
        all_data.extend(data)

    blind_path = DATA_DIR / "blind_test.json"
    if blind_path.exists():
        with open(blind_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for d in data:
            d["source"] = "blind"
        all_data.extend(data)

    return all_data


def load_model():
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained("klue/bert-base")
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    model.eval()

    with open(MODEL_DIR / "label_map.json", "r", encoding="utf-8") as f:
        label_map = json.load(f)
    id2label = {int(k): v for k, v in label_map["id2label"].items()}

    return model, tokenizer, id2label


def predict_all(model, tokenizer, id2label, data):
    from ai.agents.preprocessing import preprocess

    results = []
    for item in data:
        text = preprocess(item["text"])
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=64)

        with torch.no_grad():
            outputs = model(**inputs)

        probs = torch.softmax(outputs.logits, dim=-1)
        pred_id = torch.argmax(probs, dim=-1).item()
        confidence = probs[0][pred_id].item()
        intent = id2label.get(pred_id, "general")

        results.append({
            "text": item["text"],
            "label": item["label"],
            "predicted": intent,
            "confidence": confidence,
            "correct": intent == item["label"],
            "source": item.get("source", "unknown"),
        })

    return results


def analyze_thresholds(predictions):
    """threshold별 precision, recall, coverage 분석"""
    thresholds = np.arange(0.50, 0.96, 0.05)
    analysis = []

    total = len(predictions)
    total_correct = sum(1 for p in predictions if p["correct"])

    for threshold in thresholds:
        # threshold 넘는 것만 선택
        above = [p for p in predictions if p["confidence"] >= threshold]
        below = [p for p in predictions if p["confidence"] < threshold]

        coverage = len(above) / total if total > 0 else 0
        correct_above = sum(1 for p in above if p["correct"])
        precision = correct_above / len(above) if len(above) > 0 else 0
        recall = correct_above / total_correct if total_correct > 0 else 0

        # Overconfident errors: 틀렸는데 confidence가 높은 것
        overconfident = sum(1 for p in above if not p["correct"])
        overconfident_rate = overconfident / len(above) if len(above) > 0 else 0

        # False rejection: 맞았는데 threshold 밑이라 폴백되는 것
        false_rejected = sum(1 for p in below if p["correct"])
        false_rejection_rate = false_rejected / total_correct if total_correct > 0 else 0

        analysis.append({
            "threshold": round(float(threshold), 2),
            "coverage": round(coverage, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "overconfident_errors": overconfident,
            "overconfident_rate": round(overconfident_rate, 4),
            "false_rejections": false_rejected,
            "false_rejection_rate": round(false_rejection_rate, 4),
            "accepted": len(above),
            "rejected": len(below),
        })

    return analysis


def plot_threshold_analysis(analysis, total):
    """threshold 분석 시각화"""
    thresholds = [a["threshold"] for a in analysis]
    precisions = [a["precision"] for a in analysis]
    recalls = [a["recall"] for a in analysis]
    coverages = [a["coverage"] for a in analysis]
    overconf_rates = [a["overconfident_rate"] for a in analysis]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # 1. Precision / Recall / Coverage
    ax = axes[0]
    ax.plot(thresholds, precisions, "b-o", label="Precision", linewidth=2)
    ax.plot(thresholds, recalls, "r-s", label="Recall", linewidth=2)
    ax.plot(thresholds, coverages, "g--^", label="Coverage", linewidth=2)
    ax.set_xlabel("Confidence Threshold")
    ax.set_ylabel("Rate")
    ax.set_title("Precision / Recall / Coverage by Threshold")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1.05)
    # 0.7 라인 표시
    ax.axvline(x=0.7, color="gray", linestyle=":", alpha=0.7, label="0.7")
    ax.text(0.71, 0.05, "0.7", fontsize=9, color="gray")

    # 2. Overconfident Error Rate
    ax = axes[1]
    bars = ax.bar(thresholds, overconf_rates, width=0.04, color="#e74c3c", alpha=0.7)
    ax.set_xlabel("Confidence Threshold")
    ax.set_ylabel("Overconfident Error Rate")
    ax.set_title("Overconfident Errors (wrong but above threshold)")
    ax.grid(True, alpha=0.3)
    for bar, rate in zip(bars, overconf_rates):
        if rate > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.003,
                    f"{rate:.2%}", ha="center", fontsize=8)

    # 3. Confidence 분포 (correct vs incorrect)
    ax = axes[2]
    # This will be a separate call since we need raw predictions
    ax.set_xlabel("Confidence")
    ax.set_ylabel("Count")
    ax.set_title("Confidence Distribution (placeholder)")
    ax.text(0.5, 0.5, "See confidence_distribution plot", transform=ax.transAxes, ha="center")

    plt.suptitle(f"Confidence Threshold Analysis ({total} samples)", fontsize=14)
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "confidence_threshold.png", dpi=150)
    plt.close()
    print("  -> confidence_threshold.png")


def plot_confidence_distribution(predictions):
    """correct vs incorrect confidence 분포"""
    correct_confs = [p["confidence"] for p in predictions if p["correct"]]
    incorrect_confs = [p["confidence"] for p in predictions if not p["correct"]]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 히스토그램
    ax = axes[0]
    bins = np.arange(0, 1.05, 0.05)
    ax.hist(correct_confs, bins=bins, alpha=0.7, label=f"Correct ({len(correct_confs)})", color="#2ecc71")
    ax.hist(incorrect_confs, bins=bins, alpha=0.7, label=f"Incorrect ({len(incorrect_confs)})", color="#e74c3c")
    ax.axvline(x=0.7, color="black", linestyle="--", alpha=0.5, label="threshold=0.7")
    ax.set_xlabel("Confidence")
    ax.set_ylabel("Count")
    ax.set_title("Confidence Distribution: Correct vs Incorrect")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 카테고리별 오분류 confidence
    ax = axes[1]
    category_errors = defaultdict(list)
    for p in predictions:
        if not p["correct"]:
            category_errors[p["label"]].append(p["confidence"])

    if category_errors:
        cats = sorted(category_errors.keys())
        positions = range(len(cats))
        data = [category_errors[c] for c in cats]
        bp = ax.boxplot(data, positions=positions, widths=0.6, patch_artist=True)
        for patch in bp["boxes"]:
            patch.set_facecolor("#e74c3c")
            patch.set_alpha(0.5)
        ax.set_xticks(positions)
        ax.set_xticklabels(cats, rotation=30, ha="right")
        ax.axhline(y=0.7, color="black", linestyle="--", alpha=0.5, label="threshold=0.7")
        ax.set_ylabel("Confidence")
        ax.set_title("Incorrect Predictions — Confidence by Category")
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "confidence_distribution.png", dpi=150)
    plt.close()
    print("  -> confidence_distribution.png")


def main():
    print("=" * 70)
    print("  Confidence Threshold 분석")
    print("=" * 70)

    data = load_test_data()
    print(f"  테스트 데이터: {len(data)}문장 "
          f"(adversarial: {sum(1 for d in data if d.get('source')=='adversarial')}, "
          f"blind: {sum(1 for d in data if d.get('source')=='blind')})")

    model, tokenizer, id2label = load_model()
    predictions = predict_all(model, tokenizer, id2label, data)

    total = len(predictions)
    correct = sum(1 for p in predictions if p["correct"])
    incorrect = total - correct
    print(f"  전체: {total}, 정답: {correct}, 오답: {incorrect}")

    # Threshold 분석
    print(f"\n{'='*70}")
    print("  Threshold별 분석")
    print(f"{'='*70}")

    analysis = analyze_thresholds(predictions)

    print(f"\n  {'Threshold':>9} {'Coverage':>9} {'Precision':>10} {'Recall':>8} "
          f"{'Overconf':>9} {'FalseRej':>9}")
    print(f"  {'-'*57}")
    for a in analysis:
        marker = " <-- 현재" if a["threshold"] == 0.70 else ""
        print(f"  {a['threshold']:>9.2f} {a['coverage']:>9.1%} {a['precision']:>10.1%} "
              f"{a['recall']:>8.1%} {a['overconfident_errors']:>6}건 "
              f"{a['false_rejections']:>6}건{marker}")

    # 최적 threshold 추천 (F1-like: precision과 recall의 조화평균)
    best = None
    best_score = 0
    for a in analysis:
        if a["precision"] > 0 and a["recall"] > 0:
            f1_like = 2 * a["precision"] * a["recall"] / (a["precision"] + a["recall"])
            if f1_like > best_score:
                best_score = f1_like
                best = a

    if best:
        print(f"\n  추천 threshold: {best['threshold']:.2f}")
        print(f"    Precision={best['precision']:.1%}, Recall={best['recall']:.1%}, "
              f"Coverage={best['coverage']:.1%}")

    # Overconfident 에러 상세 (confidence > 0.9인데 틀린 것)
    print(f"\n{'='*70}")
    print("  Overconfident Errors (confidence >= 0.9이지만 틀린 것)")
    print(f"{'='*70}")
    overconf = [p for p in predictions if not p["correct"] and p["confidence"] >= 0.9]
    if overconf:
        for p in overconf:
            print(f"  \"{p['text']}\" → 정답:{p['label']} / 예측:{p['predicted']} (conf={p['confidence']:.3f})")
        print(f"  총 {len(overconf)}건 -- 이 케이스는 threshold로 못 잡음")
    else:
        print("  없음")

    # Low confidence 정답 (confidence < 0.7인데 맞은 것)
    print(f"\n{'='*70}")
    print("  False Rejections (confidence < 0.7이지만 맞은 것)")
    print(f"{'='*70}")
    false_rej = [p for p in predictions if p["correct"] and p["confidence"] < 0.7]
    if false_rej:
        for p in false_rej[:15]:
            print(f"  \"{p['text']}\" -> 예측:{p['predicted']} (conf={p['confidence']:.3f})")
        if len(false_rej) > 15:
            print(f"  ... 외 {len(false_rej)-15}건")
        print(f"  총 {len(false_rej)}건 -- 이 케이스는 맞았지만 폴백 처리됨")
    else:
        print("  없음")

    # 시각화
    print(f"\n[Charts]")
    plot_threshold_analysis(analysis, total)
    plot_confidence_distribution(predictions)

    # JSON 저장
    output = {
        "total_samples": total,
        "correct": correct,
        "incorrect": incorrect,
        "threshold_analysis": analysis,
        "overconfident_errors": [
            {"text": p["text"], "label": p["label"], "predicted": p["predicted"], "confidence": round(p["confidence"], 4)}
            for p in predictions if not p["correct"] and p["confidence"] >= 0.9
        ],
        "false_rejections_at_0.7": len(false_rej),
    }
    output_path = RESULTS_DIR / "confidence_analysis.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  -> {output_path}")

    print(f"\n{'='*70}")
    print("  Confidence 분석 완료!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
