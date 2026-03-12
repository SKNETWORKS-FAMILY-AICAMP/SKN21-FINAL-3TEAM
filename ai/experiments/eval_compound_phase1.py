"""
Phase 1 (규칙 기반) 복합 질문 감지 평가 — 멀티라벨 전용 지표

평가 지표:
  [이진 감지]
    - Precision / Recall / F1  (복합 감지를 양성 클래스로)
    - Over-triggering Rate  : 단순 질문 → 복합 오감지 (FP / 실제 단순)
    - Under-triggering Rate : 복합 질문 → 단순 오감지 (FN / 실제 복합)

  [멀티라벨 Intent 집합]
    - Subset Accuracy (Exact Match) : 예측 intent 집합 == 실제 intent 집합
    - Hamming Loss                  : 레이블 단위 오류율
    - Macro F1                      : intent별 F1 단순 평균
    - Micro F1                      : 전체 TP/FP/FN 기반 F1
    - Jaccard Score                 : |예측 ∩ 실제| / |예측 ∪ 실제| (샘플별 평균)

사용법:
    cd /path/to/SKN21-FINAL-3TEAM
    python -m ai.experiments.eval_compound_phase1
"""

import json
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from ai.agents.intent_classifier import (
    INTENT_LABELS,
    detect_compound_query,
    get_classifier,
)

# ── 상수 ──────────────────────────────────────────────────────────────────────

TEST_DATA_PATH = ROOT / "data" / "training" / "intent" / "complex_test.json"

# deprecated 라벨 → 현행 라벨 매핑
_DEPRECATED = {
    "meeting_generate": "doc_generate",
    "meeting_summary": "doc_summary",
}

ALL_INTENTS = INTENT_LABELS  # 8개 intent 순서 고정


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def normalize(intents) -> set[str]:
    """deprecated 라벨 변환 + INTENT_LABELS 에 없는 라벨 제거"""
    result = set()
    for i in intents:
        mapped = _DEPRECATED.get(i, i)
        if mapped in ALL_INTENTS:
            result.add(mapped)
    return result


def to_binary_vector(intent_set: set[str]) -> list[int]:
    """intent 집합 → 8차원 이진 벡터"""
    return [1 if label in intent_set else 0 for label in ALL_INTENTS]


# ── 예측 ──────────────────────────────────────────────────────────────────────

def predict_intent_set(text: str) -> tuple[bool, set[str]]:
    """
    텍스트에 대한 intent 집합 예측 (detect_compound_query 전용).

    Returns:
        (is_complex_pred, intent_set or None)
        - 복합: (True, {hint1, hint2, ...})
        - 단순: (False, None)  ← 단일 분류기는 Phase 1 평가 범위 밖
    """
    sub_queries = detect_compound_query(text)

    if sub_queries:
        hints = normalize(sq["hint"] for sq in sub_queries)
        return True, hints if hints else {"general"}

    return False, None


# ── 지표 계산 ────────────────────────────────────────────────────────────────

def compute_detection_metrics(
    y_true_complex: list[bool],
    y_pred_complex: list[bool],
) -> dict:
    """이진 복합 감지 지표"""
    tp = sum(t and p for t, p in zip(y_true_complex, y_pred_complex))
    fp = sum(not t and p for t, p in zip(y_true_complex, y_pred_complex))
    fn = sum(t and not p for t, p in zip(y_true_complex, y_pred_complex))
    tn = sum(not t and not p for t, p in zip(y_true_complex, y_pred_complex))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0 else 0.0
    )

    n_true_complex = sum(y_true_complex)
    n_true_simple  = len(y_true_complex) - n_true_complex

    over_trigger  = fp / n_true_simple  if n_true_simple  > 0 else 0.0  # FP / 실제 단순
    under_trigger = fn / n_true_complex if n_true_complex > 0 else 0.0  # FN / 실제 복합

    return {
        "TP": tp, "FP": fp, "FN": fn, "TN": tn,
        "Precision": precision,
        "Recall":    recall,
        "F1":        f1,
        "Over-triggering Rate":  over_trigger,
        "Under-triggering Rate": under_trigger,
    }


