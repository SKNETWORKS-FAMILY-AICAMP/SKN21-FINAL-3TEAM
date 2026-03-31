"""
기존 synthetic_summary.jsonl에서 300건을 선별하는 스크립트

- 짧은(~1.5K): 50건 랜덤 선별
- 중간(1.5K~3K): 250건 랜덤 선별
- 나머지 버림

사용법:
    python ai/finetuning/scripts/select_existing_synthetic.py
    python ai/finetuning/scripts/select_existing_synthetic.py --dry-run
"""

import argparse
import json
import io
import random
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "v2_summary"

INPUT_FILE = DATA_DIR / "synthetic_summary.jsonl"
OUTPUT_FILE = DATA_DIR / "synthetic_selected.jsonl"


def get_doc_length(sample: dict) -> int:
    """user 메시지에서 문서 길이 추출"""
    user_content = sample["messages"][1]["content"]
    # "문서 내용:\n" 이후가 실제 문서
    if "문서 내용:\n" in user_content:
        doc = user_content.split("문서 내용:\n", 1)[1]
    else:
        doc = user_content
    return len(doc)


def main():
    parser = argparse.ArgumentParser(description="기존 합성 데이터에서 300건 선별")
    parser.add_argument("--input", type=str, default=str(INPUT_FILE))
    parser.add_argument("--output", type=str, default=str(OUTPUT_FILE))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    random.seed(args.seed)

    # 데이터 로드
    input_path = Path(args.input)
    if not input_path.exists():
        print("[오류] 입력 파일 없음: %s" % args.input)
        sys.exit(1)

    with open(input_path, encoding="utf-8") as f:
        samples = [json.loads(line.strip()) for line in f if line.strip()]

    print("=" * 60)
    print("  기존 합성 데이터 선별 (300건)")
    print("=" * 60)
    print("  입력: %s (%d건)" % (args.input, len(samples)))

    # 길이별 분류
    short_samples = []   # ~1.5K
    medium_samples = []  # 1.5K~3K

    for s in samples:
        doc_len = get_doc_length(s)
        if doc_len < 1500:
            short_samples.append(s)
        elif doc_len < 3000:
            medium_samples.append(s)

    print("  짧은(~1.5K): %d건" % len(short_samples))
    print("  중간(1.5K~3K): %d건" % len(medium_samples))

    # 선별
    if len(short_samples) < 50:
        print("[경고] 짧은 데이터 부족: %d건 (목표 50건)" % len(short_samples))
        selected_short = short_samples
    else:
        selected_short = random.sample(short_samples, 50)

    if len(medium_samples) < 250:
        print("[경고] 중간 데이터 부족: %d건 (목표 250건)" % len(medium_samples))
        selected_medium = medium_samples
    else:
        selected_medium = random.sample(medium_samples, 250)

    selected = selected_short + selected_medium
    random.shuffle(selected)

    print("\n  선별 결과:")
    print("    짧은: %d건" % len(selected_short))
    print("    중간: %d건" % len(selected_medium))
    print("    합계: %d건" % len(selected))

    if args.dry_run:
        print("\n[DRY RUN] 파일 저장 안 함")
        return

    # 저장
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for s in selected:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print("\n  저장: %s (%d건)" % (args.output, len(selected)))


if __name__ == "__main__":
    main()
