"""
GPT 기반 학습 데이터 생성 — Round 3 (doc_summary 경계 + 잔여 오답 보강)

Held-out 오답 9건 분석 → 3가지 핵심 패턴:
  1. doc_summary 과잉 트리거 (3건) — "정리해줘/분석해줘" ≠ doc_summary
  2. doc_summary 누락 (3건) — "요약/핵심 정리" + 다른 intent 복합
  3. judgment 미인식 (1건) — "규정 분석/검토 결과" = judgment
  + doc_search/doc_generate 경계 보강

사용법 (RunPod):
  export OPENAI_API_KEY=sk-...
  python -m ai.experiments.generate_gpt_data_r3
"""

import argparse
import asyncio
import json
import os
import random
from pathlib import Path
from collections import Counter

random.seed(44)

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "data" / "training" / "intent_multilabel"

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_search",
]


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
# 패턴 1: doc_summary 과잉 트리거 방지
# — "정리해줘", "분석해줘", "검토해줘"가 있어도 doc_summary가 아닌 경우
# ══════════════════════════════════════════════════════════════════════════════

FALSE_POS_DOC_SUMMARY_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

모델이 "정리해줘", "분석해줘", "검토해줘" 같은 표현을 보면 doc_summary로 잘못 분류합니다.

## doc_summary vs 다른 intent 구분:
- doc_summary: **긴 문서의 핵심을 추려서 짧게 요약** → "요약해줘", "핵심만 뽑아줘", "간추려줘", "줄여줘"
- doc_search: 문서를 **찾아서 정리** → "규정 찾아서 정리해줘", "자료 조회해서 알려줘"
- doc_generate: 새 문서를 **작성해서 정리** → "보고서로 정리해줘", "문서로 만들어줘"
- judgment: 규정 **분석/검토해서 판단** → "규정 분석 결과 알려줘", "검토 결과 정리해줘"

## doc_summary가 아닌 예시:
- "인사 규정을 분석해서 정리해줘" → doc_search (규정을 찾아서 보는 것)
- "출장비 규정을 검토해서 정리해줘" → doc_search
- "프로젝트 결과를 보고서로 정리해줘" → doc_generate (새 문서 작성)
- "사내 규정 분석 그리고 검토 결과를 정리해줘" → judgment (규정 검토 판단)

{intent_type} 문장을 {n}개 만들어주세요.
"정리/분석/검토" 단어가 포함되지만 doc_summary가 **아닌** 문장입니다.

## 응답 형식 (JSON 배열):
[
  {{"text": "문장", "labels": ["정확한_intent"]}},
  ...
]

JSON 배열만 응답하세요."""

FALSE_POS_SUMMARY_TYPES = [
    {"intent_type": "doc_search 단일 — 문서/규정을 '찾아서 정리', '조회해서 정리', '검토해서 알려줘' (문서 요약이 아닌 검색+제공)", "label": "doc_search"},
    {"intent_type": "doc_generate 단일 — 결과물을 '정리해서 보고서로', '정리해서 문서로', '보고서로 정리' (요약이 아닌 새 문서 작성)", "label": "doc_generate"},
    {"intent_type": "judgment 단일 — 규정을 '분석해서 결과', '검토 결과 정리', '분석 그리고 검토' (요약이 아닌 규정 판단)", "label": "judgment"},
]


# ══════════════════════════════════════════════════════════════════════════════
# 패턴 2: doc_summary 포함 복합 (doc_summary 누락 방지)
# — doc_summary + 다른 intent가 모두 필요한 명확한 복합 문장
# ══════════════════════════════════════════════════════════════════════════════

DOC_SUMMARY_COMPOUND_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

모델이 복합 질문에서 doc_summary를 놓치는 문제가 있습니다.
**{intent1} + doc_summary** 복합 질문을 {n}개 만들어주세요.

## doc_summary의 핵심:
- 문서/보고서/회의록의 **핵심 내용을 추려서 짧게 요약**하는 것
- 키워드: "요약", "핵심 정리", "간추려", "줄여서", "요점만", "핵심만 뽑아"

## {intent1} + doc_summary 예시:
{examples}

## 규칙:
1. doc_summary와 {intent1} 두 intent가 모두 **분명하게** 드러나야 함
2. doc_summary 부분은 "요약/핵심 정리/간추려/줄여서" 같은 명확한 표현 사용
3. 자연스러운 구어체, 다양한 주제
4. 접속사 없이 자연스럽게 연결하는 문장 포함

## 응답 형식 (JSON 배열):
[
  "문장1",
  "문장2",
  ...
]

JSON 배열만 응답하세요."""

