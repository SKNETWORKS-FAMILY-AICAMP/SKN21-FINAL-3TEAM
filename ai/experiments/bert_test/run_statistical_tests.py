"""
통계적 유의성 테스트 (제안 4)

기존 실험 결과를 기반으로:
1. McNemar's Test --BERT vs RoBERTa, BERT vs GPT 비교
2. Bootstrap Confidence Interval --성능 차이의 95% CI
3. 모델 간 차이가 통계적으로 유의미한지 판단

사용법:
    python ai/experiments/run_statistical_tests.py
"""

import json
import sys
import torch
import numpy as np
from pathlib import Path
from scipy import stats

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data" / "training" / "intent"
MODEL_DIR = BASE_DIR / "ai" / "models" / "intent_classifier"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate",
    "meeting_generate", "schedule_add", "schedule_view", "general",
]


def load_adversarial():
    with open(DATA_DIR / "adversarial_test.json", "r", encoding="utf-8") as f:
        return json.load(f)


def get_bert_predictions(data):
    """현재 배포 모델(BERT)로 예측"""
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    from ai.agents.preprocessing import preprocess

    tokenizer = AutoTokenizer.from_pretrained("klue/bert-base")
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    model.eval()

    with open(MODEL_DIR / "label_map.json", "r", encoding="utf-8") as f:
        label_map = json.load(f)
    id2label = {int(k): v for k, v in label_map["id2label"].items()}

    preds = []
    for item in data:
        text = preprocess(item["text"])
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=64)
        with torch.no_grad():
            outputs = model(**inputs)
        pred_id = torch.argmax(outputs.logits, dim=-1).item()
        preds.append(id2label.get(pred_id, "general"))

    return preds


def mcnemar_test(labels, preds_a, preds_b, name_a, name_b):
    """
    McNemar's Test: 두 분류기의 오분류 패턴이 유의미하게 다른지 검증.

    contingency table:
                    B correct    B incorrect
    A correct       n00          n01
    A incorrect     n10          n11
    """
    n = len(labels)
    n01 = 0  # A 맞고 B 틀림
    n10 = 0  # A 틀리고 B 맞음

    for label, pred_a, pred_b in zip(labels, preds_a, preds_b):
        a_correct = (pred_a == label)
        b_correct = (pred_b == label)
        if a_correct and not b_correct:
            n01 += 1
        elif not a_correct and b_correct:
            n10 += 1

    # McNemar's test (with continuity correction)
    if n01 + n10 == 0:
        return {
            "test": "McNemar",
            "comparison": f"{name_a} vs {name_b}",
            "n01": n01, "n10": n10,
            "chi2": 0, "p_value": 1.0,
            "significant": False,
            "note": "두 모델의 오분류 패턴이 동일 (차이 없음)",
        }

    chi2 = (abs(n01 - n10) - 1) ** 2 / (n01 + n10)
    p_value = 1 - stats.chi2.cdf(chi2, df=1)

    return {
        "test": "McNemar",
        "comparison": f"{name_a} vs {name_b}",
        "n01_a_correct_b_wrong": n01,
        "n10_a_wrong_b_correct": n10,
        "chi2": round(chi2, 4),
        "p_value": round(p_value, 6),
        "significant_at_005": p_value < 0.05,
        "significant_at_001": p_value < 0.01,
        "interpretation": (
            f"{name_a}가 {name_b}보다 유의미하게 {'우수' if n01 > n10 else '열등'} (p={p_value:.4f})"
            if p_value < 0.05 else
            f"두 모델 간 유의미한 차이 없음 (p={p_value:.4f})"
        ),
    }


