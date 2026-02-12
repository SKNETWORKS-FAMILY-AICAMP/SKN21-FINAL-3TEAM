"""
실험 1 (GPT 파트): GPT Zero-shot + Few-shot 비교

실행 (RunPod 또는 로컬):
    pip install openai
    export OPENAI_API_KEY='sk-...'
    python ai/experiments/run_gpt_comparison.py
"""

import json
import os
import time
from pathlib import Path
from openai import OpenAI
from sklearn.metrics import f1_score, accuracy_score

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "intent"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate",
    "meeting_generate", "schedule_add", "schedule_view", "general",
]

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

# Few-shot 예시 — adversarial_test.json과 겹치지 않는 문장만 사용
FEW_SHOT_EXAMPLES = [
    # judgment
    {"role": "user", "content": "야근 수당 어떻게 신청하나요?"},
    {"role": "assistant", "content": "judgment"},
    {"role": "user", "content": "회사에서 부업 해도 되나요?"},
    {"role": "assistant", "content": "judgment"},
    {"role": "user", "content": "연차 며칠인지 알고 싶어요"},
    {"role": "assistant", "content": "judgment"},
    # doc_search
    {"role": "user", "content": "작년 연말 보고서 있어?"},
    {"role": "assistant", "content": "doc_search"},
    {"role": "user", "content": "출장 신청서 양식 좀 찾아줘"},
    {"role": "assistant", "content": "doc_search"},
    {"role": "user", "content": "마케팅 기획서 검색해줘"},
    {"role": "assistant", "content": "doc_search"},
    # doc_generate
    {"role": "user", "content": "주간 업무 보고서 좀 써줘"},
    {"role": "assistant", "content": "doc_generate"},
    {"role": "user", "content": "프로젝트 완료 보고서 작성해줘"},
    {"role": "assistant", "content": "doc_generate"},
    {"role": "user", "content": "고객 제안서 새로 만들어줘"},
    {"role": "assistant", "content": "doc_generate"},
    # meeting_generate
    {"role": "user", "content": "아까 팀 회의 내용 정리 좀"},
    {"role": "assistant", "content": "meeting_generate"},
    {"role": "user", "content": "월요일 스크럼 회의록 써줘"},
    {"role": "assistant", "content": "meeting_generate"},
    {"role": "user", "content": "지난주 리뷰 미팅 요약 부탁해"},
    {"role": "assistant", "content": "meeting_generate"},
    # schedule_add
    {"role": "user", "content": "수요일 오전에 면접 일정 넣어줘"},
    {"role": "assistant", "content": "schedule_add"},
    {"role": "user", "content": "다음 주 월요일 팀 회의 예약해"},
    {"role": "assistant", "content": "schedule_add"},
    {"role": "user", "content": "내일 오후 2시에 미팅 등록해줘"},
    {"role": "assistant", "content": "schedule_add"},
    # schedule_view
    {"role": "user", "content": "이번 주 금요일 일정 확인해줘"},
    {"role": "assistant", "content": "schedule_view"},
    {"role": "user", "content": "내일 오전에 뭐가 있지?"},
    {"role": "assistant", "content": "schedule_view"},
    {"role": "user", "content": "다음 달 일정 보여줘"},
    {"role": "assistant", "content": "schedule_view"},
    # general
    {"role": "user", "content": "오늘 날씨 어때?"},
    {"role": "assistant", "content": "general"},
    {"role": "user", "content": "점심 뭐 먹을까?"},
    {"role": "assistant", "content": "general"},
    {"role": "user", "content": "ㅎㅎ 재밌다"},
    {"role": "assistant", "content": "general"},
]


def load_adversarial():
    with open(DATA_DIR / "adversarial_test.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return [(d["text"], d["label"]) for d in data]


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
    # 혹시 카테고리 외 텍스트가 오면 fallback
    if result not in INTENT_LABELS:
        # "doc_search." 같은 경우 처리
        for label in INTENT_LABELS:
            if label in result:
                return label
        return "general"
    return result


def evaluate(name, preds, labels):
    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, average="macro", labels=INTENT_LABELS, zero_division=0)
    return {"method": name, "accuracy": round(acc, 4), "f1_macro": round(f1, 4)}


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY 환경변수를 설정하세요.")
        print("  export OPENAI_API_KEY='sk-...'")
        return

    client = OpenAI(api_key=api_key)

    print("=" * 60)
    print("  실험 1 (GPT): Zero-shot / Few-shot 비교")
    print("=" * 60)

    adv_data = load_adversarial()
    texts, labels = zip(*adv_data)
    print(f"\n  테스트셋: {len(adv_data)}문장")

    results = []

    for mode in ["zero-shot", "few-shot"]:
        name = f"GPT {'Zero-shot' if mode == 'zero-shot' else 'Few-shot'}"
        print(f"\n  [{mode}] 실행 중...")

        preds = []
        t0 = time.time()
        for i, text in enumerate(texts):
            pred = gpt_classify(client, text, mode)
            preds.append(pred)
            if (i + 1) % 10 == 0:
                print(f"    {i + 1}/{len(texts)}...")
        elapsed = (time.time() - t0) * 1000

        r = evaluate(name, preds, labels)
        r["time_ms"] = round(elapsed / len(texts), 2)
        r["cost"] = f"~${0.01 if mode == 'zero-shot' else 0.03}"
        results.append(r)
        print(f"    F1={r['f1_macro']}  Acc={r['accuracy']}  {r['time_ms']}ms/문장")

    with open(RESULTS_DIR / "gpt_comparison.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  -> gpt_comparison.json")
    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    main()
