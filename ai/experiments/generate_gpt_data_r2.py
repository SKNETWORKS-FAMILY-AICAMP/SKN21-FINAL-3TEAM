"""
GPT 기반 학습 데이터 생성 — Round 2 (오답 패턴 타겟 보강)

Held-out 오답 12건 분석 → 5가지 약점 패턴에 집중:
  1. doc_qa 과잉 트리거 방지 (5건) — "알려줘/확인해줘"가 doc_qa가 아닌 단일 intent
  2. doc_search↔doc_qa 혼동 방지 (3건) — "~에서 ~부분" = doc_search, not doc_qa
  3. 2번째 intent 누락 방지 (3건) — "내용으로 보고서 만들어줘" = doc_generate+doc_qa
  4. judgment 과잉 트리거 방지 (1건) — "분석/검토" ≠ judgment
  5. doc_search↔doc_generate 구분 (1건) — "찾아줘" vs "만들어줘"

사용법 (RunPod):
  export OPENAI_API_KEY=sk-...
  python -m ai.experiments.generate_gpt_data_r2
"""

import argparse
import asyncio
import json
import os
import random
from pathlib import Path
from collections import Counter

random.seed(43)

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "data" / "training" / "intent_multilabel"

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_search",
]

# ── GPT 호출 ──────────────────────────────────────────────────────────────────