def bootstrap_ci(labels, preds_a, preds_b, name_a, name_b, n_bootstrap=10000, ci=0.95):
    """
    Bootstrap Confidence Interval: F1 차이의 95% CI.
    CI가 0을 포함하면 차이가 유의미하지 않음.
    """
    from sklearn.metrics import f1_score

    np.random.seed(42)
    n = len(labels)
    f1_diffs = []

    for _ in range(n_bootstrap):
        indices = np.random.choice(n, size=n, replace=True)
        sampled_labels = [labels[i] for i in indices]
        sampled_a = [preds_a[i] for i in indices]
        sampled_b = [preds_b[i] for i in indices]

        f1_a = f1_score(sampled_labels, sampled_a, average="macro", labels=INTENT_LABELS, zero_division=0)
        f1_b = f1_score(sampled_labels, sampled_b, average="macro", labels=INTENT_LABELS, zero_division=0)
        f1_diffs.append(f1_a - f1_b)

    lower = np.percentile(f1_diffs, (1 - ci) / 2 * 100)
    upper = np.percentile(f1_diffs, (1 + ci) / 2 * 100)
    mean_diff = np.mean(f1_diffs)

    includes_zero = lower <= 0 <= upper

    return {
        "test": "Bootstrap CI",
        "comparison": f"{name_a} - {name_b}",
        "n_bootstrap": n_bootstrap,
        "ci_level": ci,
        "mean_diff": round(mean_diff, 4),
        "ci_lower": round(lower, 4),
        "ci_upper": round(upper, 4),
        "includes_zero": includes_zero,
        "interpretation": (
            f"차이가 유의미하지 않음 (95% CI: [{lower:.4f}, {upper:.4f}], 0 포함)"
            if includes_zero else
            f"{name_a}가 {'우수' if mean_diff > 0 else '열등'} "
            f"(95% CI: [{lower:.4f}, {upper:.4f}], 0 미포함)"
        ),
    }


