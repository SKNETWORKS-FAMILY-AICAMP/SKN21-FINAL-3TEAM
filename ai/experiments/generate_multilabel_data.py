"""
멀티라벨 Intent 학습 데이터 생성기

기존 v2 단일 라벨 데이터를 멀티라벨 형식으로 변환하고,
서로 다른 intent 문장을 조합하여 복합 학습 데이터를 자동 생성.

출력 형식:
  {"text": "...", "labels": ["doc_search", "judgment"]}

사용법:
  cd /path/to/SKN21-FINAL-3TEAM
  python -m ai.experiments.generate_multilabel_data
"""

import json
import random
import re
from pathlib import Path
from collections import defaultdict

random.seed(42)

ROOT = Path(__file__).resolve().parent.parent.parent
V2_TRAIN = ROOT / "data" / "training" / "intent_v2" / "splits" / "train.jsonl"
V2_VAL   = ROOT / "data" / "training" / "intent_v2" / "splits" / "val.jsonl"
V2_TEST  = ROOT / "data" / "training" / "intent_v2" / "splits" / "test.jsonl"
ADV_TEST = ROOT / "data" / "training" / "intent" / "adversarial_test.json"

OUT_DIR  = ROOT / "data" / "training" / "intent_multilabel"
OUT_DIR.mkdir(parents=True, exist_ok=True)

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_qa",
]

# ── 자연스러운 복합 조합 쌍 + 접속사 템플릿 ──────────────────────────────────

# (intent_A, intent_B, [템플릿들])
# 템플릿: {A} = 문장A, {B} = 문장B, {A_stem} = 문장A의 동사 어간
COMPOUND_PAIRS = [
    # 규정 검색 → 판단
    ("doc_search", "judgment", [
        "{A_short} 찾아서 {B_short}",
        "{A_short} 검색하고 {B_short}",
        "{A_short} 확인한 다음 {B_short}",
    ]),
    # 일정 조회 → 일정 추가
    ("schedule_view", "schedule_add", [
        "{A_short} 확인하고 {B_short}",
        "{A_short} 보여주고 {B_short}",
    ]),
    # 문서 검색 → 문서 생성
    ("doc_search", "doc_generate", [
        "{A_short} 바탕으로 {B_short}",
        "{A_short} 찾아서 {B_short}",
        "{A_short} 확인하고 {B_short}",
    ]),
    # 문서 요약 → 문서 생성
    ("doc_summary", "doc_generate", [
        "{A_short} 요약하고 {B_short}",
        "{A_short} 정리한 다음 {B_short}",
    ]),
    # 문서 QA → 판단
    ("doc_qa", "judgment", [
        "{A_short} 확인하고 {B_short}",
        "{A_short} 알아본 다음 {B_short}",
    ]),
    # 문서 검색 → 문서 요약
    ("doc_search", "doc_summary", [
        "{A_short} 찾아서 {B_short}",
        "{A_short} 검색하고 {B_short}",
    ]),
    # 판단 → 문서 생성
    ("judgment", "doc_generate", [
        "{A_short} 판단하고 {B_short}",
        "{A_short} 확인한 다음 {B_short}",
    ]),
    # 일정 조회 → 판단
    ("schedule_view", "judgment", [
        "{A_short} 확인하고 {B_short}",
    ]),
    # 문서 QA → 문서 생성
    ("doc_qa", "doc_generate", [
        "{A_short} 확인해서 {B_short}",
        "{A_short} 알아보고 {B_short}",
    ]),
    # 문서 검색 → 문서 QA
    ("doc_search", "doc_qa", [
        "{A_short} 찾아서 {B_short}",
    ]),
]

# 범용 접속사 (위 pair에 없는 조합용)
GENERIC_CONNECTORS = [
    "{A} 그리고 {B}",
    "{A_short} 하고 {B_short}",
]


# ── 문장 단축 ────────────────────────────────────────────────────────────────

