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

# ── 후처리 규칙 (rule guide) ──

def apply_post_rules(user_input: str, intents: list) -> list:
    """모델 출력에 후처리 규칙 적용 — 학습으로 해결 안 되는 패턴 보정"""

    # 규칙 1: 존재하지 않는 intent → doc_generate로 교체
    intents = [i if i in VALID_INTENTS else "doc_generate" for i in intents]

    # 규칙 0 (judgment KNOWN_OVERRIDES): Planner가 judgment를 doc_retrieve로 출력하는 패턴 보정
    #
    # 핵심 구분:
    #   - 단일 step: "규정 알려줘" → doc_retrieve를 judgment로 교체 ✅
    #   - 멀티 step: "규정 찾아서 확인하고 만들어줘" → 첫 step은 doc_retrieve 유지 ❌
    #     (찾아서/검색해서 같은 검색 동사가 있으면 첫 step은 문서 검색이 맞음)
    #
    _JUDGMENT_PATTERNS = [
        r"(규정|규칙|지침|내규).*(알려|설명|안내|어떻게)",
        r"(기준|평가|심사|절차).*(알려|설명|안내|어떻게)",
        r"(복리후생|복지|수당|혜택|지원금|포상).*(뭐|어떤|있어|있나|있습니까)",
        r"(퇴직금|급여|연봉|월급|수당|상여).*(계산|산정|산출|얼마)",
        r"(지각|결근|조퇴|무단|위반|어기).*(어떻게|불이익|처벌|징계|벌|감봉)",
        r"(인센티브|성과급|보너스).*(기준|조건|자격)",
        r"(연차|재택|출장|야근|경조사|퇴직).*(규정|기준|정산).*(어떻게|되|돼|뭐|좀)",
        r"(규정|기준).*(차이|비교|다른)",
        r"(몇\s*시|적용|해당|가능).*(돼|되|인지|한지)",
    ]
    _HAS_SEARCH_VERB = re.search(r"(찾아서|검색해서|조회해서|찾아보고|찾아줘.+확인|찾고)", user_input)

    if len(intents) == 1 and intents[0] == "doc_retrieve":
        # 단일 step: 규정 패턴이면 judgment로 교체
        for pat in _JUDGMENT_PATTERNS:
            if re.search(pat, user_input):
                intents[0] = "judgment"
                break
    elif len(intents) >= 2 and intents[0] == "doc_retrieve" and not _HAS_SEARCH_VERB:
        # 멀티 step: 검색 동사가 없을 때만 첫 step을 judgment로 교체
        # "연차 규정도 알려줘" (검색 동사 없음) → judgment ✅
        # "규정 찾아서 확인하고" (검색 동사 있음) → doc_retrieve 유지 ✅
        for pat in _JUDGMENT_PATTERNS:
            if re.search(pat, user_input):
                intents[0] = "judgment"
                break

    # 규칙 0b: 멀티 step에서 doc_retrieve 2개 연속인데, 두 번째가 judgment 패턴이면 교체
    # "규정 찾아서 (doc_retrieve) 확인하고 (doc_retrieve→judgment)" 보정
    if len(intents) >= 2:
        for idx in range(1, len(intents)):
            if intents[idx] == "doc_retrieve" and \
               re.search(r"(확인하고|판단하고|가능한지|되는지|봐줘|봐서|해도\s*돼)", user_input):
                # 앞에 doc_retrieve가 이미 있으면, 이 step은 judgment일 가능성 높음
                if any(intents[j] == "doc_retrieve" for j in range(idx)):
                    intents[idx] = "judgment"
                    break

    # 규칙 2: 입력이 3글자 이하 → general 강제
    if len(user_input.strip()) <= 3:
        return ["general"]

    # 규칙 3: 영어 "minutes/report" + 만들어/작성 → doc_generate
    if re.search(r"(?i)(minutes|report)", user_input) and \
       re.search(r"(만들|작성|써|뽑아)", user_input):
        return ["doc_generate"]

    # 규칙 4: "도와줘/도움" 단독 → general (모호한 요청)
    if re.search(r"(도와줘|도움|도와주|헬프)", user_input) and \
       not re.search(r"(찾아|검색|작성|만들|등록|확인|알려|잡아)", user_input):
        return ["general"]

    # 규칙 5: Step Collapse 방지 — 접속사 3개 이상이면 최소 3-step
    connectors = len(re.findall(r"(찾아서|검색해서|확인하고|보고|바탕으로|그 다음|그리고|한 다음|후에|만들고|정리하고|요약하고)", user_input))
    if connectors >= 2 and len(intents) < 3:
        pass  # 모델 출력 유지 — 무리하게 step 늘리면 오히려 악화

    # 규칙 10: "A 찾아서 B 확인하고 C 만들어줘" 패턴 — doc_retrieve→judgment 축소 방지
    # 문서를 찾고 + 판단/확인 + 생성/등록이 모두 포함된 입력인데 2-step이면 doc_retrieve 복원
    if re.search(r"(찾아서|검색해서|조회해서)", user_input) and \
       re.search(r"(확인하고|판단하고|보고|검토하고)", user_input) and \
       re.search(r"(만들어|작성해|잡아|등록|넣어)", user_input) and \
       len(intents) == 2:
        # 2-step → 3-step 복원: 첫 step 앞에 doc_retrieve 삽입
        if intents[0] != "doc_retrieve":
            intents.insert(0, "doc_retrieve")

    # 규칙 11: "A도 찾아서 B도 찾아서" — 검색 동사 2회 이상 + 생성 → 최소 3-step
    search_verbs = len(re.findall(r"(찾아|검색|조회|찾고|검색하고)", user_input))
    if search_verbs >= 2 and \
       re.search(r"(만들어|작성해|뽑아|써\s*줘)", user_input) and \
       len(intents) < 3:
        # doc_retrieve가 1개면 하나 더 추가
        if intents.count("doc_retrieve") < 2:
            intents.insert(0, "doc_retrieve")

    # 규칙 6: "취소" → schedule_add (schedule_view 아님)
    if re.search(r"취소", user_input) and intents and intents[0] == "schedule_view":
        intents[0] = "schedule_add"

    # 규칙 8: "변경/수정" + 일정 관련 → schedule_add 단일 (과잉 분리 방지)
    if re.search(r"(변경|수정)", user_input) and \
       re.search(r"(회의|미팅|일정|스케줄)", user_input) and \
       len(intents) >= 2 and "schedule_add" in intents:
        return ["schedule_add"]

    # 규칙 9: "만들어줘/작성해줘/써줘"로 끝나는데 마지막 step이 doc_generate가 아니면 교체
    if re.search(r"(만들어|작성해|써\s*줘|뽑아)\s*줘?\s*$", user_input) and \
       len(intents) >= 2 and intents[-1] != "doc_generate":
        intents[-1] = "doc_generate"

    return intents


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

