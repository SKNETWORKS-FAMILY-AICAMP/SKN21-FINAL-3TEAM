"""
학습 데이터 합치기 + train/eval 분할

사용법:
    python data/training/v2_generate/merge_and_split.py
    python data/training/v2_generate/merge_and_split.py --eval-ratio 0.1
"""

import argparse
import io
import json
import random
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent

SYNTHETIC_PATH = BASE_DIR / "synthetic_generate.jsonl"
AIHUB_CLEANED_PATH = BASE_DIR / "ai_hub_generate_cleaned.jsonl"
AIHUB_ORIGINAL_PATH = BASE_DIR / "ai_hub_generate.jsonl"
TRAIN_PATH = BASE_DIR / "train.jsonl"
EVAL_PATH = BASE_DIR / "eval.jsonl"


def load_jsonl(path: Path) -> list:
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    return samples


def detect_doc_type(sample: dict) -> str:
    user_msg = sample["messages"][1]["content"]
    if "회의록" in user_msg:
        return "meeting_minutes"
    elif "보고서" in user_msg or "업무보고" in user_msg:
        return "report"
    elif "제안서" in user_msg:
        return "proposal"
    return "unknown"


def analyze_fields(samples: list, label: str):
    """필드 분포 분석"""
    type_counts = {"meeting_minutes": 0, "report": 0, "proposal": 0}
    field_stats = {}

    for s in samples:
        doc_type = detect_doc_type(s)
        if doc_type == "unknown":
            continue
        type_counts[doc_type] += 1

        try:
            out = json.loads(s["messages"][2]["content"])
        except:
            continue

        for key, val in out.items():
            k = f"{doc_type}:{key}"
            if k not in field_stats:
                field_stats[k] = {"total": 0, "filled": 0}
            field_stats[k]["total"] += 1
            if val and val != [] and val != "" and val != {}:
                field_stats[k]["filled"] += 1

    print(f"\n=== {label} ({len(samples)}건) ===")
    print(f"  유형: {type_counts}")

    # priority 필드만 출력
    priority_keys = [
        "meeting_minutes:content", "meeting_minutes:summary",
        "meeting_minutes:decisions", "meeting_minutes:action_items",
        "report:overview", "report:main_content",
        "report:tasks", "report:next_plan",
        "proposal:content", "proposal:expected_effect",
        "proposal:schedule", "proposal:budget",
    ]
    print(f"  priority 필드 채움률:")
    for k in priority_keys:
        if k in field_stats:
            s = field_stats[k]
            pct = s["filled"] / s["total"] * 100 if s["total"] > 0 else 0
            print(f"    {k}: {s['filled']}/{s['total']} ({pct:.0f}%)")


def main():
    parser = argparse.ArgumentParser(description="학습 데이터 합치기 + 분할")
    parser.add_argument("--eval-ratio", type=float, default=0.1, help="eval 비율 (기본 10%)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    # 데이터 로드
    print("데이터 로드 중...")

    if SYNTHETIC_PATH.exists():
        synthetic = load_jsonl(SYNTHETIC_PATH)
        print(f"  Synthetic: {len(synthetic)}건")
    else:
        print(f"  [경고] {SYNTHETIC_PATH} 없음")
        synthetic = []

    if AIHUB_CLEANED_PATH.exists():
        aihub = load_jsonl(AIHUB_CLEANED_PATH)
        print(f"  AI Hub (정제): {len(aihub)}건")
    elif AIHUB_ORIGINAL_PATH.exists():
        aihub = load_jsonl(AIHUB_ORIGINAL_PATH)
        print(f"  AI Hub (원본, 정제본 없음): {len(aihub)}건")
    else:
        print(f"  [경고] AI Hub 데이터 없음")
        aihub = []

    # 합치기
    all_samples = synthetic + aihub
    print(f"\n합산: {len(all_samples)}건")

    if not all_samples:
        print("[오류] 데이터가 없습니다.")
        return

    # JSON 유효성 체크
    valid = []
    invalid = 0
    for s in all_samples:
        try:
            json.loads(s["messages"][2]["content"])
            valid.append(s)
        except:
            invalid += 1

    if invalid:
        print(f"  JSON 무효 제거: {invalid}건")
    print(f"  유효 데이터: {len(valid)}건")

    # 분할 전 분석
    analyze_fields(valid, "전체 (분할 전)")

    # 셔플 + 분할
    rng = random.Random(args.seed)
    rng.shuffle(valid)

    eval_count = int(len(valid) * args.eval_ratio)
    train_count = len(valid) - eval_count

    eval_data = valid[:eval_count]
    train_data = valid[eval_count:]

    # 저장
    with open(TRAIN_PATH, "w", encoding="utf-8") as f:
        for s in train_data:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    with open(EVAL_PATH, "w", encoding="utf-8") as f:
        for s in eval_data:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"\n=== 분할 완료 ===")
    print(f"  train: {train_count}건 → {TRAIN_PATH}")
    print(f"  eval:  {eval_count}건 → {EVAL_PATH}")

    # 분할 후 분석
    analyze_fields(train_data, "train")
    analyze_fields(eval_data, "eval")


if __name__ == "__main__":
    main()
