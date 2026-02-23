"""
오분류 분석 — 최종 모델의 틀린 문장을 유형별로 분류

Stage 4 결과를 기반으로 오분류 사례를 수집하고,
유형별(경계 혼동, 초단문, 오타, 과신뢰, 맥락의존)로 분류한다.

사용법:
    python ai/experiments_v2/run_error_analysis.py
    python ai/experiments_v2/run_error_analysis.py --model klue/bert-base

사전: pip install transformers scikit-learn matplotlib seaborn
"""

import argparse
import json
import torch
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import confusion_matrix, f1_score

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "intent_v2"
SPLITS_DIR = DATA_DIR / "splits"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_qa",
]
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}
ID2LABEL = {i: label for i, label in enumerate(INTENT_LABELS)}

MAX_LENGTH = 64
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 경계 쌍 정의 (오분류 유형 판별용)
BOUNDARY_PAIRS = {
    frozenset({"doc_search", "doc_qa"}): "high",
    frozenset({"doc_search", "judgment"}): "high",
    frozenset({"doc_qa", "judgment"}): "high",
    frozenset({"doc_summary", "doc_qa"}): "high",
    frozenset({"doc_generate", "doc_summary"}): "high",
    frozenset({"schedule_add", "schedule_view"}): "high",
    frozenset({"doc_search", "doc_summary"}): "medium",
    frozenset({"judgment", "general"}): "medium",
    frozenset({"doc_generate", "doc_qa"}): "medium",
    frozenset({"doc_search", "doc_generate"}): "medium",
}


def load_jsonl(path):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def load_model(model_name):
    """학습된 모델 로드 (서비스 디렉토리 또는 HuggingFace)"""
    model_dir = BASE_DIR / "ai" / "models" / "intent_classifier"

    if (model_dir / "model.safetensors").exists() or (model_dir / "pytorch_model.bin").exists():
        print(f"  서비스 디렉토리에서 로드: {model_dir}")
        tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
        return model, tokenizer

    # 서비스 모델 없으면 base 모델 로드 (학습 안 된 상태)
    print(f"  [WARN] 서비스 모델 없음, base 모델 사용: {model_name}")
    trust_remote = "distilkobert" in model_name
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=trust_remote)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=len(INTENT_LABELS),
        id2label=ID2LABEL, label2id=LABEL2ID,
        trust_remote_code=trust_remote,
    )
    return model, tokenizer


def predict_batch(model, tokenizer, texts):
    """배치 예측 → (preds, confidences, all_probs)"""
    model.eval()
    model.to(device)

    preds = []
    confidences = []
    all_probs = []

    for text in texts:
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=MAX_LENGTH)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()[0]
        pred_id = np.argmax(probs)
        preds.append(ID2LABEL[pred_id])
        confidences.append(probs[pred_id])
        all_probs.append(probs)

    return preds, confidences, all_probs


def classify_error_type(text, true_label, pred_label, confidence):
    """오분류 유형 분류"""
    types = []

    # 1. 경계 혼동
    pair = frozenset({true_label, pred_label})
    if pair in BOUNDARY_PAIRS:
        types.append(f"boundary_{BOUNDARY_PAIRS[pair]}")

    # 2. 초단문 (4어절 이하)
    word_count = len(text.split())
    if word_count <= 4:
        types.append("short_text")

    # 3. 오타/비표준
    import re
    chosung_pattern = re.compile(r"[ㄱ-ㅎ]{2,}")
    if chosung_pattern.search(text):
        types.append("typo_chosung")
    if any(c in text for c in ["ㅋ", "ㅎ", "ㅠ", "ㅜ"]):
        types.append("informal")

    # 4. 과신뢰 (틀렸는데 confidence > 0.9)
    if confidence > 0.9:
        types.append("overconfident")

    # 5. 저신뢰 (confidence < 0.5)
    if confidence < 0.5:
        types.append("low_confidence")

    if not types:
        types.append("other")

    return types


