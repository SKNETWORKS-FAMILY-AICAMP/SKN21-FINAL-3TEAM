"""
Planner LoRA Held-out 평가 스크립트

학습 데이터와 독립된 held-out 테스트셋(planner_test_cases.json)으로
LoRA fine-tuned 모델의 일반화 성능을 측정.

사용법:
    # LoRA 모델 평가
    python ai/finetuning/scripts/eval_planner_holdout.py

    # 어댑터 경로 지정
    python ai/finetuning/scripts/eval_planner_holdout.py --adapter outputs/v3_planner/final

    # base 모델만 평가 (LoRA 없이)
    python ai/finetuning/scripts/eval_planner_holdout.py --base-only
"""

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

# ── 상수 ──

VALID_INTENTS = {"judgment", "doc_retrieve", "doc_generate",
                 "schedule_add", "schedule_view", "general"}

WEIGHTS = {
    "intent_recall": 0.30,
    "order_accuracy": 0.25,
    "intent_precision": 0.20,
    "dep_correctness": 0.15,
    "efficiency": 0.10,
}

PLANNER_SYSTEM_PROMPT = """당신은 업무 자동화 시스템의 Task Planner입니다.
사용자 요청을 분석하여 실행 가능한 단계별 계획을 JSON으로 출력하세요.

## 사용 가능한 intent (6개)
- judgment: 사규/규정 기반 판단 ("~해도 되나요?", "규정 확인")
- doc_retrieve: 문서 검색/조회/요약 ("~문서 찾아줘", "~내용 알려줘")
- doc_generate: 문서 생성 ("보고서 만들어줘", "회의록 작성해줘")
- schedule_add: 일정 등록 ("~에 회의 잡아줘", "휴가 등록")
- schedule_view: 일정 조회 ("다음 주 일정 보여줘")
- general: 일반 질문 (위에 해당하지 않는 경우)

## 출력 형식 (반드시 이 JSON 형식만 출력)
{
  "plan": [
    {
      "step_id": 1,
      "intent": "intent_name",
      "query": "이 단계에서 처리할 구체적 요청",
      "depends_on": []
    }
  ]
}

## 규칙
1. depends_on: 이 단계가 실행되기 전에 완료되어야 하는 step_id 목록
2. depends_on이 비어있으면 즉시 실행 가능 (병렬 처리 가능)
3. 단순 요청은 1단계로 처리
4. 최대 4단계까지만 분해
5. JSON만 출력하고 다른 설명은 하지 마세요"""


# ── JSON 추출 ──

def extract_json(text: str) -> dict | None:
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


# ── 평가 지표 (v3.1) ──

def _multiset_intersection(a: list, b: list) -> int:
    ca, cb = Counter(a), Counter(b)
    return sum((ca & cb).values())


def _lcs_length(a: list, b: list) -> int:
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


def evaluate_single(test_case: dict, pred_text: str, latency_ms: float) -> dict:
    """단일 케이스 v3.1 평가"""
    result = {
        "test_id": test_case["id"],
        "category": test_case["category"],
        "input": test_case["input"],
        "raw_output": pred_text,
        "latency_ms": latency_ms,
        "json_valid": False,
        "plan_nonempty": False,
        "usable": False,
        "metrics": {},
        "error": None,
    }

    expected = test_case["expected"]
    expected_intents = [s["intent"] for s in expected["plan"]]
    result["expected_intents"] = expected_intents

    # JSON 파싱
    parsed = extract_json(pred_text)
    if parsed is None:
        result["error"] = "JSON 파싱 실패"
        result["actual_intents"] = []
        return result
    result["json_valid"] = True

    if "plan" not in parsed or not isinstance(parsed["plan"], list):
        result["error"] = "plan 필드 없음"
        result["actual_intents"] = []
        return result

    plan = parsed["plan"]
    result["plan_nonempty"] = len(plan) > 0

    if not result["plan_nonempty"]:
        result["error"] = "빈 plan"
        result["actual_intents"] = []
        return result

    result["usable"] = True
    actual_intents = [s.get("intent", "") for s in plan]
    result["actual_intents"] = actual_intents

    # Intent Recall (30%)
    matched = _multiset_intersection(actual_intents, expected_intents)
    recall = matched / len(expected_intents) if expected_intents else (
        1.0 if not actual_intents else 0.0)

    # Order Accuracy (25%)
    if expected_intents:
        lcs = _lcs_length(actual_intents, expected_intents)
        order = lcs / len(expected_intents)
    else:
        order = 1.0 if not actual_intents else 0.0

    # Precision (20%)
    precision = matched / len(actual_intents) if actual_intents else (
        1.0 if not expected_intents else 0.0)

    # Dep Correctness (15%)
    min_len = min(len(plan), len(expected["plan"]))
    max_len = max(len(plan), len(expected["plan"]))
    dep_matches = 0
    for i in range(min_len):
        gold_deps = set(expected["plan"][i].get("depends_on", []))
        pred_deps_raw = plan[i].get("depends_on", [])
        pred_deps = set(pred_deps_raw) if isinstance(pred_deps_raw, list) else set()
        if gold_deps == pred_deps:
            dep_matches += 1
    dep_corr = dep_matches / max_len if max_len > 0 else 1.0

    # Efficiency (10%)
    diff = abs(len(plan) - expected["num_steps"])
    efficiency = max(0.0, 1.0 - diff * 0.3)

    # Weighted score
    score = (recall * WEIGHTS["intent_recall"] +
             order * WEIGHTS["order_accuracy"] +
             precision * WEIGHTS["intent_precision"] +
             dep_corr * WEIGHTS["dep_correctness"] +
             efficiency * WEIGHTS["efficiency"])

    hallucinated = [i for i in actual_intents if i not in VALID_INTENTS]

    result["metrics"] = {
        "intent_recall": round(recall, 4),
        "order_accuracy": round(order, 4),
        "intent_precision": round(precision, 4),
        "dep_correctness": round(dep_corr, 4),
        "efficiency": round(efficiency, 4),
        "score": round(score, 4),
    }
    result["hallucinated"] = hallucinated
    result["perfect"] = score >= 0.99

    return result


