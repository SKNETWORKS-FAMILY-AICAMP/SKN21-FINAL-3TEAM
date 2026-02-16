"""
최종 비교: GPT vs BERT(실험6 전처리 적용) — 동일 212문장 Adversarial 기준

실행:
    export OPENAI_API_KEY='sk-...'
    python ai/experiments/run_final_comparison.py

비교 대상:
    1. GPT-4o-mini Zero-shot
    2. GPT-4o-mini Few-shot
    3. BERT Fine-tuned (전처리 없음, 실험5 baseline)
    4. BERT Fine-tuned + 풀 전처리 (실험6 Config E)
"""

import json
import os
import sys
import time
from pathlib import Path

# Python 3.13 경로 호환
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data" / "training" / "intent"
MODEL_DIR = BASE_DIR / "ai" / "models" / "intent_classifier"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate",
    "meeting_generate", "schedule_add", "schedule_view", "general",
]

# ── GPT 설정 ──

SYSTEM_PROMPT = """당신은 한국어 사내 업무 보조 챗봇의 의도 분류기입니다.
사용자 입력을 아래 7개 카테고리 중 하나로 분류하세요.

- judgment: 사내 규정/법률 관련 질문 (연차, 수당, 징계, 겸직 등)
- doc_search: 기존 문서 검색/조회 (찾아줘, 양식, 템플릿 등)
- doc_generate: 새 문서 작성/생성 (작성해줘, 만들어줘, 초안 등)
- meeting_generate: 회의록 생성/정리 (회의 정리, 회의록, 미팅 요약 등)
- schedule_add: 일정 추가/예약 (잡아줘, 등록, 예약 등)
- schedule_view: 일정 조회/확인 (일정 알려줘, 뭐 있어, 비어있어 등)
- general: 일반 대화/인사/기타 (안녕, 고마워, 잡담 등)

반드시 카테고리 이름만 응답하세요. 다른 텍스트는 포함하지 마세요."""

FEW_SHOT_EXAMPLES = [
    {"role": "user", "content": "야근 수당 어떻게 신청하나요?"},
    {"role": "assistant", "content": "judgment"},
    {"role": "user", "content": "회사에서 부업 해도 되나요?"},
    {"role": "assistant", "content": "judgment"},
    {"role": "user", "content": "연차 며칠인지 알고 싶어요"},
    {"role": "assistant", "content": "judgment"},
    {"role": "user", "content": "작년 연말 보고서 있어?"},
    {"role": "assistant", "content": "doc_search"},
    {"role": "user", "content": "출장 신청서 양식 좀 찾아줘"},
    {"role": "assistant", "content": "doc_search"},
    {"role": "user", "content": "마케팅 기획서 검색해줘"},
    {"role": "assistant", "content": "doc_search"},
    {"role": "user", "content": "주간 업무 보고서 좀 써줘"},
    {"role": "assistant", "content": "doc_generate"},
    {"role": "user", "content": "프로젝트 완료 보고서 작성해줘"},
    {"role": "assistant", "content": "doc_generate"},
    {"role": "user", "content": "고객 제안서 새로 만들어줘"},
    {"role": "assistant", "content": "doc_generate"},
    {"role": "user", "content": "아까 팀 회의 내용 정리 좀"},
    {"role": "assistant", "content": "meeting_generate"},
    {"role": "user", "content": "월요일 스크럼 회의록 써줘"},
    {"role": "assistant", "content": "meeting_generate"},
    {"role": "user", "content": "지난주 리뷰 미팅 요약 부탁해"},
    {"role": "assistant", "content": "meeting_generate"},
    {"role": "user", "content": "수요일 오전에 면접 일정 넣어줘"},
    {"role": "assistant", "content": "schedule_add"},
    {"role": "user", "content": "다음 주 월요일 팀 회의 예약해"},
    {"role": "assistant", "content": "schedule_add"},
    {"role": "user", "content": "내일 오후 2시에 미팅 등록해줘"},
    {"role": "assistant", "content": "schedule_add"},
    {"role": "user", "content": "이번 주 금요일 일정 확인해줘"},
    {"role": "assistant", "content": "schedule_view"},
    {"role": "user", "content": "내일 오전에 뭐가 있지?"},
    {"role": "assistant", "content": "schedule_view"},
    {"role": "user", "content": "다음 달 일정 보여줘"},
    {"role": "assistant", "content": "schedule_view"},
    {"role": "user", "content": "오늘 날씨 어때?"},
    {"role": "assistant", "content": "general"},
    {"role": "user", "content": "점심 뭐 먹을까?"},
    {"role": "assistant", "content": "general"},
    {"role": "user", "content": "ㅎㅎ 재밌다"},
    {"role": "assistant", "content": "general"},
]


# ── 데이터 로드 ──

