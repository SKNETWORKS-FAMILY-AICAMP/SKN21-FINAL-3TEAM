"""
LoRA v1 모델 재평가 — RAG 개선 환경 (Reranker + HyDE + Score Threshold)

목적:
  - 기존 v1 평가(86.6%)는 eval.jsonl에 하드코딩된 규정 컨텍스트로 평가
  - 이 스크립트는 실제 RAG 파이프라인(개선 버전)으로 컨텍스트를 라이브 검색하여 평가
  - RAG 개선이 최종 판단 정확도에 미치는 실질 효과 측정

비교 모드:
  Mode A (baseline): eval.jsonl의 기존 컨텍스트 그대로 사용 (=v1 평가 재현)
  Mode B (rag-improved): RAG 개선 파이프라인으로 컨텍스트 라이브 검색 후 평가
  Mode C (rag-baseline): RAG 기존(RRF만)으로 컨텍스트 검색 후 평가

실행 (RunPod):
  # 전체 비교 (baseline + rag-improved + rag-baseline)
  python scripts/eval_lora_v1_rag_improved.py --mode all --adapter_path outputs/v1_judgment/final

  # RAG 개선 환경만
  python scripts/eval_lora_v1_rag_improved.py --mode rag-improved --adapter_path outputs/v1_judgment/final

  # baseline만 (v1 평가 재현)
  python scripts/eval_lora_v1_rag_improved.py --mode baseline --adapter_path outputs/v1_judgment/final

  # 샘플 수 제한 (빠른 테스트)
  python scripts/eval_lora_v1_rag_improved.py --mode all --max_samples 30

환경:
  pip install transformers peft bitsandbytes accelerate torch pyyaml qdrant-client sentence-transformers
  .env에 QDRANT_URL, QDRANT_API_KEY 필요
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import torch
import yaml

# 프로젝트 루트
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


# ── CLI ──

def parse_args():
    parser = argparse.ArgumentParser(description="LoRA v1 모델 재평가 — RAG 개선 환경")
    parser.add_argument("--mode", choices=["baseline", "rag-improved", "rag-baseline", "all"],
                        default="all", help="평가 모드 (기본: all)")
    parser.add_argument("--adapter_path", default=str(ROOT / "outputs" / "v1_judgment" / "final"),
                        help="LoRA 어댑터 경로")
    parser.add_argument("--config", default=str(ROOT / "ai" / "finetuning" / "configs" / "v1_judgment.yaml"),
                        help="YAML 설정 파일 경로")
    parser.add_argument("--max_samples", type=int, default=0,
                        help="최대 평가 샘플 수 (0=전체, 기본: 전체)")
    parser.add_argument("--top_k", type=int, default=10,
                        help="RAG 검색 결과 수 (기본: 10)")
    parser.add_argument("--score_threshold", type=float, default=-2.0,
                        help="Score threshold for RAG improved (기본: -2.0)")
    parser.add_argument("--output_dir", default=str(ROOT / "outputs" / "v1_judgment"),
                        help="결과 저장 디렉토리")
    return parser.parse_args()


# ── 유틸리티 ──

VALID_RESULTS = {"yes", "no", "conditional", "no_regulation"}


def parse_judgment_json(text: str) -> dict | None:
    """텍스트에서 judgment JSON 추출"""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    if not text.startswith("{"):
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def extract_question_from_user_msg(user_content: str) -> str:
    """user message에서 순수 질문만 추출 (규정 컨텍스트 제거)"""
    # "## 사용자 질문" 이후 텍스트
    if "## 사용자 질문" in user_content:
        return user_content.split("## 사용자 질문")[-1].strip()
    # "질문:" 이후 텍스트
    if "질문:" in user_content:
        return user_content.split("질문:")[-1].strip()
    # fallback: 전체 반환
    return user_content


def build_user_prompt_with_rag_context(question: str, rag_results: list[dict]) -> str:
    """RAG 검색 결과 + 질문 → user prompt 생성 (eval.jsonl 학습 데이터와 동일 형식)

    학습 데이터 헤더 형식:
        ### 제9조 (원격근무)
        ### 개인정보처리규정 — 제5조 (개인정보 수집 원칙)
    """
    if not rag_results:
        return f"## 관련 규정 문서\n(관련 규정을 찾지 못했습니다)\n\n## 사용자 질문\n{question}"

    context_parts = []
    for doc in rag_results:
        title = doc.get("title", "")
        article = doc.get("article", "")
        content = doc.get("content", "")

        # 학습 데이터와 동일한 헤더 형식
        if article and title and title != article:
            header = f"### {title} — {article}"
        elif article:
            header = f"### {article}"
        elif title:
            header = f"### {title}"
        else:
            header = f"### 규정"

        context_parts.append(f"{header}\n{content}")

    context_text = "\n\n".join(context_parts)
    return f"## 관련 규정 문서\n{context_text}\n\n## 사용자 질문\n{question}"


def header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ── 모델 로드 ──

def load_model(config_path: str, adapter_path: str):
    """LoRA v1 모델 로드 (QLoRA 4-bit + adapter)"""
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    model_id = config["model"]["base_model"]
    print(f"  베이스 모델: {model_id}")
    print(f"  어댑터: {adapter_path}")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()
    torch.cuda.empty_cache()

    print(f"  VRAM: {torch.cuda.memory_allocated()/1e9:.1f} GB")
    return tokenizer, model


# ── 추론 ──

def run_inference(tokenizer, model, system_prompt: str, user_prompt: str) -> str:
    """모델 추론 — system + user → assistant 응답 생성"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    except Exception:
        prompt = f"[시스템]\n{system_prompt}\n\n[사용자]\n{user_prompt}\n\n[어시스턴트]\n"

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048).to(model.device)
    input_len = inputs["input_ids"].shape[1]

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )

    return tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True).strip()