def shorten_sentence(text):
    """문장 끝의 종결어미 제거하여 접속 가능한 형태로 변환"""
    original = text
    # 다단계 종결어미 제거 (긴 패턴부터)
    endings = [
        # 정중 요청
        r'하여\s*주시기\s*바랍니다',
        r'해\s*주시기\s*바랍니다',
        r'부탁드립니다',
        r'부탁합니다',
        # ~해 주세요 / ~해줘 / ~해 줘
        r'해\s*주세요',
        r'해\s*줘',
        r'해줘',
        r'해주세요',
        # ~아/어 주세요 / ~아/어 줘
        r'[가-힣]아\s*주세요',
        r'[가-힣]어\s*주세요',
        r'[가-힣]아\s*줘',
        r'[가-힣]어\s*줘',
        # 동사+줘/주세요
        r'(?:보여|알려|찾아|만들어|정리해|검색해|확인해|조회해|등록해|추가해|작성해|생성해|요약해)\s*(?:줘|주세요|줄래|줄래요|줄 수 있어\??|줄 수 있나요\??)',
        # 일반 종결
        r'(?:합니다|합니까|하세요|할래요?|할게요?|해봐|해요|하나요|인가요|인지|되나요|돼\?|돼요\?|있나요|있어\??|없나요|없어\??|뭐야\??|뭐예요\??|뭔가요)',
        # 보조 종결
        r'(?:줘|주세요|볼래|볼게|봐|봐요)',
        # 의문형 "~수 있어?", "~수 있나?"
        r'수\s*있(?:어|나|을까)\??',
    ]
    for pattern in endings:
        text = re.sub(r'\s*' + pattern + r'\s*[.?!]*$', '', text).strip()

    # 맨 끝 물음표/마침표/느낌표 제거
    text = re.sub(r'[.?!]+$', '', text).strip()

    # 빈 문자열이면 원문 반환
    return text if len(text) >= 3 else original


# ── 데이터 로드 ──────────────────────────────────────────────────────────────

def load_jsonl(path):
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def load_by_intent(items):
    """intent별로 텍스트 그룹핑"""
    groups = defaultdict(list)
    for item in items:
        groups[item["label"]].append(item["text"])
    return groups


# ── 복합 데이터 생성 ─────────────────────────────────────────────────────────

def generate_compound_examples(intent_groups, n_per_pair=30):
    """
    intent 쌍별로 n_per_pair개 복합 문장 생성.

    전략:
      70% — 원문 "그리고" 연결 (항상 문법적으로 정확)
      30% — 쌍별 전용 템플릿 (자연스러운 복합 문장)
    """
    compounds = []
    seen_texts = set()

    # 전용 템플릿이 있는 쌍
    pair_templates = {
        (a, b): t for a, b, t in COMPOUND_PAIRS
    }

    # 생성 대상 쌍 목록 (전용 템플릿 쌍만)
    all_pairs = [(a, b) for a, b, _ in COMPOUND_PAIRS]

    for intent_a, intent_b in all_pairs:
        texts_a = intent_groups.get(intent_a, [])
        texts_b = intent_groups.get(intent_b, [])
        if not texts_a or not texts_b:
            continue

        templates = pair_templates.get((intent_a, intent_b), [])
        n_template = int(n_per_pair * 0.3)  # 30% 템플릿
        n_simple   = n_per_pair - n_template  # 70% 그리고 연결

        generated = 0
        attempts = 0

        # ── 1) "그리고" 연결 (원문 그대로) ──
        while generated < n_simple and attempts < n_per_pair * 20:
            attempts += 1
            a = random.choice(texts_a)
            b = random.choice(texts_b)
            text = f"{a} 그리고 {b}"
            if text not in seen_texts:
                seen_texts.add(text)
                compounds.append({
                    "text": text,
                    "labels": sorted(set([intent_a, intent_b])),
                })
                generated += 1

        # ── 2) 전용 템플릿 (단축형 조합) ──
        tmpl_generated = 0
        attempts = 0
        while tmpl_generated < n_template and templates and attempts < n_per_pair * 20:
            attempts += 1
            a = random.choice(texts_a)
            b = random.choice(texts_b)
            a_short = shorten_sentence(a)
            b_short = shorten_sentence(b)
            if len(a_short) < 4 or len(b_short) < 4:
                continue

            template = random.choice(templates)
            text = template.format(
                A=a, B=b, A_short=a_short, B_short=b_short,
            )
            # 마지막 문장(B)의 종결어미 복원
            if not re.search(r'(줘|주세요|할래|합니다|바랍니다|해봐|하세요|나요|돼\??|뭐야|확인|판단)\s*[.?!]*$', text):
                text += " 해줘"

            if text not in seen_texts:
                seen_texts.add(text)
                compounds.append({
                    "text": text,
                    "labels": sorted(set([intent_a, intent_b])),
                })
                tmpl_generated += 1

    return compounds


# ── 단일 → 멀티라벨 변환 ─────────────────────────────────────────────────────

def convert_single_to_multilabel(items):
    """단일 라벨 → 멀티라벨 형식"""
    return [{"text": item["text"], "labels": [item["label"]]} for item in items]


