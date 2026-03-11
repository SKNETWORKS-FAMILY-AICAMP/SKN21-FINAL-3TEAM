"""
합성 데이터 합치기: 선별 300건 + 중간+ 150건 + 긴 250건 → 700건

사용법:
    python ai/finetuning/scripts/combine_synthetic.py
    python ai/finetuning/scripts/combine_synthetic.py --dry-run
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


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line.strip()) for line in f if line.strip()]


def get_doc_length(sample: dict) -> int:
    user_content = sample["messages"][1]["content"]
    if "문서 내용:\n" in user_content:
        doc = user_content.split("문서 내용:\n", 1)[1]
    else:
        doc = user_content
    return len(doc)


def main():
    parser = argparse.ArgumentParser(description="합성 데이터 합치기 → 700건")
    parser.add_argument("--output", type=str,
                        default=str(DATA_DIR / "synthetic_summary_v2.jsonl"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    random.seed(args.seed)

    # 파일 로드
    selected = load_jsonl(DATA_DIR / "synthetic_selected.jsonl")
    medium_plus = load_jsonl(DATA_DIR / "synthetic_medium_plus.jsonl")
    long_docs = load_jsonl(DATA_DIR / "synthetic_long.jsonl")

    print("=" * 60)
    print("  합성 데이터 합치기")
    print("=" * 60)
    print("  선별 (기존): %d건" % len(selected))
    print("  중간+ (3K~5K): %d건" % len(medium_plus))
    print("  긴 (5K~10K): %d건" % len(long_docs))

    combined = selected + medium_plus + long_docs
    random.shuffle(combined)

    # 길이 분포 확인
    lengths = [get_doc_length(s) for s in combined]
    short = sum(1 for l in lengths if l < 1500)
    mid = sum(1 for l in lengths if 1500 <= l < 5000)
    long_cnt = sum(1 for l in lengths if l >= 5000)

    print("\n  합계: %d건" % len(combined))
    print("  길이 분포:")
    print("    짧은 (<1.5K): %d건" % short)
    print("    중간 (1.5K~5K): %d건" % mid)
    print("    긴 (5K+): %d건" % long_cnt)
    if lengths:
        print("    min=%d, max=%d, avg=%d" % (min(lengths), max(lengths), sum(lengths) // len(lengths)))

    if args.dry_run:
        print("\n[DRY RUN] 파일 저장 안 함")
        return

    # 저장
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for s in combined:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print("\n  저장: %s" % args.output)


if __name__ == "__main__":
    main()
