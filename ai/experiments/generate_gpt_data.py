"""
GPT 기반 멀티라벨 학습 데이터 생성 (Knowledge Distillation)

GPT-4o-mini에게 다양한 복합 질문을 생성하게 하여,
sLLM(BERT) 파인튜닝용 고품질 학습 데이터를 만든다.

사용법 (RunPod):
  export OPENAI_API_KEY=sk-...
  python -m ai.experiments.generate_gpt_data

  # 생성 개수 조절:
  python -m ai.experiments.generate_gpt_data --n-per-combo 20
"""

import argparse
import asyncio
import json
import os
import random
from pathlib import Path
from collections import Counter, defaultdict

random.seed(42)

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "data" / "training" / "intent_multilabel"

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_qa",
]

INTENT_DESCRIPTIONS = {
    "judgment": "규정 위반 여부 판단, 가능/불가능 판단, 적용 가능성 검토, 처벌 기준 확인",
    "doc_search": "문서/규정 검색, 찾기, 조회, 어디 있는지 물어보기",
    "doc_generate": "문서 작성, 생성, 회의록/보고서/제안서/기획서 만들기",
    "doc_summary": "문서 요약, 핵심 정리, 간추리기, 요점 뽑기",
    "schedule_add": "일정 등록, 추가, 잡기, 미팅 설정",
    "schedule_view": "일정 조회, 확인, 보기, 빈 시간 확인",
    "general": "일반 대화, 인사, 잡담, 시스템 관련 질문",
    "doc_qa": "문서 내용에 대한 질문, 특정 정보 추출 (금액, 날짜, 수치, 담당자 등)",
}

# ── 2중 복합 조합 ─────────────────────────────────────────────────────────────

COMPOUND_COMBOS = [
    ("doc_search", "judgment"),
    ("doc_search", "doc_summary"),
    ("doc_search", "doc_generate"),
    ("doc_search", "doc_qa"),
    ("doc_qa", "judgment"),
    ("doc_qa", "doc_generate"),
    ("doc_qa", "doc_summary"),
    ("doc_summary", "doc_generate"),
    ("doc_summary", "judgment"),
    ("judgment", "doc_generate"),
    ("schedule_view", "schedule_add"),
    ("schedule_view", "judgment"),
    ("schedule_view", "doc_generate"),
    ("doc_qa", "schedule_view"),
    ("judgment", "schedule_add"),
    ("schedule_add", "doc_generate"),
    ("doc_search", "schedule_view"),
]

# ── 3중 복합 조합 ─────────────────────────────────────────────────────────────

TRIPLE_COMBOS = [
    ("doc_search", "judgment", "doc_generate"),
    ("doc_search", "doc_summary", "judgment"),
    ("doc_qa", "doc_summary", "doc_generate"),
    ("doc_search", "doc_qa", "judgment"),
    ("doc_search", "doc_qa", "doc_generate"),
    ("schedule_view", "schedule_add", "doc_generate"),
    ("doc_qa", "judgment", "doc_generate"),
]

# ── 함정 단일 (접속사 있지만 단일 intent) ─────────────────────────────────────

TRAP_INTENTS = ["doc_search", "judgment", "doc_qa", "doc_generate", "doc_summary", "schedule_view"]

# ── 프롬프트 ──────────────────────────────────────────────────────────────────

COMPOUND_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

아래 두 가지 intent가 **모두 포함된** 한국어 복합 질문을 {n}개 만들어주세요.

Intent 1: {intent1} — {desc1}
Intent 2: {intent2} — {desc2}

## 규칙:
1. 실제 직장인이 챗봇에게 말하듯 자연스러운 구어체로 작성
2. "그리고", "이랑" 같은 접속사 없이 자연스럽게 두 의도를 녹여내는 문장도 포함
3. 짧은 문장(10~20자)부터 긴 문장(40~60자)까지 다양하게
4. 매번 다른 주제(인사, 출장, 경비, 휴가, 보안, 계약, 성과, 예산, 회의, 교육 등)
5. 비슷한 문장 반복하지 말 것
6. 각 문장은 반드시 두 intent가 모두 필요한 경우여야 함

## 응답 형식 (JSON 배열):
[
  "문장1",
  "문장2",
  ...
]

