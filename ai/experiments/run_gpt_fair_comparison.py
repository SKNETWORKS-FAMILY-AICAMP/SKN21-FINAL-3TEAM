"""
GPT Adversarial Few-shot 공정 비교 (제안 3)

기존 실험 7에서 GPT few-shot이 일반적인 예시만 사용했던 한계를 보완.
초성, 1어절, 복합의도, 격식체 등 adversarial 패턴을 포함한 few-shot으로 재비교.

사용법:
    export OPENAI_API_KEY='sk-...'
    python ai/experiments/run_gpt_fair_comparison.py
"""

import json
import os
import sys
import time
import torch
from pathlib import Path
from sklearn.metrics import accuracy_score, f1_score, classification_report

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

# ── GPT 설정 (개선된 프롬프트) ──

SYSTEM_PROMPT_V2 = """당신은 한국어 사내 업무 보조 챗봇의 의도 분류기입니다.
사용자 입력을 아래 7개 카테고리 중 하나로 분류하세요.

- judgment: 사내 규정/법률 기반 판단 요청 (연차, 수당, 징계, 겸직, 해고 등의 가부 판단)
- doc_search: 기존 문서 검색/조회 (찾아줘, 양식, 템플릿, 보여줘 등)
- doc_generate: 새 문서 작성/생성 (작성해줘, 만들어줘, 초안, 써줘 등)
- meeting_generate: 회의록 생성/정리 (회의 정리, 회의록, 미팅 요약 등)
- schedule_add: 일정 추가/예약 (잡아줘, 등록, 예약, 넣어줘 등)
- schedule_view: 일정 조회/확인 (알려줘, 뭐 있어, 비어있어, 확인 등)
- general: 일반 대화/인사/기타 (안녕, 고마워, 잡담, 감정 표현 등)

분류 규칙:
- 복합 의도 시 최종 목적을 기준으로 분류 (예: "규정 찾아서 판단해줘" → judgment)
- 1~2어절의 짧은 입력도 키워드 기반으로 분류 (예: "규정" → doc_search, "회의록" → meeting_generate)
- 초성/오타/슬랭도 의미를 파악하여 분류 (예: "ㅎㅇㄹ" → 회의록 → meeting_generate)
- 감정 표현이나 일상 대화는 general

반드시 카테고리 이름만 응답하세요."""