## 절대 규칙 (System Constraints)
{intent_constraints}

## 작성 규칙 (Rule)
1. depends_on: 이 단계가 실행되기 전에 완료되어야 하는 step_id 목록. 비어있으면 즉시 실행 가능(병렬).
2. [금지 1 - 과도한 압축 금지]: 문서를 찾고(doc_retrieve) 그 내용을 바탕으로 판단(judgment)을 요구하는 경우, 절대 judgment 하나로 압축하지 마세요. 두 단계가 모두 필요합니다.
3. [금지 2 - Intent 혼동 방지]: 규정이나 문서를 단순히 찾아달라는 요청은 doc_retrieve입니다. judgment는 명확히 가부(가능 여부) 판단을 물을 때만 사용하세요.
4. [금지 3 - 과잉 분리 금지]: 동일한 대상(예: 하나의 규정)에 대해 판단할 때 judgment를 여러 번 분리하지 말고 한 번의 step으로 처리하세요.
5. 단순 요청은 1단계로 처리하고, 최대 4단계까지만 분해하세요.
6. JSON만 출력하고 다른 설명은 하지 마세요."""

# Few-shot 프롬프트 (실험 B용)
PLANNER_SYSTEM_PROMPT_FEWSHOT = """당신은 업무 자동화 시스템의 Task Planner입니다.
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