# ── 평가 실행 ──

def evaluate_mode(
    tokenizer,
    model,
    eval_samples: list[dict],
    mode: str,
    rag_pipeline=None,
    top_k: int = 10,
    use_reranker: bool = False,
    score_threshold: float | None = None,
    use_hyde: bool = False,
) -> dict:
    """하나의 모드로 전체 eval 샘플 평가

    Args:
        mode: "baseline" | "rag-improved" | "rag-baseline"
    """
    total = 0
    json_valid = 0
    result_correct = 0
    category_stats: dict[str, dict[str, int]] = {}
    rag_times = []
    infer_times = []
    per_sample_results = []

    for i, sample in enumerate(eval_samples, 1):
        messages = sample["messages"]
        system_prompt = messages[0]["content"]
        original_user_prompt = messages[1]["content"]

        # Gold 라벨 추출
        gold_parsed = parse_judgment_json(messages[2]["content"])
        if not gold_parsed:
            continue
        gold_result = gold_parsed.get("result", "")
        total += 1

        if gold_result not in category_stats:
            category_stats[gold_result] = {"correct": 0, "total": 0}
        category_stats[gold_result]["total"] += 1

        # 모드별 user prompt 구성
        if mode == "baseline":
            # eval.jsonl의 기존 컨텍스트 그대로 사용
            user_prompt = original_user_prompt
            rag_time = 0
        else:
            # RAG로 컨텍스트 라이브 검색
            question = extract_question_from_user_msg(original_user_prompt)
            _t_rag = time.time()
            rag_results = rag_pipeline.retrieve(
                query=question,
                user_id=None,
                top_k=top_k,
                filter={"source": "regulations"},
                use_reranker=use_reranker,
                score_threshold=score_threshold,
                use_hyde=use_hyde,
            )
            rag_time = time.time() - _t_rag
            rag_times.append(rag_time)
            user_prompt = build_user_prompt_with_rag_context(question, rag_results)

        # 추론
        _t_infer = time.time()
        pred_text = run_inference(tokenizer, model, system_prompt, user_prompt)
        infer_time = time.time() - _t_infer
        infer_times.append(infer_time)

        pred_parsed = parse_judgment_json(pred_text)

        sample_result = {
            "index": i,
            "gold": gold_result,
            "pred": None,
            "correct": False,
            "json_valid": False,
            "rag_time": round(rag_time, 3),
            "infer_time": round(infer_time, 3),
        }

        if pred_parsed is not None:
            json_valid += 1
            sample_result["json_valid"] = True
            pred_result = pred_parsed.get("result", "")
            sample_result["pred"] = pred_result

            if pred_result == gold_result:
                result_correct += 1
                category_stats[gold_result]["correct"] += 1
                sample_result["correct"] = True

        per_sample_results.append(sample_result)

        # 진행 로그 (처음 5건 + 매 30건)
        if i <= 5 or i % 30 == 0 or i == len(eval_samples):
            pred_str = sample_result["pred"] or "JSON_FAIL"
            status = "OK" if sample_result["correct"] else "MISS"
            acc_so_far = result_correct / total * 100
            print(f"  [{mode}] {i:03d}/{len(eval_samples)} "
                  f"gold={gold_result:<14} pred={pred_str:<14} {status} "
                  f"(acc={acc_so_far:.1f}%, rag={rag_time:.2f}s, infer={infer_time:.1f}s)")

    # 결과 집계
    json_valid_rate = json_valid / total if total > 0 else 0
    accuracy = result_correct / total if total > 0 else 0
    avg_rag_time = sum(rag_times) / len(rag_times) if rag_times else 0
    avg_infer_time = sum(infer_times) / len(infer_times) if infer_times else 0

    return {
        "mode": mode,
        "total": total,
        "json_valid": json_valid,
        "json_valid_rate": round(json_valid_rate, 4),
        "result_correct": result_correct,
        "result_accuracy": round(accuracy, 4),
        "category_stats": category_stats,
        "avg_rag_time": round(avg_rag_time, 3),
        "avg_infer_time": round(avg_infer_time, 3),
        "per_sample_results": per_sample_results,
    }