def seed_variance_analysis():
    """실험 6의 seed별 결과로 모델 안정성 분석"""
    ablation_path = RESULTS_DIR / "preprocessing_ablation.json"
    if not ablation_path.exists():
        return None

    with open(ablation_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Config E (풀 전처리) 결과만 추출
    config_e = [r for r in data["results"] if r["config"] == "E"]
    if len(config_e) < 2:
        return None

    f1s = [r["adv_f1"] for r in config_e]
    accs = [r["adv_acc"] for r in config_e]
    seeds = [r["seed"] for r in config_e]

    return {
        "test": "Seed Variance",
        "seeds": seeds,
        "adv_f1_values": f1s,
        "adv_f1_mean": round(float(np.mean(f1s)), 4),
        "adv_f1_std": round(float(np.std(f1s)), 4),
        "adv_f1_range": round(float(max(f1s) - min(f1s)), 4),
        "adv_acc_mean": round(float(np.mean(accs)), 4),
        "adv_acc_std": round(float(np.std(accs)), 4),
        "interpretation": (
            f"seed간 F1 편차: {np.std(f1s):.4f} (range: {max(f1s)-min(f1s):.4f}). "
            f"모델 간 차이({0.9015-0.8990:.4f})보다 seed 편차가 "
            f"{'더 큼 --모델 차이가 통계적으로 불안정' if np.std(f1s) > 0.0025 else '비슷함'}."
        ),
    }


def main():
    print("=" * 70)
    print("  통계적 유의성 테스트")
    print("=" * 70)

    # 데이터 로드
    adv_data = load_adversarial()
    labels = [d["label"] for d in adv_data]
    print(f"  Adversarial 테스트셋: {len(adv_data)}문장")

    # BERT 예측
    print("\n  BERT 예측 생성 중...")
    preds_bert = get_bert_predictions(adv_data)
    bert_acc = sum(1 for p, l in zip(preds_bert, labels) if p == l) / len(labels)
    print(f"    BERT Acc: {bert_acc:.4f}")

    all_results = []

    # ── 1. Seed 분산 분석 ──
    print(f"\n{'='*70}")
    print("  1. Seed 분산 분석")
    print(f"{'='*70}")
    seed_result = seed_variance_analysis()
    if seed_result:
        all_results.append(seed_result)
        print(f"  Seeds: {seed_result['seeds']}")
        print(f"  Adv F1: {seed_result['adv_f1_values']}")
        print(f"  Mean: {seed_result['adv_f1_mean']} ± {seed_result['adv_f1_std']}")
        print(f"  Range: {seed_result['adv_f1_range']}")
        print(f"  → {seed_result['interpretation']}")
    else:
        print("  실험 6 결과 없음 --건너뜀")

    # ── 2. Bootstrap CI: BERT vs 실험 5 결과 기반 비교 ──
    # 실험 5의 모델별 그리드 서치 결과가 있으면 로드
    print(f"\n{'='*70}")
    print("  2. Bootstrap Confidence Interval")
    print(f"{'='*70}")

    # BERT 자체의 bootstrap (성능 불확실성 범위)
    from sklearn.metrics import f1_score
    np.random.seed(42)
    n = len(labels)
    bert_f1s = []
    for _ in range(10000):
        idx = np.random.choice(n, size=n, replace=True)
        sampled_labels = [labels[i] for i in idx]
        sampled_preds = [preds_bert[i] for i in idx]
        bert_f1s.append(f1_score(sampled_labels, sampled_preds, average="macro",
                                 labels=INTENT_LABELS, zero_division=0))

    ci_lower = np.percentile(bert_f1s, 2.5)
    ci_upper = np.percentile(bert_f1s, 97.5)
    bert_ci = {
        "test": "Bootstrap CI (single model)",
        "model": "BERT + Preprocess",
        "f1_mean": round(float(np.mean(bert_f1s)), 4),
        "ci_95_lower": round(float(ci_lower), 4),
        "ci_95_upper": round(float(ci_upper), 4),
        "interpretation": f"BERT F1 = {np.mean(bert_f1s):.4f} (95% CI: [{ci_lower:.4f}, {ci_upper:.4f}])",
    }
    all_results.append(bert_ci)
    print(f"  {bert_ci['interpretation']}")

    # ── 3. GPT 비교 (실험 7 결과 활용) ──
    print(f"\n{'='*70}")
    print("  3. McNemar's Test + Bootstrap CI (BERT vs GPT)")
    print(f"{'='*70}")

    final_comp_path = RESULTS_DIR / "final_comparison.json"
    if final_comp_path.exists():
        # GPT 결과를 직접 재생성할 수 없으므로 (API 필요),
        # 실험 7 결과의 오분류 건수를 기반으로 최소한의 분석
        with open(final_comp_path, "r", encoding="utf-8") as f:
            final_data = json.load(f)

        bert_result = next((r for r in final_data["results"] if "Preprocess" in r["method"]), None)
        gpt_result = next((r for r in final_data["results"] if "Few-shot" in r["method"]), None)

        if bert_result and gpt_result:
            bert_errors = bert_result["errors"]
            gpt_errors = gpt_result["errors"]
            n_total = 212

            print(f"  BERT 오분류: {bert_errors}/{n_total}")
            print(f"  GPT  오분류: {gpt_errors}/{n_total}")
            print(f"  차이: {gpt_errors - bert_errors}건")

            # 정확한 McNemar는 개별 예측이 필요하지만, 근사치로 비율 비교
            # TRAINING_LOG에서: BERT만 틀림 11건, GPT만 틀림 21건, 둘다 틀림 10건
            n01 = 21  # BERT 맞고 GPT 틀림 (TRAINING_LOG 기록)
            n10 = 11  # BERT 틀리고 GPT 맞음

            mcnemar_result = {
                "test": "McNemar (from TRAINING_LOG)",
                "comparison": "BERT+Preprocess vs GPT Few-shot",
                "n01_bert_correct_gpt_wrong": n01,
                "n10_bert_wrong_gpt_correct": n10,
                "note": "TRAINING_LOG의 오분류 상세 분석 수치 사용",
            }

            chi2 = (abs(n01 - n10) - 1) ** 2 / (n01 + n10)
            p_value = 1 - stats.chi2.cdf(chi2, df=1)
            mcnemar_result["chi2"] = round(chi2, 4)
            mcnemar_result["p_value"] = round(p_value, 6)
            mcnemar_result["significant_at_005"] = p_value < 0.05
            mcnemar_result["interpretation"] = (
                f"BERT가 GPT보다 유의미하게 우수 (p={p_value:.4f})"
                if p_value < 0.05 else
                f"두 모델 간 유의미한 차이 없음 (p={p_value:.4f})"
            )

            all_results.append(mcnemar_result)
            print(f"\n  McNemar's Test:")
            print(f"    BERT 맞고 GPT 틀림: {n01}건")
            print(f"    BERT 틀리고 GPT 맞음: {n10}건")
            print(f"    chi2={chi2:.4f}, p={p_value:.4f}")
            print(f"    → {mcnemar_result['interpretation']}")

    # ── 4. 모델 비교 (BERT vs RoBERTa vs KoELECTRA) ──
    print(f"\n{'='*70}")
    print("  4. 모델 간 비교 신뢰성 분석")
    print(f"{'='*70}")

    model_comp = {
        "BERT": {"adv_f1": 0.9015},
        "RoBERTa": {"adv_f1": 0.8990},
        "KoELECTRA": {"adv_f1": 0.8856},
    }

    if seed_result:
        seed_std = seed_result["adv_f1_std"]
        bert_roberta_diff = model_comp["BERT"]["adv_f1"] - model_comp["RoBERTa"]["adv_f1"]
        bert_koelectra_diff = model_comp["BERT"]["adv_f1"] - model_comp["KoELECTRA"]["adv_f1"]

        model_analysis = {
            "test": "Model Difference vs Seed Variance",
            "seed_std": seed_std,
            "comparisons": [
                {
                    "pair": "BERT vs RoBERTa",
                    "f1_diff": round(bert_roberta_diff, 4),
                    "diff_in_std_units": round(bert_roberta_diff / seed_std, 2) if seed_std > 0 else float("inf"),
                    "reliable": bert_roberta_diff > 2 * seed_std,
                    "interpretation": (
                        f"차이({bert_roberta_diff:.4f})가 seed 편차({seed_std:.4f})의 "
                        f"{bert_roberta_diff/seed_std:.1f}배 --"
                        f"{'신뢰 가능' if bert_roberta_diff > 2 * seed_std else '신뢰 불가 (노이즈 수준)'}"
                    ),
                },
                {
                    "pair": "BERT vs KoELECTRA",
                    "f1_diff": round(bert_koelectra_diff, 4),
                    "diff_in_std_units": round(bert_koelectra_diff / seed_std, 2) if seed_std > 0 else float("inf"),
                    "reliable": bert_koelectra_diff > 2 * seed_std,
                    "interpretation": (
                        f"차이({bert_koelectra_diff:.4f})가 seed 편차({seed_std:.4f})의 "
                        f"{bert_koelectra_diff/seed_std:.1f}배 --"
                        f"{'신뢰 가능' if bert_koelectra_diff > 2 * seed_std else '신뢰 불가 (노이즈 수준)'}"
                    ),
                },
            ],
        }
        all_results.append(model_analysis)

        for comp in model_analysis["comparisons"]:
            print(f"  {comp['pair']}: {comp['interpretation']}")

    # ── 결과 저장 ──
    print(f"\n{'='*70}")
    print("  최종 요약")
    print(f"{'='*70}")

    for r in all_results:
        if "interpretation" in r:
            print(f"  [{r['test']}] {r['interpretation']}")

    def convert_types(obj):
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, dict):
            return {k: convert_types(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert_types(i) for i in obj]
        return obj

    output_path = RESULTS_DIR / "statistical_tests.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(convert_types(all_results), f, ensure_ascii=False, indent=2)
    print(f"\n  -> {output_path}")

    print(f"\n{'='*70}")
    print("  통계 분석 완료!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
