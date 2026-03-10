"""
멀티라벨 Intent 학습 데이터 생성기 v4

v3 대비 변경사항 (v3+후처리 오답 11건 분석 반영):
- judgment 단독 인식 강화: "판단도 부탁", "위반 여부랑", "쓸 수 있는지" 패턴
- doc_generate vs doc_summary 구분: "회의록 정리/공유"=generate, "보고서로 정리"=generate
- doc_qa vs doc_summary 구분: "핵심 수치 알려줘"=qa, "핵심만 정리"=summary
- connector trap 보강: "X이랑 Y 판단해줘"=단일judgment, "규정 검토 분석"=judgment
- doc_search 누락 방지: 3중에서 "찾아서" 포함 패턴 강화
- 골든 데이터 40→70개 (30개 추가)
- 3중 intent 템플릿 확대 (10→15개)

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

OUT_DIR  = ROOT / "data" / "training" / "intent_multilabel"
OUT_DIR.mkdir(parents=True, exist_ok=True)

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_qa",
]

# ── 쌍별 전용 템플릿 (접속사형 + 무접속사형 혼합) ──────────────────────────────
# {A}=원문A, {B}=원문B, {A_short}=어간A, {B_short}=어간B

COMPOUND_PAIRS = [
    # 규정 검색 → 판단 (v2 오답 다수 — 집중 보강)
    ("doc_search", "judgment", [
        "{A_short} 찾아서 {B_short}",
        "{A_short} 검색하고 {B_short}",
        "{A_short} 확인한 다음 {B_short}",
        "{A_short}이랑 {B_short}",
        "{A_short}, {B_short}도",
        "{A_short} {B_short}까지 확인해줘",
        "{A_short}부터 {B_short}까지 다 알려줘",
        "{A_short} 확인 후 {B_short}",
        "{A_short} 알려주고 {B_short}도",
        # v3 추가 — 조건절/순차 의존
        "{A_short} 위반 여부까지 확인해줘",
        "{A_short}이랑 위반인지도 알려줘",
        "{A_short}, 가능한지도 판단해줘",
        "{A_short} 알려주고 위반 여부도 봐줘",
        "{A_short} 규정 확인하고 {B_short}",
    ]),
    # 일정 조회 → 일정 추가 (v2 오답: 있으면/보고 패턴 약함)
    ("schedule_view", "schedule_add", [
        "{A_short} 확인하고 {B_short}",
        "{A_short} 보여주고 {B_short}",
        "{A_short} 있으면 {B_short}",
        "{A_short} 비어있는 데 맞춰 {B_short}",
        "{A_short} 보고 {B_short}",
        "{A_short} 확인 후 {B_short}",
        "{A_short}, {B_short}",
        "{A_short}, 빈 데 {B_short}",
        "{A_short}에 맞춰서 {B_short}",
        # v3 추가
        "{A_short} 비는지 보고 {B_short}",
        "{A_short} 겹치는 거 없는지 확인 후 {B_short}",
        "{A_short} 빈 시간 있으면 {B_short}",
        "{A_short}, 빈 날에 {B_short}",
    ]),
    # 문서 검색 → 문서 생성 (v2 오답: 참고해서 패턴)
    ("doc_search", "doc_generate", [
        "{A_short} 바탕으로 {B_short}",
        "{A_short} 찾아서 {B_short}",
        "{A_short} 확인하고 {B_short}",
        "{A_short} 참고해서 {B_short}",
        "{A_short} 토대로 {B_short}",
        "{A_short} 내용으로 {B_short}",
        "{A_short}, {B_short}도",
        "{A_short}이랑 {B_short}",
        # v3 추가
        "{A_short} 참고해서 이번 {B_short}",
        "{A_short} 기반으로 {B_short}",
        "{A_short} 찾아서 그걸로 {B_short}",
    ]),
    # 문서 요약 → 문서 생성
    ("doc_summary", "doc_generate", [
        "{A_short} 요약하고 {B_short}",
        "{A_short} 정리한 다음 {B_short}",
        "{A_short} 정리해서 {B_short}",
        "{A_short}, {B_short}도",
        "{A_short}이랑 {B_short}",
        "{A_short} 뽑아서 {B_short}에 넣어줘",
        # v3 추가
        "{A_short} 핵심만 뽑아서 {B_short}",
        "{A_short} 정리하고 그걸로 {B_short}",
    ]),
    # 문서 QA → 판단 (v2 오답: 확인하고+적용 패턴)
    ("doc_qa", "judgment", [
        "{A_short} 확인하고 {B_short}",
        "{A_short} 알아본 다음 {B_short}",
        "{A_short} 확인해서 {B_short}",
        "{A_short}, {B_short}도",
        "{A_short} 보고 {B_short}",
        "{A_short}이랑 {B_short}",
        # v3 추가
        "{A_short} 확인하고 적용 가능한지도 봐줘",
        "{A_short} 알아보고 위반인지 판단해줘",
        "{A_short} 내용 확인하고 {B_short}",
    ]),
    # 문서 검색 → 문서 요약 (v2 오답: 압축 표현)
    ("doc_search", "doc_summary", [
        "{A_short} 찾아서 {B_short}",
        "{A_short} 검색하고 {B_short}",
        "{A_short} 중에 {B_short}",
        "{A_short} 관련 부분 {B_short}",
        "{A_short}, {B_short}",
        "{A_short}이랑 {B_short}",
        "{A_short} {B_short}까지",
        # v3 추가 — 압축 표현 (검색+정리가 한 문장)
        "{A_short} 사례 정리해줘",
        "{A_short} 찾아서 요약해줘",
        "{A_short} 관련 내용 요약본 알려줘",
    ]),
    # 판단 → 문서 생성 (v2 오답: 검토하고+수정본)
    ("judgment", "doc_generate", [
        "{A_short} 판단하고 {B_short}",
        "{A_short} 확인한 다음 {B_short}",
        "{A_short} 검토하고 {B_short}",
        "{A_short}, {B_short}도",
        "{A_short} 보고 {B_short}",
        "{A_short} 결과를 {B_short}",
        # v3 추가
        "{A_short} 검토하고 수정본 만들어줘",
        "{A_short} 문제 있는지 보고 {B_short}",
        "{A_short} 판단 후 결과를 {B_short}",
    ]),
    # 일정 조회 → 판단
    ("schedule_view", "judgment", [
        "{A_short} 확인하고 {B_short}",
        "{A_short} 보고 {B_short}",
        "{A_short}, {B_short}도",
        "{A_short}이랑 {B_short}",
        # v3 추가
        "{A_short} 확인하고 가능한지 판단해줘",
    ]),
    # 문서 QA → 문서 생성 (v2 오답: 토대로/내용으로 패턴)
    ("doc_qa", "doc_generate", [
        "{A_short} 확인해서 {B_short}",
        "{A_short} 알아보고 {B_short}",
        "{A_short} 토대로 {B_short}",
        "{A_short} 내용으로 {B_short}",
        "{A_short}, {B_short}도",
        "{A_short} 참고해서 {B_short}",
        # v3 추가 — 순차 의존 강화
        "{A_short} 토대로 후속 {B_short}",
        "{A_short} 내용으로 보고서 만들어줘",
        "{A_short} 내용 확인하고 {B_short}",
        "{A_short} 결과로 {B_short}",
    ]),
    # 문서 검색 → 문서 QA
    ("doc_search", "doc_qa", [
        "{A_short} 찾아서 {B_short}",
        "{A_short} 검색하고 {B_short}",
        "{A_short}, {B_short}도",
        "{A_short}이랑 {B_short}",
        # v3 추가
        "{A_short} 찾아서 내용 알려줘",
    ]),
    # 문서 QA → 문서 요약
    ("doc_qa", "doc_summary", [
        "{A_short} 확인하고 {B_short}",
        "{A_short} 내용 {B_short}",
        "{A_short}, {B_short}도",
        # v3 추가
        "{A_short} 알려주고 {B_short}도",
        "{A_short} 확인하고 핵심만 정리해줘",
    ]),
    # 일정 조회 → 문서 생성
    ("schedule_view", "doc_generate", [
        "{A_short} 확인하고 {B_short}",
        "{A_short}, {B_short}도",
        "{A_short}이랑 {B_short}",
        # v3 추가
        "{A_short} 보고 {B_short}",
    ]),
    # 문서 검색 → 일정 조회
    ("doc_search", "schedule_view", [
        "{A_short}이랑 {B_short}",
        "{A_short}, {B_short}도",
        "{A_short} 확인하고 {B_short}",
        # v3 추가
        "{A_short}도 보고 싶고 {B_short}도 궁금해",
    ]),
    # ── v3 새 쌍 추가 ──
    # 문서 요약 → 판단 (v2 오답 id15: 요약본이랑 위반 기준)
    ("doc_summary", "judgment", [
        "{A_short}이랑 {B_short}",
        "{A_short}, {B_short}도",
        "{A_short} 정리하고 {B_short}",
        "{A_short} 요약하고 {B_short}",
        "{A_short} 핵심 정리하고 위반인지도 봐줘",
        # v4 추가 — [오답 15] "요약본이랑 처벌 기준" 패턴
        "{A_short} 요약본이랑 {B_short}",
        "{A_short} 요약해주고 {B_short}도",
    ]),
]

# ── 3중 intent 조합 ──────────────────────────────────────────────────────────

TRIPLE_COMBOS = [
    ("doc_search", "judgment", "doc_generate"),
    ("schedule_view", "schedule_add", "doc_generate"),
    ("doc_search", "doc_summary", "judgment"),
    ("doc_qa", "doc_summary", "doc_generate"),
    ("schedule_view", "judgment", "schedule_add"),
    ("doc_search", "doc_qa", "judgment"),
    ("doc_search", "doc_generate", "doc_summary"),
    # v3 추가 조합
    ("doc_qa", "judgment", "doc_generate"),
    ("doc_search", "judgment", "doc_summary"),
    ("doc_qa", "doc_generate", "schedule_view"),
]

TRIPLE_TEMPLATES = [
    "{A_short} 찾아서 {B_short}, {C_short}까지",
    "{A_short} 확인하고 {B_short} 다음에 {C_short}",
    "{A_short} 보고 {B_short}, {C_short}도",
    "{A_short}, {B_short}, {C_short}까지 전부",
    "{A_short} 확인 후 {B_short} 결과를 {C_short}",
    "{A_short} 찾아서 {B_short} 그리고 {C_short}",
    "{A_short} 확인하고 {B_short}, 그걸로 {C_short}",
    # v3 추가 — 순차 의존형
    "{A_short} 찾아서 {B_short} 판단하고 결과를 {C_short}",
    "{A_short} 확인하고 {B_short} 정리해서 {C_short}",
    "{A_short} 알아보고 {B_short}, 가능하면 {C_short}",
    # v4 추가 — [오답 46,48] "찾아서" 포함 3중, 순차 의존 강화
    "{A_short} 찾아서 {B_short}해주고 {C_short}도",
    "{A_short} 검색해서 {B_short}, 결과를 {C_short}",
    "{A_short} 찾아서 {B_short} 후에 {C_short}",
    "{A_short} 확인한 다음 {B_short}, {C_short}까지",
    "{A_short} 찾아서 {B_short}하고 그걸로 {C_short}",
]

# ── "그리고" 함정 단일 — 같은 intent 내 나열 ─────────────────────────────────

CONNECTOR_TRAP_TEMPLATES = [
    "{A} 그리고 {B}",
    "{A_short}이랑 {B_short}",
    "{A_short}, {B_short}도",
    "{A_short} 하고 {B_short}",
    # v4 추가 — [오답 59] "X이랑 Y + 단일동사" 패턴
    "{A_short}이랑 {B_short} 알려줘",
    "{A_short}이랑 {B_short} 확인해줘",
    "{A_short}랑 {B_short}",
]

# 함정 생성 대상 intent (같은 intent 문장 2개를 연결)
TRAP_INTENTS = ["doc_search", "schedule_view", "judgment", "doc_generate", "doc_summary", "doc_qa"]


# ── 문장 단축 ────────────────────────────────────────────────────────────────

def shorten_sentence(text):
    """문장 끝의 종결어미 제거하여 접속 가능한 형태로 변환"""
    original = text
    endings = [
        r'하여\s*주시기\s*바랍니다',
        r'해\s*주시기\s*바랍니다',
        r'부탁드립니다',
        r'부탁합니다',
        r'해\s*주세요',
        r'해\s*줘',
        r'해줘',
        r'해주세요',
        r'[가-힣]아\s*주세요',
        r'[가-힣]어\s*주세요',
        r'[가-힣]아\s*줘',
        r'[가-힣]어\s*줘',
        r'(?:보여|알려|찾아|만들어|정리해|검색해|확인해|조회해|등록해|추가해|작성해|생성해|요약해)\s*(?:줘|주세요|줄래|줄래요|줄 수 있어\??|줄 수 있나요\??)',
        r'(?:합니다|합니까|하세요|할래요?|할게요?|해봐|해요|하나요|인가요|인지|되나요|돼\?|돼요\?|있나요|있어\??|없나요|없어\??|뭐야\??|뭐예요\??|뭔가요)',
        r'(?:줘|주세요|볼래|볼게|봐|봐요)',
        r'수\s*있(?:어|나|을까)\??',
    ]
    for pattern in endings:
        text = re.sub(r'\s*' + pattern + r'\s*[.?!]*$', '', text).strip()
    text = re.sub(r'[.?!]+$', '', text).strip()
    return text if len(text) >= 3 else original


def extract_keyword(text):
    """문장에서 핵심 키워드(2~4어절)만 추출 — 짧은 복합용"""
    short = shorten_sentence(text)
    words = short.split()
    if len(words) <= 3:
        return short
    return " ".join(words[:3])


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


# ── 복합 데이터 생성 (v2: 다양한 패턴) ───────────────────────────────────────

def generate_compound_examples(intent_groups, n_per_pair=30):
    """
    intent 쌍별로 n_per_pair개 복합 문장 생성.

    v2 비율:
      20% — "그리고" 연결
      80% — 쌍별 전용 템플릿 (접속사형 + 무접속사형 혼합)
    """
    compounds = []
    seen_texts = set()

    pair_templates = {
        (a, b): t for a, b, t in COMPOUND_PAIRS
    }
    all_pairs = [(a, b) for a, b, _ in COMPOUND_PAIRS]

    for intent_a, intent_b in all_pairs:
        texts_a = intent_groups.get(intent_a, [])
        texts_b = intent_groups.get(intent_b, [])
        if not texts_a or not texts_b:
            continue

        templates = pair_templates.get((intent_a, intent_b), [])
        n_grigo   = int(n_per_pair * 0.2)   # 20% 그리고
        n_template = n_per_pair - n_grigo    # 80% 다양한 템플릿

        # ── 1) "그리고" 연결 (20%) ──
        generated = 0
        attempts = 0
        while generated < n_grigo and attempts < n_per_pair * 20:
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

        # ── 2) 다양한 템플릿 (80%) ──
        tmpl_generated = 0
        attempts = 0
        while tmpl_generated < n_template and templates and attempts < n_per_pair * 30:
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
            # 종결어미 없으면 추가
            if not re.search(r'(줘|주세요|할래|합니다|바랍니다|해봐|하세요|나요|돼\??|뭐야|확인|판단|부탁|까지|전부)\s*[.?!]*$', text):
                text += " 해줘"

            if text not in seen_texts:
                seen_texts.add(text)
                compounds.append({
                    "text": text,
                    "labels": sorted(set([intent_a, intent_b])),
                })
                tmpl_generated += 1

    return compounds


# ── 짧은 복합 문장 생성 ──────────────────────────────────────────────────────

SHORT_COMPOUND_TEMPLATES = [
    "{A_kw}, {B_kw}도",
    "{A_kw}이랑 {B_kw}",
    "{A_kw}, {B_kw} 부탁",
    "{A_kw} {B_kw}도",
    "{A_kw}여부랑 {B_kw}",
    "{A_kw}, {B_kw}까지",
    "{A_kw} 보고 {B_kw}",
    # v3 추가 — 동사 연쇄형 짧은 패턴
    "{A_kw} 보여주고 {B_kw}",
    "{A_kw} 확인, {B_kw}도",
    "{A_kw} 찾아줘, {B_kw}도",
    "{A_kw}이랑 {B_kw} 해줘",
]

def generate_short_compounds(intent_groups, n_total=200):
    """극단적으로 짧은 복합 문장 생성 (10~30자)"""
    shorts = []
    seen = set()

    all_pairs = [(a, b) for a, b, _ in COMPOUND_PAIRS]
    n_per_pair = max(8, n_total // len(all_pairs) + 1)

    for intent_a, intent_b in all_pairs:
        texts_a = intent_groups.get(intent_a, [])
        texts_b = intent_groups.get(intent_b, [])
        if not texts_a or not texts_b:
            continue

        generated = 0
        attempts = 0
        while generated < n_per_pair and attempts < n_per_pair * 30:
            attempts += 1
            a_kw = extract_keyword(random.choice(texts_a))
            b_kw = extract_keyword(random.choice(texts_b))
            if len(a_kw) < 2 or len(b_kw) < 2:
                continue

            template = random.choice(SHORT_COMPOUND_TEMPLATES)
            text = template.format(A_kw=a_kw, B_kw=b_kw)

            # v3: 글자수 제한 25→30으로 완화
            if len(text) > 30:
                continue

            if text not in seen:
                seen.add(text)
                shorts.append({
                    "text": text,
                    "labels": sorted(set([intent_a, intent_b])),
                })
                generated += 1

    return shorts


# ── 3중 intent 문장 생성 ─────────────────────────────────────────────────────

def generate_triple_compounds(intent_groups, n_per_combo=15):
    """3개 intent 조합 복합 문장 생성"""
    triples = []
    seen = set()

    for intent_a, intent_b, intent_c in TRIPLE_COMBOS:
        texts_a = intent_groups.get(intent_a, [])
        texts_b = intent_groups.get(intent_b, [])
        texts_c = intent_groups.get(intent_c, [])
        if not texts_a or not texts_b or not texts_c:
            continue

        generated = 0
        attempts = 0
        while generated < n_per_combo and attempts < n_per_combo * 30:
            attempts += 1
            a = random.choice(texts_a)
            b = random.choice(texts_b)
            c = random.choice(texts_c)
            a_short = shorten_sentence(a)
            b_short = shorten_sentence(b)
            c_short = shorten_sentence(c)

            if len(a_short) < 4 or len(b_short) < 4 or len(c_short) < 4:
                continue

            template = random.choice(TRIPLE_TEMPLATES)
            text = template.format(
                A=a, B=b, C=c,
                A_short=a_short, B_short=b_short, C_short=c_short,
            )
            if not re.search(r'(줘|주세요|합니다|바랍니다|하세요|나요|부탁|까지|전부)\s*[.?!]*$', text):
                text += " 해줘"

            if text not in seen:
                seen.add(text)
                triples.append({
                    "text": text,
                    "labels": sorted(set([intent_a, intent_b, intent_c])),
                })
                generated += 1

    return triples


# ── "그리고" 함정 단일 문장 생성 ─────────────────────────────────────────────

def generate_connector_traps(intent_groups, n_per_intent=15):
    """
    같은 intent 문장 2개를 "그리고/이랑" 등으로 연결.
    라벨은 단일 — over-triggering 방지 학습용.
    """
    traps = []
    seen = set()

    for intent in TRAP_INTENTS:
        texts = intent_groups.get(intent, [])
        if len(texts) < 2:
            continue

        generated = 0
        attempts = 0
        while generated < n_per_intent and attempts < n_per_intent * 30:
            attempts += 1
            a, b = random.sample(texts, 2)
            a_short = shorten_sentence(a)
            b_short = shorten_sentence(b)

            template = random.choice(CONNECTOR_TRAP_TEMPLATES)
            text = template.format(A=a, B=b, A_short=a_short, B_short=b_short)

            if not re.search(r'(줘|주세요|합니다|바랍니다|하세요|나요|부탁|까지|전부)\s*[.?!]*$', text):
                text += " 해줘"

            if text not in seen:
                seen.add(text)
                traps.append({
                    "text": text,
                    "labels": [intent],  # 단일 라벨!
                })
                generated += 1

    return traps


# ── 수동 골든 데이터 (v3) ────────────────────────────────────────────────────
# adversarial v2 오답 패턴을 직접 반영. 테스트 문장 자체가 아닌 유사 패턴.

GOLDEN_COMPOUND = [
    # ── 조건절/순차 의존 (no_connector 보강) ──
    {"text": "휴가 규정이랑 사용 가능한지 판단해줘", "labels": ["doc_search", "judgment"]},
    {"text": "복장 규정이랑 위반인지도 알려줘", "labels": ["doc_search", "judgment"]},
    {"text": "교통비 기준 위반 여부까지 확인해줘", "labels": ["doc_search", "judgment"]},
    {"text": "야근 수당 규정이랑 적용 가능한지 봐줘", "labels": ["doc_search", "judgment"]},
    {"text": "오후에 빈 시간 있으면 미팅 하나 잡아줘", "labels": ["schedule_view", "schedule_add"]},
    {"text": "내일 일정 비는지 보고 세미나 등록해줘", "labels": ["schedule_view", "schedule_add"]},
    {"text": "이번 주 빈 시간 확인하고 워크숍 넣어줘", "labels": ["schedule_view", "schedule_add"]},
    {"text": "지난 회의 내용 토대로 보고서 작성해줘", "labels": ["doc_qa", "doc_generate"]},
    {"text": "프로젝트 보고서 내용으로 제안서 만들어줘", "labels": ["doc_qa", "doc_generate"]},
    {"text": "실적 자료 토대로 분기 보고서 써줘", "labels": ["doc_qa", "doc_generate"]},
    {"text": "인사 규정 위반 사례 정리해줘", "labels": ["doc_search", "doc_summary"]},
    {"text": "보안 규정 중에서 핵심만 요약해줘", "labels": ["doc_search", "doc_summary"]},
    {"text": "출장 문서 참고해서 이번 기획서 초안 잡아줘", "labels": ["doc_search", "doc_generate"]},
    {"text": "지난 보고서 참고해서 새 제안서 작성해줘", "labels": ["doc_search", "doc_generate"]},
    # ── 암묵적 복합 (implicit 보강) ──
    {"text": "복리후생도 보고 싶고 남은 연차도 궁금해", "labels": ["doc_search", "schedule_view"]},
    {"text": "이 계약서 검토하고 수정본 만들어줘", "labels": ["judgment", "doc_generate"]},
    {"text": "매출 자료에서 핵심 수치 알려주고 발표 자료도 준비해줘", "labels": ["doc_qa", "doc_generate"]},
    {"text": "관련 조항 찾아주고 적용되는지 봐줘", "labels": ["doc_search", "judgment"]},
    {"text": "예산서에서 남은 금액 확인하고 초과 가능한지 판단해줘", "labels": ["doc_qa", "judgment"]},
    # ── 짧은 복합 보강 ──
    {"text": "일정 보여주고 하나 추가", "labels": ["schedule_view", "schedule_add"]},
    {"text": "일정 확인, 빈 데 추가해줘", "labels": ["schedule_view", "schedule_add"]},
    {"text": "문서 검색, 판단도 해줘", "labels": ["doc_search", "judgment"]},
    {"text": "보고서 마감이랑 내일 일정", "labels": ["doc_generate", "schedule_view"]},
    {"text": "요약해주고 제안서도 써줘", "labels": ["doc_summary", "doc_generate"]},
    {"text": "규정 찾아줘, 위반인지도 봐줘", "labels": ["doc_search", "judgment"]},
    # ── judgment vs doc_qa 구분 강화 ──
    # "위반/가능/적용/처벌" = judgment (doc_qa 아님)
    {"text": "위반 여부 판단해줘", "labels": ["judgment"]},
    {"text": "이 경우 규정에 적용 가능한지 봐줘", "labels": ["judgment"]},
    {"text": "처벌 기준이 어떻게 되는지 판단해줘", "labels": ["judgment"]},
    {"text": "이번 건 가능한지 규정대로 판단해줘", "labels": ["judgment"]},
    {"text": "규정 위반인지 아닌지 확인해줘", "labels": ["judgment"]},
    # "내용/어떤 내용/뭐야" = doc_qa (judgment 아님)
    {"text": "지난 회의에서 뭐 결정됐어", "labels": ["doc_qa"]},
    {"text": "보고서에 어떤 내용 있어", "labels": ["doc_qa"]},
    {"text": "계약 조건이 뭐야", "labels": ["doc_qa"]},
    {"text": "프로젝트 현황 알려줘", "labels": ["doc_qa"]},
    {"text": "매출 실적이 얼마야", "labels": ["doc_qa"]},
    # ── 함정 단일 보강 (over-triggering 방지) ──
    {"text": "규정 꼼꼼히 확인해서 자세하게 알려줘", "labels": ["doc_search"]},
    {"text": "보고서 작성해서 보내줘", "labels": ["doc_generate"]},
    {"text": "문서 찾아서 보여줘", "labels": ["doc_search"]},
    {"text": "일정 확인하고 알려줘", "labels": ["schedule_view"]},
    {"text": "회의 내용이랑 결정사항 알려줘", "labels": ["doc_qa"]},

    # ═══ v4 추가 — 오답 11건 분석 반영 (30개) ═══

    # ── [오답 1,41,43] judgment 짧은/암묵적 패턴 ──
    # "쓸 수 있는지", "판단도 부탁", "위반 여부랑" → 모델이 judgment 확률 낮게 예측
    {"text": "연차 규정이랑 이번 달 사용 가능한지 알려줘", "labels": ["doc_search", "judgment"]},
    {"text": "출장비 이번 건 쓸 수 있는지 알려줘", "labels": ["judgment"]},
    {"text": "경조사비 사용 가능한지 알려줘", "labels": ["judgment"]},
    {"text": "규정 검색하고 판단도 부탁해", "labels": ["doc_search", "judgment"]},
    {"text": "서류 찾아주고 판단도 해줘", "labels": ["doc_search", "judgment"]},
    {"text": "위반 여부랑 관련 규정 알려줘", "labels": ["doc_search", "judgment"]},
    {"text": "초과근무 규정 위반 여부랑 관련 문서 찾아줘", "labels": ["doc_search", "judgment"]},
    {"text": "복리후생 어떤 거 있는지 알려줘", "labels": ["doc_search"]},

    # ── [오답 17,46] doc_generate vs doc_summary 구분 ──
    # "회의록 정리/공유" = generate, "보고서로 정리" = generate
    {"text": "회의록 깔끔하게 정리해줘", "labels": ["doc_generate"]},
    {"text": "회의록 정리해서 팀에 공유해줘", "labels": ["doc_generate"]},
    {"text": "미팅 내용 정리해서 회의록 만들어줘", "labels": ["doc_generate"]},
    {"text": "결과를 보고서로 정리해줘", "labels": ["doc_generate"]},
    {"text": "분석 결과를 보고서로 만들어줘", "labels": ["doc_generate"]},
    {"text": "이 내용 요약해서 보고서 작성해줘", "labels": ["doc_summary", "doc_generate"]},

    # ── [오답 31] doc_qa vs doc_summary 구분 ──
    # "핵심 수치/금액/데이터 알려줘" = doc_qa (정보 추출)
    {"text": "보고서에서 핵심 수치 알려줘", "labels": ["doc_qa"]},
    {"text": "매출 데이터 얼마인지 알려줘", "labels": ["doc_qa"]},
    {"text": "예산 남은 금액 확인해줘", "labels": ["doc_qa"]},
    {"text": "실적 보고서에서 핵심 수치 뽑아주고 발표 자료 만들어줘", "labels": ["doc_qa", "doc_generate"]},

    # ── [오답 51,59] connector trap 보강 ──
    # "규정 검토 분석 결과" = judgment (단일)
    {"text": "규정 검토 결과 알려줘", "labels": ["judgment"]},
    {"text": "분석 결과를 알려줘", "labels": ["judgment"]},
    {"text": "규정 검토해서 분석 결과 정리해줘", "labels": ["judgment"]},
    # "X이랑 Y 판단해줘" = judgment 단일 (같은 주제 나열)
    {"text": "야근 수당이랑 초과근무 수당 알려줘", "labels": ["judgment"]},
    {"text": "연차이랑 병가 기준 판단해줘", "labels": ["judgment"]},
    {"text": "통상임금이랑 시간외수당 기준 알려줘", "labels": ["judgment"]},

    # ── [오답 15] doc_summary+judgment 과잉 doc_search 방지 ──
    # "요약본이랑 처벌 기준" = doc_summary+judgment (doc_search 아님)
    {"text": "규정 요약본이랑 처벌 기준 알려줘", "labels": ["doc_summary", "judgment"]},
    {"text": "규정 요약해주고 위반 시 처벌 기준도 알려줘", "labels": ["doc_summary", "judgment"]},

    # ── [오답 12] "어떤 거 있는지" = doc_search ──
    {"text": "복리후생 어떤 거 있는지 알려줘", "labels": ["doc_search"]},
    {"text": "지원 제도 뭐가 있는지 알려줘", "labels": ["doc_search"]},
]


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
    n_triple = sum(1 for item in items if len(item["labels"]) >= 3)

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
    print(f"  전체: {len(items)}개 (단일: {n_single}, 2중복합: {n_multi - n_triple}, 3중복합: {n_triple})")
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
    print("멀티라벨 Intent 학습 데이터 생성 v4")
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

    intent_groups = load_by_intent(train_single)

    # 3. 2중 복합 데이터 생성 (다양한 패턴)
    n_pairs = len(COMPOUND_PAIRS)
    n_per_pair = max(30, len(train_single) // 3 // n_pairs + 1)
    print(f"\n[2중 복합] 조합당 {n_per_pair}개 생성 (비율: 그리고 20% / 템플릿 80%)")
    compounds = generate_compound_examples(intent_groups, n_per_pair=n_per_pair)
    print(f"  → 생성: {len(compounds)}개")

    # 4. 짧은 복합 데이터 생성 (v3: 150→200)
    print(f"\n[짧은 복합] 생성 중...")
    short_compounds = generate_short_compounds(intent_groups, n_total=200)
    print(f"  → 생성: {len(short_compounds)}개")

    # 5. 3중 intent 데이터 생성 (v4: 25→30개/조합, 템플릿 15개)
    print(f"\n[3중 복합] 조합당 30개 생성...")
    triple_compounds = generate_triple_compounds(intent_groups, n_per_combo=30)
    print(f"  → 생성: {len(triple_compounds)}개")

    # 6. "그리고" 함정 단일 데이터 생성 (v4: 15→20개/intent, 템플릿 7개)
    print(f"\n[함정 단일] intent당 20개 생성...")
    connector_traps = generate_connector_traps(intent_groups, n_per_intent=20)
    print(f"  → 생성: {len(connector_traps)}개")

    # 7. 수동 골든 데이터 (v3 신규)
    golden = GOLDEN_COMPOUND.copy()
    print(f"\n[골든 데이터] {len(golden)}개 (수동 작성)")

    # 8. 전체 복합 데이터 합치기
    golden_compound = [g for g in golden if len(g["labels"]) >= 2]
    golden_single   = [g for g in golden if len(g["labels"]) == 1]
    all_compounds = compounds + short_compounds + triple_compounds + golden_compound
    print(f"\n전체 복합 데이터: {len(all_compounds)}개")
    print(f"  2중: {len(compounds)}, 짧은: {len(short_compounds)}, 3중: {len(triple_compounds)}, 골든복합: {len(golden_compound)}")
    print(f"함정 단일 데이터: {len(connector_traps)}개")
    print(f"골든 단일 데이터: {len(golden_single)}개")

    # 9. 복합 데이터 분할
    comp_train, comp_val, comp_test = split_compound_data(all_compounds)
    trap_train, trap_val, trap_test = split_compound_data(connector_traps)
    print(f"\n복합 분할: train={len(comp_train)}, val={len(comp_val)}, test={len(comp_test)}")
    print(f"함정 분할: train={len(trap_train)}, val={len(trap_val)}, test={len(trap_test)}")

    # 10. 최종 합치기 (골든 단일은 train에만 추가)
    final_train = train_multi + comp_train + trap_train + golden_single
    final_val   = val_multi + comp_val + trap_val
    final_test  = test_multi + comp_test + trap_test

    random.shuffle(final_train)
    random.shuffle(final_val)
    random.shuffle(final_test)

    # 11. 저장
    print(f"\n저장 경로: {OUT_DIR}")
    save_jsonl(final_train, OUT_DIR / "train.jsonl")
    save_jsonl(final_val,   OUT_DIR / "val.jsonl")
    save_jsonl(final_test,  OUT_DIR / "test.jsonl")

    # 복합 데이터만 따로 저장 (검증용)
    save_jsonl(all_compounds, OUT_DIR / "compound_only.jsonl")

    # 12. 통계
    print_stats(final_train, "Train 데이터")
    print_stats(final_val,   "Val 데이터")
    print_stats(final_test,  "Test 데이터")
    print_stats(all_compounds, "복합 데이터 전체")

    # 13. v3 vs v4 비교
    print(f"\n{'─'*50}")
    print("  v3 vs v4 데이터 비교")
    print(f"{'─'*50}")
    n_total = len(final_train) + len(final_val) + len(final_test)
    n_compound = len(all_compounds)
    n_trap = len(connector_traps)
    print(f"  {'항목':<20} {'v3':>8} {'v4':>8}")
    print(f"  {'─'*20} {'─'*8} {'─'*8}")
    print(f"  {'전체 데이터':<20} {'4,272':>8} {n_total:>8}")
    print(f"  {'복합 데이터':<20} {'1,269':>8} {n_compound:>8}")
    print(f"  {'짧은 복합':<18} {'210':>10} {len(short_compounds):>8}")
    print(f"  {'3중 복합':<18} {'250':>10} {len(triple_compounds):>8}")
    print(f"  {'함정 단일':<18} {'90':>10} {n_trap:>8}")
    print(f"  {'골든 데이터':<18} {'40':>10} {len(golden):>8}")
    print(f"  {'쌍별 템플릿수':<18} {'~12개':>10} {'~14개':>8}")
    print(f"  {'3중 템플릿수':<18} {'10개':>10} {'15개':>8}")
    print(f"  {'함정 템플릿수':<18} {'4개':>10} {'7개':>8}")

    # 14. 샘플 출력
    print(f"\n{'─'*50}")
    print("  복합 데이터 샘플 (유형별)")
    print(f"{'─'*50}")

    print("\n  [2중 복합 - 다양한 패턴]")
    for item in random.sample(compounds, min(5, len(compounds))):
        labels_str = " + ".join(item["labels"])
        print(f"    [{labels_str}] {item['text']}")

    print("\n  [짧은 복합]")
    for item in random.sample(short_compounds, min(5, len(short_compounds))):
        labels_str = " + ".join(item["labels"])
        print(f"    [{labels_str}] {item['text']}")

    if triple_compounds:
        print("\n  [3중 복합]")
        for item in random.sample(triple_compounds, min(5, len(triple_compounds))):
            labels_str = " + ".join(item["labels"])
            print(f"    [{labels_str}] {item['text']}")

    print("\n  [골든 데이터 (수동)]")
    for item in random.sample(golden_compound, min(5, len(golden_compound))):
        labels_str = " + ".join(item["labels"])
        print(f"    [{labels_str}] {item['text']}")

    print("\n  [함정 단일 (그리고/이랑 있지만 단일)]")
    for item in random.sample(connector_traps, min(5, len(connector_traps))):
        labels_str = " + ".join(item["labels"])
        print(f"    [{labels_str}] {item['text']}")
    print()


if __name__ == "__main__":
    main()
