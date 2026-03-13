"""
Planner 비교 결과 재평가 스크립트
이미 돌린 comparison_report.json을 읽어서 개선된 지표로 재평가

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
class EvalResultV2:
    test_id: str
    category: str
    input_text: str
    model: str

    # 전제 조건 (pass/fail)
    json_valid: bool = False
    plan_extracted: bool = False

    # 핵심 지표 (0.0 ~ 1.0)
    intent_precision: float = 0.0   # 모델 출력 intent 중 맞는 비율
    intent_recall: float = 0.0     # 정답 intent 중 찾은 비율
    dep_validity: float = 0.0      # 의존성 논리적 유효성
    efficiency: float = 0.0        # 단계 수 적절성

    # 보조 지표
    hallucinated_intents: list = field(default_factory=list)
    has_cycle: bool = False
    latency_ms: float = 0.0

    # 종합
    score: float = 0.0
    details: dict = field(default_factory=dict)

    @property
    def passed_prereq(self) -> bool:
        return self.json_valid and self.plan_extracted


# ── 핵심 평가 함수 ─────────────────────────────────────────

def _multiset_intersection(a: list, b: list) -> int:
    """두 리스트의 multiset 교집합 크기 (순서 무관, 중복 허용)"""
    ca, cb = Counter(a), Counter(b)
    return sum((ca & cb).values())


def _detect_cycle(plan: list[dict]) -> bool:
    """의존성 그래프에 순환이 있는지 DFS로 검사"""
    adj = {}
    for step in plan:
        sid = step.get("step_id")
        deps = step.get("depends_on", [])
        if isinstance(deps, list):
            adj[sid] = deps
        else:
            adj[sid] = []

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


def _check_dep_validity(plan: list[dict]) -> tuple[float, list[str]]:
    """의존성 유효성 검사 — 여러 항목 체크 후 비율 반환"""
    if not plan:
        return 0.0, ["빈 plan"]

    checks = []
    errors = []
    step_ids = {s.get("step_id") for s in plan}

    # 1. 존재하지 않는 step_id 참조
    for step in plan:
        deps = step.get("depends_on", [])
        if not isinstance(deps, list):
            checks.append(False)
            errors.append(f"step {step.get('step_id')}: depends_on이 list가 아님")
            continue
        invalid_refs = [d for d in deps if d not in step_ids]
        if invalid_refs:
            checks.append(False)
            errors.append(f"step {step.get('step_id')}: 존재하지 않는 step 참조 {invalid_refs}")
        else:
            checks.append(True)

    # 2. 자기 자신 참조
    for step in plan:
        sid = step.get("step_id")
        deps = step.get("depends_on", [])
        if isinstance(deps, list) and sid in deps:
            checks.append(False)
            errors.append(f"step {sid}: 자기 자신 참조")
        else:
            checks.append(True)

    # 3. 순환 의존성
    has_cycle = _detect_cycle(plan)
    checks.append(not has_cycle)
    if has_cycle:
        errors.append("순환 의존성 발견")

    # 4. 역방향 의존성 (step 3이 step 5에 의존 등)
    for step in plan:
        sid = step.get("step_id")
        deps = step.get("depends_on", [])
        if isinstance(deps, list):
            backward = [d for d in deps if isinstance(d, int) and d >= sid]
            if backward:
                checks.append(False)
                errors.append(f"step {sid}: 역방향 의존 {backward}")
            else:
                checks.append(True)

    score = sum(checks) / len(checks) if checks else 0.0
    return score, errors


def _calc_efficiency(actual_steps: int, expected_steps: int) -> float:
    """단계 수 효율성 — 적절한 수에 가까울수록 높은 점수"""
    if expected_steps == 0:
        return 0.0
    if actual_steps == expected_steps:
        return 1.0
    # 차이가 클수록 감소, 최소 0점
    diff = abs(actual_steps - expected_steps)
    return max(0.0, 1.0 - (diff * 0.3))


def evaluate_v2(test_case: dict, model_name: str,
                raw_output: str, latency_ms: float) -> EvalResultV2:
    """개선된 평가 함수"""
    result = EvalResultV2(
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

    # ── Intent Precision & Recall ──────────────────
    expected_intents = [s["intent"] for s in expected["plan"]]
    actual_intents = [s.get("intent", "") for s in plan]

    # hallucination 체크
    result.hallucinated_intents = [i for i in actual_intents if i not in VALID_INTENTS]

    # multiset 기반 (순서 무관, 중복 허용)
    matched = _multiset_intersection(actual_intents, expected_intents)

    if len(actual_intents) > 0:
        result.intent_precision = matched / len(actual_intents)
    if len(expected_intents) > 0:
        result.intent_recall = matched / len(expected_intents)

    result.details["expected_intents"] = expected_intents
    result.details["actual_intents"] = actual_intents
    result.details["intent_matched"] = matched

    # ── Dependency Validity ────────────────────────
    dep_score, dep_errors = _check_dep_validity(plan)
    result.dep_validity = dep_score
    result.has_cycle = _detect_cycle(plan)
    if dep_errors:
        result.details["dep_errors"] = dep_errors

    # ── Efficiency ─────────────────────────────────
    result.efficiency = _calc_efficiency(len(plan), expected["num_steps"])
    result.details["actual_steps"] = len(plan)
    result.details["expected_steps"] = expected["num_steps"]

    # ── 종합 점수 (가중합) ──────────────────────────
    result.score = (
        result.intent_precision * 0.40 +
        result.intent_recall * 0.25 +
        result.dep_validity * 0.20 +
        result.efficiency * 0.15
    )

    return result


# ── 리포트 출력 ────────────────────────────────────────────

def print_report(all_results: dict[str, list[EvalResultV2]], test_cases: list):
    print("\n" + "=" * 80)
    print("PLANNER EVALUATION REPORT (v2 metrics)")
    print("=" * 80)

    for model_name, results in all_results.items():
        total = len(results)
        passed = sum(1 for r in results if r.passed_prereq)
        failed = total - passed

        avg_precision = sum(r.intent_precision for r in results) / total
        avg_recall = sum(r.intent_recall for r in results) / total
        avg_dep = sum(r.dep_validity for r in results) / total
        avg_eff = sum(r.efficiency for r in results) / total
        avg_score = sum(r.score for r in results) / total
        avg_latency = sum(r.latency_ms for r in results) / total

        hallucination_count = sum(len(r.hallucinated_intents) for r in results)
        cycle_count = sum(1 for r in results if r.has_cycle)
        perfect_count = sum(1 for r in results if r.score >= 0.99)

        print(f"\n{'━' * 50}")
        print(f"  Model: {model_name}")
        print(f"{'━' * 50}")

        print(f"\n  [전제 조건]")
        print(f"    JSON 파싱 성공:     {passed}/{total} ({passed/total*100:.1f}%)")
        print(f"    JSON 파싱 실패:     {failed}/{total}")

        print(f"\n  [핵심 지표]")
        print(f"    Intent Precision:   {avg_precision:.3f}  (모델 출력 중 맞는 비율)")
        print(f"    Intent Recall:      {avg_recall:.3f}  (정답 중 찾은 비율)")
        print(f"    Dep Validity:       {avg_dep:.3f}  (의존성 논리적 유효성)")
        print(f"    Efficiency:         {avg_eff:.3f}  (단계 수 적절성)")
        print(f"    ──────────────────────")
        print(f"    Weighted Score:     {avg_score:.3f}")

        print(f"\n  [보조 지표]")
        print(f"    Hallucinated:       {hallucination_count}건 (없는 intent 사용)")
        print(f"    Cycle Detected:     {cycle_count}건 (순환 의존성)")
        print(f"    Perfect Score:      {perfect_count}/{total}")
        print(f"    Avg Latency:        {avg_latency:.0f}ms")

        # 카테고리별 세부
        print(f"\n  [카테고리별 점수]")
        categories = sorted(set(r.category for r in results))
        print(f"    {'Category':<15} {'Score':>6} {'Prec':>6} {'Rec':>6} {'Dep':>6} {'Eff':>6} {'N':>4}")
        print(f"    {'─'*55}")
        for cat in categories:
            cat_rs = [r for r in results if r.category == cat]
            n = len(cat_rs)
            print(f"    {cat:<15} "
                  f"{sum(r.score for r in cat_rs)/n:>6.3f} "
                  f"{sum(r.intent_precision for r in cat_rs)/n:>6.3f} "
                  f"{sum(r.intent_recall for r in cat_rs)/n:>6.3f} "
                  f"{sum(r.dep_validity for r in cat_rs)/n:>6.3f} "
                  f"{sum(r.efficiency for r in cat_rs)/n:>6.3f} "
                  f"{n:>4}")

        # 실패 케이스 상세
        failed_cases = [r for r in results if r.score < 0.7]
        if failed_cases:
            print(f"\n  [낮은 점수 케이스 (< 0.7)]")
            for r in sorted(failed_cases, key=lambda x: x.score):
                print(f"    {r.test_id} ({r.category}): score={r.score:.3f}")
                print(f"      입력: {r.input_text[:60]}")
                if not r.passed_prereq:
                    print(f"      → JSON 파싱 실패")
                else:
                    d = r.details
                    print(f"      expected: {d.get('expected_intents')}")
                    print(f"      actual:   {d.get('actual_intents')}")
                    if r.hallucinated_intents:
                        print(f"      hallucinated: {r.hallucinated_intents}")
                    if d.get("dep_errors"):
                        print(f"      dep_errors: {d['dep_errors']}")

    # 모델 간 비교
    if len(all_results) > 1:
        print(f"\n{'━' * 60}")
        print("  MODEL COMPARISON")
        print(f"{'━' * 60}")

        header = f"  {'Metric':<22}"
        for name in all_results:
            header += f"{name:>15}"
        print(header)
        print(f"  {'─' * (22 + 15 * len(all_results))}")

        metrics = [
            ("JSON Pass Rate",
             lambda rs: sum(r.passed_prereq for r in rs) / len(rs) * 100, "%"),
            ("Intent Precision",
             lambda rs: sum(r.intent_precision for r in rs) / len(rs), "f"),
            ("Intent Recall",
             lambda rs: sum(r.intent_recall for r in rs) / len(rs), "f"),
            ("Dep Validity",
             lambda rs: sum(r.dep_validity for r in rs) / len(rs), "f"),
            ("Efficiency",
             lambda rs: sum(r.efficiency for r in rs) / len(rs), "f"),
            ("Weighted Score",
             lambda rs: sum(r.score for r in rs) / len(rs), "f"),
            ("Hallucinations",
             lambda rs: sum(len(r.hallucinated_intents) for r in rs), "d"),
            ("Cycles",
             lambda rs: sum(r.has_cycle for r in rs), "d"),
            ("Avg Latency (ms)",
             lambda rs: sum(r.latency_ms for r in rs) / len(rs), "ms"),
        ]

        for name, fn, fmt in metrics:
            line = f"  {name:<22}"
            for model, rs in all_results.items():
                val = fn(rs)
                if fmt == "%":
                    line += f"{val:>14.1f}%"
                elif fmt == "f":
                    line += f"{val:>15.3f}"
                elif fmt == "d":
                    line += f"{val:>15d}"
                elif fmt == "ms":
                    line += f"{val:>15.0f}"
            print(line)


# ── 메인 ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Planner 결과 재평가 (v2 지표)")
    parser.add_argument(
        "--report", default=None,
        help="comparison_report.json 경로")
    parser.add_argument(
        "--test-cases", default=None,
        help="planner_test_cases.json 경로")
    parser.add_argument(
        "--project-root", default=None,
        help="프로젝트 루트 경로")
    args = parser.parse_args()

    # 프로젝트 루트 탐지
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

    # 파일 경로
    report_path = Path(args.report) if args.report else \
        root / "outputs" / "planner_comparison" / "comparison_report.json"
    test_path = Path(args.test_cases) if args.test_cases else \
        root / "data" / "evaluation" / "planner_test_cases.json"

    if not report_path.exists():
        print(f"ERROR: {report_path} not found")
        print("먼저 compare_planner_models.py를 실행하세요.")
        sys.exit(1)

    if not test_path.exists():
        print(f"ERROR: {test_path} not found")
        sys.exit(1)

    # 데이터 로드
    with open(report_path) as f:
        report = json.load(f)
    with open(test_path) as f:
        test_data = json.load(f)

    test_lookup = {tc["id"]: tc for tc in test_data["test_cases"]}

    print(f"Report: {report_path}")
    print(f"Test cases: {test_path}")
    print(f"Models: {report['models']}")
    print(f"Original test count: {report['num_test_cases']}")
    print(f"Current test count: {len(test_data['test_cases'])}")

    # 재평가
    all_results: dict[str, list[EvalResultV2]] = {}

    for model_name, raw_results in report["results"].items():
        results = []
        for r in raw_results:
            test_id = r["test_id"]
            tc = test_lookup.get(test_id)
            if tc is None:
                # 테스트 케이스가 v2에서 ID가 바뀐 경우 스킵
                continue

            ev = evaluate_v2(
                test_case=tc,
                model_name=model_name,
                raw_output=r["raw_output"],
                latency_ms=r.get("latency_ms", 0),
            )
            results.append(ev)

        all_results[model_name] = results
        print(f"  {model_name}: {len(results)} cases evaluated")

    if not all_results or all(len(v) == 0 for v in all_results.values()):
        print("\nWARNING: 매칭되는 테스트 케이스가 없습니다.")
        print("report의 test_id와 test_cases의 id가 다를 수 있습니다.")
        print(f"Report test_ids: {[r['test_id'] for r in list(report['results'].values())[0][:5]]}...")
        print(f"Test case ids: {list(test_lookup.keys())[:5]}...")
        sys.exit(1)

    # 리포트 출력
    print_report(all_results, test_data["test_cases"])

    # 결과 JSON 저장
    output_path = report_path.parent / "evaluation_v2_report.json"
    v2_report = {
        "timestamp": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "metrics_version": "v2",
        "weights": {
            "intent_precision": 0.40,
            "intent_recall": 0.25,
            "dep_validity": 0.20,
            "efficiency": 0.15,
        },
        "results": {
            model: [
                {
                    "test_id": r.test_id,
                    "category": r.category,
                    "input": r.input_text,
                    "json_valid": r.json_valid,
                    "plan_extracted": r.plan_extracted,
                    "intent_precision": round(r.intent_precision, 4),
                    "intent_recall": round(r.intent_recall, 4),
                    "dep_validity": round(r.dep_validity, 4),
                    "efficiency": round(r.efficiency, 4),
                    "score": round(r.score, 4),
                    "hallucinated_intents": r.hallucinated_intents,
                    "has_cycle": r.has_cycle,
                    "latency_ms": round(r.latency_ms, 1),
                    "details": r.details,
                }
                for r in results
            ]
            for model, results in all_results.items()
        },
        "summary": {
            model: {
                "json_pass_rate": round(sum(r.passed_prereq for r in rs) / len(rs), 4),
                "intent_precision": round(sum(r.intent_precision for r in rs) / len(rs), 4),
                "intent_recall": round(sum(r.intent_recall for r in rs) / len(rs), 4),
                "dep_validity": round(sum(r.dep_validity for r in rs) / len(rs), 4),
                "efficiency": round(sum(r.efficiency for r in rs) / len(rs), 4),
                "weighted_score": round(sum(r.score for r in rs) / len(rs), 4),
                "hallucination_total": sum(len(r.hallucinated_intents) for r in rs),
                "cycle_count": sum(r.has_cycle for r in rs),
                "avg_latency_ms": round(sum(r.latency_ms for r in rs) / len(rs), 1),
            }
            for model, rs in all_results.items()
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(v2_report, f, ensure_ascii=False, indent=2)

    print(f"\nv2 Report saved: {output_path}")


if __name__ == "__main__":
    main()
