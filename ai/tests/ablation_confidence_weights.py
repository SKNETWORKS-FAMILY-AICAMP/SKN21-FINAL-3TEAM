"""
Confidence 가중치 Ablation Study

목적: LLM 60% + RAG 25% + Coverage 15% 조합이
      다른 가중치 조합 대비 최적임을 실험적으로 검증

평가 기준:
  1. 방향 정확도 — 기대 방향(상향/하향/유지)과 실제 방향 일치 여부
  2. 과신 방지력 — LLM이 과신할 때 얼마나 효과적으로 하향 보정하는가
  3. 환각 차단력 — 규정 없을 때 confidence를 낮게 제한하는가
  4. 보수적 LLM 보완력 — RAG가 좋은데 LLM이 소극적일 때 상향 보정하는가
  5. 이상적 조건 안정성 — 모든 조건이 좋을 때 적절한 고점수를 유지하는가
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ai.agents.judgment_agent import _group_regulations


# ── 시나리오 정의 (기존 5개 + 추가 5개 = 10개) ──

SCENARIOS = [
    # 기존 5개
    {
        "name": "① 이상적 (높은RAG+다중규정)",
        "llm_conf": 0.9,
        "context": [
            {"content": "c", "source": "취업규칙 15조", "score": 0.95},
            {"content": "c", "source": "취업규칙 16조", "score": 0.90},
            {"content": "c", "source": "재택근무 규정 3조", "score": 0.85},
        ],
        "cross_refs": [],
        "expected_direction": "유지",
        "criteria": {"min": 0.85, "max": 1.0},
    },
    {
        "name": "② LLM 과신 (RAG 낮음)",
        "llm_conf": 0.95,
        "context": [
            {"content": "c", "source": "취업규칙 1조", "score": 0.25},
        ],
        "cross_refs": [],
        "expected_direction": "하향",
        "criteria": {"min": 0.5, "max": 0.8},
    },
    {
        "name": "③ 근거 없음 (환각 위험)",
        "llm_conf": 0.8,
        "context": [],
        "cross_refs": [],
        "expected_direction": "대폭하향",
        "criteria": {"min": 0.0, "max": 0.35},
    },
    {
        "name": "④ 규정 충돌",
        "llm_conf": 0.85,
        "context": [
            {"content": "c", "source": "취업규칙 10조", "score": 0.80},
            {"content": "c", "source": "정보보안 규정 5조", "score": 0.75},
        ],
        "cross_refs": [{"relationship": "충돌"}, {"relationship": "충돌"}],
        "expected_direction": "하향",
        "criteria": {"min": 0.4, "max": 0.75},
    },
    {
        "name": "⑤ 보수적 LLM (RAG 높음)",
        "llm_conf": 0.5,
        "context": [
            {"content": "c", "source": "취업규칙 20조", "score": 0.92},
            {"content": "c", "source": "인사 규정 3조", "score": 0.88},
        ],
        "cross_refs": [],
        "expected_direction": "상향",
        "criteria": {"min": 0.6, "max": 0.85},
    },
    # 추가 5개 (엣지 케이스)
    {
        "name": "⑥ RAG 중간 + 단일 규정",
        "llm_conf": 0.7,
        "context": [
            {"content": "c", "source": "취업규칙 5조", "score": 0.55},
        ],
        "cross_refs": [],
        "expected_direction": "소폭하향",
        "criteria": {"min": 0.45, "max": 0.72},
    },
    {
        "name": "⑦ LLM 극도 과신 (0.99)",
        "llm_conf": 0.99,
        "context": [
            {"content": "c", "source": "취업규칙 1조", "score": 0.15},
        ],
        "cross_refs": [],
        "expected_direction": "하향",
        "criteria": {"min": 0.4, "max": 0.75},
    },
    {
        "name": "⑧ LLM 극도 불확실 (0.3)",
        "llm_conf": 0.3,
        "context": [
            {"content": "c", "source": "취업규칙 8조", "score": 0.95},
            {"content": "c", "source": "복무 규정 2조", "score": 0.90},
            {"content": "c", "source": "인사 규정 1조", "score": 0.85},
        ],
        "cross_refs": [],
        "expected_direction": "상향",
        "criteria": {"min": 0.45, "max": 0.75},
    },
    {
        "name": "⑨ 모든 것이 중간",
        "llm_conf": 0.6,
        "context": [
            {"content": "c", "source": "취업규칙 3조", "score": 0.60},
            {"content": "c", "source": "보안 규정 7조", "score": 0.55},
        ],
        "cross_refs": [],
        "expected_direction": "유지",
        "criteria": {"min": 0.45, "max": 0.70},
    },
    {
        "name": "⑩ 3중 충돌 + 높은 LLM",
        "llm_conf": 0.9,
        "context": [
            {"content": "c", "source": "취업규칙 10조", "score": 0.80},
            {"content": "c", "source": "정보보안 규정 5조", "score": 0.75},
            {"content": "c", "source": "징계 규정 3조", "score": 0.70},
        ],
        "cross_refs": [
            {"relationship": "충돌"},
            {"relationship": "충돌"},
            {"relationship": "충돌"},
        ],
        "expected_direction": "하향",
        "criteria": {"min": 0.3, "max": 0.65},
    },
]


# ── 가중치 조합 ──

WEIGHT_CONFIGS = [
    {"name": "A) LLM 100%",       "llm": 1.0,  "rag": 0.0,  "cov": 0.0},
    {"name": "B) 80/15/5",        "llm": 0.80, "rag": 0.15, "cov": 0.05},
    {"name": "C) 70/20/10",       "llm": 0.70, "rag": 0.20, "cov": 0.10},
    {"name": "D) 60/25/15 (현재)", "llm": 0.60, "rag": 0.25, "cov": 0.15},
    {"name": "E) 50/30/20",       "llm": 0.50, "rag": 0.30, "cov": 0.20},
    {"name": "F) 40/40/20",       "llm": 0.40, "rag": 0.40, "cov": 0.20},
    {"name": "G) 33/33/34",       "llm": 0.33, "rag": 0.33, "cov": 0.34},
]


def calibrate_with_weights(scenario: dict, w_llm: float, w_rag: float, w_cov: float) -> float:
    """주어진 가중치로 confidence를 보정한다 (감점 로직 포함)."""
    llm_conf = scenario["llm_conf"]
    context = scenario["context"]
    cross_refs = scenario["cross_refs"]

    # 규정 없음 → 강제 캡 0.3 (가중치 무관)
    if not context:
        return round(min(llm_conf, 0.3), 3)

    # RAG 평균 score
    avg_score = sum(d.get("score", 0) for d in context) / len(context)
    rag_factor = min(avg_score / 0.8, 1.0)

    # 규정 커버리지
    groups = _group_regulations(context)
    coverage_factor = min(len(groups) / 2.0, 1.0)

    # 충돌 감점
    conflict_count = sum(1 for cr in cross_refs if cr.get("relationship") == "충돌")
    conflict_penalty = 0.1 * conflict_count

    calibrated = (
        llm_conf * w_llm
        + rag_factor * w_rag
        + coverage_factor * w_cov
        - conflict_penalty
    )
    return round(max(0.0, min(1.0, calibrated)), 3)


def check_direction(raw: float, calibrated: float, expected: str) -> bool:
    """보정 방향이 기대와 일치하는지 판단."""
    diff = calibrated - raw
    if "대폭하향" in expected:
        return diff < -0.3
    elif "소폭하향" in expected:
        return -0.3 < diff < 0
    elif "하향" in expected:
        return diff < -0.05
    elif "상향" in expected:
        return diff > 0.05
    elif "유지" in expected:
        return abs(diff) < 0.15
    return False


def check_range(calibrated: float, criteria: dict) -> bool:
    """보정 결과가 합리적 범위 내인지 판단."""
    return criteria["min"] <= calibrated <= criteria["max"]


def run_ablation():
    """전체 Ablation 실험 실행."""

    print("=" * 90)
    print("  Confidence 가중치 Ablation Study")
    print("  10개 시나리오 × 7개 가중치 조합 = 70개 실험")
    print("=" * 90)

    # 결과 저장
    results = {}  # {config_name: {direction_acc, range_acc, scores[]}}

    for wc in WEIGHT_CONFIGS:
        direction_correct = 0
        range_correct = 0
        scores = []

        for s in SCENARIOS:
            cal = calibrate_with_weights(s, wc["llm"], wc["rag"], wc["cov"])
            raw = s["llm_conf"]
            d_ok = check_direction(raw, cal, s["expected_direction"])
            r_ok = check_range(cal, s["criteria"])
            if d_ok:
                direction_correct += 1
            if r_ok:
                range_correct += 1
            scores.append({
                "scenario": s["name"],
                "raw": raw,
                "calibrated": cal,
                "diff": round(cal - raw, 3),
                "direction_ok": d_ok,
                "range_ok": r_ok,
            })

        results[wc["name"]] = {
            "direction_acc": direction_correct / len(SCENARIOS) * 100,
            "range_acc": range_correct / len(SCENARIOS) * 100,
            "combined": (direction_correct + range_correct) / (len(SCENARIOS) * 2) * 100,
            "scores": scores,
        }

    # ── 종합 순위 출력 ──
    print("\n" + "=" * 90)
    print("  종합 순위 (방향 정확도 + 범위 적합도)")
    print("=" * 90)

    header = f"{'순위':>4}  {'가중치 조합':<22}  {'방향 정확도':>10}  {'범위 적합도':>10}  {'종합 점수':>10}"
    print(header)
    print("-" * 75)

    ranked = sorted(results.items(), key=lambda x: x[1]["combined"], reverse=True)
    for rank, (name, data) in enumerate(ranked, 1):
        marker = " ★" if "현재" in name else ""
        print(
            f"{rank:>4}  {name:<22}  {data['direction_acc']:>8.1f}%  "
            f"{data['range_acc']:>8.1f}%  {data['combined']:>8.1f}%{marker}"
        )

    # ── 시나리오별 상세 비교 ──
    print("\n" + "=" * 90)
    print("  시나리오별 상세 비교")
    print("=" * 90)

    for s in SCENARIOS:
        print(f"\n  {s['name']}  (LLM raw: {s['llm_conf']}, 기대: {s['expected_direction']})")
        print(f"  적합 범위: [{s['criteria']['min']}, {s['criteria']['max']}]")
        print(f"  {'가중치 조합':<22}  {'보정값':>6}  {'변화':>7}  {'방향':>4}  {'범위':>4}")
        print(f"  {'-'*55}")

        for wc in WEIGHT_CONFIGS:
            r = results[wc["name"]]
            score_data = [sc for sc in r["scores"] if sc["scenario"] == s["name"]][0]
            d_mark = "O" if score_data["direction_ok"] else "X"
            r_mark = "O" if score_data["range_ok"] else "X"
            marker = " ★" if "현재" in wc["name"] else ""
            print(
                f"  {wc['name']:<22}  {score_data['calibrated']:>6.3f}  "
                f"{score_data['diff']:>+7.3f}  {d_mark:>4}  {r_mark:>4}{marker}"
            )

    # ── CSV 형태 결과 (PPT 표용) ──
    print("\n" + "=" * 90)
    print("  PPT용 요약 데이터")
    print("=" * 90)

    print(f"\n{'가중치':<22}", end="")
    for s in SCENARIOS:
        short = s["name"][:6]
        print(f"  {short:>8}", end="")
    print(f"  {'방향%':>6}  {'범위%':>6}  {'종합%':>6}")

    print("-" * 130)
    for wc in WEIGHT_CONFIGS:
        r = results[wc["name"]]
        marker = " ★" if "현재" in wc["name"] else ""
        print(f"{wc['name']:<22}", end="")
        for s in SCENARIOS:
            score_data = [sc for sc in r["scores"] if sc["scenario"] == s["name"]][0]
            print(f"  {score_data['calibrated']:>8.3f}", end="")
        print(f"  {r['direction_acc']:>5.1f}  {r['range_acc']:>5.1f}  {r['combined']:>5.1f}{marker}")

    return results, ranked


if __name__ == "__main__":
    results, ranked = run_ablation()
    print(f"\n\n{'='*90}")
    print(f"  결론: 최적 가중치 = {ranked[0][0]} (종합 {ranked[0][1]['combined']:.1f}%)")
    print(f"{'='*90}")