# ── 모델 로드 ──

def load_model(adapter_path: str | None = None):
    """Kanana-1.5-8B + (optional) LoRA 어댑터 로드"""
    model_id = "kakaocorp/kanana-1.5-8b-instruct-2505"

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    mode = "base"
    if adapter_path:
        print(f"  LoRA 어댑터 로드: {adapter_path}")
        model = PeftModel.from_pretrained(model, adapter_path)
        mode = "lora"

    model.eval()
    print(f"  VRAM: {torch.cuda.memory_allocated()/1e9:.1f} GB ({mode})")
    return tokenizer, model, mode


def generate(model, tokenizer, user_input: str) -> tuple[str, float]:
    """추론 실행"""
    messages = [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    input_len = inputs["input_ids"].shape[1]

    t0 = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )
    latency = (time.time() - t0) * 1000

    pred_text = tokenizer.decode(
        outputs[0][input_len:], skip_special_tokens=True).strip()
    return pred_text, latency


# ── 메인 ──

def main():
    parser = argparse.ArgumentParser(description="Planner LoRA held-out 평가")
    parser.add_argument("--adapter", default=None,
                        help="LoRA 어댑터 경로 (미지정 시 outputs/v3_planner/final)")
    parser.add_argument("--base-only", action="store_true",
                        help="base 모델만 평가 (LoRA 없이)")
    parser.add_argument("--test-cases", default=None,
                        help="held-out 테스트 JSON 경로")
    parser.add_argument("--output", default=None,
                        help="결과 저장 경로")
    args = parser.parse_args()

    # 프로젝트 루트
    import subprocess
    try:
        root = Path(subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True).stdout.strip())
    except Exception:
        root = Path.cwd()

    # 테스트 데이터
    test_path = Path(args.test_cases) if args.test_cases else \
        root / "data" / "evaluation" / "planner_test_cases.json"
    if not test_path.exists():
        print(f"ERROR: {test_path} not found")
        return

    with open(test_path) as f:
        test_data = json.load(f)
    test_cases = test_data["test_cases"]
    print(f"\nHeld-out 테스트: {test_path.name} ({len(test_cases)}건)")

    # 모델 로드
    adapter_path = None
    if not args.base_only:
        adapter_path = args.adapter or str(root / "outputs" / "v3_planner" / "final")
        if not Path(adapter_path).exists():
            print(f"ERROR: adapter not found at {adapter_path}")
            print("  --base-only 로 base 모델만 평가하거나, --adapter 경로를 지정하세요")
            return

    print(f"\n모델 로드 중...")
    tokenizer, model, mode = load_model(adapter_path)

    # 평가
    print(f"\n{'='*65}")
    print(f"  HELD-OUT 평가 시작 ({mode.upper()} model, {len(test_cases)}건)")
    print(f"{'='*65}\n")

    results = []
    for i, tc in enumerate(test_cases, 1):
        pred_text, latency = generate(model, tokenizer, tc["input"])
        result = evaluate_single(tc, pred_text, latency)
        results.append(result)

        # 진행 표시
        status = "FAIL"
        if result["usable"]:
            if result["perfect"]:
                status = "OK"
            else:
                status = f"{result['metrics']['score']:.3f}"

        if i <= 10 or not result["usable"] or not result.get("perfect", False) or i % 20 == 0:
            print(f"  [{i:03d}] {tc['id']:>8} ({tc['category']:<12}) "
                  f"{status:>6} | {latency:>5.0f}ms | "
                  f"exp={result['expected_intents']} "
                  f"got={result['actual_intents']}")
            if result["error"]:
                print(f"         ⚠ {result['error']}")

    # ── 집계 ──
    total = len(results)
    usable_results = [r for r in results if r["usable"]]
    failed_results = [r for r in results if not r["usable"]]
    usable = len(usable_results)

    print(f"\n{'='*65}")
    print(f"  HELD-OUT 평가 결과 ({mode.upper()}, v3.1 지표)")
    print(f"{'='*65}")
    print(f"  총 평가:        {total}건")
    print(f"  유효 응답:      {usable}/{total} ({usable/total*100:.1f}%)")

    if failed_results:
        json_fail = sum(1 for r in failed_results if not r["json_valid"])
        empty_plan = sum(1 for r in failed_results
                         if r["json_valid"] and not r["plan_nonempty"])
        print(f"  실패 내역:")
        if json_fail > 0:
            print(f"    JSON 파싱 실패: {json_fail}건")
        if empty_plan > 0:
            print(f"    빈 plan 출력:   {empty_plan}건")
        # 카테고리별 실패
        fail_cats = {}
        for r in failed_results:
            fail_cats[r["category"]] = fail_cats.get(r["category"], 0) + 1
        for cat, cnt in sorted(fail_cats.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {cnt}건")

    if usable > 0:
        avg = lambda key: sum(r["metrics"][key] for r in usable_results) / usable

        print(f"\n  [Planning 능력] — 유효 {usable}건 기준")
        print(f"    Intent Recall:     {avg('intent_recall'):.3f}")
        print(f"    Order Accuracy:    {avg('order_accuracy'):.3f}")
        print(f"    Intent Precision:  {avg('intent_precision'):.3f}")
        print(f"    Dep Correctness:   {avg('dep_correctness'):.3f}")
        print(f"    Efficiency:        {avg('efficiency'):.3f}")
        print(f"    ─────────────────────")
        print(f"    Weighted Score:    {avg('score'):.3f}")

        perfect = sum(1 for r in usable_results if r["perfect"])
        print(f"\n    Perfect Score:     {perfect}/{usable} ({perfect/usable*100:.1f}%)")
        avg_lat = sum(r["latency_ms"] for r in usable_results) / usable
        print(f"    Avg Latency:       {avg_lat:.0f}ms")

        # 카테고리별
        cats = sorted(set(r["category"] for r in usable_results))
        print(f"\n  [카테고리별] — 유효 응답 기준")
        print(f"    {'Category':<15} {'Score':>6} {'Recall':>7} {'Order':>7} "
              f"{'Prec':>6} {'DepC':>6} {'Eff':>5} {'N':>3}/{' Total':>5}")
        print(f"    {'─'*65}")
        for cat in cats:
            rs = [r for r in usable_results if r["category"] == cat]
            total_cat = sum(1 for r in results if r["category"] == cat)
            n = len(rs)
            cavg = lambda key, _rs=rs: sum(r["metrics"][key] for r in _rs) / len(_rs)
            print(f"    {cat:<15} {cavg('score'):>6.3f} {cavg('intent_recall'):>7.3f} "
                  f"{cavg('order_accuracy'):>7.3f} {cavg('intent_precision'):>6.3f} "
                  f"{cavg('dep_correctness'):>6.3f} {cavg('efficiency'):>5.3f} "
                  f"{n:>3}/{total_cat:>3}")

        # 오답 상세
        wrong = [r for r in usable_results if not r["perfect"]]
        if wrong:
            print(f"\n  [오답 상세] — {len(wrong)}건")
            for r in sorted(wrong, key=lambda x: x["metrics"]["score"]):
                m = r["metrics"]
                print(f"    {r['test_id']} ({r['category']}): score={m['score']:.3f}")
                print(f"      입력: {r['input'][:70]}")
                print(f"      expected: {r['expected_intents']}")
                print(f"      actual:   {r['actual_intents']}")
                print(f"      R={m['intent_recall']:.2f} O={m['order_accuracy']:.2f} "
                      f"P={m['intent_precision']:.2f} D={m['dep_correctness']:.2f} "
                      f"E={m['efficiency']:.2f}")
                if r.get("hallucinated"):
                    print(f"      hallucinated: {r['hallucinated']}")

    print(f"\n{'='*65}")

    # 결과 저장
    output_path = Path(args.output) if args.output else \
        root / "outputs" / "v3_planner" / f"holdout_eval_{mode}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model_mode": mode,
        "adapter_path": adapter_path,
        "test_cases_path": str(test_path),
        "total": total,
        "usable": usable,
        "usable_rate": round(usable / total, 4) if total else 0,
        "metrics": {k: round(avg(k), 4) for k in WEIGHTS} if usable > 0 else None,
        "weighted_score": round(avg("score"), 4) if usable > 0 else None,
        "perfect_rate": round(
            sum(1 for r in usable_results if r["perfect"]) / usable, 4
        ) if usable > 0 else 0,
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"  결과 저장: {output_path}")


if __name__ == "__main__":
    main()