def load_adversarial():
    with open(DATA_DIR / "adversarial_test.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return [(d["text"], d["label"]) for d in data]


# ── GPT 분류 ──

def gpt_classify(client, text, mode="zero-shot"):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if mode == "few-shot":
        messages.extend(FEW_SHOT_EXAMPLES)
    messages.append({"role": "user", "content": text})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0,
        max_tokens=20,
    )
    result = response.choices[0].message.content.strip().lower()
    if result not in INTENT_LABELS:
        for label in INTENT_LABELS:
            if label in result:
                return label
        return "general"
    return result


# ── BERT 분류 ──

def load_bert_model():
    """BERT 모델 로드"""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    model_dir = MODEL_DIR
    if not (model_dir / "model.safetensors").exists():
        print(f"  [ERROR] 모델 파일 없음: {model_dir}")
        return None, None, None

    # 로컬 tokenizer_config.json의 tokenizer_class가 비정상이므로
    # 원본 klue/bert-base 토크나이저 사용 (학습 시 사용한 것과 동일)
    tokenizer = AutoTokenizer.from_pretrained("klue/bert-base")
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    model.eval()

    with open(model_dir / "label_map.json", "r", encoding="utf-8") as f:
        label_map = json.load(f)
    id2label = {int(k): v for k, v in label_map["id2label"].items()}

    return model, tokenizer, id2label


def bert_classify(model, tokenizer, id2label, text):
    """BERT 단일 문장 분류"""
    import torch

    inputs = tokenizer(
        text, return_tensors="pt", padding=True,
        truncation=True, max_length=128,
    )
    with torch.no_grad():
        outputs = model(**inputs)

    probs = torch.softmax(outputs.logits, dim=-1)
    pred_id = torch.argmax(probs, dim=-1).item()
    confidence = probs[0][pred_id].item()
    intent = id2label.get(pred_id, "general")

    return intent, confidence


# ── 평가 ──

def evaluate(preds, labels):
    from sklearn.metrics import f1_score, accuracy_score, classification_report

    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, average="macro", labels=INTENT_LABELS, zero_division=0)
    return acc, f1


