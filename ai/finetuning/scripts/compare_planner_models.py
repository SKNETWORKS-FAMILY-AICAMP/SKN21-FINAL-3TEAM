"""
Planner 베이스 모델 비교 스크립트
Qwen3-8B vs Kanana-1.5-8B vs EXAONE-3.5-7.8B

사용법:
  # RunPod에서 실행
  python ai/finetuning/scripts/compare_planner_models.py

  # 특정 모델만 테스트
  python ai/finetuning/scripts/compare_planner_models.py --models qwen kanana

  # vLLM 서버 모드 (서버가 이미 떠있을 때)
  python ai/finetuning/scripts/compare_planner_models.py --mode vllm --vllm-url http://localhost:8000/v1
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field

# ── 모델 정의 ──────────────────────────────────────────────

MODEL_REGISTRY = {
    "qwen": {
        "model_id": "Qwen/Qwen3-8B",
        "short_name": "Qwen3-8B",
        "load_in_4bit": True,
        "dtype": "bfloat16",
    },
    "kanana": {
        "model_id": "kakaocorp/kanana-1.5-8b-instruct-2505",
        "short_name": "Kanana-1.5-8B",
        "load_in_4bit": True,
        "dtype": "bfloat16",
    },
    "exaone": {
        "model_id": "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct",
        "short_name": "EXAONE-3.5-7.8B",
        "load_in_4bit": False,  # EXAONE은 4bit 호환 이슈
        "dtype": "bfloat16",
    },
}

# ── Planner 시스템 프롬프트 ─────────────────────────────────

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


# ── 평가 함수 ──────────────────────────────────────────────

@dataclass
class EvalResult:
    test_id: str
    category: str
    input_text: str
    model: str
    raw_output: str
    json_valid: bool = False
    plan_extracted: bool = False
    num_steps_match: bool = False
    intents_match: bool = False
    dependencies_match: bool = False
    score: float = 0.0
    latency_ms: float = 0.0
    errors: list = field(default_factory=list)


def extract_json(text: str) -> dict | None:
    """모델 출력에서 JSON 추출 (코드블록, 여분 텍스트 처리)"""
    import re

    # ```json ... ``` 블록 추출
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 순수 JSON 추출
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def evaluate_output(test_case: dict, model_name: str, raw_output: str,
                    latency_ms: float) -> EvalResult:
    """모델 출력을 expected와 비교하여 평가"""
    result = EvalResult(
        test_id=test_case["id"],
        category=test_case["category"],
        input_text=test_case["input"],
        model=model_name,
        raw_output=raw_output,
        latency_ms=latency_ms,
    )

    # 1. JSON 파싱
    parsed = extract_json(raw_output)
    if parsed is None:
        result.errors.append("JSON 파싱 실패")
        return result
    result.json_valid = True

    # 2. plan 필드 존재
    if "plan" not in parsed or not isinstance(parsed["plan"], list):
        result.errors.append("plan 필드 없음")
        return result
    result.plan_extracted = True

    plan = parsed["plan"]
    expected = test_case["expected"]

    # 3. 단계 수 비교
    result.num_steps_match = len(plan) == expected["num_steps"]
    if not result.num_steps_match:
        result.errors.append(
            f"단계 수: expected={expected['num_steps']}, got={len(plan)}")

    # 4. intent 비교 (순서 고려)
    expected_intents = [s["intent"] for s in expected["plan"]]
    actual_intents = [s.get("intent", "") for s in plan]
    result.intents_match = expected_intents == actual_intents
    if not result.intents_match:
        result.errors.append(
            f"intent: expected={expected_intents}, got={actual_intents}")

    # 5. 의존성 비교
    expected_deps = [set(s["depends_on"]) for s in expected["plan"]]
    actual_deps = []
    for s in plan:
        deps = s.get("depends_on", [])
        if isinstance(deps, list):
            actual_deps.append(set(deps))
        else:
            actual_deps.append(set())

    if len(expected_deps) == len(actual_deps):
        result.dependencies_match = all(
            e == a for e, a in zip(expected_deps, actual_deps))
    if not result.dependencies_match:
        result.errors.append(
            f"deps: expected={[list(d) for d in expected_deps]}, "
            f"got={[list(d) for d in actual_deps]}")

    # 6. 종합 점수 (가중치)
    weights = {
        "json_valid": 0.20,
        "plan_extracted": 0.10,
        "num_steps_match": 0.20,
        "intents_match": 0.30,
        "dependencies_match": 0.20,
    }
    result.score = sum(
        w for k, w in weights.items() if getattr(result, k))

    return result


# ── 모델 로딩 & 추론 ──────────────────────────────────────

def load_model_transformers(model_info: dict):
    """transformers로 직접 모델 로딩 (RunPod용)"""
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

    model_id = model_info["model_id"]
    print(f"\n{'='*60}")
    print(f"Loading: {model_info['short_name']} ({model_id})")
    print(f"{'='*60}")

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)

    load_kwargs = {
        "trust_remote_code": True,
        "device_map": "auto",
    }

    if model_info["load_in_4bit"]:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        load_kwargs["quantization_config"] = bnb_config
    else:
        load_kwargs["torch_dtype"] = torch.bfloat16

    model = AutoModelForCausalLM.from_pretrained(model_id, **load_kwargs)
    model.eval()

    return model, tokenizer


def generate_with_transformers(model, tokenizer, user_input: str,
                                max_new_tokens: int = 512) -> tuple[str, float]:
    """transformers 직접 추론"""
    import torch

    messages = [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    # chat template 적용
    if hasattr(tokenizer, "apply_chat_template"):
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
    else:
        text = f"<|system|>{PLANNER_SYSTEM_PROMPT}<|user|>{user_input}<|assistant|>"

    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    start = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    latency = (time.time() - start) * 1000

    # 입력 부분 제외하고 생성된 부분만 추출
    generated = outputs[0][inputs["input_ids"].shape[1]:]
    response = tokenizer.decode(generated, skip_special_tokens=True)

    return response.strip(), latency


def generate_with_vllm(base_url: str, model_id: str,
                       user_input: str) -> tuple[str, float]:
    """vLLM OpenAI-compatible API로 추론"""
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key="EMPTY")

    start = time.time()
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
        temperature=0.1,
        max_tokens=512,
    )
    latency = (time.time() - start) * 1000

    return response.choices[0].message.content.strip(), latency


# ── 메인 비교 실행 ─────────────────────────────────────────

def run_comparison(args):
    """전체 비교 실행"""
    # 테스트 케이스 로드
    test_file = Path(__file__).parent.parent.parent.parent / "data" / "evaluation" / "planner_test_cases.json"
    if not test_file.exists():
        print(f"ERROR: {test_file} not found")
        sys.exit(1)

    with open(test_file) as f:
        test_data = json.load(f)

    test_cases = test_data["test_cases"]
    print(f"\nLoaded {len(test_cases)} test cases")

    # 결과 저장
    all_results: dict[str, list[EvalResult]] = {}

    for model_key in args.models:
        if model_key not in MODEL_REGISTRY:
            print(f"WARNING: Unknown model '{model_key}', skipping")
            continue

        model_info = MODEL_REGISTRY[model_key]
        model_name = model_info["short_name"]
        results = []

        if args.mode == "transformers":
            model, tokenizer = load_model_transformers(model_info)

            for tc in test_cases:
                print(f"\n[{model_name}] {tc['id']}: {tc['input'][:50]}...")
                raw_output, latency = generate_with_transformers(
                    model, tokenizer, tc["input"])
                print(f"  Output: {raw_output[:100]}...")
                print(f"  Latency: {latency:.0f}ms")

                result = evaluate_output(tc, model_name, raw_output, latency)
                results.append(result)
                print(f"  Score: {result.score:.2f} | "
                      f"JSON={result.json_valid} "
                      f"Steps={result.num_steps_match} "
                      f"Intents={result.intents_match} "
                      f"Deps={result.dependencies_match}")
                if result.errors:
                    print(f"  Errors: {result.errors}")

            # 메모리 해제
            del model, tokenizer
            import torch
            torch.cuda.empty_cache()
            import gc
            gc.collect()

        elif args.mode == "vllm":
            for tc in test_cases:
                print(f"\n[{model_name}] {tc['id']}: {tc['input'][:50]}...")
                raw_output, latency = generate_with_vllm(
                    args.vllm_url, model_info["model_id"], tc["input"])
                print(f"  Output: {raw_output[:100]}...")
                print(f"  Latency: {latency:.0f}ms")

                result = evaluate_output(tc, model_name, raw_output, latency)
                results.append(result)

        all_results[model_name] = results

    # ── 결과 리포트 ──────────────────────────────────────

    print("\n" + "=" * 80)
    print("PLANNER BASE MODEL COMPARISON REPORT")
    print("=" * 80)

    # 모델별 요약
    for model_name, results in all_results.items():
        print(f"\n{'─' * 40}")
        print(f"Model: {model_name}")
        print(f"{'─' * 40}")

        total = len(results)
        json_ok = sum(1 for r in results if r.json_valid)
        plan_ok = sum(1 for r in results if r.plan_extracted)
        steps_ok = sum(1 for r in results if r.num_steps_match)
        intents_ok = sum(1 for r in results if r.intents_match)
        deps_ok = sum(1 for r in results if r.dependencies_match)
        avg_score = sum(r.score for r in results) / total if total else 0
        avg_latency = sum(r.latency_ms for r in results) / total if total else 0

        print(f"  JSON Valid:        {json_ok}/{total} ({json_ok/total*100:.0f}%)")
        print(f"  Plan Extracted:    {plan_ok}/{total} ({plan_ok/total*100:.0f}%)")
        print(f"  Steps Match:       {steps_ok}/{total} ({steps_ok/total*100:.0f}%)")
        print(f"  Intents Match:     {intents_ok}/{total} ({intents_ok/total*100:.0f}%)")
        print(f"  Deps Match:        {deps_ok}/{total} ({deps_ok/total*100:.0f}%)")
        print(f"  Avg Score:         {avg_score:.3f}")
        print(f"  Avg Latency:       {avg_latency:.0f}ms")

        # 카테고리별 점수
        categories = set(r.category for r in results)
        for cat in sorted(categories):
            cat_results = [r for r in results if r.category == cat]
            cat_avg = sum(r.score for r in cat_results) / len(cat_results)
            print(f"    [{cat}] avg={cat_avg:.3f} "
                  f"({sum(1 for r in cat_results if r.score == 1.0)}"
                  f"/{len(cat_results)} perfect)")

    # 모델 간 비교 표
    if len(all_results) > 1:
        print(f"\n{'─' * 40}")
        print("MODEL COMPARISON SUMMARY")
        print(f"{'─' * 40}")
        print(f"{'Metric':<20}", end="")
        for name in all_results:
            print(f"{name:>15}", end="")
        print()
        print("─" * (20 + 15 * len(all_results)))

        metrics = [
            ("JSON Valid %", lambda rs: sum(r.json_valid for r in rs) / len(rs) * 100),
            ("Steps Match %", lambda rs: sum(r.num_steps_match for r in rs) / len(rs) * 100),
            ("Intents Match %", lambda rs: sum(r.intents_match for r in rs) / len(rs) * 100),
            ("Deps Match %", lambda rs: sum(r.dependencies_match for r in rs) / len(rs) * 100),
            ("Avg Score", lambda rs: sum(r.score for r in rs) / len(rs)),
            ("Avg Latency(ms)", lambda rs: sum(r.latency_ms for r in rs) / len(rs)),
        ]

        for metric_name, metric_fn in metrics:
            print(f"{metric_name:<20}", end="")
            for name, rs in all_results.items():
                val = metric_fn(rs)
                if "%" in metric_name:
                    print(f"{val:>14.1f}%", end="")
                elif "Latency" in metric_name:
                    print(f"{val:>14.0f}", end="")
                else:
                    print(f"{val:>15.3f}", end="")
            print()

    # JSON 저장
    output_dir = Path(__file__).parent.parent.parent.parent / "outputs" / "planner_comparison"
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "models": list(all_results.keys()),
        "num_test_cases": len(test_cases),
        "results": {
            model: [
                {
                    "test_id": r.test_id,
                    "category": r.category,
                    "input": r.input_text,
                    "raw_output": r.raw_output,
                    "json_valid": r.json_valid,
                    "plan_extracted": r.plan_extracted,
                    "num_steps_match": r.num_steps_match,
                    "intents_match": r.intents_match,
                    "dependencies_match": r.dependencies_match,
                    "score": r.score,
                    "latency_ms": r.latency_ms,
                    "errors": r.errors,
                }
                for r in results
            ]
            for model, results in all_results.items()
        },
        "summary": {
            model: {
                "avg_score": sum(r.score for r in rs) / len(rs),
                "json_valid_rate": sum(r.json_valid for r in rs) / len(rs),
                "intents_match_rate": sum(r.intents_match for r in rs) / len(rs),
                "deps_match_rate": sum(r.dependencies_match for r in rs) / len(rs),
                "avg_latency_ms": sum(r.latency_ms for r in rs) / len(rs),
            }
            for model, rs in all_results.items()
        },
    }

    report_path = output_dir / "comparison_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\nReport saved: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Planner 베이스 모델 비교")
    parser.add_argument(
        "--models", nargs="+", default=["qwen", "kanana"],
        choices=list(MODEL_REGISTRY.keys()),
        help="비교할 모델 (default: qwen kanana)")
    parser.add_argument(
        "--mode", default="transformers",
        choices=["transformers", "vllm"],
        help="추론 방식 (default: transformers)")
    parser.add_argument(
        "--vllm-url", default="http://localhost:8000/v1",
        help="vLLM 서버 URL (mode=vllm일 때)")
    args = parser.parse_args()

    run_comparison(args)


if __name__ == "__main__":
    main()