def analyze_errors(data, preds, confidences, all_probs):
    """오분류 분석"""
    errors = []
    correct_count = 0

    for i, (item, pred, conf, probs) in enumerate(zip(data, preds, confidences, all_probs)):
        true = item["label"]
        if pred == true:
            correct_count += 1
            continue

        # Top-3 후보
        sorted_idx = np.argsort(probs)[::-1]
        top3 = [(ID2LABEL[idx], round(float(probs[idx]), 4)) for idx in sorted_idx[:3]]

        # 오류 유형
        error_types = classify_error_type(item["text"], true, pred, conf)

        errors.append({
            "text": item["text"],
            "true_label": true,
            "pred_label": pred,
            "confidence": round(float(conf), 4),
            "top3": top3,
            "error_types": error_types,
            "word_count": len(item["text"].split()),
        })

    return errors, correct_count


def generate_report(errors, total, dataset_name):
    """오분류 보고서 생성"""
    report = []
    report.append(f"# 오분류 분석 보고서 — {dataset_name}")
    report.append(f"\n총 {total}개 중 {len(errors)}개 오분류 ({len(errors)/total*100:.1f}%)\n")

    # 유형별 통계
    type_counts = Counter()
    for err in errors:
        for t in err["error_types"]:
            type_counts[t] += 1

    report.append("## 오분류 유형 분포\n")
    report.append("| 유형 | 건수 | 비율 |")
    report.append("|------|:----:|:----:|")
    for t, c in type_counts.most_common():
        report.append(f"| {t} | {c} | {c/len(errors)*100:.1f}% |")

    # 혼동 쌍 통계
    pair_counts = Counter()
    for err in errors:
        pair = f"{err['true_label']} → {err['pred_label']}"
        pair_counts[pair] += 1

    report.append("\n## 혼동 쌍 (Top 10)\n")
    report.append("| 실제 → 예측 | 건수 |")
    report.append("|------------|:----:|")
    for pair, count in pair_counts.most_common(10):
        report.append(f"| {pair} | {count} |")

    # 과신뢰 오분류
    overconfident = [e for e in errors if "overconfident" in e["error_types"]]
    if overconfident:
        report.append(f"\n## 과신뢰 오분류 ({len(overconfident)}건)\n")
        report.append("모델이 90% 이상 확신했지만 틀린 케이스:\n")
        for e in overconfident[:10]:
            report.append(f"- \"{e['text']}\"")
            report.append(f"  - 실제: `{e['true_label']}` | 예측: `{e['pred_label']}` ({e['confidence']:.2%})")

    # 경계 혼동
    boundary = [e for e in errors if any("boundary" in t for t in e["error_types"])]
    if boundary:
        report.append(f"\n## 경계 혼동 ({len(boundary)}건)\n")
        for e in boundary[:15]:
            report.append(f"- \"{e['text']}\"")
            report.append(f"  - 실제: `{e['true_label']}` | 예측: `{e['pred_label']}` ({e['confidence']:.2%})")
            report.append(f"  - Top3: {e['top3']}")

    # 전체 오분류 목록 (최대 50개)
    report.append(f"\n## 전체 오분류 목록 (상위 50건)\n")
    report.append("| # | Text | True | Pred | Conf | Types |")
    report.append("|:-:|------|------|------|:----:|-------|")
    for i, e in enumerate(sorted(errors, key=lambda x: -x["confidence"])[:50], 1):
        text_short = e["text"][:40] + "..." if len(e["text"]) > 40 else e["text"]
        types_str = ", ".join(e["error_types"])
        report.append(f"| {i} | {text_short} | {e['true_label']} | {e['pred_label']} | {e['confidence']:.2f} | {types_str} |")

    return "\n".join(report)


# ── 시각화 ──

def plot_error_type_distribution(errors, filename="error_types.png"):
    """오분류 유형 분포 파이 차트"""
    type_counts = Counter()
    for err in errors:
        for t in err["error_types"]:
            type_counts[t] += 1

    labels = [k for k, _ in type_counts.most_common()]
    values = [v for _, v in type_counts.most_common()]

    fig, ax = plt.subplots(figsize=(8, 6))
    colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
    ax.pie(values, labels=labels, autopct="%1.1f%%", colors=colors)
    ax.set_title("Error Type Distribution")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