JSON 배열만 응답하세요."""

TRIPLE_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

아래 세 가지 intent가 **모두 포함된** 한국어 복합 질문을 {n}개 만들어주세요.

Intent 1: {intent1} — {desc1}
Intent 2: {intent2} — {desc2}
Intent 3: {intent3} — {desc3}

## 규칙:
1. 실제 직장인이 챗봇에게 말하듯 자연스러운 구어체
2. 세 가지 의도가 자연스럽게 하나의 문장/요청에 녹아있어야 함
3. 다양한 주제, 다양한 길이
4. 비슷한 문장 반복하지 말 것

## 응답 형식 (JSON 배열):
[
  "문장1",
  "문장2",
  ...
]

JSON 배열만 응답하세요."""

TRAP_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

아래 intent에 해당하는 **단일 intent** 한국어 질문을 {n}개 만들어주세요.
단, "그리고", "이랑", "~도" 같은 접속사/나열 표현이 포함되어 있지만
실제로는 **하나의 intent**만 해당하는 함정 문장이어야 합니다.

Intent: {intent} — {desc}

## 예시:
- "연차이랑 병가 규정 찾아줘" → 둘 다 doc_search (단일)
- "이번 건이랑 저번 건 위반 여부 판단해줘" → 둘 다 judgment (단일)

## 규칙:
1. 접속사("그리고", "이랑", "~도", "~랑", "하고")가 반드시 포함
2. 같은 intent 안에서 여러 항목을 나열하는 것
3. 다른 intent로 오인하기 쉬운 표현 사용
4. 다양한 주제

## 응답 형식 (JSON 배열):
[
  "문장1",
  "문장2",
  ...
]

JSON 배열만 응답하세요."""

CONFUSING_PROMPT = """당신은 사내 업무 지원 챗봇의 학습 데이터를 만드는 전문가입니다.

doc_search와 doc_qa는 혼동하기 쉬운 intent입니다.
아래 규칙에 따라 **정확하게 라벨링된** 질문을 {n}개 만들어주세요.

## 구분 기준:
- doc_search: 문서/규정 자체를 찾는 것 ("~규정 찾아줘", "~문서 보여줘", "~어디 있어")
- doc_qa: 이미 알고 있는 문서에서 특정 정보를 추출하는 것 ("~얼마야", "~언제야", "~뭐야", "~몇 퍼센트야")

## 응답 형식 (JSON 배열):
[
  {{"text": "문장", "labels": ["intent"]}},
  ...
]

{n}개 중:
- doc_search 단일: {n_half}개
- doc_qa 단일: {n_half}개