# 기존 일반 few-shot (실험 7에서 사용)
ORIGINAL_FEW_SHOT = [
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

# 개선된 adversarial few-shot (일반 + adversarial 패턴 포함)
ADVERSARIAL_FEW_SHOT = [
    # 일반 예시 (카테고리별 2개)
    {"role": "user", "content": "야근 수당 어떻게 신청하나요?"},
    {"role": "assistant", "content": "judgment"},
    {"role": "user", "content": "작년 연말 보고서 있어?"},
    {"role": "assistant", "content": "doc_search"},
    {"role": "user", "content": "주간 업무 보고서 좀 써줘"},
    {"role": "assistant", "content": "doc_generate"},
    {"role": "user", "content": "아까 팀 회의 내용 정리 좀"},
    {"role": "assistant", "content": "meeting_generate"},
    {"role": "user", "content": "수요일 오전에 면접 일정 넣어줘"},
    {"role": "assistant", "content": "schedule_add"},
    {"role": "user", "content": "이번 주 금요일 일정 확인해줘"},
    {"role": "assistant", "content": "schedule_view"},
    {"role": "user", "content": "오늘 날씨 어때?"},
    {"role": "assistant", "content": "general"},

    # Adversarial 패턴: 1어절
    {"role": "user", "content": "규정"},
    {"role": "assistant", "content": "doc_search"},
    {"role": "user", "content": "회의록"},
    {"role": "assistant", "content": "meeting_generate"},
    {"role": "user", "content": "일정"},
    {"role": "assistant", "content": "schedule_view"},

    # Adversarial 패턴: 초성/비정형
    {"role": "user", "content": "ㅎㅇㄹ 정리해줘"},
    {"role": "assistant", "content": "meeting_generate"},
    {"role": "user", "content": "연챠 쓸 수 있어?"},
    {"role": "assistant", "content": "judgment"},

    # Adversarial 패턴: 복합 의도
    {"role": "user", "content": "규정 검색해서 위반 여부 판단해줘"},
    {"role": "assistant", "content": "judgment"},
    {"role": "user", "content": "지난 회의록 찾아서 후속 회의록 작성해줘"},
    {"role": "assistant", "content": "meeting_generate"},

    # Adversarial 패턴: 경계
    {"role": "user", "content": "회사가 부당해요"},
    {"role": "assistant", "content": "judgment"},
    {"role": "user", "content": "야근하기 싫다"},
    {"role": "assistant", "content": "general"},

    # Adversarial 패턴: 격식체
    {"role": "user", "content": "해당 규정에 대한 판단을 요청드립니다"},
    {"role": "assistant", "content": "judgment"},
    {"role": "user", "content": "금주 일정을 확인해 주시겠습니까?"},
    {"role": "assistant", "content": "schedule_view"},
]


def load_adversarial():
    with open(DATA_DIR / "adversarial_test.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return [(d["text"], d["label"]) for d in data]


def gpt_classify(client, text, system_prompt, few_shot):
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(few_shot)
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


def bert_classify(model, tokenizer, id2label, text):
    from ai.agents.preprocessing import preprocess
    text = preprocess(text)

    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=64)
    with torch.no_grad():
        outputs = model(**inputs)
    probs = torch.softmax(outputs.logits, dim=-1)
    pred_id = torch.argmax(probs, dim=-1).item()
    return id2label.get(pred_id, "general")


def evaluate(preds, labels):
    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, average="macro", labels=INTENT_LABELS, zero_division=0)
    return acc, f1


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY 환경변수를 설정하세요.")
        print("  export OPENAI_API_KEY='sk-...'")
        return

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    adv_data = load_adversarial()
    texts, labels = zip(*adv_data)

    print("=" * 70)
    print("  GPT 공정 비교: 기존 vs Adversarial Few-shot (212문장)")
    print("=" * 70)
    print(f"  테스트셋: {len(adv_data)}문장")

    results = []

    # ── 1. BERT + 전처리 (baseline) ──
    print("\n  [1/4] BERT + 전처리 (baseline)...")
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained("klue/bert-base")
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    model.eval()
    with open(MODEL_DIR / "label_map.json", "r", encoding="utf-8") as f:
        label_map = json.load(f)
    id2label = {int(k): v for k, v in label_map["id2label"].items()}

    preds_bert = []
    t0 = time.time()
    for text in texts:
        preds_bert.append(bert_classify(model, tokenizer, id2label, text))
    elapsed_bert = (time.time() - t0) * 1000
    acc, f1 = evaluate(preds_bert, labels)
    results.append({
        "method": "BERT + Preprocess",
        "f1_macro": round(f1, 4), "accuracy": round(acc, 4),
        "time_ms": round(elapsed_bert / len(texts), 2), "cost": "$0",
        "errors": sum(1 for p, l in zip(preds_bert, labels) if p != l),
    })
    print(f"    F1={f1:.4f}  Acc={acc:.4f}  오분류={results[-1]['errors']}건")

    # ── 2. GPT 기존 few-shot (실험 7과 동일) ──
    print("\n  [2/4] GPT Few-shot (기존, 일반 예시 21문장)...")
    preds_gpt_orig = []
    t0 = time.time()
    for i, text in enumerate(texts):
        preds_gpt_orig.append(gpt_classify(client, text, SYSTEM_PROMPT_V2, ORIGINAL_FEW_SHOT))
        if (i + 1) % 20 == 0:
            print(f"    {i + 1}/{len(texts)}...")
    elapsed = (time.time() - t0) * 1000
    acc, f1 = evaluate(preds_gpt_orig, labels)
    results.append({
        "method": "GPT Few-shot (original)",
        "f1_macro": round(f1, 4), "accuracy": round(acc, 4),
        "time_ms": round(elapsed / len(texts), 2),
        "cost": f"~${len(texts) * 0.03 / 70:.3f}",
        "errors": sum(1 for p, l in zip(preds_gpt_orig, labels) if p != l),
    })
    print(f"    F1={f1:.4f}  Acc={acc:.4f}  오분류={results[-1]['errors']}건")

    # ── 3. GPT adversarial few-shot (개선) ──
    print("\n  [3/4] GPT Few-shot (adversarial 패턴 포함)...")
    preds_gpt_adv = []
    t0 = time.time()
    for i, text in enumerate(texts):
        preds_gpt_adv.append(gpt_classify(client, text, SYSTEM_PROMPT_V2, ADVERSARIAL_FEW_SHOT))
        if (i + 1) % 20 == 0:
            print(f"    {i + 1}/{len(texts)}...")
    elapsed = (time.time() - t0) * 1000
    acc, f1 = evaluate(preds_gpt_adv, labels)
    results.append({
        "method": "GPT Few-shot (adversarial)",
        "f1_macro": round(f1, 4), "accuracy": round(acc, 4),
        "time_ms": round(elapsed / len(texts), 2),
        "cost": f"~${len(texts) * 0.03 / 70:.3f}",
        "errors": sum(1 for p, l in zip(preds_gpt_adv, labels) if p != l),
    })
    print(f"    F1={f1:.4f}  Acc={acc:.4f}  오분류={results[-1]['errors']}건")

    # ── 4. GPT adversarial few-shot + 개선 프롬프트 ──
    print("\n  [4/4] GPT Zero-shot (개선 프롬프트)...")
    preds_gpt_v2 = []
    t0 = time.time()
    for i, text in enumerate(texts):
        preds_gpt_v2.append(gpt_classify(client, text, SYSTEM_PROMPT_V2, []))
        if (i + 1) % 20 == 0:
            print(f"    {i + 1}/{len(texts)}...")
    elapsed = (time.time() - t0) * 1000
    acc, f1 = evaluate(preds_gpt_v2, labels)
    results.append({
        "method": "GPT Zero-shot (improved prompt)",
        "f1_macro": round(f1, 4), "accuracy": round(acc, 4),
        "time_ms": round(elapsed / len(texts), 2),
        "cost": f"~${len(texts) * 0.01 / 70:.3f}",
        "errors": sum(1 for p, l in zip(preds_gpt_v2, labels) if p != l),
    })
    print(f"    F1={f1:.4f}  Acc={acc:.4f}  오분류={results[-1]['errors']}건")

    # ── 결과 요약 ──
    print(f"\n{'='*70}")
    print("  최종 결과 비교")
    print(f"{'='*70}")
    print(f"\n  {'방법':<42} {'F1':>7} {'Acc':>7} {'오분류':>6}")
    print(f"  {'-'*64}")
    for r in sorted(results, key=lambda x: -x["f1_macro"]):
        print(f"  {r['method']:<42} {r['f1_macro']:>7.4f} {r['accuracy']:>7.4f} {r['errors']:>5}건")

    # 개선 효과
    orig = next(r for r in results if "original" in r["method"])
    adv = next(r for r in results if "adversarial" in r["method"])
    bert = next(r for r in results if "BERT" in r["method"])
    delta = adv["f1_macro"] - orig["f1_macro"]
    print(f"\n  GPT few-shot 개선 효과: {orig['f1_macro']:.4f} → {adv['f1_macro']:.4f} ({'+' if delta>=0 else ''}{delta:.4f})")
    print(f"  BERT vs GPT(adversarial): {bert['f1_macro']:.4f} vs {adv['f1_macro']:.4f} "
          f"({'BERT 우위' if bert['f1_macro'] > adv['f1_macro'] else 'GPT 우위'} "
          f"{abs(bert['f1_macro'] - adv['f1_macro']):.4f})")

    # 오분류 비교 (GPT 개선 후에도 틀리는 것 vs 개선된 것)
    print(f"\n{'='*70}")
    print("  GPT 기존 → adversarial 개선 상세")
    print(f"{'='*70}")

    improved = 0
    regressed = 0
    for text, label, orig_p, adv_p in zip(texts, labels, preds_gpt_orig, preds_gpt_adv):
        if orig_p != label and adv_p == label:
            improved += 1
        elif orig_p == label and adv_p != label:
            regressed += 1

    print(f"  개선된 것: {improved}건 (기존 틀렸으나 이제 맞음)")
    print(f"  악화된 것: {regressed}건 (기존 맞았으나 이제 틀림)")
    print(f"  순 개선: {improved - regressed}건")

    # JSON 저장
    output = {
        "test_set": "adversarial_212",
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "experiment": "fair_comparison",
        "results": results,
        "gpt_improvement": {
            "improved": improved,
            "regressed": regressed,
            "net": improved - regressed,
        },
    }
    output_path = RESULTS_DIR / "gpt_fair_comparison.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  -> {output_path}")

    print(f"\n{'='*70}")
    print("  GPT 공정 비교 완료!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