def plot_confusion_heatmap(data, preds, filename="confusion_final.png"):
    """정규화된 혼동행렬"""
    labels = [d["label"] for d in data]
    cm = confusion_matrix(labels, preds, labels=INTENT_LABELS)
    cm_norm = cm.astype("float") / cm.sum(axis=1, keepdims=True)

    fig, axes = plt.subplots(1, 2, figsize=(18, 7))

    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=INTENT_LABELS, yticklabels=INTENT_LABELS, ax=axes[0])
    axes[0].set_title("Confusion Matrix (Counts)")
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("Actual")

    sns.heatmap(cm_norm, annot=True, fmt=".2f", cmap="YlOrRd",
                xticklabels=INTENT_LABELS, yticklabels=INTENT_LABELS, ax=axes[1])
    axes[1].set_title("Confusion Matrix (Normalized)")
    axes[1].set_xlabel("Predicted")
    axes[1].set_ylabel("Actual")

    plt.suptitle(f"Error Analysis — {len(data)} samples", fontsize=14)
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


def plot_confidence_by_correctness(data, preds, confidences, filename="confidence_correct_vs_wrong.png"):
    """정답 vs 오답 Confidence 분포 비교"""
    labels = [d["label"] for d in data]
    correct_conf = [c for l, p, c in zip(labels, preds, confidences) if l == p]
    wrong_conf = [c for l, p, c in zip(labels, preds, confidences) if l != p]

    fig, ax = plt.subplots(figsize=(8, 5))
    bins = np.linspace(0, 1, 30)
    ax.hist(correct_conf, bins=bins, alpha=0.6, label=f"Correct ({len(correct_conf)})", color="#4A90D9")
    ax.hist(wrong_conf, bins=bins, alpha=0.6, label=f"Wrong ({len(wrong_conf)})", color="#D96459")
    ax.set_xlabel("Confidence")
    ax.set_ylabel("Count")
    ax.set_title("Confidence: Correct vs Wrong Predictions")
    ax.legend()
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"  -> {filename}")


# ── 메인 ──

def main():
    parser = argparse.ArgumentParser(description="오분류 분석")
    parser.add_argument("--model", type=str, default="klue/bert-base")
    args = parser.parse_args()

    print("=" * 60)
    print("  오분류 분석 (Error Analysis)")
    print("=" * 60)

    model, tokenizer = load_model(args.model)

    # 데이터 로드
    datasets = {}
    if (SPLITS_DIR / "test.jsonl").exists():
        datasets["test"] = load_jsonl(SPLITS_DIR / "test.jsonl")
    adv_path = DATA_DIR / "adversarial_v2.json"
    if adv_path.exists():
        with open(adv_path, "r", encoding="utf-8") as f:
            datasets["adversarial"] = json.load(f)

    all_errors = {}

    for ds_name, data in datasets.items():
        print(f"\n--- {ds_name} ({len(data)}개) ---")

        # 유효 라벨만 (레거시 데이터 필터)
        data = [d for d in data if d["label"] in set(INTENT_LABELS)]

        texts = [d["text"] for d in data]
        preds, confidences, all_probs = predict_batch(model, tokenizer, texts)

        # 오분류 분석
        errors, correct = analyze_errors(data, preds, confidences, all_probs)
        all_errors[ds_name] = errors
        print(f"  정답: {correct}/{len(data)} ({correct/len(data)*100:.1f}%)")
        print(f"  오답: {len(errors)}/{len(data)} ({len(errors)/len(data)*100:.1f}%)")

        # 보고서 생성
        report = generate_report(errors, len(data), ds_name)
        report_path = RESULTS_DIR / f"error_analysis_{ds_name}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"  -> {report_path.name}")

        # 오류 데이터 JSON
        errors_path = RESULTS_DIR / f"errors_{ds_name}.json"
        with open(errors_path, "w", encoding="utf-8") as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)

        # 차트
        if errors:
            plot_error_type_distribution(errors, f"error_types_{ds_name}.png")
        plot_confusion_heatmap(data, preds, f"confusion_analysis_{ds_name}.png")
        plot_confidence_by_correctness(data, preds, confidences,
                                        f"confidence_analysis_{ds_name}.png")

    # 통합 요약
    print("\n" + "=" * 60)
    print("  오분류 분석 완료")
    print("=" * 60)
    for ds_name, errors in all_errors.items():
        if errors:
            type_counts = Counter()
            for e in errors:
                for t in e["error_types"]:
                    type_counts[t] += 1
            print(f"\n  [{ds_name}] 주요 유형: {type_counts.most_common(3)}")
    print(f"\n  결과: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