DOC_SUMMARY_COMPOUND_CONFIGS = [
    {
        "intent1": "doc_generate",
        "labels": ["doc_generate", "doc_summary"],
        "examples": '- "회의 결과 요약하고 보고서에 반영해줘" → 요약(doc_summary) + 보고서 작성(doc_generate)\n- "지난 자료 핵심 정리해서 제안서 만들어줘" → 핵심 정리(doc_summary) + 제안서(doc_generate)\n- "프로젝트 경과 요점 뽑아서 주간 보고서 써줘" → 요점(doc_summary) + 보고서(doc_generate)',
    },
    {
        "intent1": "doc_search",
        "labels": ["doc_search", "doc_summary"],
        "examples": '- "복리후생 규정 찾아서 핵심만 요약해줘" → 규정 찾기(doc_search) + 요약(doc_summary)\n- "출장비 관련 문서 찾아서 간단히 정리해줘" → 문서 찾기(doc_search) + 정리(doc_summary)\n- "취업규칙에서 징계 관련 부분 요약 좀" → 규정 찾기(doc_search) + 요약(doc_summary)',
    },
    {
        "intent1": "doc_search",
        "labels": ["doc_search", "doc_summary"],
        "examples": '- "보고서에서 매출 수치 확인하고 전체 핵심도 요약해줘" → 수치 확인(doc_qa) + 요약(doc_summary)\n- "계약서 만료일 알려주고 주요 조항 요약해줘" → 날짜 확인(doc_qa) + 요약(doc_summary)',
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# 패턴 3: judgment 인식 강화
# — "규정 분석/검토" 맥락에서 judgment를 정확히 잡도록
# ══════════════════════════════════════════════════════════════════════════════

JUDGMENT_RECOGNITION_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

모델이 "규정 분석", "검토 결과" 같은 표현에서 judgment를 놓치고 doc_search나 doc_summary로 분류합니다.

## judgment의 핵심:
- 규정/기준에 비추어 **위반 여부, 가능 여부, 적법성**을 판단하는 것
- "분석해서 판단", "검토 결과", "가능한지", "위반인지", "적용되는지"

## judgment인 예시:
- "사내 규정 분석 그리고 검토 결과를 정리해줘" → judgment (규정 판단 결과)
- "출장비 규정 검토해서 이번 건 가능한지 알려줘" → judgment
- "인사 규정 분석 결과 알려줘" → judgment (규정 판단)
- "재택근무 규정 검토해봐" → judgment (규정 위반/준수 판단)

{category} 문장을 {n}개 만들어주세요.

## 응답 형식 (JSON 배열):
[
  {{"text": "문장", "labels": {labels_json}}},
  ...
]

JSON 배열만 응답하세요."""

JUDGMENT_CONFIGS = [
    {
        "category": "judgment 단일 — '규정 분석', '검토 결과', '규정 검토' 표현이 포함된 judgment 문장",
        "labels_json": '["judgment"]',
    },
    {
        "category": "judgment + doc_search 복합 — 규정을 찾아서(doc_search) 판단(judgment)하는 문장",
        "labels_json": '["doc_search", "judgment"]',
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# 패턴 4: doc_generate 단일 (doc_search 과잉 방지)
# — "보고서/기획서 작성해줘"만인데 doc_search가 추가되는 문제
# ══════════════════════════════════════════════════════════════════════════════

DOC_GENERATE_ONLY_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

모델이 "보고서", "기획서", "제안서" 같은 단어를 보면 doc_search를 추가하는 경향이 있습니다.
하지만 **새로운 문서를 작성하는 것**은 doc_generate만 해당합니다.

## doc_generate만 해당하는 예시:
- "프로젝트 기획서 작성해줘" → doc_generate (새로 만드는 것)
- "주간 보고서 써줘" → doc_generate
- "회의록 만들어줘" → doc_generate
- "사업 계획서 작성해줘" → doc_generate

doc_generate **단일** intent 문장을 {n}개 만들어주세요.
"보고서/기획서/제안서/회의록" 등 문서 단어가 포함되지만, 기존 문서를 찾는 것이 아니라 **새로 작성**하는 문장입니다.

## 응답 형식 (JSON 배열):
[
  {{"text": "문장", "labels": ["doc_generate"]}},
  ...
]

JSON 배열만 응답하세요."""


# ══════════════════════════════════════════════════════════════════════════════
# 패턴 5: doc_search 단일 강화 (general 오분류 방지)
# — 문서 검색/확인 요청이 general로 빠지는 문제
# ══════════════════════════════════════════════════════════════════════════════

DOC_SEARCH_STRONG_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

모델이 애매한 표현의 문서 검색 요청을 general(일반 대화)로 잘못 분류합니다.

## doc_search인 예시:
- "문서 꼼꼼하게 검토해서 빠진 거 없는지 확인해줘" → doc_search
- "관련 서류 좀 봐줘" → doc_search
- "해당 파일 확인 좀" → doc_search
- "자료 있으면 보여줘" → doc_search

doc_search 단일 문장을 {n}개 만들어주세요.
직접적으로 "찾아줘/검색해줘"를 안 쓰지만, **문서를 확인/검토/조회하는 요청**인 문장입니다.
"확인해줘", "봐줘", "있나", "어딨어" 같은 간접적 표현을 사용하세요.

## 응답 형식 (JSON 배열):
[
  {{"text": "문장", "labels": ["doc_search"]}},
  ...
]

JSON 배열만 응답하세요."""


# ══════════════════════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-4o-mini")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("OPENAI_API_KEY 환경변수를 설정하세요")
        return

    print("GPT Round 3 — doc_summary 경계 + 잔여 오답 보강")
    print(f"모델: {args.model}")
    print("=" * 60)

    all_data = []
    semaphore = asyncio.Semaphore(3)

    # ── 패턴 1: doc_summary 과잉 방지 (3종 × 20개 = 60개) ──
    print("\n[1/5] doc_summary 과잉 트리거 방지 ('정리/분석/검토' ≠ doc_summary)...")
    for cfg in FALSE_POS_SUMMARY_TYPES:
        async with semaphore:
            prompt = FALSE_POS_DOC_SUMMARY_PROMPT.format(
                intent_type=cfg["intent_type"], n=20
            )
            results = await call_gpt(prompt, api_key, args.model)
            count = 0
            for item in results:
                if isinstance(item, dict) and "text" in item and "labels" in item:
                    valid_labels = [l for l in item["labels"] if l in INTENT_LABELS]
                    if valid_labels and "doc_summary" not in valid_labels:
                        all_data.append({"text": item["text"].strip(), "labels": sorted(valid_labels)})
                        count += 1
            print(f"  [{cfg['label']} — doc_summary 아님] {count}개 생성")

    # ── 패턴 2: doc_summary 포함 복합 (3종 × 20개 = 60개) ──
    print("\n[2/5] doc_summary 포함 복합 (doc_summary 누락 방지)...")
    for cfg in DOC_SUMMARY_COMPOUND_CONFIGS:
        async with semaphore:
            prompt = DOC_SUMMARY_COMPOUND_PROMPT.format(
                intent1=cfg["intent1"], n=20, examples=cfg["examples"]
            )
            results = await call_gpt(prompt, api_key, args.model)
            count = 0
            for text in results:
                if isinstance(text, str) and len(text) >= 5:
                    all_data.append({"text": text.strip(), "labels": sorted(cfg["labels"])})
                    count += 1
            print(f"  [doc_summary+{cfg['intent1']}] {count}개 생성")

    # ── 패턴 3: judgment 인식 강화 (2종 × 20개 = 40개) ──
    print("\n[3/5] judgment 인식 강화 ('규정 분석/검토' = judgment)...")
    for cfg in JUDGMENT_CONFIGS:
        async with semaphore:
            prompt = JUDGMENT_RECOGNITION_PROMPT.format(
                category=cfg["category"], n=20, labels_json=cfg["labels_json"]
            )
            results = await call_gpt(prompt, api_key, args.model)
            count = 0
            for item in results:
                if isinstance(item, dict) and "text" in item and "labels" in item:
                    valid_labels = [l for l in item["labels"] if l in INTENT_LABELS]
                    if valid_labels:
                        all_data.append({"text": item["text"].strip(), "labels": sorted(valid_labels)})
                        count += 1
            print(f"  [judgment {'단일' if 'judgment' == cfg['labels_json'] else '복합'}] {count}개 생성")

    # ── 패턴 4: doc_generate 단일 (20개) ──
    print("\n[4/5] doc_generate 단일 (doc_search 과잉 방지)...")
    async with semaphore:
        prompt = DOC_GENERATE_ONLY_PROMPT.format(n=20)
        results = await call_gpt(prompt, api_key, args.model)
        count = 0
        for item in results:
            if isinstance(item, dict) and "text" in item and "labels" in item:
                valid_labels = [l for l in item["labels"] if l in INTENT_LABELS]
                if valid_labels:
                    all_data.append({"text": item["text"].strip(), "labels": sorted(valid_labels)})
                    count += 1
        print(f"  [doc_generate 단일] {count}개 생성")

    # ── 패턴 5: doc_search 강화 (20개) ──
    print("\n[5/5] doc_search 간접 표현 강화 (general 오분류 방지)...")
    async with semaphore:
        prompt = DOC_SEARCH_STRONG_PROMPT.format(n=20)
        results = await call_gpt(prompt, api_key, args.model)
        count = 0
        for item in results:
            if isinstance(item, dict) and "text" in item and "labels" in item:
                valid_labels = [l for l in item["labels"] if l in INTENT_LABELS]
                if valid_labels:
                    all_data.append({"text": item["text"].strip(), "labels": sorted(valid_labels)})
                    count += 1
        print(f"  [doc_search 간접] {count}개 생성")

    # ── 중복 제거 ──
    seen = set()
    unique_data = []
    for item in all_data:
        text = item["text"].strip()
        if text not in seen:
            seen.add(text)
            unique_data.append(item)
    all_data = unique_data

    # ── 통계 ──
    print(f"\n{'='*60}")
    print(f"Round 3 GPT 생성 합계: {len(all_data)}개")

    label_counts = Counter()
    for item in all_data:
        for label in item["labels"]:
            label_counts[label] += 1

    n_single = sum(1 for d in all_data if len(d["labels"]) == 1)
    n_multi = sum(1 for d in all_data if len(d["labels"]) >= 2)

    print(f"  단일: {n_single}개, 복합: {n_multi}개")
    print(f"\n  Intent별 출현:")
    for label in INTENT_LABELS:
        bar = "█" * (label_counts.get(label, 0) // 2)
        print(f"    {label:<16} {label_counts.get(label, 0):4d}  {bar}")

    # ── 저장 ──
    r3_path = OUT_DIR / "gpt_generated_r3.jsonl"
    with open(r3_path, "w", encoding="utf-8") as f:
        for item in all_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"\n저장: {r3_path} ({len(all_data)}개)")

    # ── 기존 데이터와 합치기 ──
    print(f"\n{'='*60}")
    print("기존 데이터와 합치기...")

    existing_train = []
    with open(OUT_DIR / "train.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                existing_train.append(json.loads(line))

    existing_texts = {d["text"].strip() for d in existing_train}
    new_data = [d for d in all_data if d["text"].strip() not in existing_texts]

    print(f"  기존 train: {len(existing_train)}개")
    print(f"  R3 신규 (중복 제거 후): {len(new_data)}개")

    random.shuffle(new_data)
    n = len(new_data)
    n_train = int(n * 0.8)
    n_val = int(n * 0.1)
    r3_train = new_data[:n_train]
    r3_val = new_data[n_train:n_train + n_val]
    r3_test = new_data[n_train + n_val:]

    merged_train = existing_train + r3_train
    random.shuffle(merged_train)

    existing_val = []
    with open(OUT_DIR / "val.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                existing_val.append(json.loads(line))
    merged_val = existing_val + r3_val

    existing_test = []
    with open(OUT_DIR / "test.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                existing_test.append(json.loads(line))
    merged_test = existing_test + r3_test

    for name, data in [("train", merged_train), ("val", merged_val), ("test", merged_test)]:
        path = OUT_DIR / f"{name}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"  -> {name}.jsonl: {len(data)}개 저장")

    # 최종 통계
    final_counts = Counter()
    for item in merged_train:
        for label in item["labels"]:
            final_counts[label] += 1

    print(f"\n{'─'*60}")
    print(f"  최종 Train 데이터")
    print(f"{'─'*60}")
    print(f"  전체: {len(merged_train)}개")
    for label in INTENT_LABELS:
        bar = "█" * (final_counts.get(label, 0) // 5)
        print(f"    {label:<16} {final_counts.get(label, 0):4d}  {bar}")

    # 샘플
    print(f"\n{'─'*60}")
    print("  R3 GPT 생성 샘플")
    print(f"{'─'*60}")
    samples = random.sample(all_data, min(10, len(all_data)))
    for item in samples:
        labels_str = " + ".join(item["labels"])
        print(f"  [{labels_str}] {item['text']}")


if __name__ == "__main__":
    asyncio.run(main())
