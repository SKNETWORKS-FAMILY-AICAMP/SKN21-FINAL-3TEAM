"""
Planner 비교 결과 재평가 스크립트 (v3 지표)

지표 구조:
  [전제 조건] JSON Valid + Plan 존재 → pass/fail
  [핵심 지표]
    Intent Recall      30%  — 정답 intent를 빠뜨리지 않았는가
    Order Accuracy     25%  — intent 순서가 맞는가 (LCS 기반)
    Intent Precision   20%  — 불필요한 단계를 추가하지 않았는가
    Dep Correctness    15%  — 의존성이 expected와 일치하는가
    Efficiency         10%  — 단계 수가 적절한가

사용법:
  python ai/finetuning/scripts/evaluate_planner_report.py
  python ai/finetuning/scripts/evaluate_planner_report.py --report outputs/planner_comparison/comparison_report.json
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from dataclasses import dataclass, field

VALID_INTENTS = {"judgment", "doc_retrieve", "doc_generate",
                 "schedule_add", "schedule_view", "general"}

WEIGHTS = {
    "intent_recall": 0.30,
    "order_accuracy": 0.25,
    "intent_precision": 0.20,
    "dep_correctness": 0.15,
    "efficiency": 0.10,
}


# ── JSON 추출 ──────────────────────────────────────────────

def extract_json(text: str) -> dict | None:
    import re
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ── 평가 결과 구조 ─────────────────────────────────────────

@dataclass
class EvalResult:
    test_id: str
    category: str
    input_text: str
    model: str

    # 전제 조건 (pass/fail)
    json_valid: bool = False
    plan_extracted: bool = False

    # 핵심 지표 (0.0 ~ 1.0)
    intent_recall: float = 0.0       # 정답 intent 중 찾은 비율
    order_accuracy: float = 0.0      # LCS 기반 순서 정확도
    intent_precision: float = 0.0    # 모델 출력 중 맞는 비율
    dep_correctness: float = 0.0     # 의존성 expected 대비 정확도
    efficiency: float = 0.0          # 단계 수 적절성

    # 보조 지표
    hallucinated_intents: list = field(default_factory=list)
    has_cycle: bool = False
    dep_structural_valid: bool = True
    latency_ms: float = 0.0

    # 종합
    score: float = 0.0
    details: dict = field(default_factory=dict)

    @property
    def passed_prereq(self) -> bool:
        return self.json_valid and self.plan_extracted


# ── 핵심 평가 함수 ─────────────────────────────────────────

def _multiset_intersection(a: list, b: list) -> int:
    """두 리스트의 multiset 교집합 크기"""
    ca, cb = Counter(a), Counter(b)
    return sum((ca & cb).values())


def _lcs_length(a: list, b: list) -> int:
    """Longest Common Subsequence 길이 (순서 보존)"""
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return 0
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]


def _detect_cycle(plan: list[dict]) -> bool:
    """의존성 그래프 순환 검사 (DFS)"""
    adj = {}
    for step in plan:
        sid = step.get("step_id")
        deps = step.get("depends_on", [])
        adj[sid] = deps if isinstance(deps, list) else []

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {sid: WHITE for sid in adj}

    def dfs(node):
        if node not in color:
            return False
        color[node] = GRAY
        for neighbor in adj.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                return True
            if color[neighbor] == WHITE and dfs(neighbor):
                return True
        color[node] = BLACK
        return False

    return any(dfs(node) for node in adj if color.get(node) == WHITE)


def _check_structural_validity(plan: list[dict]) -> tuple[bool, list[str]]:
    """구조적 유효성 (순환, 유령참조, 자기참조) — 보조 지표"""
    if not plan:
        return False, ["빈 plan"]

    errors = []
    step_ids = {s.get("step_id") for s in plan}

    for step in plan:
        sid = step.get("step_id")
        deps = step.get("depends_on", [])
        if not isinstance(deps, list):
            errors.append(f"step {sid}: depends_on이 list가 아님")
            continue
        # 유령 참조
        invalid = [d for d in deps if d not in step_ids]
        if invalid:
            errors.append(f"step {sid}: 없는 step 참조 {invalid}")
        # 자기 참조
        if sid in deps:
            errors.append(f"step {sid}: 자기 참조")

    if _detect_cycle(plan):
        errors.append("순환 의존성")

    return len(errors) == 0, errors


def _calc_dep_correctness(actual_plan: list[dict],
                          expected_plan: list[dict]) -> float:
    """의존성 정확도 — expected의 depends_on과 actual을 비교"""
    if not expected_plan:
        return 1.0 if not actual_plan else 0.0

    # step 수가 다르면 매칭 가능한 범위만 비교
    min_len = min(len(actual_plan), len(expected_plan))
    if min_len == 0:
        return 0.0

    matches = 0
    for i in range(min_len):
        expected_deps = set(expected_plan[i].get("depends_on", []))
        actual_deps_raw = actual_plan[i].get("depends_on", [])
        actual_deps = set(actual_deps_raw) if isinstance(actual_deps_raw, list) else set()

        if expected_deps == actual_deps:
            matches += 1

    # 길이가 다른 만큼 감점
    max_len = max(len(actual_plan), len(expected_plan))
    return matches / max_len


def _calc_efficiency(actual_steps: int, expected_steps: int) -> float:
    """단계 수 효율성"""
    if expected_steps == 0:
        return 1.0 if actual_steps == 0 else 0.0
    if actual_steps == expected_steps:
        return 1.0
    diff = abs(actual_steps - expected_steps)
    return max(0.0, 1.0 - (diff * 0.3))


# ── 메인 평가 ──────────────────────────────────────────────

def evaluate(test_case: dict, model_name: str,
             raw_output: str, latency_ms: float) -> EvalResult:
    result = EvalResult(
        test_id=test_case["id"],
        category=test_case["category"],
        input_text=test_case["input"],
        model=model_name,
        latency_ms=latency_ms,
    )

    # ── 전제 조건 ──────────────────────────────────
    parsed = extract_json(raw_output)
    if parsed is None:
        result.details["error"] = "JSON 파싱 실패"
        return result
    result.json_valid = True

    if "plan" not in parsed or not isinstance(parsed["plan"], list):
        result.details["error"] = "plan 필드 없음"
        return result
    result.plan_extracted = True

    plan = parsed["plan"]
    expected = test_case["expected"]

    expected_intents = [s["intent"] for s in expected["plan"]]
    actual_intents = [s.get("intent", "") for s in plan]

    result.details["expected_intents"] = expected_intents
    result.details["actual_intents"] = actual_intents

    # ── 1. Intent Recall (30%) ─────────────────────
    result.hallucinated_intents = [i for i in actual_intents if i not in VALID_INTENTS]
    matched = _multiset_intersection(actual_intents, expected_intents)
    result.details["intent_matched"] = matched

    if len(expected_intents) > 0:
        result.intent_recall = matched / len(expected_intents)
    else:
        result.intent_recall = 1.0 if len(actual_intents) == 0 else 0.0

    # ── 2. Order Accuracy (25%) — LCS 기반 ─────────
    if len(expected_intents) == 0:
        result.order_accuracy = 1.0 if len(actual_intents) == 0 else 0.0
    else:
        lcs = _lcs_length(actual_intents, expected_intents)
        result.order_accuracy = lcs / len(expected_intents)
    result.details["lcs_length"] = _lcs_length(actual_intents, expected_intents)

    # ── 3. Intent Precision (20%) ──────────────────
    if len(actual_intents) > 0:
        result.intent_precision = matched / len(actual_intents)
    else:
        result.intent_precision = 1.0 if len(expected_intents) == 0 else 0.0

    # ── 4. Dep Correctness (15%) ───────────────────
    result.dep_correctness = _calc_dep_correctness(plan, expected["plan"])
    result.details["dep_correctness"] = result.dep_correctness

    # 구조적 유효성 (보조)
    structural_ok, structural_errors = _check_structural_validity(plan)
    result.dep_structural_valid = structural_ok
    result.has_cycle = _detect_cycle(plan)
    if structural_errors:
        result.details["structural_errors"] = structural_errors

    # ── 5. Efficiency (10%) ────────────────────────
    result.efficiency = _calc_efficiency(len(plan), expected["num_steps"])
    result.details["actual_steps"] = len(plan)
    result.details["expected_steps"] = expected["num_steps"]

    # ── 종합 점수 ──────────────────────────────────
    result.score = (
        result.intent_recall * WEIGHTS["intent_recall"] +
        result.order_accuracy * WEIGHTS["order_accuracy"] +
        result.intent_precision * WEIGHTS["intent_precision"] +
        result.dep_correctness * WEIGHTS["dep_correctness"] +
        result.efficiency * WEIGHTS["efficiency"]
    )

    return result


# ── 리포트 출력 ────────────────────────────────────────────

def print_report(all_results: dict[str, list[EvalResult]]):
    print("\n" + "=" * 80)
    print("PLANNER EVALUATION REPORT (v3 metrics)")
    print("=" * 80)
    print(f"\n  가중치: Recall={WEIGHTS['intent_recall']:.0%} "
          f"Order={WEIGHTS['order_accuracy']:.0%} "
          f"Precision={WEIGHTS['intent_precision']:.0%} "
          f"DepCorr={WEIGHTS['dep_correctness']:.0%} "
          f"Efficiency={WEIGHTS['efficiency']:.0%}")

    for model_name, results in all_results.items():
        total = len(results)
        passed_results = [r for r in results if r.passed_prereq]
        failed_results = [r for r in results if not r.passed_prereq]
        passed = len(passed_results)
        failed = len(failed_results)

        print(f"\n{'━' * 55}")
        print(f"  Model: {model_name}")
        print(f"{'━' * 55}")

        # ── JSON 신뢰성 (별도 보고) ──
        print(f"\n  [JSON 신뢰성]")
        print(f"    Pass Rate:            {passed}/{total} ({passed/total*100:.1f}%)")
        if failed > 0:
            print(f"    실패:                 {failed}건")
            # 카테고리별 실패 분포
            fail_cats = {}
            for r in failed_results:
                fail_cats[r.category] = fail_cats.get(r.category, 0) + 1
            for cat, cnt in sorted(fail_cats.items(), key=lambda x: -x[1]):
                print(f"      {cat}: {cnt}건")

        # ── Planning 능력 (JSON 성공 케이스만) ──
        if passed == 0:
            print(f"\n  [Planning 능력] — JSON 성공 케이스 없음, 평가 불가")
            continue

        pavg = lambda attr: sum(getattr(r, attr) for r in passed_results) / passed

        print(f"\n  [Planning 능력] — JSON 성공 {passed}건 기준")
        print(f"    Intent Recall:         {pavg('intent_recall'):.3f}     (30%  빠뜨린 intent)")
        print(f"    Order Accuracy:        {pavg('order_accuracy'):.3f}     (25%  순서 정확도)")
        print(f"    Intent Precision:      {pavg('intent_precision'):.3f}     (20%  불필요 단계)")
        print(f"    Dep Correctness:       {pavg('dep_correctness'):.3f}     (15%  의존성 일치)")
        print(f"    Efficiency:            {pavg('efficiency'):.3f}     (10%  단계 수)")
        print(f"    ─────────────────────────────")
        print(f"    Weighted Score:        {pavg('score'):.3f}")

        print(f"\n  [보조 지표]")
        print(f"    Hallucination:         {sum(len(r.hallucinated_intents) for r in passed_results)}건")
        print(f"    Cycle:                 {sum(r.has_cycle for r in passed_results)}건")
        print(f"    Structural Invalid:    {sum(not r.dep_structural_valid for r in passed_results)}건")
        perfect = sum(1 for r in passed_results if r.score >= 0.99)
        print(f"    Perfect Score:         {perfect}/{passed} ({perfect/passed*100:.1f}%)")
        print(f"    Avg Latency:           {pavg('latency_ms'):.0f}ms")

        # 카테고리별 (JSON 성공 케이스만)
        print(f"\n  [카테고리별] — JSON 성공 케이스 기준")
        cats = sorted(set(r.category for r in passed_results))
        print(f"    {'Category':<15} {'Score':>6} {'Recall':>7} {'Order':>7} "
              f"{'Prec':>6} {'DepC':>6} {'Eff':>5} {'N':>3}")
        print(f"    {'─' * 60}")
        for cat in cats:
            rs = [r for r in passed_results if r.category == cat]
            n = len(rs)
            if n == 0:
                continue
            cavg = lambda attr, _rs=rs: sum(getattr(r, attr) for r in _rs) / len(_rs)
            print(f"    {cat:<15} {cavg('score'):>6.3f} {cavg('intent_recall'):>7.3f} "
                  f"{cavg('order_accuracy'):>7.3f} {cavg('intent_precision'):>6.3f} "
                  f"{cavg('dep_correctness'):>6.3f} {cavg('efficiency'):>5.3f} {n:>3}")

        # 실패 케이스 (JSON 성공했지만 점수 낮은 것만)
        low_score = [r for r in passed_results if r.score < 0.7]
        if low_score:
            print(f"\n  [Planning 낮은 점수 (< 0.7)] — {len(low_score)}건")
            for r in sorted(low_score, key=lambda x: x.score):
                d = r.details
                print(f"    {r.test_id} ({r.category}): {r.score:.3f}")
                print(f"      입력: {r.input_text[:60]}")
                print(f"      expected: {d.get('expected_intents')}")
                print(f"      actual:   {d.get('actual_intents')}")
                print(f"      recall={r.intent_recall:.2f} order={r.order_accuracy:.2f} "
                      f"prec={r.intent_precision:.2f} dep={r.dep_correctness:.2f} "
                      f"eff={r.efficiency:.2f}")
                if r.hallucinated_intents:
                    print(f"      hallucinated: {r.hallucinated_intents}")
                if d.get("structural_errors"):
                    print(f"      structural: {d['structural_errors']}")

    # 모델 간 비교
    if len(all_results) > 1:
        print(f"\n{'━' * 65}")
        print("  MODEL COMPARISON")
        print(f"{'━' * 65}")

        # JSON 신뢰성 비교
        header = f"  {'Metric':<24}"
        for name in all_results:
            header += f"{name:>18}"
        print(header)
        print(f"  {'─' * (24 + 18 * len(all_results))}")

        # JSON 별도
        line = f"  {'JSON Pass Rate':<24}"
        for model, rs in all_results.items():
            val = sum(r.passed_prereq for r in rs) / len(rs) * 100
            line += f"{val:>17.1f}%"
        print(line)

        print(f"  {'─' * (24 + 18 * len(all_results))}")

        # Planning 능력 (JSON 성공만)
        line = f"  {'Eval Sample Size':<24}"
        for model, rs in all_results.items():
            passed = [r for r in rs if r.passed_prereq]
            line += f"{len(passed):>18d}"
        print(line)

        planning_metrics = [
            ("Intent Recall (30%)",
             lambda rs: sum(r.intent_recall for r in rs) / len(rs)),
            ("Order Accuracy (25%)",
             lambda rs: sum(r.order_accuracy for r in rs) / len(rs)),
            ("Intent Precision (20%)",
             lambda rs: sum(r.intent_precision for r in rs) / len(rs)),
            ("Dep Correctness (15%)",
             lambda rs: sum(r.dep_correctness for r in rs) / len(rs)),
            ("Efficiency (10%)",
             lambda rs: sum(r.efficiency for r in rs) / len(rs)),
            ("─── Planning Score",
             lambda rs: sum(r.score for r in rs) / len(rs)),
        ]

        for name, fn in planning_metrics:
            line = f"  {name:<24}"
            for model, rs in all_results.items():
                passed = [r for r in rs if r.passed_prereq]
                if passed:
                    val = fn(passed)
                    line += f"{val:>18.3f}"
                else:
                    line += f"{'N/A':>18}"
            print(line)

        print(f"  {'─' * (24 + 18 * len(all_results))}")

        aux_metrics = [
            ("Hallucinations",
             lambda rs: sum(len(r.hallucinated_intents) for r in rs), "d"),
            ("Struct Invalid",
             lambda rs: sum(not r.dep_structural_valid for r in rs), "d"),
            ("Avg Latency (ms)",
             lambda rs: sum(r.latency_ms for r in rs) / len(rs), "ms"),
        ]

        for name, fn, fmt in aux_metrics:
            line = f"  {name:<24}"
            for model, rs in all_results.items():
                passed = [r for r in rs if r.passed_prereq]
                if not passed:
                    line += f"{'N/A':>18}"
                    continue
                val = fn(passed)
                if fmt == "d":
                    line += f"{val:>18d}"
                elif fmt == "ms":
                    line += f"{val:>18.0f}"
            print(line)


# ── 메인 ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Planner 결과 재평가 (v3 지표)")
    parser.add_argument("--report", default=None,
                        help="comparison_report.json 경로")
    parser.add_argument("--test-cases", default=None,
                        help="planner_test_cases.json 경로")
    parser.add_argument("--project-root", default=None,
                        help="프로젝트 루트 경로")
    args = parser.parse_args()

    # 프로젝트 루트
    if args.project_root:
        root = Path(args.project_root)
    else:
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True)
            root = Path(result.stdout.strip())
        except Exception:
            root = Path.cwd()

    report_path = Path(args.report) if args.report else \
        root / "outputs" / "planner_comparison" / "comparison_report.json"
    test_path = Path(args.test_cases) if args.test_cases else \
        root / "data" / "evaluation" / "planner_test_cases.json"

    if not report_path.exists():
        print(f"ERROR: {report_path} not found")
        sys.exit(1)
    if not test_path.exists():
        print(f"ERROR: {test_path} not found")
        sys.exit(1)

    with open(report_path) as f:
        report = json.load(f)
    with open(test_path) as f:
        test_data = json.load(f)

    test_lookup = {tc["id"]: tc for tc in test_data["test_cases"]}

    print(f"Report: {report_path}")
    print(f"Test cases: {test_path} ({len(test_data['test_cases'])}개)")
    print(f"Models: {report['models']}")

    # 재평가
    all_results: dict[str, list[EvalResult]] = {}

    for model_name, raw_results in report["results"].items():
        results = []
        for r in raw_results:
            tc = test_lookup.get(r["test_id"])
            if tc is None:
                continue
            ev = evaluate(tc, model_name, r["raw_output"], r.get("latency_ms", 0))
            results.append(ev)
        all_results[model_name] = results
        print(f"  {model_name}: {len(results)}건 평가")

    if not all_results or all(len(v) == 0 for v in all_results.values()):
        print("\nERROR: 매칭되는 테스트 케이스 없음")
        sys.exit(1)

    print_report(all_results)

    # JSON 저장
    output_path = report_path.parent / "evaluation_v3_report.json"
    v3_report = {
        "timestamp": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "metrics_version": "v3",
        "weights": WEIGHTS,
        "results": {
            model: [
                {
                    "test_id": r.test_id,
                    "category": r.category,
                    "input": r.input_text,
                    "json_valid": r.json_valid,
                    "plan_extracted": r.plan_extracted,
                    "intent_recall": round(r.intent_recall, 4),
                    "order_accuracy": round(r.order_accuracy, 4),
                    "intent_precision": round(r.intent_precision, 4),
                    "dep_correctness": round(r.dep_correctness, 4),
                    "efficiency": round(r.efficiency, 4),
                    "score": round(r.score, 4),
                    "hallucinated_intents": r.hallucinated_intents,
                    "has_cycle": r.has_cycle,
                    "dep_structural_valid": r.dep_structural_valid,
                    "latency_ms": round(r.latency_ms, 1),
                    "details": r.details,
                }
                for r in results
            ]
            for model, results in all_results.items()
        },
        "summary": {
            model: (lambda total, passed: {
                "total_cases": len(total),
                "json_pass_rate": round(sum(r.passed_prereq for r in total) / len(total), 4),
                "eval_sample_size": len(passed),
                "planning_metrics": {
                    "intent_recall": round(sum(r.intent_recall for r in passed) / len(passed), 4),
                    "order_accuracy": round(sum(r.order_accuracy for r in passed) / len(passed), 4),
                    "intent_precision": round(sum(r.intent_precision for r in passed) / len(passed), 4),
                    "dep_correctness": round(sum(r.dep_correctness for r in passed) / len(passed), 4),
                    "efficiency": round(sum(r.efficiency for r in passed) / len(passed), 4),
                    "weighted_score": round(sum(r.score for r in passed) / len(passed), 4),
                } if passed else None,
                "auxiliary": {
                    "hallucinations": sum(len(r.hallucinated_intents) for r in passed),
                    "struct_invalid": sum(not r.dep_structural_valid for r in passed),
                    "avg_latency_ms": round(sum(r.latency_ms for r in passed) / len(passed), 1),
                } if passed else None,
            })(rs, [r for r in rs if r.passed_prereq])
            for model, rs in all_results.items()
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(v3_report, f, ensure_ascii=False, indent=2)

    print(f"\nv3 Report saved: {output_path}")


if __name__ == "__main__":
    main()
