"""
LLM 기준선 + 하이브리드 평가 스크립트

3가지 비교:
  1) sLLM only (BERT + Per-label Threshold)
  2) LLM only (GPT-4o-mini)
  3) Hybrid (sLLM 확신 높으면 사용, 낮으면 LLM fallback)

사용법 (RunPod):
  export OPENAI_API_KEY=sk-...
  python -m ai.experiments.eval_hybrid

  # confidence threshold 조절:
  python -m ai.experiments.eval_hybrid --confidence 0.7
"""

import argparse
import asyncio
import json
import os
import numpy as np
import torch
from pathlib import Path
from collections import defaultdict
from sklearn.metrics import f1_score
from transformers import AutoTokenizer, AutoModelForSequenceClassification

ROOT = Path(__file__).resolve().parent.parent.parent

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_qa",
]
NUM_LABELS = len(INTENT_LABELS)
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}

# ── LLM 프롬프트 ──────────────────────────────────────────────────────────────

INTENT_CLASSIFICATION_PROMPT = """당신은 사내 업무 지원 챗봇의 Intent 분류기입니다.

사용자 질문을 분석하여 해당하는 intent를 모두 선택하세요.
한 문장에 여러 의도가 있으면 복수 선택합니다.

## Intent 목록:
- judgment: 규정 위반 여부 판단, 가능/불가능 판단, 적용 가능성 검토
- doc_search: 문서/규정 검색, 찾기, 조회
- doc_generate: 문서 작성, 생성, 회의록/보고서/제안서 만들기
- doc_summary: 문서 요약, 핵심 정리, 간추리기
- schedule_add: 일정 등록, 추가, 잡기
- schedule_view: 일정 조회, 확인, 보기
- general: 일반 대화, 인사, 잡담
- doc_qa: 문서 내용 질문, 특정 정보 추출 (금액, 날짜, 담당자 등)

## 규칙:
1. 복합 질문이면 해당 intent를 모두 선택 (예: "규정 찾아서 위반인지 봐줘" → doc_search, judgment)
2. 같은 intent의 항목을 나열한 것은 단일 intent (예: "연차이랑 병가 규정 찾아줘" → doc_search)
3. 반드시 JSON 배열로만 응답하세요

## 응답 형식:
["intent1", "intent2"]

사용자 질문: {text}"""


# ── 공통 함수 ─────────────────────────────────────────────────────────────────

def labels_to_vector(labels_list):
    vec = [0.0] * NUM_LABELS
    for label in labels_list:
        if label in LABEL2ID:
            vec[LABEL2ID[label]] = 1.0
    return vec


def evaluate(y_pred_labels_list, y_true_labels_list):
    n = len(y_pred_labels_list)
    y_pred = np.array([labels_to_vector(sorted(p)) for p in y_pred_labels_list])
    y_true = np.array([labels_to_vector(sorted(t)) for t in y_true_labels_list])

    exact_match = np.all(y_pred == y_true, axis=1).mean()
    hamming = (y_pred != y_true).mean()

    jaccard_scores = []
    for i in range(n):
        inter = np.logical_and(y_pred[i], y_true[i]).sum()
        union = np.logical_or(y_pred[i], y_true[i]).sum()
        jaccard_scores.append(inter / union if union > 0 else 1.0)
    jaccard = np.mean(jaccard_scores)

    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    micro_f1 = f1_score(y_true, y_pred, average="micro", zero_division=0)

    true_multi = (y_true.sum(axis=1) >= 2)
    pred_multi = (y_pred.sum(axis=1) >= 2)
    n_single = (~true_multi).sum()
    n_multi = true_multi.sum()
    fp = ((~true_multi) & pred_multi).sum()
    fn = (true_multi & (~pred_multi)).sum()
    over = fp / n_single if n_single > 0 else 0.0
    under = fn / n_multi if n_multi > 0 else 0.0

    return {
        "subset_accuracy": exact_match,
        "hamming_loss": hamming,
        "jaccard": jaccard,
        "macro_f1": macro_f1,
        "micro_f1": micro_f1,
        "over_triggering": over,
        "under_triggering": under,
        "fp": int(fp), "fn": int(fn),
        "n_single": int(n_single), "n_multi": int(n_multi),
    }