## 3-step 예시 (중요! 이런 패턴은 절대 2-step으로 줄이지 마세요)

예시 1: "출장 규정 문서 찾아서 해외출장 가능한지 확인하고 출장 보고서 만들어줘"
→ {"plan": [
    {"step_id": 1, "intent": "doc_retrieve", "query": "출장 규정 문서 검색", "depends_on": []},
    {"step_id": 2, "intent": "judgment", "query": "해외출장 가능 여부 판단", "depends_on": [1]},
    {"step_id": 3, "intent": "doc_generate", "query": "출장 보고서 작성", "depends_on": [2]}
  ]}

예시 2: "연차 규정 확인하고 팀 일정 보고 비는 날에 휴가 등록해줘"
→ {"plan": [
    {"step_id": 1, "intent": "judgment", "query": "연차 규정 확인", "depends_on": []},
    {"step_id": 2, "intent": "schedule_view", "query": "팀 일정 조회", "depends_on": []},
    {"step_id": 3, "intent": "schedule_add", "query": "비는 날에 휴가 등록", "depends_on": [1, 2]}
  ]}

예시 3: "마케팅 보고서 찾고 경쟁사 자료도 검색해서 비교 제안서 만들어줘"
→ {"plan": [
    {"step_id": 1, "intent": "doc_retrieve", "query": "마케팅 보고서 검색", "depends_on": []},
    {"step_id": 2, "intent": "doc_retrieve", "query": "경쟁사 자료 검색", "depends_on": []},
    {"step_id": 3, "intent": "doc_generate", "query": "비교 제안서 작성", "depends_on": [1, 2]}
  ]}

## 절대 규칙 (System Constraints)
{intent_constraints}

