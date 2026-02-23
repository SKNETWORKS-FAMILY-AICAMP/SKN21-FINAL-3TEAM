"""
독립 테스트셋 Blind 평가 (제안 1)

모델 오분류 패턴에 기반하지 않은 독립적인 70문장으로 평가.
기존 adversarial_test.json과 겹치지 않는 순수 업무 시나리오 기반.

사용법:
    python ai/experiments/run_blind_evaluation.py
"""

import json
import sys
import time
import torch
import numpy as np
from pathlib import Path
from sklearn.metrics import (
    accuracy_score, f1_score, classification_report, confusion_matrix,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

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


def load_blind_test():
    path = DATA_DIR / "blind_test.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def load_model():
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained("klue/bert-base")
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    model.eval()

    with open(MODEL_DIR / "label_map.json", "r", encoding="utf-8") as f:
        label_map = json.load(f)
    id2label = {int(k): v for k, v in label_map["id2label"].items()}

    return model, tokenizer, id2label


def predict(model, tokenizer, id2label, text, use_preprocess=False):
    if use_preprocess:
        from ai.agents.preprocessing import preprocess
        text = preprocess(text)

    inputs = tokenizer(
        text, return_tensors="pt", padding=True,
        truncation=True, max_length=64,
    )
    with torch.no_grad():
        outputs = model(**inputs)

    probs = torch.softmax(outputs.logits, dim=-1)
    pred_id = torch.argmax(probs, dim=-1).item()
    confidence = probs[0][pred_id].item()
    intent = id2label.get(pred_id, "general")

    return intent, confidence


def main():
    data = load_blind_test()
    texts = [d["text"] for d in data]
    labels = [d["label"] for d in data]

    print("=" * 70)
    print("  독립 테스트셋 Blind 평가")
    print("=" * 70)
    print(f"  테스트셋: blind_test.json ({len(data)}문장)")
    print(f"  카테고리 분포: ", end="")
    from collections import Counter
    dist = Counter(labels)
    print(", ".join(f"{k}:{v}" for k, v in sorted(dist.items())))

    model, tokenizer, id2label = load_model()

    results = []

    for mode_name, use_pp in [("전처리 없음", False), ("전처리 적용", True)]:
        print(f"\n--- {mode_name} ---")

        preds = []
        confidences = []
        t0 = time.time()
        for text in texts:
            intent, conf = predict(model, tokenizer, id2label, text, use_preprocess=use_pp)
            preds.append(intent)
            confidences.append(conf)
        elapsed = (time.time() - t0) * 1000

        acc = accuracy_score(labels, preds)
        f1 = f1_score(labels, preds, average="macro", labels=INTENT_LABELS, zero_division=0)

        print(f"  Accuracy: {acc:.4f}")
        print(f"  F1 (macro): {f1:.4f}")
        print(f"  평균 confidence: {np.mean(confidences):.4f}")
        print(f"  속도: {elapsed/len(texts):.2f}ms/문장")

        # 오분류 상세
        errors = [(t, l, p, c) for t, l, p, c in zip(texts, labels, preds, confidences) if l != p]
        print(f"  오분류: {len(errors)}건")
        for text, label, pred, conf in errors:
            print(f"    \"{text}\" → 정답:{label} / 예측:{pred} (conf={conf:.3f})")

        # 카테고리별 리포트
        print(f"\n  분류 리포트:")
        report = classification_report(labels, preds, target_names=INTENT_LABELS, digits=4, zero_division=0)
        for line in report.split("\n"):
            print(f"    {line}")

        results.append({
            "mode": mode_name,
            "accuracy": round(acc, 4),
            "f1_macro": round(f1, 4),
            "avg_confidence": round(float(np.mean(confidences)), 4),
            "errors": len(errors),
            "time_ms_per_sentence": round(elapsed / len(texts), 2),
            "error_details": [
                {"text": t, "label": l, "predicted": p, "confidence": round(c, 4)}
                for t, l, p, c in errors
            ],
        })

        # 혼동행렬 (전처리 적용 버전)
        if use_pp:
            cm = confusion_matrix(labels, preds, labels=INTENT_LABELS)
            plt.figure(figsize=(10, 8))
            sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                        xticklabels=INTENT_LABELS, yticklabels=INTENT_LABELS)
            plt.title(f"Blind Test Confusion Matrix (preprocess={use_pp})\n"
                      f"{len(data)} samples — F1={f1:.4f}")
            plt.xlabel("Predicted")
            plt.ylabel("Actual")
            plt.tight_layout()
            plt.savefig(RESULTS_DIR / "confusion_blind_test.png", dpi=150)
            plt.close()
            print(f"\n  -> confusion_blind_test.png")

    # 결과 저장
    output = {
        "test_set": "blind_test",
        "n_samples": len(data),
        "results": results,
    }
    output_path = RESULTS_DIR / "blind_evaluation.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  -> {output_path}")

    # adversarial 대비 비교
    print(f"\n{'='*70}")
    print("  Adversarial(212) vs Blind(70) 비교")
    print(f"{'='*70}")
    adv_path = RESULTS_DIR / "final_comparison.json"
    if adv_path.exists():
        with open(adv_path, "r", encoding="utf-8") as f:
            adv_data = json.load(f)
        bert_pp = next((r for r in adv_data["results"] if "Preprocess" in r["method"]), None)
        if bert_pp:
            blind_pp = results[1]  # 전처리 적용 결과
            print(f"  {'셋':<20} {'F1':>8} {'Acc':>8} {'오분류':>8}")
            print(f"  {'-'*46}")
            print(f"  {'Adversarial(212)':<20} {bert_pp['f1_macro']:>8.4f} {bert_pp['accuracy']:>8.4f} {bert_pp['errors']:>7}건")
            print(f"  {'Blind(70)':<20} {blind_pp['f1_macro']:>8.4f} {blind_pp['accuracy']:>8.4f} {blind_pp['errors']:>7}건")

    print(f"\n{'='*70}")
    print("  Blind 평가 완료!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