def print_eval_result(result: dict):
    """평가 결과 출력"""
    header(f"평가 결과: {result['mode']}")
    print(f"  총 평가:      {result['total']}건")
    print(f"  JSON 유효율:  {result['json_valid']}/{result['total']} "
          f"({result['json_valid_rate']*100:.1f}%)")
    print(f"  판단 정확도:  {result['result_correct']}/{result['total']} "
          f"({result['result_accuracy']*100:.1f}%)")
    if result['avg_rag_time'] > 0:
        print(f"  평균 RAG 시간:   {result['avg_rag_time']:.3f}s")
    print(f"  평균 추론 시간:  {result['avg_infer_time']:.3f}s")

    print(f"\n  {'카테고리':<15} {'정확도':>10} {'건수':>8}")
    print("  " + "-" * 38)
    for cat in sorted(result["category_stats"].keys()):
        stats = result["category_stats"][cat]
        acc = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {cat:<15} {acc:>9.1f}% {stats['correct']:>3}/{stats['total']:<3}건")


def print_comparison(results: list[dict]):
    """모드별 비교표 출력"""
    header("종합 비교")

    # 비교 테이블
    print(f"  {'모드':<25} {'정확도':>8} {'JSON유효':>10} {'RAG시간':>10} {'추론시간':>10}")
    print("  " + "-" * 68)
    for r in results:
        rag_str = f"{r['avg_rag_time']:.3f}s" if r['avg_rag_time'] > 0 else "N/A"
        print(f"  {r['mode']:<25} "
              f"{r['result_accuracy']*100:>7.1f}% "
              f"{r['json_valid_rate']*100:>9.1f}% "
              f"{rag_str:>10} "
              f"{r['avg_infer_time']:.3f}s")

    # 카테고리별 비교
    all_cats = set()
    for r in results:
        all_cats.update(r["category_stats"].keys())

    print(f"\n  카테고리별 정확도 비교:")
    print(f"  {'카테고리':<15}", end="")
    for r in results:
        print(f" {'| ' + r['mode']:<20}", end="")
    print()
    print("  " + "-" * (15 + 20 * len(results)))

    for cat in sorted(all_cats):
        print(f"  {cat:<15}", end="")
        for r in results:
            stats = r["category_stats"].get(cat, {"correct": 0, "total": 0})
            acc = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
            print(f" | {acc:>6.1f}% ({stats['correct']:>3}/{stats['total']:<3})", end="")
        print()

    # baseline 대비 변화
    if len(results) >= 2:
        baseline = results[0]
        for r in results[1:]:
            diff = (r["result_accuracy"] - baseline["result_accuracy"]) * 100
            print(f"\n  {r['mode']} vs {baseline['mode']}: {diff:+.1f}%p")
            for cat in sorted(all_cats):
                b_stats = baseline["category_stats"].get(cat, {"correct": 0, "total": 0})
                r_stats = r["category_stats"].get(cat, {"correct": 0, "total": 0})
                b_acc = b_stats["correct"] / b_stats["total"] * 100 if b_stats["total"] > 0 else 0
                r_acc = r_stats["correct"] / r_stats["total"] * 100 if r_stats["total"] > 0 else 0
                diff_cat = r_acc - b_acc
                arrow = "+" if diff_cat > 0 else ""
                print(f"    {cat:<15} {b_acc:.1f}% → {r_acc:.1f}% ({arrow}{diff_cat:.1f}%p)")

    # 오분류 패턴 분석
    if len(results) >= 2:
        header("오분류 패턴 분석 (RAG 개선)")
        rag_result = results[1]  # rag-improved
        confusion = defaultdict(int)
        for sr in rag_result["per_sample_results"]:
            if not sr["correct"] and sr["pred"]:
                confusion[f"{sr['gold']} → {sr['pred']}"] += 1

        if confusion:
            print(f"  {'오분류 패턴':<30} {'건수':>6}")
            print("  " + "-" * 38)
            for pattern, count in sorted(confusion.items(), key=lambda x: -x[1]):
                print(f"  {pattern:<30} {count:>5}건")
        else:
            print("  오분류 없음!")


