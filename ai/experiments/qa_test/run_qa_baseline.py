"""
QA Baseline 실험: Midm-2.0-Base-Instruct vs A.X-3.1-Light

두 한국어 sLLM의 QA 능력을 정량(ROUGE-L, Token F1) + 정성(답변 저장) 방식으로 비교한다.

사용법:
    # 두 모델 모두 실행
    python ai/experiments/run_qa_baseline.py

    # 특정 모델만 실행
    python ai/experiments/run_qa_baseline.py --model midm
    python ai/experiments/run_qa_baseline.py --model ax

    # Colab 환경 예시
    !python ai/experiments/run_qa_baseline.py --model midm

환경:
    pip install transformers bitsandbytes accelerate rouge-score torch
    GPU: Colab L4 (24GB VRAM) 권장
"""

import argparse
import json
import re
import time
from pathlib import Path
from collections import Counter

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from rouge_score import rouge_scorer

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_PATH = BASE_DIR / "ai" / "data" / "qa_samples.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ── 모델 설정 ──
MODEL_CONFIGS = {
    "midm": {
        "model_id": "K-intelligence/Midm-2.0-Base-Instruct",
        "short_name": "Midm-2.0-Base",
        "max_new_tokens": 128,
    },
    "ax": {
        "model_id": "skt/A.X-3.1-Light",
        "short_name": "A.X-3.1-Light",
        "max_new_tokens": 128,
    },
}

# ── 정성 평가용 저장 개수 ──
QUALITATIVE_SAMPLE_IDS = [
    "gen_001", "gen_005", "gen_010", "gen_014", "gen_019",
    "biz_001", "biz_003", "biz_007", "biz_011", "biz_017",
]


# ── 데이터 로드 ──

def load_qa_samples():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── 지표 계산 ──

def normalize_answer(text: str) -> str:
    """답변 텍스트 정규화 (공백, 특수문자 처리)"""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s가-힣]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def token_f1(pred: str, gold: str) -> float:
    """SQuAD 방식 토큰 F1 (한국어 어절 단위)"""
    pred_tokens = normalize_answer(pred).split()
    gold_tokens = normalize_answer(gold).split()
    if not pred_tokens or not gold_tokens:
        return 0.0
    pred_counter = Counter(pred_tokens)
    gold_counter = Counter(gold_tokens)
    common = sum((pred_counter & gold_counter).values())
    if common == 0:
        return 0.0
    precision = common / len(pred_tokens)
    recall = common / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def rouge_l(pred: str, gold: str, scorer) -> float:
    """ROUGE-L F1"""
    result = scorer.score(gold, pred)
    return result["rougeL"].fmeasure


# ── 모델 로드 ──

def load_model_4bit(model_id: str):
    """bitsandbytes 4-bit 양자화로 모델 로드"""
    print(f"\n  모델 로드 중: {model_id}")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()
    print(f"  로드 완료. Device map: {model.hf_device_map}")
    return tokenizer, model


# ── 추론 ──

def build_prompt(tokenizer, context: str, question: str) -> str:
    """chat template 적용 QA 프롬프트 생성"""
    user_msg = f"다음 글을 읽고 질문에 간결하게 답하세요.\n\n[글]\n{context}\n\n[질문]\n{question}"
    messages = [{"role": "user", "content": user_msg}]
    try:
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    except Exception:
        # chat template 미지원 시 fallback
        prompt = f"[지문]\n{context}\n\n[질문]\n{question}\n\n[답변]\n"
    return prompt


def generate_answer(tokenizer, model, context: str, question: str, max_new_tokens: int) -> str:
    """단일 QA 추론"""
    prompt = build_prompt(tokenizer, context, question)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    input_len = inputs["input_ids"].shape[1]

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated = outputs[0][input_len:]
    answer = tokenizer.decode(generated, skip_special_tokens=True).strip()
    # 첫 줄만 취함 (모델이 추가 설명을 붙이는 경우 방지)
    answer = answer.split("\n")[0].strip()
    return answer


# ── 메인 평가 루프 ──

def evaluate_model(model_key: str, samples: list) -> dict:
    cfg = MODEL_CONFIGS[model_key]
    tokenizer, model = load_model_4bit(cfg["model_id"])
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)

    predictions = []
    total_time = 0.0

    print(f"\n  [{cfg['short_name']}] 추론 시작 ({len(samples)}건)")
    for i, sample in enumerate(samples, 1):
        t0 = time.time()
        pred = generate_answer(
            tokenizer, model,
            sample["context"], sample["question"],
            cfg["max_new_tokens"],
        )
        elapsed = time.time() - t0
        total_time += elapsed

        tf1 = token_f1(pred, sample["answer"])
        rl = rouge_l(pred, sample["answer"], scorer)

        predictions.append({
            "id": sample["id"],
            "domain": sample["domain"],
            "question": sample["question"],
            "gold_answer": sample["answer"],
            "pred_answer": pred,
            "token_f1": round(tf1, 4),
            "rouge_l": round(rl, 4),
            "infer_sec": round(elapsed, 2),
        })

        print(f"    [{i:02d}/{len(samples)}] {sample['id']} | TF1={tf1:.3f} ROUGE-L={rl:.3f} | '{pred[:40]}...'")

    # 메모리 해제
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return {
        "model_key": model_key,
        "model_id": cfg["model_id"],
        "short_name": cfg["short_name"],
        "predictions": predictions,
        "total_infer_sec": round(total_time, 2),
        "avg_infer_sec": round(total_time / len(samples), 2),
    }