# ── sLLM (BERT) ──────────────────────────────────────────────────────────────

def load_bert_model(model_dir):
    model_dir = Path(model_dir)
    with open(model_dir / "model_info.json", "r", encoding="utf-8") as f:
        model_info = json.load(f)

    base_model = model_info.get("base_model", "monologg/koelectra-base-v3-discriminator")
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.eval()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"sLLM 모델 로드: {model_dir} (base: {base_model})")
    return model, tokenizer, device


def bert_predict_with_confidence(model, tokenizer, text, device, per_label_thresholds=None):
    """BERT 예측 + 각 label별 확률 반환"""
    inputs = tokenizer(
        text, return_tensors="pt", padding=True,
        truncation=True, max_length=128,
    ).to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    probs = torch.sigmoid(outputs.logits)[0].cpu().numpy()

    if per_label_thresholds is not None:
        pred_labels = [INTENT_LABELS[j] for j in range(NUM_LABELS)
                       if probs[j] >= per_label_thresholds[j]]
    else:
        pred_labels = [INTENT_LABELS[j] for j in range(NUM_LABELS) if probs[j] >= 0.5]

    if not pred_labels:
        pred_labels = [INTENT_LABELS[np.argmax(probs)]]

    # confidence = 예측된 label들의 평균 확률
    pred_indices = [LABEL2ID[l] for l in pred_labels]
    confidence = np.mean([probs[i] for i in pred_indices])

    return sorted(pred_labels), probs, float(confidence)


# ── LLM (GPT) ────────────────────────────────────────────────────────────────

async def llm_predict(text, api_key, model_name="gpt-4o-mini"):
    """GPT로 intent 분류"""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)

    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": INTENT_CLASSIFICATION_PROMPT.format(text=text)}
            ],
            temperature=0.0,
            max_tokens=100,
        )
        content = response.content if hasattr(response, 'content') else response.choices[0].message.content
        content = content.strip()

        # JSON 파싱
        if content.startswith("["):
            labels = json.loads(content)
        else:
            # ```json [...] ``` 형태 처리
            import re
            match = re.search(r'\[.*?\]', content, re.DOTALL)
            if match:
                labels = json.loads(match.group())
            else:
                labels = ["general"]

        # 유효한 label만 필터링
        valid_labels = [l for l in labels if l in LABEL2ID]
        if not valid_labels:
            valid_labels = ["general"]

        return sorted(valid_labels)

    except Exception as e:
        print(f"  LLM 오류: {e} → general 반환")
        return ["general"]


async def llm_predict_batch(texts, api_key, model_name="gpt-4o-mini"):
    """배치 LLM 예측 (동시 5개씩)"""
    import asyncio

    results = [None] * len(texts)
    semaphore = asyncio.Semaphore(5)  # 동시 5개 제한

    async def predict_one(idx, text):
        async with semaphore:
            result = await llm_predict(text, api_key, model_name)
            results[idx] = result
            if (idx + 1) % 10 == 0:
                print(f"  LLM 진행: {idx + 1}/{len(texts)}")

    tasks = [predict_one(i, text) for i, text in enumerate(texts)]
    await asyncio.gather(*tasks)
    return results


# ── 출력 함수 ─────────────────────────────────────────────────────────────────

def print_comparison(results_dict, title="비교"):
    metrics = [
        ("Subset Accuracy", "subset_accuracy"),
        ("Hamming Loss", "hamming_loss"),
        ("Jaccard Score", "jaccard"),
        ("Macro F1", "macro_f1"),
        ("Micro F1", "micro_f1"),
        ("Over-triggering", "over_triggering"),
        ("Under-triggering", "under_triggering"),
    ]

    names = list(results_dict.keys())
    header = f"  {'지표':<24}" + "".join(f"{n:>14}" for n in names)
    sep_line = f"  {'─'*24}" + "".join(f"{'─'*14}" for _ in names)

    print(f"\n{'═'*60}")
    print(f"  {title}")
    print(f"{'═'*60}")
    print(header)
    print(sep_line)

    for name, key in metrics:
        vals = [results_dict[n][key] for n in names]
        if key == "hamming_loss":
            row = f"  {name:<24}" + "".join(f"{v:>13.4f}" for v in vals)
        elif key in ("over_triggering", "under_triggering"):
            row = f"  {name:<24}" + "".join(f"{v*100:>12.1f}%" for v in vals)
        else:
            row = f"  {name:<24}" + "".join(f"{v*100:>12.1f}%" for v in vals)
        print(row)