다양한 주제, 다양한 표현으로 만들어주세요.
JSON 배열만 응답하세요."""


# ── GPT 호출 ──────────────────────────────────────────────────────────────────

async def call_gpt(prompt, api_key, model="gpt-4o-mini", temperature=0.9):
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=4096,
        )
        content = response.choices[0].message.content.strip()

        # JSON 파싱
        import re
        if content.startswith("```"):
            match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
            if match:
                content = match.group(1).strip()

        return json.loads(content)

    except Exception as e:
        print(f"  GPT 오류: {e}")
        return []


# ── 생성 함수 ─────────────────────────────────────────────────────────────────

async def generate_compound_data(api_key, n_per_combo=15, model="gpt-4o-mini"):
    """2중 복합 데이터 생성"""
    all_data = []
    semaphore = asyncio.Semaphore(3)

    async def gen_one(intent1, intent2):
        async with semaphore:
            prompt = COMPOUND_PROMPT.format(
                n=n_per_combo,
                intent1=intent1, desc1=INTENT_DESCRIPTIONS[intent1],
                intent2=intent2, desc2=INTENT_DESCRIPTIONS[intent2],
            )
            texts = await call_gpt(prompt, api_key, model)
            results = []
            for text in texts:
                if isinstance(text, str) and len(text) >= 5:
                    results.append({
                        "text": text.strip(),
                        "labels": sorted([intent1, intent2]),
                    })
            print(f"  [{intent1}+{intent2}] {len(results)}개 생성")
            return results

    tasks = [gen_one(a, b) for a, b in COMPOUND_COMBOS]
    results = await asyncio.gather(*tasks)
    for r in results:
        all_data.extend(r)

    return all_data


async def generate_triple_data(api_key, n_per_combo=10, model="gpt-4o-mini"):
    """3중 복합 데이터 생성"""
    all_data = []
    semaphore = asyncio.Semaphore(3)

    async def gen_one(intent1, intent2, intent3):
        async with semaphore:
            prompt = TRIPLE_PROMPT.format(
                n=n_per_combo,
                intent1=intent1, desc1=INTENT_DESCRIPTIONS[intent1],
                intent2=intent2, desc2=INTENT_DESCRIPTIONS[intent2],
                intent3=intent3, desc3=INTENT_DESCRIPTIONS[intent3],
            )
            texts = await call_gpt(prompt, api_key, model)
            results = []
            for text in texts:
                if isinstance(text, str) and len(text) >= 5:
                    results.append({
                        "text": text.strip(),
                        "labels": sorted([intent1, intent2, intent3]),
                    })
            print(f"  [{intent1}+{intent2}+{intent3}] {len(results)}개 생성")
            return results

    tasks = [gen_one(a, b, c) for a, b, c in TRIPLE_COMBOS]
    results = await asyncio.gather(*tasks)
    for r in results:
        all_data.extend(r)

    return all_data


async def generate_trap_data(api_key, n_per_intent=15, model="gpt-4o-mini"):
    """함정 단일 데이터 생성"""
    all_data = []
    semaphore = asyncio.Semaphore(3)

    async def gen_one(intent):
        async with semaphore:
            prompt = TRAP_PROMPT.format(
                n=n_per_intent,
                intent=intent, desc=INTENT_DESCRIPTIONS[intent],
            )
            texts = await call_gpt(prompt, api_key, model)
            results = []
            for text in texts:
                if isinstance(text, str) and len(text) >= 5:
                    results.append({
                        "text": text.strip(),
                        "labels": [intent],
                    })
            print(f"  [{intent} 함정] {len(results)}개 생성")
            return results

    tasks = [gen_one(intent) for intent in TRAP_INTENTS]
    results = await asyncio.gather(*tasks)
    for r in results:
        all_data.extend(r)

    return all_data


async def generate_confusing_data(api_key, n_total=40, model="gpt-4o-mini"):
    """doc_search↔doc_qa 혼동 방지 데이터 생성"""
    prompt = CONFUSING_PROMPT.format(n=n_total, n_half=n_total // 2)
    results = await call_gpt(prompt, api_key, model)

    all_data = []
    for item in results:
        if isinstance(item, dict) and "text" in item and "labels" in item:
            valid_labels = [l for l in item["labels"] if l in INTENT_DESCRIPTIONS]
            if valid_labels:
                all_data.append({
                    "text": item["text"].strip(),
                    "labels": sorted(valid_labels),
                })

    print(f"  [doc_search↔doc_qa 구분] {len(all_data)}개 생성")
    return all_data


# ── 중복 제거 ─────────────────────────────────────────────────────────────────

def deduplicate(data):
    seen = set()
    unique = []
    for item in data:
        text = item["text"].strip()
        if text not in seen:
            seen.add(text)
            unique.append(item)
    return unique


# ── 통계 출력 ─────────────────────────────────────────────────────────────────

def print_stats(data, title):
    n_single = sum(1 for item in data if len(item["labels"]) == 1)
    n_multi = sum(1 for item in data if len(item["labels"]) >= 2)
    n_triple = sum(1 for item in data if len(item["labels"]) >= 3)

    label_counts = Counter()
    for item in data:
        for label in item["labels"]:
            label_counts[label] += 1

    pair_counts = Counter()
    for item in data:
        if len(item["labels"]) >= 2:
            pair_counts[tuple(item["labels"])] += 1

    print(f"\n{'─'*50}")
    print(f"  {title}")
    print(f"{'─'*50}")
    print(f"  전체: {len(data)}개 (단일: {n_single}, 2중복합: {n_multi - n_triple}, 3중복합: {n_triple})")
    print(f"\n  Intent별 출현 횟수:")
    for label in INTENT_LABELS:
        bar = "█" * (label_counts.get(label, 0) // 5)
        print(f"    {label:<16} {label_counts.get(label, 0):4d}  {bar}")

    if pair_counts:
        print(f"\n  복합 조합별 (상위 10):")
        for pair, count in pair_counts.most_common(10):
            print(f"    {'+'.join(pair):<40} {count:3d}")


# ── 메인 ─────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-per-combo", type=int, default=15,
                        help="2중 복합 조합당 생성 개수 (기본 15)")
    parser.add_argument("--n-triple", type=int, default=10,
                        help="3중 복합 조합당 생성 개수 (기본 10)")
    parser.add_argument("--n-trap", type=int, default=15,
                        help="함정 단일 intent당 생성 개수 (기본 15)")
    parser.add_argument("--n-confusing", type=int, default=40,
                        help="doc_search↔doc_qa 구분 데이터 (기본 40)")
    parser.add_argument("--model", default="gpt-4o-mini")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("❌ OPENAI_API_KEY 환경변수를 설정하세요:")
        print("   export OPENAI_API_KEY=sk-...")
        return

    print("GPT 기반 멀티라벨 학습 데이터 생성")
    print(f"모델: {args.model}")
    print("=" * 50)

    # ── 1) 2중 복합 ──
    print(f"\n[1/4] 2중 복합 데이터 ({len(COMPOUND_COMBOS)}조합 × {args.n_per_combo}개)...")
    compound_data = await generate_compound_data(api_key, args.n_per_combo, args.model)

    # ── 2) 3중 복합 ──
    print(f"\n[2/4] 3중 복합 데이터 ({len(TRIPLE_COMBOS)}조합 × {args.n_triple}개)...")
    triple_data = await generate_triple_data(api_key, args.n_triple, args.model)

    # ── 3) 함정 단일 ──
    print(f"\n[3/4] 함정 단일 데이터 ({len(TRAP_INTENTS)}intent × {args.n_trap}개)...")
    trap_data = await generate_trap_data(api_key, args.n_trap, args.model)

    # ── 4) doc_search↔doc_qa 구분 ──
    print(f"\n[4/4] doc_search↔doc_qa 구분 데이터 ({args.n_confusing}개)...")
    confusing_data = await generate_confusing_data(api_key, args.n_confusing, args.model)

    # ── 합치기 + 중복 제거 ──
    all_gpt_data = compound_data + triple_data + trap_data + confusing_data
    all_gpt_data = deduplicate(all_gpt_data)

    print(f"\n{'='*50}")
    print(f"GPT 생성 데이터 합계: {len(all_gpt_data)}개")
    print(f"  2중 복합: {len(compound_data)}개")
    print(f"  3중 복합: {len(triple_data)}개")
    print(f"  함정 단일: {len(trap_data)}개")
    print(f"  doc_search↔doc_qa: {len(confusing_data)}개")

    print_stats(all_gpt_data, "GPT 생성 데이터 통계")

    # ── 저장 ──
    gpt_path = OUT_DIR / "gpt_generated.jsonl"
    with open(gpt_path, "w", encoding="utf-8") as f:
        for item in all_gpt_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"\n저장: {gpt_path} ({len(all_gpt_data)}개)")

    # ── 기존 데이터와 합치기 ──
    print(f"\n{'='*50}")
    print("기존 템플릿 데이터와 합치기...")

    existing_train_path = OUT_DIR / "train.jsonl"
    existing_train = []
    with open(existing_train_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                existing_train.append(json.loads(line))

    print(f"  기존 train: {len(existing_train)}개")
    print(f"  GPT 생성:   {len(all_gpt_data)}개")

    # GPT 데이터의 80%를 train에, 10% val, 10% test
    random.shuffle(all_gpt_data)
    n = len(all_gpt_data)
    n_train = int(n * 0.8)
    n_val = int(n * 0.1)
    gpt_train = all_gpt_data[:n_train]
    gpt_val = all_gpt_data[n_train:n_train + n_val]
    gpt_test = all_gpt_data[n_train + n_val:]

    # 합치기
    merged_train = existing_train + gpt_train
    random.shuffle(merged_train)

    existing_val = []
    with open(OUT_DIR / "val.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                existing_val.append(json.loads(line))
    merged_val = existing_val + gpt_val

    existing_test = []
    with open(OUT_DIR / "test.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                existing_test.append(json.loads(line))
    merged_test = existing_test + gpt_test

    # 저장
    for name, data in [("train", merged_train), ("val", merged_val), ("test", merged_test)]:
        path = OUT_DIR / f"{name}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"  → {name}.jsonl: {len(data)}개 저장")

    print_stats(merged_train, "최종 Train 데이터 (기존 + GPT)")

    # ── 샘플 출력 ──
    print(f"\n{'─'*50}")
    print("  GPT 생성 샘플")
    print(f"{'─'*50}")

    for category, data in [("2중 복합", compound_data), ("3중 복합", triple_data),
                            ("함정 단일", trap_data), ("doc_search↔doc_qa", confusing_data)]:
        print(f"\n  [{category}]")
        samples = random.sample(data, min(3, len(data)))
        for item in samples:
            labels_str = " + ".join(item["labels"])
            print(f"    [{labels_str}] {item['text']}")


if __name__ == "__main__":
    asyncio.run(main())