# ── 메인 ──

def main():
    args = parse_args()

    header("LoRA v1 재평가 — RAG 개선 환경")
    print(f"  모드: {args.mode}")
    print(f"  어댑터: {args.adapter_path}")
    print(f"  RAG top_k: {args.top_k}")
    print(f"  Score threshold: {args.score_threshold}")

    # 1. eval.jsonl 로드
    eval_path = ROOT / "data" / "training" / "v1_judgment" / "eval.jsonl"
    eval_samples = []
    with open(eval_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                eval_samples.append(json.loads(line))

    if args.max_samples > 0:
        eval_samples = eval_samples[:args.max_samples]
    print(f"  평가 샘플: {len(eval_samples)}건")

    # 2. 모델 로드
    header("모델 로드")
    tokenizer, model = load_model(args.config, args.adapter_path)

    # 3. RAG 파이프라인 초기화 (필요 시)
    rag_pipeline = None
    need_rag = args.mode in ("rag-improved", "rag-baseline", "all")
    if need_rag:
        header("RAG 파이프라인 초기화")
        from ai.rag.qdrant_pipeline import get_qdrant_pipeline
        rag_pipeline = get_qdrant_pipeline()
        print("  초기화 완료")

    # 4. 평가 실행
    all_results = []

    if args.mode in ("baseline", "all"):
        header("Mode A: Baseline (기존 컨텍스트)")
        result_baseline = evaluate_mode(
            tokenizer, model, eval_samples,
            mode="baseline",
        )
        print_eval_result(result_baseline)
        all_results.append(result_baseline)

    if args.mode in ("rag-improved", "all"):
        header("Mode B: RAG Improved (Reranker + HyDE + Threshold)")
        result_rag_improved = evaluate_mode(
            tokenizer, model, eval_samples,
            mode="rag-improved",
            rag_pipeline=rag_pipeline,
            top_k=args.top_k,
            use_reranker=True,
            score_threshold=args.score_threshold,
            use_hyde=True,
        )
        print_eval_result(result_rag_improved)
        all_results.append(result_rag_improved)

    if args.mode in ("rag-baseline", "all"):
        header("Mode C: RAG Baseline (RRF만)")
        result_rag_baseline = evaluate_mode(
            tokenizer, model, eval_samples,
            mode="rag-baseline",
            rag_pipeline=rag_pipeline,
            top_k=args.top_k,
            use_reranker=False,
            score_threshold=None,
            use_hyde=False,
        )
        print_eval_result(result_rag_baseline)
        all_results.append(result_rag_baseline)

    # 5. 비교
    if len(all_results) >= 2:
        print_comparison(all_results)

    # 6. 결과 저장
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "eval_rag_improved.json"

    save_data = {
        "config": {
            "mode": args.mode,
            "adapter_path": args.adapter_path,
            "top_k": args.top_k,
            "score_threshold": args.score_threshold,
            "max_samples": args.max_samples,
            "eval_count": len(eval_samples),
        },
        "results": [],
    }
    for r in all_results:
        # per_sample_results는 별도 저장 (파일 크기 관리)
        r_save = {k: v for k, v in r.items() if k != "per_sample_results"}
        save_data["results"].append(r_save)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {output_path}")

    # 상세 결과 (per_sample) 별도 저장
    for r in all_results:
        detail_path = output_dir / f"eval_detail_{r['mode'].replace('-', '_')}.json"
        with open(detail_path, "w", encoding="utf-8") as f:
            json.dump(r["per_sample_results"], f, ensure_ascii=False, indent=2)
        print(f"  상세 결과: {detail_path}")

    # 7. 최종 요약
    header("최종 요약")
    for r in all_results:
        print(f"  {r['mode']:<25} → 정확도 {r['result_accuracy']*100:.1f}% "
              f"(JSON {r['json_valid_rate']*100:.1f}%)")

    if len(all_results) >= 2:
        best = max(all_results, key=lambda x: x["result_accuracy"])
        print(f"\n  최고 성능: {best['mode']} ({best['result_accuracy']*100:.1f}%)")
        if best["result_accuracy"] >= 0.90:
            print("  → 목표 90% 달성! v2 학습 불필요")
        else:
            print(f"  → 목표 90% 미달 ({best['result_accuracy']*100:.1f}%). v2 보강 데이터 학습 필요")


if __name__ == "__main__":
    main()