def compute_multilabel_metrics(
    y_true_sets: list[set[str]],
    y_pred_sets: list[set[str]],
) -> dict:
    """멀티라벨 intent 집합 지표"""
    n = len(y_true_sets)

    # ── Subset Accuracy ──
    exact_match = sum(t == p for t, p in zip(y_true_sets, y_pred_sets))
    subset_accuracy = exact_match / n

    # ── Hamming Loss ──
    total_label_errors = 0
    for t_set, p_set in zip(y_true_sets, y_pred_sets):
        t_vec = to_binary_vector(t_set)
        p_vec = to_binary_vector(p_set)
        total_label_errors += sum(tv != pv for tv, pv in zip(t_vec, p_vec))
    hamming_loss = total_label_errors / (n * len(ALL_INTENTS))

    # ── Jaccard Score (샘플별 평균) ──
    jaccard_scores = []
    for t_set, p_set in zip(y_true_sets, y_pred_sets):
        inter = len(t_set & p_set)
        union = len(t_set | p_set)
        jaccard_scores.append(inter / union if union > 0 else 1.0)
    jaccard = sum(jaccard_scores) / n

    # ── Macro F1 / Micro F1 (레이블 단위) ──
    per_label_tp = {label: 0 for label in ALL_INTENTS}
    per_label_fp = {label: 0 for label in ALL_INTENTS}
    per_label_fn = {label: 0 for label in ALL_INTENTS}

    for t_set, p_set in zip(y_true_sets, y_pred_sets):
        for label in ALL_INTENTS:
            t_bit = label in t_set
            p_bit = label in p_set
            if t_bit and p_bit:
                per_label_tp[label] += 1
            elif not t_bit and p_bit:
                per_label_fp[label] += 1
            elif t_bit and not p_bit:
                per_label_fn[label] += 1

    per_label_f1 = {}
    for label in ALL_INTENTS:
        tp = per_label_tp[label]
        fp = per_label_fp[label]
        fn = per_label_fn[label]
        p  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        per_label_f1[label] = 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    macro_f1 = sum(per_label_f1.values()) / len(ALL_INTENTS)

    micro_tp = sum(per_label_tp.values())
    micro_fp = sum(per_label_fp.values())
    micro_fn = sum(per_label_fn.values())
    micro_p  = micro_tp / (micro_tp + micro_fp) if (micro_tp + micro_fp) > 0 else 0.0
    micro_r  = micro_tp / (micro_tp + micro_fn) if (micro_tp + micro_fn) > 0 else 0.0
    micro_f1 = (
        2 * micro_p * micro_r / (micro_p + micro_r)
        if (micro_p + micro_r) > 0 else 0.0
    )

    return {
        "Subset Accuracy (Exact Match)": subset_accuracy,
        "Hamming Loss":                  hamming_loss,
        "Jaccard Score":                 jaccard,
        "Macro F1":                      macro_f1,
        "Micro F1":                      micro_f1,
        "per_label_f1":                  per_label_f1,
    }


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    # 테스트 데이터 로드
    with open(TEST_DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    samples = raw["data"]
    print(f"\n테스트 데이터: {len(samples)}개 로드 완료")
    print(f"카테고리: {raw['categories']}\n")

    # ── 예측 수행 ──
    y_true_complex = []
    y_pred_complex = []
    # 멀티라벨 평가용: is_complex=True 케이스만
    y_true_sets_complex = []
    y_pred_sets_complex = []
    detail_rows = []

    for item in samples:
        text     = item["text"]
        expected = item["expected"]

        true_is_complex = expected["is_complex"]
        if true_is_complex:
            true_intents = normalize(expected["intents"])
        else:
            true_intents = None

        # 예측 (단일 분류기 호출 없음)
        pred_is_complex, pred_intents = predict_intent_set(text)

        y_true_complex.append(true_is_complex)
        y_pred_complex.append(pred_is_complex)

        # 복합 케이스만 intent 집합 평가 수집
        if true_is_complex:
            y_true_sets_complex.append(true_intents)
            y_pred_sets_complex.append(pred_intents if pred_intents else set())

        # 정답 여부: 이진 감지 + (복합이면 intent 집합도)
        if true_is_complex:
            correct = (pred_is_complex == true_is_complex) and (pred_intents == true_intents)
        else:
            correct = (pred_is_complex == true_is_complex)

        detail_rows.append({
            "id":       item["id"],
            "category": item["category"],
            "text":     text,
            "true_complex": true_is_complex,
            "pred_complex": pred_is_complex,
            "true_intents": sorted(true_intents) if true_intents else [],
            "pred_intents": sorted(pred_intents) if pred_intents else [],
            "correct": correct,
        })

    # ── 결과 출력 ──
    sep = "─" * 60

    print(sep)
    print("[ 이진 복합 감지 지표 ]")
    print(sep)
    det = compute_detection_metrics(y_true_complex, y_pred_complex)
    print(f"  Precision            : {det['Precision']:.4f} ({det['Precision']*100:.1f}%)")
    print(f"  Recall               : {det['Recall']:.4f} ({det['Recall']*100:.1f}%)")
    print(f"  F1                   : {det['F1']:.4f} ({det['F1']*100:.1f}%)")
    print(f"  Over-triggering Rate : {det['Over-triggering Rate']:.4f}  "
          f"({det['FP']} / {sum(not t for t in y_true_complex)} 단순 질문 오감지)")
    print(f"  Under-triggering Rate: {det['Under-triggering Rate']:.4f}  "
          f"({det['FN']} / {sum(y_true_complex)} 복합 질문 미감지)")
    print(f"  (TP={det['TP']}  FP={det['FP']}  FN={det['FN']}  TN={det['TN']})")

    print()
    print(sep)
    print(f"[ 멀티라벨 Intent 집합 지표 — 복합 케이스 {len(y_true_sets_complex)}개 기준 ]")
    print(sep)
    ml = compute_multilabel_metrics(y_true_sets_complex, y_pred_sets_complex)
    print(f"  Subset Accuracy (Exact Match) : {ml['Subset Accuracy (Exact Match)']:.4f} "
          f"({ml['Subset Accuracy (Exact Match)']*100:.1f}%)")
    print(f"  Hamming Loss                  : {ml['Hamming Loss']:.4f}")
    print(f"  Jaccard Score                 : {ml['Jaccard Score']:.4f} "
          f"({ml['Jaccard Score']*100:.1f}%)")
    print(f"  Macro F1                      : {ml['Macro F1']:.4f} "
          f"({ml['Macro F1']*100:.1f}%)")
    print(f"  Micro F1                      : {ml['Micro F1']:.4f} "
          f"({ml['Micro F1']*100:.1f}%)")

    print()
    print("  Intent별 F1:")
    for label, f1 in ml["per_label_f1"].items():
        bar = "█" * int(f1 * 20)
        print(f"    {label:<16} {f1:.4f}  {bar}")

    print()
    print(sep)
    print("[ 카테고리별 Exact Match ]")
    print(sep)
    from collections import defaultdict
    cat_correct = defaultdict(lambda: [0, 0])
    for row in detail_rows:
        cat = row["category"]
        cat_correct[cat][1] += 1
        if row["correct"]:
            cat_correct[cat][0] += 1
    for cat, (ok, total) in sorted(cat_correct.items()):
        print(f"  {cat:<26} {ok}/{total}  ({ok/total*100:.0f}%)")

    print()
    print(sep)
    print("[ 오답 목록 ]")
    print(sep)
    errors = [r for r in detail_rows if not r["correct"]]
    if not errors:
        print("  오답 없음 — 전체 정답!")
    for r in errors:
        print(f"  [{r['id']:2d}] [{r['category']}]")
        print(f"       text  : {r['text']}")
        print(f"       true  : complex={r['true_complex']}  intents={r['true_intents']}")
        print(f"       pred  : complex={r['pred_complex']}  intents={r['pred_intents']}")

    # ── 요약 테이블 (Phase 2 비교용) ──
    print()
    print(sep)
    print("[ Phase 1 최종 요약 — Phase 2 비교 기준점 ]")
    print(sep)
    print(f"  {'지표':<34} {'Phase 1 (규칙 기반)'}")
    print(f"  {'─'*34} {'─'*20}")
    print(f"  {'복합감지 F1':<34} {det['F1']*100:.1f}%")
    print(f"  {'Over-triggering Rate':<34} {det['Over-triggering Rate']*100:.1f}%")
    print(f"  {'Under-triggering Rate':<34} {det['Under-triggering Rate']*100:.1f}%")
    print(f"  {'Subset Accuracy (Exact Match)':<34} {ml['Subset Accuracy (Exact Match)']*100:.1f}%")
    print(f"  {'Hamming Loss':<34} {ml['Hamming Loss']:.4f}")
    print(f"  {'Jaccard Score':<34} {ml['Jaccard Score']*100:.1f}%")
    print(f"  {'Macro F1':<34} {ml['Macro F1']*100:.1f}%")
    print(f"  {'Micro F1':<34} {ml['Micro F1']*100:.1f}%")
    print()
    print("  → Phase 2 (멀티라벨 BERT) 에서 위 수치들을 기준점으로 개선 목표 설정")
    print()


if __name__ == "__main__":
    main()