# ── Train / Val / Test 분할 ──────────────────────────────────────────────────

def split_compound_data(compounds, train_ratio=0.7, val_ratio=0.15):
    """복합 데이터를 train/val/test로 분할"""
    random.shuffle(compounds)
    n = len(compounds)
    n_train = int(n * train_ratio)
    n_val   = int(n * val_ratio)

    return (
        compounds[:n_train],
        compounds[n_train:n_train + n_val],
        compounds[n_train + n_val:],
    )


# ── 저장 ─────────────────────────────────────────────────────────────────────

def save_jsonl(items, path):
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  → {path.name}: {len(items)}개 저장")


# ── 통계 출력 ────────────────────────────────────────────────────────────────

def print_stats(items, title):
    from collections import Counter
    n_single = sum(1 for item in items if len(item["labels"]) == 1)
    n_multi  = sum(1 for item in items if len(item["labels"]) >= 2)

    label_counts = Counter()
    for item in items:
        for label in item["labels"]:
            label_counts[label] += 1

    pair_counts = Counter()
    for item in items:
        if len(item["labels"]) >= 2:
            pair_counts[tuple(item["labels"])] += 1

    print(f"\n{'─'*50}")
    print(f"  {title}")
    print(f"{'─'*50}")
    print(f"  전체: {len(items)}개 (단일: {n_single}, 복합: {n_multi})")
    print(f"\n  Intent별 출현 횟수:")
    for label in INTENT_LABELS:
        bar = "█" * (label_counts[label] // 10)
        print(f"    {label:<16} {label_counts[label]:4d}  {bar}")

    if pair_counts:
        print(f"\n  복합 조합별:")
        for pair, count in pair_counts.most_common():
            print(f"    {'+'.join(pair):<35} {count:3d}")


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    print("멀티라벨 Intent 학습 데이터 생성")
    print("=" * 50)

    # 1. 기존 v2 데이터 로드
    train_single = load_jsonl(V2_TRAIN)
    val_single   = load_jsonl(V2_VAL)
    test_single  = load_jsonl(V2_TEST)
    print(f"\nv2 데이터 로드: train={len(train_single)}, val={len(val_single)}, test={len(test_single)}")

    # 2. 단일 → 멀티라벨 변환
    train_multi = convert_single_to_multilabel(train_single)
    val_multi   = convert_single_to_multilabel(val_single)
    test_multi  = convert_single_to_multilabel(test_single)

    # 3. 복합 데이터 생성 (train 데이터 기반)
    intent_groups = load_by_intent(train_single)
    # 3:1 비율 맞추기: 단일 2,327개 → 복합 ~776개 필요 → 10쌍 × 78개
    n_per_pair = max(30, len(train_single) // 3 // len(COMPOUND_PAIRS) + 1)
    print(f"3:1 비율 목표 → 조합당 {n_per_pair}개 생성")
    compounds = generate_compound_examples(intent_groups, n_per_pair=n_per_pair)
    print(f"\n복합 데이터 생성: {len(compounds)}개")

    # 4. 복합 데이터 분할
    comp_train, comp_val, comp_test = split_compound_data(compounds)
    print(f"  train: {len(comp_train)}, val: {len(comp_val)}, test: {len(comp_test)}")

    # 5. 합치기
    final_train = train_multi + comp_train
    final_val   = val_multi + comp_val
    final_test  = test_multi + comp_test

    random.shuffle(final_train)
    random.shuffle(final_val)
    random.shuffle(final_test)

    # 6. 저장
    print(f"\n저장 경로: {OUT_DIR}")
    save_jsonl(final_train, OUT_DIR / "train.jsonl")
    save_jsonl(final_val,   OUT_DIR / "val.jsonl")
    save_jsonl(final_test,  OUT_DIR / "test.jsonl")

    # 복합 데이터만 따로 저장 (검증용)
    save_jsonl(compounds, OUT_DIR / "compound_only.jsonl")

    # 7. 통계
    print_stats(final_train, "Train 데이터")
    print_stats(final_val,   "Val 데이터")
    print_stats(final_test,  "Test 데이터")
    print_stats(compounds,   "복합 데이터 전체")

    # 8. 샘플 출력
    print(f"\n{'─'*50}")
    print("  복합 데이터 샘플 (10개)")
    print(f"{'─'*50}")
    for item in random.sample(compounds, min(10, len(compounds))):
        labels_str = " + ".join(item["labels"])
        print(f"  [{labels_str}]")
        print(f"    {item['text']}")
        print()


if __name__ == "__main__":
    main()