# ── 지표 집계 ──

def compute_summary(result: dict) -> dict:
    preds = result["predictions"]

    def avg_metrics(items):
        if not items:
            return {"token_f1": 0.0, "rouge_l": 0.0, "count": 0}
        return {
            "token_f1": round(sum(p["token_f1"] for p in items) / len(items), 4),
            "rouge_l": round(sum(p["rouge_l"] for p in items) / len(items), 4),
            "count": len(items),
        }

    general = [p for p in preds if p["domain"] == "general"]
    business = [p for p in preds if p["domain"] == "business"]

    return {
        "model": result["short_name"],
        "model_id": result["model_id"],
        "overall": avg_metrics(preds),
        "general": avg_metrics(general),
        "business": avg_metrics(business),
        "avg_infer_sec": result["avg_infer_sec"],
        "total_infer_sec": result["total_infer_sec"],
    }


# ── 결과 출력 ──

def print_comparison(summaries: list):
    print("\n" + "=" * 70)
    print("  QA Baseline 결과 비교")
    print("=" * 70)
    header = f"  {'모델':<20} {'전체 TF1':>10} {'전체 RL':>10} {'일반 TF1':>10} {'업무 TF1':>10} {'속도(s)':>8}"
    print(header)
    print("  " + "-" * 68)
    for s in summaries:
        print(
            f"  {s['model']:<20}"
            f" {s['overall']['token_f1']:>10.4f}"
            f" {s['overall']['rouge_l']:>10.4f}"
            f" {s['general']['token_f1']:>10.4f}"
            f" {s['business']['token_f1']:>10.4f}"
            f" {s['avg_infer_sec']:>8.2f}"
        )
    print("=" * 70)


# ── 정성 평가 샘플 추출 ──

def extract_qualitative(all_results: list) -> list:
    qualitative = []
    for result in all_results:
        model_samples = []
        for pred in result["predictions"]:
            if pred["id"] in QUALITATIVE_SAMPLE_IDS:
                model_samples.append(pred)
        qualitative.append({
            "model": result["short_name"],
            "samples": model_samples,
        })
    return qualitative


# ── 저장 ──

def save_results(all_results: list, summaries: list):
    # 정량 결과
    quant_path = RESULTS_DIR / "qa_quantitative.json"
    with open(quant_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)
    print(f"\n  [저장] {quant_path}")

    # 정성 결과 (전체 예측 + 정성 샘플 플래그)
    qual_data = []
    for result in all_results:
        for pred in result["predictions"]:
            entry = {
                "model": result["short_name"],
                "qualitative_sample": pred["id"] in QUALITATIVE_SAMPLE_IDS,
                **pred,
            }
            qual_data.append(entry)

    qual_path = RESULTS_DIR / "qa_qualitative.json"
    with open(qual_path, "w", encoding="utf-8") as f:
        json.dump(qual_data, f, ensure_ascii=False, indent=2)
    print(f"  [저장] {qual_path}")


# ── 엔트리포인트 ──

def main():
    parser = argparse.ArgumentParser(description="QA Baseline 실험")
    parser.add_argument(
        "--model",
        choices=["midm", "ax", "all"],
        default="all",
        help="실행할 모델 (기본: all)",
    )
    args = parser.parse_args()

    target_keys = ["midm", "ax"] if args.model == "all" else [args.model]

    samples = load_qa_samples()
    print(f"데이터 로드: {len(samples)}건")

    all_results = []
    summaries = []

    for key in target_keys:
        print(f"\n{'=' * 70}")
        print(f"  모델: {MODEL_CONFIGS[key]['short_name']}")
        print(f"{'=' * 70}")

        result = evaluate_model(key, samples)
        summary = compute_summary(result)

        all_results.append(result)
        summaries.append(summary)

        print(f"\n  [{summary['model']}] 완료")
        print(f"    전체 Token F1: {summary['overall']['token_f1']:.4f}")
        print(f"    전체 ROUGE-L : {summary['overall']['rouge_l']:.4f}")
        print(f"    일반 Token F1: {summary['general']['token_f1']:.4f}")
        print(f"    업무 Token F1: {summary['business']['token_f1']:.4f}")
        print(f"    평균 추론 시간: {summary['avg_infer_sec']:.2f}s/sample")

    if len(summaries) > 1:
        print_comparison(summaries)

    save_results(all_results, summaries)
    print("\n실험 완료!")


if __name__ == "__main__":
    main()
