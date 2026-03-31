"""
기존 데이터 필터링 + 선별

1. C급(content/summary 미달) 제거
2. short 초과분 선별 (A급 80% / B급 20% 비율)
3. filtered 파일 저장

사용법:
    python data/training/v2_generate/filter_and_select.py
"""

import io
import json
import random
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent

SYN_PATHS = [
    BASE_DIR / "synthetic_generate.jsonl",
    BASE_DIR / "synthetic_report.jsonl",
    BASE_DIR / "synthetic_proposal.jsonl",
]
AIHUB_PATH = BASE_DIR / "ai_hub_generate_cleaned.jsonl"
SYN_OUT = BASE_DIR / "synthetic_filtered.jsonl"
AIHUB_OUT = BASE_DIR / "ai_hub_filtered.jsonl"

ALWAYS_FIELDS = {
    "meeting_minutes": ["content", "summary"],
    "report": ["overview", "main_content"],
    "proposal": ["content", "expected_effect"],
}
PRIORITY_FIELDS = {
    "meeting_minutes": ["decisions", "action_items"],
    "report": ["tasks", "next_plan", "issues"],
    "proposal": ["schedule", "budget", "background", "current_situation"],
}
SHORT_TARGET = {
    "meeting_minutes": 150,
    "report": 150,
    "proposal": 150,
}


def detect_type(user_msg):
    if "회의록" in user_msg: return "meeting_minutes"
    elif "보고서" in user_msg or "업무보고" in user_msg: return "report"
    elif "제안서" in user_msg: return "proposal"
    return None


def get_length_cat(user_msg):
    import re
    match = re.search(r'\[(?:회의 내용|업무 내용|제안 내용|내용)\]\s*\n', user_msg)
    if match:
        actual = user_msg[match.end():].strip()
    else:
        actual = user_msg
    plen = len(actual)
    if plen < 200: return "short"
    elif plen < 800: return "mid"
    elif plen < 1500: return "long"
    return "xlong"


def get_grade(sample):
    """A/B/C 등급 판정"""
    user_msg = sample["messages"][1]["content"]
    try:
        out = json.loads(sample["messages"][2]["content"])
    except:
        return None, None, None

    dt = detect_type(user_msg)
    if not dt:
        return None, None, None

    lcat = get_length_cat(user_msg)

    # always 필드 체크
    always_ok = all(
        bool(out.get(k) and out.get(k) != [] and out.get(k) != "")
        for k in ALWAYS_FIELDS[dt]
    )
    if not always_ok:
        return "C", dt, lcat

    # priority 필드 체크
    prio_filled = all(
        bool(out.get(k) and out.get(k) != [] and out.get(k) != "")
        for k in PRIORITY_FIELDS[dt]
    )
    return ("A" if prio_filled else "B"), dt, lcat


def load_jsonl(path):
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    return samples


def filter_dataset(samples, label):
    """C급 제거 + short 선별"""
    rng = random.Random(42)

    # 등급 분류
    graded = []
    c_count = 0
    for s in samples:
        grade, dt, lcat = get_grade(s)
        if grade is None:
            continue
        if grade == "C":
            c_count += 1
            continue
        graded.append({"sample": s, "grade": grade, "dt": dt, "lcat": lcat})

    print(f"[{label}] C급 제거: {c_count}건, 남은: {len(graded)}건")

    # short 초과분 선별
    keep = []
    for dt in ["meeting_minutes", "report", "proposal"]:
        short_a = [g for g in graded if g["dt"] == dt and g["lcat"] == "short" and g["grade"] == "A"]
        short_b = [g for g in graded if g["dt"] == dt and g["lcat"] == "short" and g["grade"] == "B"]
        non_short = [g for g in graded if g["dt"] == dt and g["lcat"] != "short"]

        target = SHORT_TARGET[dt]
        current_short = len(short_a) + len(short_b)

        if current_short <= target:
            # 부족하거나 딱 맞으면 전부 유지
            keep.extend(short_a)
            keep.extend(short_b)
        else:
            # 초과: A급 80% / B급 20% 비율로 선별
            n_a = int(target * 0.8)
            n_b = target - n_a

            rng.shuffle(short_a)
            rng.shuffle(short_b)

            selected_a = short_a[:n_a]
            selected_b = short_b[:n_b]

            # B급이 부족하면 A급으로 채움
            if len(selected_b) < n_b:
                extra = n_b - len(selected_b)
                selected_a = short_a[:n_a + extra]

            keep.extend(selected_a)
            keep.extend(selected_b)
            removed = current_short - len(selected_a) - len(selected_b)
            print(f"  {dt} short: {current_short}건 → {len(selected_a)+len(selected_b)}건 (A:{len(selected_a)} B:{len(selected_b)}, 제거:{removed}건)")

        keep.extend(non_short)

    return [g["sample"] for g in keep]


def main():
    print("=== 데이터 필터링 + 선별 ===\n")

    # Synthetic (3개 파일 병합 로드)
    syn = []
    for p in SYN_PATHS:
        if p.exists():
            loaded = load_jsonl(p)
            print(f"  {p.name}: {len(loaded)}건")
            syn.extend(loaded)
    print(f"Synthetic 로드: {len(syn)}건")
    syn_filtered = filter_dataset(syn, "Synthetic")

    with open(SYN_OUT, "w", encoding="utf-8") as f:
        for s in syn_filtered:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"Synthetic 필터 결과: {len(syn_filtered)}건 → {SYN_OUT}\n")

    # AI Hub
    aihub = load_jsonl(AIHUB_PATH)
    print(f"AI Hub 로드: {len(aihub)}건")
    aihub_filtered = filter_dataset(aihub, "AI Hub")

    with open(AIHUB_OUT, "w", encoding="utf-8") as f:
        for s in aihub_filtered:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"AI Hub 필터 결과: {len(aihub_filtered)}건 → {AIHUB_OUT}\n")

    # 합산 현황
    total = len(syn_filtered) + len(aihub_filtered)
    print(f"=== 합산: {total}건 (목표 1500건, 추가 생성 필요: {max(0, 1500-total)}건) ===")


if __name__ == "__main__":
    main()
