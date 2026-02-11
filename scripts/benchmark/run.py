"""
모델 벤치마크 실행 스크립트 (이슈 #7)

Qwen3 / Kanana / EXAONE / Tri-7B 베이스 모델 비교
평가 축: 한국어, 규정해석, 판단형식, 속도

사용법:
  # 개별 모델 벤치마크
  python scripts/benchmark/run.py --model qwen3
  python scripts/benchmark/run.py --model kanana
  python scripts/benchmark/run.py --model exaone
  python scripts/benchmark/run.py --model tri7b

  # 전체 비교 리포트
  python scripts/benchmark/run.py --report

  # 특정 카테고리만 테스트 (빠른 확인용)
  python scripts/benchmark/run.py --model qwen3 --category judgment

  # GPU 지정
  python scripts/benchmark/run.py --model qwen3 --device cuda:0
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
import torch
from tqdm import tqdm

# ============================================================
# 경로 설정
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"

sys.path.insert(0, str(PROJECT_DIR))


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================
# 모델 로딩
# ============================================================
def load_model(model_key: str, config: dict, device: str = "auto"):
    """4-bit 양자화로 모델 로드"""
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    model_cfg = config["models"][model_key]
    model_id = model_cfg["model_id"]
    inf_cfg = config["inference"]

    print(f"\n{'='*60}")
    print(f"모델 로딩: {model_cfg['name']} ({model_id})")
    print(f"양자화: {inf_cfg['quantization']}")
    print(f"{'='*60}")

    # 토크나이저
    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        trust_remote_code=True,
        padding_side="left",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 4-bit 양자화 설정
    if inf_cfg["quantization"] == "4bit":
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
    else:
        bnb_config = None

    # 모델 로드
    load_start = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map=device,
        trust_remote_code=True,
        torch_dtype=torch.float16,
    )
    model.eval()
    load_time = time.time() - load_start
    print(f"모델 로드 완료: {load_time:.1f}초")

    # GPU 메모리 확인
    if torch.cuda.is_available():
        mem = torch.cuda.max_memory_allocated() / 1024**3
        print(f"GPU 메모리 사용: {mem:.1f} GB")

    return model, tokenizer


# ============================================================
# 프롬프트 생성
# ============================================================
def build_prompt(item: dict, tokenizer) -> str:
    """테스트 항목을 모델 입력 프롬프트로 변환"""
    system_msg = (
        "당신은 듀듀테크놀로지의 사내규정 전문 AI 어시스턴트입니다. "
        "질문에 정확하고 구조화된 형식으로 답변하세요."
    )
    user_msg = f"{item['instruction']}\n\n{item['input']}"

    # 카테고리별 출력 형식 힌트
    category = item["category"]
    if category == "judgment":
        user_msg += (
            "\n\n[출력 형식] Yes/No/조건부로 판단하고, "
            "[근거]와 [조건/대안]을 포함하세요."
        )
    elif category in ("meeting_analysis", "doc_summary", "risk_detection"):
        user_msg += "\n\n[출력 형식] JSON으로 응답하세요."
    elif category == "regulation_qa":
        user_msg += "\n\n[출력 형식] 관련 조항을 인용하며 상세히 설명하세요."

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

    # apply_chat_template 시도, 실패 시 수동 포맷
    try:
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    except Exception:
        prompt = (
            f"### System:\n{system_msg}\n\n"
            f"### User:\n{user_msg}\n\n"
            f"### Assistant:\n"
        )

    return prompt


# ============================================================
# 추론 실행
# ============================================================
def run_inference(model, tokenizer, prompt: str, config: dict) -> dict:
    """단일 프롬프트 추론 + 시간 측정"""
    inf_cfg = config["inference"]

    inputs = tokenizer(
        prompt, return_tensors="pt", truncation=True, max_length=4096
    )
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    input_len = inputs["input_ids"].shape[1]

    start_time = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=inf_cfg["max_new_tokens"],
            temperature=inf_cfg["temperature"],
            top_p=inf_cfg["top_p"],
            do_sample=inf_cfg["do_sample"],
            repetition_penalty=inf_cfg["repetition_penalty"],
            pad_token_id=tokenizer.pad_token_id,
        )
    end_time = time.time()

    # 결과 디코딩 (입력 부분 제외)
    generated_ids = outputs[0][input_len:]
    output_text = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
    output_tokens = len(generated_ids)
    elapsed = end_time - start_time

    return {
        "output": output_text,
        "input_tokens": input_len,
        "output_tokens": output_tokens,
        "latency_sec": round(elapsed, 3),
        "tokens_per_sec": (
            round(output_tokens / elapsed, 1) if elapsed > 0 else 0
        ),
    }


# ============================================================
# 평가 함수들
# ============================================================
def evaluate_judgment_accuracy(output: str, reference: str) -> dict:
    """규정 판단 정확도: Yes/No/조건부 매칭"""
    ref_match = re.search(r"(Yes|No|조건부)", reference)
    ref_type = ref_match.group(1) if ref_match else "unknown"

    out_match = re.search(r"(Yes|No|조건부)", output)
    out_type = out_match.group(1) if out_match else "unknown"

    correct = ref_type == out_type

    # 근거 조항 언급 여부
    basis_pattern = r"제\d+조"
    ref_articles = set(re.findall(basis_pattern, reference))
    out_articles = set(re.findall(basis_pattern, output))
    basis_recall = (
        len(ref_articles & out_articles) / len(ref_articles)
        if ref_articles
        else 0.0
    )

    return {
        "judgment_correct": correct,
        "ref_type": ref_type,
        "out_type": out_type,
        "basis_recall": round(basis_recall, 2),
    }


def evaluate_json_validity(output: str) -> dict:
    """JSON 출력 유효성 검사"""
    json_match = re.search(r"\{[\s\S]*\}", output)
    if not json_match:
        return {"json_valid": False, "json_parsed": None, "fields": []}

    try:
        parsed = json.loads(json_match.group())
        fields = list(parsed.keys()) if isinstance(parsed, dict) else []
        return {"json_valid": True, "json_parsed": parsed, "fields": fields}
    except json.JSONDecodeError:
        return {"json_valid": False, "json_parsed": None, "fields": []}


def evaluate_field_completeness(
    output: str, reference: str, category: str
) -> dict:
    """필드 완전성: reference 대비 output 필드 매칭"""
    ref_json = evaluate_json_validity(reference)
    out_json = evaluate_json_validity(output)

    if not ref_json["json_valid"] or not out_json["json_valid"]:
        return {
            "field_completeness": 0.0,
            "missing_fields": [],
            "extra_fields": [],
        }

    ref_fields = set(ref_json["fields"])
    out_fields = set(out_json["fields"])

    if not ref_fields:
        return {
            "field_completeness": 1.0,
            "missing_fields": [],
            "extra_fields": [],
        }

    completeness = len(ref_fields & out_fields) / len(ref_fields)
    missing = list(ref_fields - out_fields)
    extra = list(out_fields - ref_fields)

    return {
        "field_completeness": round(completeness, 2),
        "missing_fields": missing,
        "extra_fields": extra,
    }


def evaluate_rouge_l(output: str, reference: str) -> float:
    """ROUGE-L 점수 계산"""
    try:
        from rouge_score import rouge_scorer

        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)
        score = scorer.score(reference, output)
        return round(score["rougeL"].fmeasure, 4)
    except ImportError:
        # rouge_score 미설치 시 간이 계산 (토큰 겹침 기반)
        ref_tokens = set(reference.split())
        out_tokens = set(output.split())
        if not ref_tokens or not out_tokens:
            return 0.0
        overlap = len(ref_tokens & out_tokens)
        precision = overlap / len(out_tokens)
        recall = overlap / len(ref_tokens)
        if precision + recall == 0:
            return 0.0
        return round(2 * precision * recall / (precision + recall), 4)


def evaluate_item(item: dict, output: str) -> dict:
    """단일 테스트 항목 종합 평가"""
    reference = item["reference_output"]
    if isinstance(reference, dict):
        reference = json.dumps(reference, ensure_ascii=False)

    category = item["category"]
    scores = {}

    # 1) ROUGE-L (전체 공통)
    scores["rouge_l"] = evaluate_rouge_l(output, reference)

    # 2) 카테고리별 평가
    if category == "judgment":
        j_eval = evaluate_judgment_accuracy(output, reference)
        scores.update(j_eval)

    if category in ("meeting_analysis", "doc_summary", "risk_detection"):
        j_valid = evaluate_json_validity(output)
        scores["json_valid"] = j_valid["json_valid"]
        f_comp = evaluate_field_completeness(output, reference, category)
        scores["field_completeness"] = f_comp["field_completeness"]
        scores["missing_fields"] = f_comp["missing_fields"]

    if category == "risk_detection":
        ref_json = evaluate_json_validity(reference)
        out_json = evaluate_json_validity(output)
        if ref_json["json_parsed"] and out_json["json_parsed"]:
            ref_risk = ref_json["json_parsed"].get("risk_detected")
            out_risk = out_json["json_parsed"].get("risk_detected")
            scores["risk_correct"] = ref_risk == out_risk
        else:
            scores["risk_correct"] = False

    if category == "regulation_qa":
        article_pattern = r"제\d+조"
        ref_articles = set(re.findall(article_pattern, reference))
        out_articles = set(re.findall(article_pattern, output))
        scores["article_cited"] = (
            len(ref_articles & out_articles) > 0 if ref_articles else True
        )

    return scores


# ============================================================
# 메인 벤치마크 실행
# ============================================================
def run_benchmark(
    model_key: str,
    config: dict,
    device: str,
    category_filter: str = None,
):
    """단일 모델 벤치마크 실행"""
    paths = config["paths"]
    testset_path = PROJECT_DIR / paths["testset"]
    results_dir = PROJECT_DIR / paths["results_dir"]
    results_dir.mkdir(parents=True, exist_ok=True)

    # 테스트셋 로드
    testset = []
    with open(testset_path, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line.strip())
            if category_filter and item["category"] != category_filter:
                continue
            testset.append(item)

    print(f"\n테스트 항목: {len(testset)}개")
    if category_filter:
        print(f"필터: {category_filter}")

    # 모델 로드
    model, tokenizer = load_model(model_key, config, device)
    model_name = config["models"][model_key]["name"]

    # 추론 + 평가
    results = []
    total_start = time.time()

    for item in tqdm(testset, desc=f"[{model_name}] 벤치마크"):
        prompt = build_prompt(item, tokenizer)
        inf_result = run_inference(model, tokenizer, prompt, config)
        eval_scores = evaluate_item(item, inf_result["output"])

        results.append(
            {
                "test_id": item["test_id"],
                "category": item["category"],
                "subcategory": item["subcategory"],
                "input_preview": item["input"][:100],
                "output": inf_result["output"],
                "reference_preview": str(item["reference_output"])[:200],
                "input_tokens": inf_result["input_tokens"],
                "output_tokens": inf_result["output_tokens"],
                "latency_sec": inf_result["latency_sec"],
                "tokens_per_sec": inf_result["tokens_per_sec"],
                "scores": eval_scores,
            }
        )

    total_time = time.time() - total_start

    # 결과 저장
    result_data = {
        "model_key": model_key,
        "model_name": model_name,
        "model_id": config["models"][model_key]["model_id"],
        "params": config["models"][model_key]["params"],
        "timestamp": datetime.now().isoformat(),
        "total_items": len(results),
        "total_time_sec": round(total_time, 1),
        "device": str(device),
        "results": results,
    }

    output_file = results_dir / f"{model_key}_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {output_file}")
    print_summary(result_data)

    # GPU 메모리 해제
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return result_data


# ============================================================
# 요약 출력
# ============================================================
def print_summary(result_data: dict):
    """단일 모델 결과 요약 출력"""
    results = result_data["results"]
    model_name = result_data["model_name"]

    print(f"\n{'='*60}")
    print(f"[{model_name}] 벤치마크 요약")
    print(f"{'='*60}")

    categories = {}
    for r in results:
        categories.setdefault(r["category"], []).append(r)

    for cat, items in sorted(categories.items()):
        print(f"\n--- {cat} ({len(items)}개) ---")

        avg_latency = sum(r["latency_sec"] for r in items) / len(items)
        avg_tps = sum(r["tokens_per_sec"] for r in items) / len(items)
        print(f"  속도: {avg_latency:.2f}s/item, {avg_tps:.0f} tok/s")

        rouge_scores = [r["scores"].get("rouge_l", 0) for r in items]
        avg_rouge = sum(rouge_scores) / len(rouge_scores)
        print(f"  ROUGE-L: {avg_rouge:.4f}")

        if cat == "judgment":
            correct = sum(
                1 for r in items if r["scores"].get("judgment_correct")
            )
            pct = correct / len(items) * 100
            print(f"  판단 정확도: {correct}/{len(items)} ({pct:.0f}%)")
            basis_avg = sum(
                r["scores"].get("basis_recall", 0) for r in items
            ) / len(items)
            print(f"  근거 재현율: {basis_avg:.2f}")

        if cat in ("meeting_analysis", "doc_summary", "risk_detection"):
            valid = sum(
                1 for r in items if r["scores"].get("json_valid")
            )
            pct = valid / len(items) * 100
            print(f"  JSON 유효율: {valid}/{len(items)} ({pct:.0f}%)")
            fc_avg = sum(
                r["scores"].get("field_completeness", 0) for r in items
            ) / len(items)
            print(f"  필드 완전성: {fc_avg:.2f}")

        if cat == "risk_detection":
            correct = sum(
                1 for r in items if r["scores"].get("risk_correct")
            )
            print(f"  리스크 감지 정확도: {correct}/{len(items)}")

        if cat == "regulation_qa":
            cited = sum(
                1 for r in items if r["scores"].get("article_cited")
            )
            pct = cited / len(items) * 100
            print(f"  조항 인용율: {cited}/{len(items)} ({pct:.0f}%)")

    # 전체
    all_latency = sum(r["latency_sec"] for r in results) / len(results)
    all_tps = sum(r["tokens_per_sec"] for r in results) / len(results)
    all_rouge = sum(
        r["scores"].get("rouge_l", 0) for r in results
    ) / len(results)
    print(f"\n{'='*60}")
    print(
        f"전체 평균: ROUGE-L={all_rouge:.4f}, "
        f"{all_latency:.2f}s/item, {all_tps:.0f} tok/s"
    )
    print(f"총 소요시간: {result_data['total_time_sec']:.0f}초")


# ============================================================
# 비교 리포트 생성
# ============================================================
def generate_report(config: dict):
    """모든 모델 결과를 비교하는 마크다운 리포트 생성"""
    results_dir = PROJECT_DIR / config["paths"]["results_dir"]
    report_path = PROJECT_DIR / config["paths"]["report"]

    # 결과 파일 로드
    model_results = {}
    for f in sorted(results_dir.glob("*_results.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        model_results[data["model_key"]] = data

    if not model_results:
        print("결과 파일이 없습니다. 먼저 벤치마크를 실행하세요.")
        print("  python scripts/benchmark/run.py --model qwen3")
        return

    print(
        f"\n비교 대상: "
        f"{', '.join(r['model_name'] for r in model_results.values())}"
    )

    # ---- 모델별 점수 집계 ----
    def calc_model_scores(data):
        results = data["results"]

        cats = {}
        for r in results:
            cats.setdefault(r["category"], []).append(r)

        scores = {}
        for cat, items in cats.items():
            s = {
                "count": len(items),
                "avg_rouge_l": sum(
                    r["scores"].get("rouge_l", 0) for r in items
                ) / len(items),
                "avg_latency": sum(r["latency_sec"] for r in items)
                / len(items),
                "avg_tps": sum(r["tokens_per_sec"] for r in items)
                / len(items),
            }

            if cat == "judgment":
                correct = sum(
                    1
                    for r in items
                    if r["scores"].get("judgment_correct")
                )
                s["judgment_accuracy"] = correct / len(items)
                s["basis_recall"] = sum(
                    r["scores"].get("basis_recall", 0) for r in items
                ) / len(items)

            if cat in ("meeting_analysis", "doc_summary", "risk_detection"):
                valid = sum(
                    1 for r in items if r["scores"].get("json_valid")
                )
                s["json_validity"] = valid / len(items)
                s["field_completeness"] = sum(
                    r["scores"].get("field_completeness", 0) for r in items
                ) / len(items)

            if cat == "risk_detection":
                correct = sum(
                    1 for r in items if r["scores"].get("risk_correct")
                )
                s["risk_accuracy"] = correct / len(items)

            if cat == "regulation_qa":
                cited = sum(
                    1 for r in items if r["scores"].get("article_cited")
                )
                s["article_citation"] = cited / len(items)

            scores[cat] = s

        scores["_overall"] = {
            "avg_rouge_l": sum(
                r["scores"].get("rouge_l", 0) for r in results
            ) / len(results),
            "avg_latency": sum(r["latency_sec"] for r in results)
            / len(results),
            "avg_tps": sum(r["tokens_per_sec"] for r in results)
            / len(results),
            "total_time": data["total_time_sec"],
        }

        return scores

    all_scores = {k: calc_model_scores(d) for k, d in model_results.items()}

    # ---- 4축 점수 ----
    def calc_axis(scores):
        axis = {}
        # 한국어
        axis["korean"] = scores["_overall"]["avg_rouge_l"]

        # 규정해석
        reg = []
        if "judgment" in scores:
            reg.append(scores["judgment"].get("judgment_accuracy", 0))
        if "regulation_qa" in scores:
            reg.append(scores["regulation_qa"].get("article_citation", 0))
        if "risk_detection" in scores:
            reg.append(scores["risk_detection"].get("risk_accuracy", 0))
        axis["regulation"] = sum(reg) / len(reg) if reg else 0

        # 판단형식
        fmt = []
        for c in ("meeting_analysis", "doc_summary", "risk_detection"):
            if c in scores:
                fmt.append(scores[c].get("json_validity", 0))
                fmt.append(scores[c].get("field_completeness", 0))
        if "judgment" in scores:
            fmt.append(scores["judgment"].get("judgment_accuracy", 0))
        axis["format"] = sum(fmt) / len(fmt) if fmt else 0

        # 속도 (raw)
        axis["speed_raw"] = scores["_overall"]["avg_tps"]
        return axis

    axis_scores = {k: calc_axis(s) for k, s in all_scores.items()}

    # 속도 정규화
    max_spd = max(a["speed_raw"] for a in axis_scores.values()) or 1
    for a in axis_scores.values():
        a["speed"] = a["speed_raw"] / max_spd

    # 종합 점수
    w = config["eval_axes"]
    for a in axis_scores.values():
        a["total"] = (
            a["korean"] * w["korean"]["weight"]
            + a["regulation"] * w["regulation"]["weight"]
            + a["format"] * w["format"]["weight"]
            + a["speed"] * w["speed"]["weight"]
        )

    # ---- 마크다운 생성 ----
    L = []  # lines
    L.append("# 모델 벤치마크 비교 리포트")
    L.append(f"\n> 생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    L.append("> 테스트셋: benchmark_testset.jsonl (87개)")
    L.append("")

    # 종합 순위
    L.append("## 종합 순위")
    L.append("")
    ranked = sorted(axis_scores.items(), key=lambda x: -x[1]["total"])

    L.append(
        "| 순위 | 모델 | 한국어 | 규정해석 | 판단형식 | 속도 | **종합** |"
    )
    L.append("|:----:|------|:------:|:-------:|:-------:|:----:|:-------:|")
    medals = ["1", "2", "3", "4"]
    for i, (key, a) in enumerate(ranked):
        name = model_results[key]["model_name"]
        L.append(
            f"| {medals[i]} | **{name}** "
            f"| {a['korean']:.3f} | {a['regulation']:.3f} "
            f"| {a['format']:.3f} | {a['speed']:.3f} "
            f"| **{a['total']:.3f}** |"
        )

    L.append("")
    L.append(
        f"_가중치: 한국어 {w['korean']['weight']}, "
        f"규정해석 {w['regulation']['weight']}, "
        f"판단형식 {w['format']['weight']}, "
        f"속도 {w['speed']['weight']}_"
    )

    # 카테고리별 상세
    L.append("\n---\n")
    L.append("## 카테고리별 상세")

    cat_order = [
        "judgment",
        "regulation_qa",
        "meeting_analysis",
        "doc_summary",
        "risk_detection",
        "korean_understanding",
    ]
    cat_names = {
        "judgment": "규정 판단",
        "regulation_qa": "규정 해석 Q&A",
        "meeting_analysis": "회의록 분석",
        "doc_summary": "문서 요약",
        "risk_detection": "리스크 감지",
        "korean_understanding": "한국어 이해력",
    }

    for cat in cat_order:
        label = cat_names.get(cat, cat)
        L.append(f"\n### {label}")
        L.append("")

        has = [k for k in model_results if cat in all_scores.get(k, {})]
        if not has:
            L.append("_데이터 없음_")
            continue

        hdr = "| 지표 |"
        sep = "|------|"
        for k in has:
            hdr += f" {model_results[k]['model_name']} |"
            sep += ":------:|"
        L.append(hdr)
        L.append(sep)

        metrics = [
            ("ROUGE-L", "avg_rouge_l"),
            ("평균 지연(초)", "avg_latency"),
            ("tok/s", "avg_tps"),
        ]
        if cat == "judgment":
            metrics += [
                ("판단 정확도", "judgment_accuracy"),
                ("근거 재현율", "basis_recall"),
            ]
        if cat in ("meeting_analysis", "doc_summary", "risk_detection"):
            metrics += [
                ("JSON 유효율", "json_validity"),
                ("필드 완전성", "field_completeness"),
            ]
        if cat == "risk_detection":
            metrics += [("리스크 감지 정확도", "risk_accuracy")]
        if cat == "regulation_qa":
            metrics += [("조항 인용율", "article_citation")]

        for m_label, m_key in metrics:
            row = f"| {m_label} |"
            for k in has:
                val = all_scores[k].get(cat, {}).get(m_key, "-")
                if isinstance(val, float):
                    row += f" {val:.3f} |"
                else:
                    row += f" {val} |"
            L.append(row)

    # 속도 비교
    L.append("\n---\n")
    L.append("## 속도 비교")
    L.append("")
    L.append(
        "| 모델 | 파라미터 | 평균 지연(초) | tok/s | 총 소요시간 |"
    )
    L.append("|------|:-------:|:------------:|:-----:|:----------:|")
    for key, data in model_results.items():
        s = all_scores[key]["_overall"]
        L.append(
            f"| {data['model_name']} | {data['params']} "
            f"| {s['avg_latency']:.2f} | {s['avg_tps']:.0f} "
            f"| {s['total_time']:.0f}초 |"
        )

    # 결론
    L.append("\n---\n")
    L.append("## 결론")
    L.append("")
    best_key = ranked[0][0]
    best_name = model_results[best_key]["model_name"]
    L.append(f"**추천 베이스 모델: {best_name}**")
    L.append("")
    L.append("| 평가 축 | 최고 모델 |")
    L.append("|---------|---------|")
    for ax_label, ax_key in [
        ("한국어", "korean"),
        ("규정해석", "regulation"),
        ("판단형식", "format"),
        ("속도", "speed"),
    ]:
        best = max(axis_scores.items(), key=lambda x: x[1][ax_key])
        bname = model_results[best[0]]["model_name"]
        L.append(f"| {ax_label} | {bname} ({best[1][ax_key]:.3f}) |")

    # 저장
    report = "\n".join(L)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n리포트 저장: {report_path}")
    print(report)


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="모델 벤치마크 (이슈 #7)"
    )
    parser.add_argument(
        "--model",
        type=str,
        help="모델 키 (qwen3, kanana, exaone, tri7b)",
    )
    parser.add_argument(
        "--report", action="store_true", help="비교 리포트 생성"
    )
    parser.add_argument(
        "--category", type=str, default=None, help="특정 카테고리만 테스트"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        help="GPU 디바이스 (auto, cuda:0, ...)",
    )
    args = parser.parse_args()

    config = load_config()

    if args.report:
        generate_report(config)
    elif args.model:
        if args.model not in config["models"]:
            avail = ", ".join(config["models"].keys())
            print(f"지원 모델: {avail}")
            sys.exit(1)
        run_benchmark(args.model, config, args.device, args.category)
    else:
        parser.print_help()
        print("\n사용 예시:")
        print("  python scripts/benchmark/run.py --model qwen3")
        print("  python scripts/benchmark/run.py --model kanana")
        print("  python scripts/benchmark/run.py --model exaone")
        print("  python scripts/benchmark/run.py --model tri7b")
        print("  python scripts/benchmark/run.py --report")


if __name__ == "__main__":
    main()