def main():
    from sklearn.metrics import classification_report

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY 환경변수를 설정하세요.")
        return

    # 데이터 로드
    adv_data = load_adversarial()
    texts, labels = zip(*adv_data)
    print("=" * 70)
    print("  최종 비교: GPT vs BERT (실험6 전처리) — 212문장 Adversarial")
    print("=" * 70)
    print(f"  테스트셋: {len(adv_data)}문장")

    results = []

    # ── 1. BERT (전처리 없음) ──
    print("\n  [1/4] BERT Fine-tuned (전처리 없음)...")
    model, tokenizer, id2label = load_bert_model()
    if model is not None:
        preds_bert_raw = []
        t0 = time.time()
        for text in texts:
            intent, _ = bert_classify(model, tokenizer, id2label, text)
            preds_bert_raw.append(intent)
        elapsed_bert_raw = (time.time() - t0) * 1000

        acc, f1 = evaluate(preds_bert_raw, labels)
        results.append({
            "method": "BERT Fine-tuned (no preprocess)",
            "accuracy": round(acc, 4),
            "f1_macro": round(f1, 4),
            "time_ms": round(elapsed_bert_raw / len(texts), 2),
            "cost": "$0",
            "errors": sum(1 for p, l in zip(preds_bert_raw, labels) if p != l),
        })
        print(f"    F1={f1:.4f}  Acc={acc:.4f}  {elapsed_bert_raw/len(texts):.1f}ms/문장  오분류={results[-1]['errors']}건")

    # ── 2. BERT + 풀 전처리 (실험6) ──
    print("\n  [2/4] BERT Fine-tuned + 풀 전처리 (실험6 Config E)...")
    if model is not None:
        from ai.agents.preprocessing import preprocess

        preds_bert_pp = []
        t0 = time.time()
        for text in texts:
            processed = preprocess(text)
            intent, _ = bert_classify(model, tokenizer, id2label, processed)
            preds_bert_pp.append(intent)
        elapsed_bert_pp = (time.time() - t0) * 1000

        acc, f1 = evaluate(preds_bert_pp, labels)
        results.append({
            "method": "BERT Fine-tuned + Preprocess (Exp6)",
            "accuracy": round(acc, 4),
            "f1_macro": round(f1, 4),
            "time_ms": round(elapsed_bert_pp / len(texts), 2),
            "cost": "$0",
            "errors": sum(1 for p, l in zip(preds_bert_pp, labels) if p != l),
        })
        print(f"    F1={f1:.4f}  Acc={acc:.4f}  {elapsed_bert_pp/len(texts):.1f}ms/문장  오분류={results[-1]['errors']}건")

    # ── 3. GPT Zero-shot ──
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    print("\n  [3/4] GPT-4o-mini Zero-shot...")
    preds_gpt_zero = []
    t0 = time.time()
    for i, text in enumerate(texts):
        pred = gpt_classify(client, text, "zero-shot")
        preds_gpt_zero.append(pred)
        if (i + 1) % 20 == 0:
            print(f"    {i + 1}/{len(texts)}...")
    elapsed_gpt_zero = (time.time() - t0) * 1000

    acc, f1 = evaluate(preds_gpt_zero, labels)
    results.append({
        "method": "GPT-4o-mini Zero-shot",
        "accuracy": round(acc, 4),
        "f1_macro": round(f1, 4),
        "time_ms": round(elapsed_gpt_zero / len(texts), 2),
        "cost": f"~${len(texts) * 0.01 / 70:.3f}",
        "errors": sum(1 for p, l in zip(preds_gpt_zero, labels) if p != l),
    })
    print(f"    F1={f1:.4f}  Acc={acc:.4f}  {elapsed_gpt_zero/len(texts):.1f}ms/문장  오분류={results[-1]['errors']}건")

    # ── 4. GPT Few-shot ──
    print("\n  [4/4] GPT-4o-mini Few-shot...")
    preds_gpt_few = []
    t0 = time.time()
    for i, text in enumerate(texts):
        pred = gpt_classify(client, text, "few-shot")
        preds_gpt_few.append(pred)
        if (i + 1) % 20 == 0:
            print(f"    {i + 1}/{len(texts)}...")
    elapsed_gpt_few = (time.time() - t0) * 1000

    acc, f1 = evaluate(preds_gpt_few, labels)
    results.append({
        "method": "GPT-4o-mini Few-shot",
        "accuracy": round(acc, 4),
        "f1_macro": round(f1, 4),
        "time_ms": round(elapsed_gpt_few / len(texts), 2),
        "cost": f"~${len(texts) * 0.03 / 70:.3f}",
        "errors": sum(1 for p, l in zip(preds_gpt_few, labels) if p != l),
    })
    print(f"    F1={f1:.4f}  Acc={acc:.4f}  {elapsed_gpt_few/len(texts):.1f}ms/문장  오분류={results[-1]['errors']}건")

    # ── 결과 저장 ──
    print("\n" + "=" * 70)
    print("  최종 결과 비교")
    print("=" * 70)
    print(f"\n  {'방법':<42} {'F1':>7} {'Acc':>7} {'속도':>10} {'오분류':>6} {'비용':>8}")
    print("  " + "-" * 82)
    for r in sorted(results, key=lambda x: -x["f1_macro"]):
        print(f"  {r['method']:<42} {r['f1_macro']:>7.4f} {r['accuracy']:>7.4f} {r['time_ms']:>8.1f}ms {r['errors']:>5}건 {r['cost']:>8}")

    # 오분류 상세 (BERT vs GPT 차이 분석)
    if model is not None:
        print("\n" + "=" * 70)
        print("  오분류 상세 비교 (BERT+전처리 vs GPT Few-shot)")
        print("=" * 70)

        print("\n  [BERT+전처리만 틀린 것]")
        bert_only_errors = 0
        for text, label, bp, gp in zip(texts, labels, preds_bert_pp, preds_gpt_few):
            if bp != label and gp == label:
                bert_only_errors += 1
                if bert_only_errors <= 10:
                    print(f"    \"{text}\" → BERT:{bp} / GPT:{gp} / 정답:{label}")
        print(f"    총 {bert_only_errors}건")

        print("\n  [GPT Few-shot만 틀린 것]")
        gpt_only_errors = 0
        for text, label, bp, gp in zip(texts, labels, preds_bert_pp, preds_gpt_few):
            if gp != label and bp == label:
                gpt_only_errors += 1
                if gpt_only_errors <= 10:
                    print(f"    \"{text}\" → GPT:{gp} / BERT:{bp} / 정답:{label}")
        print(f"    총 {gpt_only_errors}건")

        print("\n  [둘 다 틀린 것]")
        both_errors = 0
        for text, label, bp, gp in zip(texts, labels, preds_bert_pp, preds_gpt_few):
            if bp != label and gp != label:
                both_errors += 1
                if both_errors <= 10:
                    print(f"    \"{text}\" → BERT:{bp} / GPT:{gp} / 정답:{label}")
        print(f"    총 {both_errors}건")

    # JSON 저장
    output_path = RESULTS_DIR / "final_comparison.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "test_set": "adversarial_212",
            "date": time.strftime("%Y-%m-%d %H:%M"),
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  -> {output_path}")

    # GPT 결과도 업데이트 (기존 gpt_comparison.json 갱신)
    gpt_results = [r for r in results if "GPT" in r["method"]]
    with open(RESULTS_DIR / "gpt_comparison.json", "w", encoding="utf-8") as f:
        json.dump(gpt_results, f, ensure_ascii=False, indent=2)
    print(f"  -> gpt_comparison.json (업데이트)")


if __name__ == "__main__":
    main()