## 작성 규칙 (Rule)
1. depends_on: 이 단계가 실행되기 전에 완료되어야 하는 step_id 목록. 비어있으면 즉시 실행 가능(병렬).
2. [금지 1 - 과도한 압축 금지]: "A 찾아서 B 확인하고 C 만들어줘"는 반드시 3단계입니다. 절대로 2단계로 압축하지 마세요.
3. [금지 2 - Intent 혼동 방지]: 규정이나 문서를 단순히 찾아달라는 요청은 doc_retrieve입니다. judgment는 명확히 가부(가능 여부) 판단을 물을 때만 사용하세요.
4. [금지 3 - 과잉 분리 금지]: 동일한 대상(예: 하나의 규정)에 대해 판단할 때 judgment를 여러 번 분리하지 말고 한 번의 step으로 처리하세요.
5. 단순 요청은 1단계로 처리하고, 최대 4단계까지만 분해하세요.
6. JSON만 출력하고 다른 설명은 하지 마세요."""


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
    result["expected_steps"] = expected.get("num_steps", len(expected_intents))

    # JSON 파싱
    parsed = extract_json(pred_text)
    if parsed is None:
        result["error"] = "JSON 파싱 실패"
        result["actual_intents"] = []
        result["actual_steps"] = 0
        return result
    result["json_valid"] = True

    if "plan" not in parsed or not isinstance(parsed["plan"], list):
        result["error"] = "plan 필드 없음"
        result["actual_intents"] = []
        result["actual_steps"] = 0
        return result

    plan = parsed["plan"]
    result["plan_nonempty"] = len(plan) > 0

    if not result["plan_nonempty"]:
        result["error"] = "빈 plan"
        result["actual_intents"] = []
        result["actual_steps"] = 0
        return result

    result["usable"] = True
    actual_intents = [s.get("intent", "") for s in plan]

    # ── 후처리 규칙 (rule guide) ──
    actual_intents = apply_post_rules(test_case["input"], actual_intents)
    # plan 객체도 업데이트 (dep_correctness 평가용)
    for i, s in enumerate(plan):
        if i < len(actual_intents):
            s["intent"] = actual_intents[i]

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
    result["expected_steps"] = expected["num_steps"]
    result["actual_steps"] = len(plan)

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


def generate(model, tokenizer, user_input: str,
             use_fewshot: bool = False) -> tuple[str, float]:
    """추론 실행"""
    sys_prompt = PLANNER_SYSTEM_PROMPT_FEWSHOT if use_fewshot else PLANNER_SYSTEM_PROMPT
    messages = [
        {"role": "system", "content": sys_prompt},
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
    parser.add_argument("--fewshot", action="store_true",
                        help="Few-shot 프롬프트 사용 (3-step 예시 포함)")
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

    use_fewshot = getattr(args, 'fewshot', False)
    prompt_mode = "fewshot" if use_fewshot else "default"

    print(f"\n모델 로드 중...")
    tokenizer, model, mode = load_model(adapter_path)

    # 평가
    print(f"\n{'='*65}")
    print(f"  HELD-OUT 평가 시작 ({mode.upper()} model, prompt={prompt_mode}, {len(test_cases)}건)")
    print(f"{'='*65}\n")

    results = []
    for i, tc in enumerate(test_cases, 1):
        pred_text, latency = generate(model, tokenizer, tc["input"],
                                       use_fewshot=use_fewshot)
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

    if failed_results:
        print(f"  응답 실패:      {len(failed_results)}건")
        json_fail = sum(1 for r in failed_results if not r["json_valid"])
        empty_plan = sum(1 for r in failed_results
                         if r["json_valid"] and not r["plan_nonempty"])
        if json_fail > 0:
            print(f"    JSON 파싱 실패: {json_fail}건")
        if empty_plan > 0:
            print(f"    빈 plan 출력:   {empty_plan}건")
        fail_cats = {}
        for r in failed_results:
            fail_cats[r["category"]] = fail_cats.get(r["category"], 0) + 1
        for cat, cnt in sorted(fail_cats.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {cnt}건")

    # 평가 대상: usable 응답만 (JSON 파싱 성공 + plan 비어있지 않음)
    eval_count = usable
    if eval_count == 0:
        print(f"\n  평가 가능한 응답 없음")
    else:
        avg = lambda key: sum(r["metrics"][key] for r in usable_results) / eval_count

        print(f"\n  [Planning 능력] — {eval_count}건 평가")
        print(f"    Intent Recall:     {avg('intent_recall'):.3f}")
        print(f"    Order Accuracy:    {avg('order_accuracy'):.3f}")
        print(f"    Intent Precision:  {avg('intent_precision'):.3f}")
        print(f"    Dep Correctness:   {avg('dep_correctness'):.3f}")
        print(f"    Efficiency:        {avg('efficiency'):.3f}")
        print(f"    ─────────────────────")
        print(f"    Weighted Score:    {avg('score'):.3f}")

        perfect = sum(1 for r in usable_results if r["perfect"])
        print(f"\n    Perfect Match:     {perfect}/{total} ({perfect/total*100:.1f}%)")
        avg_lat = sum(r["latency_ms"] for r in usable_results) / eval_count
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

        # ── Step Collapse Rate (단계 축소율) ──
        multi_step_results = [r for r in usable_results if r["expected_steps"] >= 2]
        if multi_step_results:
            collapsed = sum(1 for r in multi_step_results
                            if r["actual_steps"] < r["expected_steps"])
            collapse_rate = collapsed / len(multi_step_results)
            over_split = sum(1 for r in usable_results
                             if r["actual_steps"] > r["expected_steps"])
            print(f"\n  [Step Collapse]")
            print(f"    Multi-step 케이스:  {len(multi_step_results)}건 "
                  f"(2+ step expected)")
            print(f"    단계 축소 발생:    {collapsed}건 "
                  f"({collapse_rate*100:.1f}%)")
            if over_split > 0:
                print(f"    과잉 분리 발생:    {over_split}건")

        # ── Exact Match by Step Count (단계 수별 정확도) ──
        step_counts = sorted(set(r["expected_steps"] for r in results))
        print(f"\n  [단계 수별 Perfect Match]")
        print(f"    {'Steps':>5}  {'Perfect':>8}  {'Total':>5}  {'Rate':>7}")
        print(f"    {'─'*35}")
        for sc in step_counts:
            sc_all = [r for r in results if r.get("expected_steps") == sc]
            sc_perfect = sum(1 for r in sc_all
                             if r.get("usable") and r.get("perfect"))
            sc_total = len(sc_all)
            rate = sc_perfect / sc_total * 100 if sc_total > 0 else 0
            bar = "█" * int(rate / 5) + "░" * (20 - int(rate / 5))
            print(f"    {sc:>5}  {sc_perfect:>5}/{sc_total:<3} {rate:>6.1f}%  {bar}")

        # ── Intent Confusion Matrix (혼동 행렬) ──
        intent_list = sorted(VALID_INTENTS)
        # expected의 각 intent에 대해 actual에서 매칭되는 intent 집계
        confusion = {exp: Counter() for exp in intent_list}
        for r in usable_results:
            exp_intents = r["expected_intents"]
            act_intents = r["actual_intents"]
            # step 단위로 positional matching
            for idx, exp_i in enumerate(exp_intents):
                if idx < len(act_intents):
                    confusion[exp_i][act_intents[idx]] += 1
                else:
                    confusion[exp_i]["(누락)"] += 1
            # actual이 더 긴 경우 (과잉 분리)
            for idx in range(len(exp_intents), len(act_intents)):
                act_i = act_intents[idx]
                confusion.setdefault("(과잉)", Counter())[act_i] += 1

        # 혼동이 있는 경우만 출력
        has_confusion = False
        for exp_i in intent_list:
            for act_i, cnt in confusion[exp_i].items():
                if act_i != exp_i and cnt > 0:
                    has_confusion = True
                    break
        has_missing = any(confusion[e].get("(누락)", 0) > 0 for e in intent_list)
        has_oversplit = "(과잉)" in confusion and sum(confusion["(과잉)"].values()) > 0

        if has_confusion or has_missing or has_oversplit:
            print(f"\n  [Intent 혼동 행렬] — 오분류만 표시")
            print(f"    {'expected':<16} → {'predicted':<16} {'건수':>4}")
            print(f"    {'─'*42}")
            for exp_i in intent_list:
                for act_i, cnt in confusion[exp_i].most_common():
                    if act_i != exp_i and cnt > 0:
                        print(f"    {exp_i:<16} → {act_i:<16} {cnt:>4}")
                if confusion[exp_i].get("(누락)", 0) > 0:
                    print(f"    {exp_i:<16} → {'(누락)':<16} "
                          f"{confusion[exp_i]['(누락)']:>4}")
            if has_oversplit:
                for act_i, cnt in confusion["(과잉)"].most_common():
                    print(f"    {'(과잉 추가)':<16} → {act_i:<16} {cnt:>4}")

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

    # Step Collapse / Exact Match by Step Count 집계
    multi_step_all = [r for r in usable_results if r["expected_steps"] >= 2]
    step_collapse_rate = (
        round(sum(1 for r in multi_step_all
                  if r["actual_steps"] < r["expected_steps"]) / len(multi_step_all), 4)
        if multi_step_all else 0
    )
    step_counts_summary = {}
    for sc in sorted(set(r.get("expected_steps", 1) for r in results)):
        sc_all = [r for r in results if r.get("expected_steps") == sc]
        sc_perfect = sum(1 for r in sc_all if r.get("usable") and r.get("perfect"))
        step_counts_summary[str(sc)] = {
            "total": len(sc_all), "perfect": sc_perfect,
            "rate": round(sc_perfect / len(sc_all), 4) if sc_all else 0,
        }

    save_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model_mode": mode,
        "adapter_path": adapter_path,
        "test_cases_path": str(test_path),
        "total": total,
        "metrics": {k: round(avg(k), 4) for k in WEIGHTS} if usable > 0 else None,
        "weighted_score": round(avg("score"), 4) if usable > 0 else None,
        "perfect_rate": round(
            sum(1 for r in usable_results if r["perfect"]) / total, 4
        ) if total > 0 else 0,
        "step_collapse_rate": step_collapse_rate,
        "exact_match_by_steps": step_counts_summary,
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"  결과 저장: {output_path}")


if __name__ == "__main__":
    main()