def print_errors(errors, title, max_show=20):
    sep = "─" * 60
    print(f"\n{sep}")
    print(f"  {title} ({len(errors)}건)")
    print(sep)
    for r in errors[:max_show]:
        print(f"  [{r['id']:2d}] [{r['category']}]")
        print(f"       text : {r['text']}")
        print(f"       true : {r['true']}")
        print(f"       pred : {r['pred']}")
        if r.get('method'):
            print(f"       방식 : {r['method']}")
        print()


# ── 메인 ─────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default=str(ROOT / "ai" / "models" / "intent_multilabel"))
    parser.add_argument("--confidence", type=float, default=0.75,
                        help="하이브리드 confidence threshold (이 이하면 LLM fallback)")
    parser.add_argument("--llm-model", default="gpt-4o-mini")
    parser.add_argument("--dataset", choices=["holdout", "adversarial", "both"], default="holdout")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("❌ OPENAI_API_KEY 환경변수를 설정하세요:")
        print("   export OPENAI_API_KEY=sk-...")
        return

    # ── 모델 로드 ──
    model, tokenizer, device = load_bert_model(args.model_dir)

    # ── Per-label Threshold 로드 ──
    strategy_path = ROOT / "ai" / "experiments" / "results" / "strategy_comparison_results.json"
    per_label_thresholds = None
    if strategy_path.exists():
        with open(strategy_path, "r", encoding="utf-8") as f:
            strategy_results = json.load(f)
        th_key = "optimal_thresholds" if "optimal_thresholds" in strategy_results else "strategy1_thresholds"
        if th_key in strategy_results:
            per_label_thresholds = np.array([
                strategy_results[th_key].get(label, 0.5)
                for label in INTENT_LABELS
            ])
            print(f"Per-label Threshold 로드 완료")

    # ── 데이터 로드 ──
    datasets = {}
    if args.dataset in ("holdout", "both"):
        holdout_path = ROOT / "data" / "training" / "intent_multilabel" / "adversarial_holdout_test.json"
        with open(holdout_path, "r", encoding="utf-8") as f:
            datasets["Held-out"] = json.load(f)["data"]
    if args.dataset in ("adversarial", "both"):
        adv_path = ROOT / "data" / "training" / "intent_multilabel" / "adversarial_compound_test.json"
        with open(adv_path, "r", encoding="utf-8") as f:
            datasets["Dev ADV"] = json.load(f)["data"]

    for ds_name, data in datasets.items():
        print(f"\n{'█'*60}")
        print(f"  데이터셋: {ds_name} ({len(data)}개)")
        print(f"{'█'*60}")

        texts = [item["text"] for item in data]
        true_labels = [item["labels"] for item in data]

        # ── 1) sLLM 예측 ──
        print(f"\n[1/3] sLLM (BERT + Threshold) 예측 중...")
        sllm_preds = []
        sllm_confidences = []
        sllm_probs_list = []
        for text in texts:
            pred, probs, conf = bert_predict_with_confidence(
                model, tokenizer, text, device, per_label_thresholds
            )
            sllm_preds.append(pred)
            sllm_confidences.append(conf)
            sllm_probs_list.append(probs)

        sllm_result = evaluate(sllm_preds, true_labels)

        # ── 2) LLM 예측 ──
        print(f"[2/3] LLM ({args.llm_model}) 예측 중...")
        llm_preds = await llm_predict_batch(texts, api_key, args.llm_model)
        llm_result = evaluate(llm_preds, true_labels)

        # ── 3) 하이브리드 예측 ──
        print(f"[3/3] 하이브리드 (confidence < {args.confidence} → LLM) 예측 중...")
        hybrid_preds = []
        hybrid_methods = []  # "sLLM" or "LLM"
        n_llm_fallback = 0

        for i in range(len(texts)):
            if sllm_confidences[i] >= args.confidence:
                hybrid_preds.append(sllm_preds[i])
                hybrid_methods.append("sLLM")
            else:
                hybrid_preds.append(llm_preds[i])
                hybrid_methods.append("LLM")
                n_llm_fallback += 1

        hybrid_result = evaluate(hybrid_preds, true_labels)

        # ── 비교 출력 ──
        print_comparison({
            "sLLM": sllm_result,
            f"LLM({args.llm_model})": llm_result,
            "Hybrid": hybrid_result,
        }, title=f"{ds_name} — sLLM vs LLM vs Hybrid")

        # ── 하이브리드 통계 ──
        sep = "─" * 60
        pct_sllm = (len(texts) - n_llm_fallback) / len(texts) * 100
        pct_llm = n_llm_fallback / len(texts) * 100
        print(f"\n{sep}")
        print(f"  하이브리드 분배 (confidence threshold: {args.confidence})")
        print(sep)
        print(f"  sLLM 처리: {len(texts) - n_llm_fallback}/{len(texts)} ({pct_sllm:.0f}%)")
        print(f"  LLM 처리:  {n_llm_fallback}/{len(texts)} ({pct_llm:.0f}%)")
        print(f"  → LLM 비용 절감: {pct_sllm:.0f}% (전량 LLM 대비)")

        # ── Confidence 분포 ──
        print(f"\n{sep}")
        print(f"  sLLM Confidence 분포")
        print(sep)
        bins = [(0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 1.01)]
        for lo, hi in bins:
            count = sum(1 for c in sllm_confidences if lo <= c < hi)
            marker = " ← LLM fallback" if hi <= args.confidence else ""
            bar = "█" * count
            print(f"  {lo:.1f}~{hi:.2f}: {count:3d}  {bar}{marker}")

        # ── 각 방식별 오답 ──
        for method_name, preds in [("sLLM", sllm_preds), (f"LLM({args.llm_model})", llm_preds), ("Hybrid", hybrid_preds)]:
            errors = []
            for idx, item in enumerate(data):
                true = sorted(item["labels"])
                pred = sorted(preds[idx])
                if true != pred:
                    err = {
                        "id": item["id"], "category": item["category"],
                        "text": item["text"], "true": true, "pred": pred,
                    }
                    if method_name == "Hybrid":
                        err["method"] = hybrid_methods[idx]
                        err["confidence"] = round(sllm_confidences[idx], 3)
                    errors.append(err)
            print_errors(errors, f"{ds_name} 오답 — {method_name}")

        # ── 하이브리드 confidence별 정확도 ──
        print(f"\n{sep}")
        print(f"  Confidence별 sLLM 정확도 (하이브리드 threshold 결정 참고)")
        print(sep)
        conf_bins = [(0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
        for lo, hi in conf_bins:
            indices = [i for i in range(len(texts)) if lo <= sllm_confidences[i] < hi]
            if indices:
                correct = sum(1 for i in indices if sorted(sllm_preds[i]) == sorted(true_labels[i]))
                acc = correct / len(indices) * 100
                print(f"  {lo:.1f}~{hi:.1f}: {correct}/{len(indices)} ({acc:.0f}%)")
            else:
                print(f"  {lo:.1f}~{hi:.1f}: 해당 없음")

    # ── 결과 저장 ──
    out = {
        "confidence_threshold": args.confidence,
        "llm_model": args.llm_model,
    }
    for ds_name in datasets:
        out[ds_name] = {
            "sllm": {k: round(v, 4) if isinstance(v, float) else v for k, v in sllm_result.items()},
            "llm": {k: round(v, 4) if isinstance(v, float) else v for k, v in llm_result.items()},
            "hybrid": {k: round(v, 4) if isinstance(v, float) else v for k, v in hybrid_result.items()},
            "llm_fallback_rate": round(n_llm_fallback / len(texts), 4),
        }

    out_path = ROOT / "ai" / "experiments" / "results" / "hybrid_evaluation_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
