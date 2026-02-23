"""
시나리오 테스트: 30문장으로 실제 라우팅 시뮬레이션

4가지 유형(boundary, short, informal, normal)별 정확도 + 오분류 상세 출력.

사용법:
    python ai/experiments_v2/run_scenario_test.py                             # Stage 5 (기본 모델)
    python ai/experiments_v2/run_scenario_test.py --stage6 --model-dir PATH   # Stage 6 (학습된 모델 경로 지정)

사전: pip install transformers torch scikit-learn
"""

import argparse
import json
import torch
import numpy as np
from pathlib import Path
from collections import Counter
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import accuracy_score, f1_score

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "intent_v2"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
FINAL_MODEL_DIR = BASE_DIR / "ai" / "models" / "intent_classifier"

SCENARIO_PATH = DATA_DIR / "scenario_test.json"

# ── Intent 정의 ──
INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_qa",
]
ID2LABEL = {i: label for i, label in enumerate(INTENT_LABELS)}

MAX_LENGTH = 64
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_model(model_dir=None):
    """모델 로드 (model_dir 지정 가능)"""
    model_path = Path(model_dir) if model_dir else FINAL_MODEL_DIR
    if not model_path.exists():
        raise FileNotFoundError(f"모델 없음: {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_path))
    model.to(device)
    model.eval()
    return model, tokenizer


def predict(model, tokenizer, text):
    """단일 문장 추론"""
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=MAX_LENGTH)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
    probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()[0]
    pred_id = int(np.argmax(probs))
    return ID2LABEL[pred_id], float(probs[pred_id]), probs


def main():
    parser = argparse.ArgumentParser(description="시나리오 테스트")
    parser.add_argument("--stage6", action="store_true", help="Stage 6 결과로 저장")
    parser.add_argument("--model-dir", type=str, default=None,
                        help="모델 디렉토리 경로 (미지정 시 ai/models/intent_classifier/)")
    args = parser.parse_args()

    stage_tag = "stage6" if args.stage6 else "stage5"
    model_dir = args.model_dir or str(FINAL_MODEL_DIR)

    print("=" * 60)
    print(f"  시나리오 테스트 ({stage_tag})")
    print("=" * 60)
    print(f"  Device: {device}")
    print(f"  Model: {model_dir}")

    # 데이터 로드
    if not SCENARIO_PATH.exists():
        raise FileNotFoundError(f"시나리오 파일 없음: {SCENARIO_PATH}")

    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        scenarios = json.load(f)

    print(f"  문장 수: {len(scenarios)}")
    cat_counts = Counter(s["category"] for s in scenarios)
    for cat, cnt in sorted(cat_counts.items()):
        print(f"    {cat}: {cnt}")

    # 모델 로드
    model, tokenizer = load_model(model_dir)

    # 추론
    results = []
    for item in scenarios:
        pred, conf, probs = predict(model, tokenizer, item["text"])
        results.append({
            "text": item["text"],
            "label": item["label"],
            "category": item["category"],
            "predicted": pred,
            "confidence": round(conf, 4),
            "correct": pred == item["label"],
        })

    # ── 전체 성능 ──
    labels = [r["label"] for r in results]
    preds = [r["predicted"] for r in results]
    total_acc = accuracy_score(labels, preds)
    total_f1 = f1_score(labels, preds, average="macro", zero_division=0)

    print(f"\n{'─' * 60}")
    print(f"  전체: Accuracy={total_acc:.4f}  F1(macro)={total_f1:.4f}")
    print(f"  정답: {sum(r['correct'] for r in results)}/{len(results)}")

    # ── 유형별 성능 ──
    categories = sorted(set(r["category"] for r in results))
    cat_results = {}

    print(f"\n  {'유형':<12} {'정답':>5} {'전체':>5} {'정확도':>8}")
    print(f"  {'─' * 32}")
    for cat in categories:
        cat_items = [r for r in results if r["category"] == cat]
        correct = sum(r["correct"] for r in cat_items)
        total = len(cat_items)
        acc = correct / total if total > 0 else 0
        cat_results[cat] = {"correct": correct, "total": total, "accuracy": round(acc, 4)}
        print(f"  {cat:<12} {correct:>5} {total:>5} {acc:>8.1%}")

    # ── 오분류 상세 ──
    errors = [r for r in results if not r["correct"]]
    if errors:
        print(f"\n{'─' * 60}")
        print(f"  오분류: {len(errors)}건")
        print(f"{'─' * 60}")
        for e in errors:
            print(f"  [{e['category']}] \"{e['text']}\"")
            print(f"    실제: {e['label']} → 예측: {e['predicted']} (conf={e['confidence']:.4f})")
    else:
        print(f"\n  오분류 0건!")

    # ── 결과 저장 ──
    output = {
        "stage": stage_tag,
        "total": {"accuracy": round(total_acc, 4), "f1_macro": round(total_f1, 4)},
        "per_category": cat_results,
        "errors": errors,
        "details": results,
    }

    output_path = RESULTS_DIR / f"scenario_test_{stage_tag}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  -> {output_path.name}")

    # ── 요약 ──
    print(f"\n{'=' * 60}")
    print(f"  시나리오 테스트 완료 ({stage_tag})")
    print(f"{'=' * 60}")
    print(f"  전체 정확도: {total_acc:.1%} ({sum(r['correct'] for r in results)}/{len(results)})")
    for cat in categories:
        cr = cat_results[cat]
        print(f"  {cat}: {cr['accuracy']:.1%} ({cr['correct']}/{cr['total']})")
    print(f"  오분류: {len(errors)}건")


if __name__ == "__main__":
    main()