async def call_gpt(prompt, api_key, model="gpt-4o-mini", temperature=0.9):
    from openai import AsyncOpenAI
    import re

    client = AsyncOpenAI(api_key=api_key)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=4096,
        )
        content = response.choices[0].message.content.strip()

        if content.startswith("```"):
            match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
            if match:
                content = match.group(1).strip()

        return json.loads(content)

    except Exception as e:
        print(f"  GPT 오류: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# 패턴 1: doc_qa 과잉 트리거 방지 — "알려줘/확인해줘" 단일 intent
# ══════════════════════════════════════════════════════════════════════════════

FALSE_POSITIVE_DOC_QA_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

아래는 intent 분류 모델이 **doc_qa로 잘못 분류하는 패턴**입니다.
이런 패턴의 학습 데이터를 만들어서 모델이 올바르게 분류하도록 교정해야 합니다.

## 핵심 규칙:
- "알려줘", "확인해줘", "보여줘" 같은 동사는 doc_qa가 아닐 수 있음
- doc_qa는 **문서 내용에 대한 구체적 질문** (금액, 날짜, 수치, 담당자 등 추출)
- 아래 패턴은 doc_qa가 **아닌** 것들:

## 올바른 분류 예시:
- "관련 자료 조회해서 알려줘" → doc_search (문서를 찾는 것)
- "다음 주 회의 중에 참석 가능한 거 골라줘" → schedule_view (일정 확인)
- "모레 미팅 시간이랑 참석자 알려줘" → schedule_view (일정 정보)
- "검토해서 빠진 거 없는지 확인해줘" → doc_search (문서 확인)
- "출장비 규정 찾아서 정리해줘" → doc_search (문서 검색)
- "인사 규정 열어줘" → doc_search (문서 검색)

{intent_type}에 해당하는 문장을 {n}개 만들어주세요.
"알려줘/확인해줘/보여줘/골라줘" 같은 동사가 포함되지만, doc_qa가 **아닌** 문장입니다.

## 응답 형식 (JSON 배열):
[
  {{"text": "문장", "labels": ["정확한_intent"]}},
  ...
]

다양한 주제, 다양한 표현으로 만들어주세요. JSON 배열만 응답하세요."""

FALSE_POS_DOC_QA_TYPES = [
    {
        "intent_type": "doc_search 단일 (문서를 찾는/조회하는 요청 — '알려줘/보여줘/확인해줘' 포함)",
        "expected_label": "doc_search",
    },
    {
        "intent_type": "schedule_view 단일 (일정/시간/참석자 확인 요청 — '알려줘/확인해줘/골라줘' 포함)",
        "expected_label": "schedule_view",
    },
    {
        "intent_type": "doc_summary 단일 (요약/정리 요청 — '알려줘/정리해줘' 포함)",
        "expected_label": "doc_summary",
    },
    {
        "intent_type": "judgment 단일 (판단/위반여부 요청 — '확인해줘/알려줘' 포함)",
        "expected_label": "judgment",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# 패턴 2: doc_search+X 복합 (doc_qa가 아닌 복합)
# ══════════════════════════════════════════════════════════════════════════════

DOC_SEARCH_COMPOUND_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

모델이 doc_search를 doc_qa로 혼동하는 문제가 있습니다.
**doc_search + {other_intent}** 복합 질문을 {n}개 만들어주세요.

## doc_search vs doc_qa 차이:
- doc_search: 문서/규정 **자체를 찾기** ("~규정 찾아줘", "~에서 ~부분 보여줘", "~문서 어디 있어")
- doc_qa: 이미 알고 있는 문서에서 **특정 정보 추출** ("~얼마야", "~몇 퍼센트야", "~담당자가 누구야")

## doc_search + {other_intent} 예시:
{examples}

## 규칙:
1. 반드시 doc_search + {other_intent} 두 가지 intent만 포함
2. doc_qa는 포함하지 않음
3. "~에서 ~부분", "~규정 찾아서", "~문서 보면서" 같은 doc_search 표현 사용
4. 자연스러운 구어체, 다양한 주제
5. 접속사 없이 자연스럽게 두 의도를 녹여내는 문장 포함

## 응답 형식 (JSON 배열):
[
  "문장1",
  "문장2",
  ...
]

JSON 배열만 응답하세요."""

DOC_SEARCH_COMPOUND_CONFIGS = [
    {
        "other_intent": "doc_summary",
        "labels": ["doc_search", "doc_summary"],
        "examples": '- "취업규칙에서 징계 관련 부분 요약 좀" → doc_search + doc_summary\n- "복리후생 규정 찾아서 핵심만 정리해줘" → doc_search + doc_summary\n- "사내 교육 가이드 열어서 주요 내용 뽑아줘" → doc_search + doc_summary',
    },
    {
        "other_intent": "judgment",
        "labels": ["doc_search", "judgment"],
        "examples": '- "관련 조항 찾아주고 이번 건에 해당되는지 봐줘" → doc_search + judgment\n- "징계 규정 찾아서 이 경우 위반인지 확인해줘" → doc_search + judgment\n- "출장비 기준 찾아주고 이번 건 가능한지도" → doc_search + judgment',
    },
    {
        "other_intent": "doc_generate",
        "labels": ["doc_search", "doc_generate"],
        "examples": '- "관련 규정 찾아서 보고서 양식으로 정리해줘" → doc_search + doc_generate\n- "출장 규정 보면서 출장 보고서 작성해줘" → doc_search + doc_generate',
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# 패턴 3: doc_generate+doc_qa 복합 (2번째 intent 누락 방지)
# ══════════════════════════════════════════════════════════════════════════════

SECOND_INTENT_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

모델이 **두 번째 intent를 놓치는** 문제가 있습니다.
아래 조합의 복합 질문을 {n}개 만들어주세요. 두 intent가 모두 분명하게 포함되어야 합니다.

## 조합: {intent1} + {intent2}

## 핵심 패턴:
{patterns}

## 규칙:
1. 두 intent가 모두 **분명하게** 드러나야 함 (하나가 숨지 않도록)
2. "~내용으로", "~결과를 바탕으로", "~확인하고" 같은 연결 패턴 적극 활용
3. 자연스러운 구어체, 다양한 주제
4. 짧은 문장(15~25자)부터 긴 문장(40~60자)까지 다양하게

## 응답 형식 (JSON 배열):
[
  "문장1",
  "문장2",
  ...
]

JSON 배열만 응답하세요."""

SECOND_INTENT_CONFIGS = [
    {
        "intent1": "doc_generate",
        "intent2": "doc_search",
        "labels": ["doc_generate", "doc_search"],
        "patterns": '- "기획안 내용으로 보고서 만들어줘" → 기획안 내용 확인(doc_qa) + 보고서 작성(doc_generate)\n- "실적 보고서 내용으로 월간 리뷰 만들어줘" → 실적 확인(doc_qa) + 리뷰 작성(doc_generate)\n- "계약서에서 조건 확인하고 요약 보고서 써줘" → 조건 확인(doc_qa) + 보고서 작성(doc_generate)',
    },
    {
        "intent1": "doc_generate",
        "intent2": "doc_summary",
        "labels": ["doc_generate", "doc_summary"],
        "patterns": '- "회의 결과 요약하고 보고서에 반영해줘" → 회의 요약(doc_summary) + 보고서 작성(doc_generate)\n- "지난 자료 핵심 정리해서 제안서 만들어줘" → 자료 정리(doc_summary) + 제안서 작성(doc_generate)',
    },
    {
        "intent1": "doc_search",
        "intent2": "doc_search",
        "labels": ["doc_search", "doc_search"],
        "patterns": '- "휴가 규정 찾아서 연차 몇 일인지 알려줘" → 규정 찾기(doc_search) + 일수 확인(doc_qa)\n- "경비 처리 기준 찾아주고 상한선이 얼마인지도" → 기준 찾기(doc_search) + 금액 확인(doc_qa)',
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# 패턴 4: judgment 과잉 트리거 방지
# ══════════════════════════════════════════════════════════════════════════════

FALSE_POS_JUDGMENT_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

모델이 "분석", "검토", "확인" 같은 단어를 보면 judgment로 잘못 분류하는 문제가 있습니다.

## judgment vs 기타 intent 구분:
- judgment: **규정 위반 여부**, **가능/불가능**, **적법성** 판단 → "위반인지", "가능한지", "합법인지"
- doc_search: 문서 검토/분석/확인 → "규정 분석해서 정리해줘", "문서 검토해줘"
- doc_summary: 내용 분석/정리 → "보고서 분석해서 요약해줘"

## judgment가 아닌 예시:
- "인사 규정을 분석해서 정리해줘" → doc_search (규정을 찾아서 정리하는 것)
- "출장비 규정을 검토해서 정리해줘" → doc_search
- "보고서 내용 분석해줘" → doc_summary
- "계약서 검토해서 빠진 거 확인해줘" → doc_search

{label_type}에 해당하는 문장을 {n}개 만들어주세요.
"분석/검토/확인/살펴보기" 같은 단어가 포함되지만, judgment가 **아닌** 문장입니다.

## 응답 형식 (JSON 배열):
[
  {{"text": "문장", "labels": ["정확한_intent"]}},
  ...
]

JSON 배열만 응답하세요."""

FALSE_POS_JUDGMENT_TYPES = [
    {"label_type": "doc_search 단일 (문서를 검토/분석/확인하는 요청)", "expected_label": "doc_search"},
    {"label_type": "doc_summary 단일 (내용을 분석/검토하여 정리/요약하는 요청)", "expected_label": "doc_summary"},
]


# ══════════════════════════════════════════════════════════════════════════════
# 패턴 5: doc_search vs doc_generate 구분
# ══════════════════════════════════════════════════════════════════════════════

SEARCH_VS_GENERATE_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

모델이 "보고서", "문서" 같은 단어를 보면 doc_generate로 분류하는 경향이 있습니다.
하지만 **기존 문서를 찾는 것**은 doc_search입니다.

## 구분 기준:
- doc_search: **이미 존재하는** 문서를 찾기/검색/조회 → "찾아줘", "어디 있어", "보여줘"
- doc_generate: **새로운** 문서를 만들기/작성/생성 → "만들어줘", "작성해줘", "써줘"

## doc_search 예시 (기존 문서 찾기):
- "상반기 보고서 찾아줘" → doc_search
- "월간 보고서 어디 있어" → doc_search
- "지난 회의록 보여줘" → doc_search
- "제안서 파일 찾아줘" → doc_search

{category}에 해당하는 문장을 {n}개 만들어주세요.

## 응답 형식 (JSON 배열):
[
  {{"text": "문장", "labels": ["{label}"]}},
  ...
]

JSON 배열만 응답하세요."""


# ══════════════════════════════════════════════════════════════════════════════
# 메인 실행
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-4o-mini")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("OPENAI_API_KEY 환경변수를 설정하세요")
        return

    print("GPT Round 2 — Held-out 오답 패턴 타겟 보강")
    print(f"모델: {args.model}")
    print("=" * 60)

    all_data = []
    semaphore = asyncio.Semaphore(3)

    # ── 패턴 1: doc_qa 과잉 트리거 방지 (4종 × 20개 = 80개) ──
    print("\n[1/5] doc_qa 과잉 트리거 방지 (단일 intent인데 doc_qa로 오분류되는 패턴)...")
    for cfg in FALSE_POS_DOC_QA_TYPES:
        async with semaphore:
            prompt = FALSE_POSITIVE_DOC_QA_PROMPT.format(
                intent_type=cfg["intent_type"], n=20
            )
            results = await call_gpt(prompt, api_key, args.model)
            count = 0
            for item in results:
                if isinstance(item, dict) and "text" in item and "labels" in item:
                    valid_labels = [l for l in item["labels"] if l in INTENT_LABELS]
                    if valid_labels and "doc_search" not in valid_labels:
                        all_data.append({"text": item["text"].strip(), "labels": sorted(valid_labels)})
                        count += 1
            print(f"  [{cfg['expected_label']} — doc_qa 아님] {count}개 생성")

    # ── 패턴 2: doc_search+X 복합 (doc_qa 아닌 복합) (3종 × 20개 = 60개) ──
    print("\n[2/5] doc_search+X 복합 (doc_qa가 아닌 조합)...")
    for cfg in DOC_SEARCH_COMPOUND_CONFIGS:
        async with semaphore:
            prompt = DOC_SEARCH_COMPOUND_PROMPT.format(
                other_intent=cfg["other_intent"], n=20,
                examples=cfg["examples"],
            )
            results = await call_gpt(prompt, api_key, args.model)
            count = 0
            for text in results:
                if isinstance(text, str) and len(text) >= 5:
                    all_data.append({"text": text.strip(), "labels": sorted(cfg["labels"])})
                    count += 1
            print(f"  [doc_search+{cfg['other_intent']}] {count}개 생성")

    # ── 패턴 3: 2번째 intent 누락 방지 (3종 × 20개 = 60개) ──
    print("\n[3/5] 2번째 intent 누락 방지 (복합인데 하나만 잡히는 패턴)...")
    for cfg in SECOND_INTENT_CONFIGS:
        async with semaphore:
            prompt = SECOND_INTENT_PROMPT.format(
                n=20,
                intent1=cfg["intent1"], intent2=cfg["intent2"],
                patterns=cfg["patterns"],
            )
            results = await call_gpt(prompt, api_key, args.model)
            count = 0
            for text in results:
                if isinstance(text, str) and len(text) >= 5:
                    all_data.append({"text": text.strip(), "labels": sorted(cfg["labels"])})
                    count += 1
            print(f"  [{cfg['intent1']}+{cfg['intent2']}] {count}개 생성")

    # ── 패턴 4: judgment 과잉 트리거 방지 (2종 × 20개 = 40개) ──
    print("\n[4/5] judgment 과잉 트리거 방지 (분석/검토 ≠ judgment)...")
    for cfg in FALSE_POS_JUDGMENT_TYPES:
        async with semaphore:
            prompt = FALSE_POS_JUDGMENT_PROMPT.format(
                label_type=cfg["label_type"], n=20
            )
            results = await call_gpt(prompt, api_key, args.model)
            count = 0
            for item in results:
                if isinstance(item, dict) and "text" in item and "labels" in item:
                    valid_labels = [l for l in item["labels"] if l in INTENT_LABELS]
                    if valid_labels and "judgment" not in valid_labels:
                        all_data.append({"text": item["text"].strip(), "labels": sorted(valid_labels)})
                        count += 1
            print(f"  [{cfg['expected_label']} — judgment 아님] {count}개 생성")

    # ── 패턴 5: doc_search vs doc_generate 구분 (2종 × 20개 = 40개) ──
    print("\n[5/5] doc_search vs doc_generate 구분...")
    for category, label in [
        ("doc_search 단일 — 기존 문서/보고서/회의록을 찾기/검색/조회하는 요청. '보고서', '회의록' 같은 단어가 있지만 새로 만드는 것이 아님", "doc_search"),
        ("doc_generate 단일 — 새로운 문서/보고서/회의록을 만들기/작성/생성하는 요청. '보고서', '회의록' 같은 단어가 있고 새로 만드는 것", "doc_generate"),
    ]:
        async with semaphore:
            prompt = SEARCH_VS_GENERATE_PROMPT.format(
                category=category, n=20, label=label
            )
            results = await call_gpt(prompt, api_key, args.model)
            count = 0
            for item in results:
                if isinstance(item, dict) and "text" in item and "labels" in item:
                    valid_labels = [l for l in item["labels"] if l in INTENT_LABELS]
                    if valid_labels:
                        all_data.append({"text": item["text"].strip(), "labels": sorted(valid_labels)})
                        count += 1
            print(f"  [{label}] {count}개 생성")

    # ── 중복 제거 ──
    seen = set()
    unique_data = []
    for item in all_data:
        text = item["text"].strip()
        if text not in seen:
            seen.add(text)
            unique_data.append(item)
    all_data = unique_data

    # ── 통계 출력 ──
    print(f"\n{'='*60}")
    print(f"Round 2 GPT 생성 합계: {len(all_data)}개")

    label_counts = Counter()
    for item in all_data:
        for label in item["labels"]:
            label_counts[label] += 1

    n_single = sum(1 for d in all_data if len(d["labels"]) == 1)
    n_multi = sum(1 for d in all_data if len(d["labels"]) >= 2)

    print(f"  단일: {n_single}개, 복합: {n_multi}개")
    print(f"\n  Intent별 출현:")
    for label in INTENT_LABELS:
        bar = "█" * (label_counts.get(label, 0) // 3)
        print(f"    {label:<16} {label_counts.get(label, 0):4d}  {bar}")

    # ── 저장 ──
    r2_path = OUT_DIR / "gpt_generated_r2.jsonl"
    with open(r2_path, "w", encoding="utf-8") as f:
        for item in all_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"\n저장: {r2_path} ({len(all_data)}개)")

    # ── 기존 train/val/test에 합치기 ──
    print(f"\n{'='*60}")
    print("기존 데이터와 합치기...")

    existing_train = []
    with open(OUT_DIR / "train.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                existing_train.append(json.loads(line))

    # 기존 데이터에서 중복 제거
    existing_texts = {d["text"].strip() for d in existing_train}
    new_data = [d for d in all_data if d["text"].strip() not in existing_texts]

    print(f"  기존 train: {len(existing_train)}개")
    print(f"  R2 신규 (중복 제거 후): {len(new_data)}개")

    # 80/10/10 분할
    random.shuffle(new_data)
    n = len(new_data)
    n_train = int(n * 0.8)
    n_val = int(n * 0.1)
    r2_train = new_data[:n_train]
    r2_val = new_data[n_train:n_train + n_val]
    r2_test = new_data[n_train + n_val:]

    # 합치기
    merged_train = existing_train + r2_train
    random.shuffle(merged_train)

    existing_val = []
    with open(OUT_DIR / "val.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                existing_val.append(json.loads(line))
    merged_val = existing_val + r2_val

    existing_test = []
    with open(OUT_DIR / "test.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                existing_test.append(json.loads(line))
    merged_test = existing_test + r2_test

    # 저장
    for name, data in [("train", merged_train), ("val", merged_val), ("test", merged_test)]:
        path = OUT_DIR / f"{name}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"  -> {name}.jsonl: {len(data)}개 저장")

    # 최종 통계
    final_label_counts = Counter()
    final_single = 0
    final_multi = 0
    for item in merged_train:
        for label in item["labels"]:
            final_label_counts[label] += 1
        if len(item["labels"]) == 1:
            final_single += 1
        else:
            final_multi += 1

    print(f"\n{'─'*60}")
    print(f"  최종 Train 데이터 (기존 + R1 GPT + R2 GPT)")
    print(f"{'─'*60}")
    print(f"  전체: {len(merged_train)}개 (단일: {final_single}, 복합: {final_multi})")
    print(f"\n  Intent별 출현:")
    for label in INTENT_LABELS:
        bar = "█" * (final_label_counts.get(label, 0) // 5)
        print(f"    {label:<16} {final_label_counts.get(label, 0):4d}  {bar}")

    # ── 샘플 출력 ──
    print(f"\n{'─'*60}")
    print("  R2 GPT 생성 샘플")
    print(f"{'─'*60}")
    samples = random.sample(all_data, min(10, len(all_data)))
    for item in samples:
        labels_str = " + ".join(item["labels"])
        print(f"  [{labels_str}] {item['text']}")


if __name__ == "__main__":
    asyncio.run(main())
