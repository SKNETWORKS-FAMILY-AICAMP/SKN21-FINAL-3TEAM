"""
학습 데이터 병합 스크립트

합성 데이터를 기존 AI Hub 데이터에 병합하여 최종 학습 데이터를 생성합니다.
중복 검사 후 목표 수에 맞게 병합합니다.

최종 산출물:
  data/training/v2_generate/aihub_generate.jsonl  <- 1,000개 (476 AI Hub + 524 합성)
  data/training/v2_summary/aihub_summary.jsonl    <- 1,000개 (700 AI Hub + 300 합성)
  data/training/v2_qa/aihub_qa.jsonl              <- 1,000개 (600 AI Hub + 400 합성)

사용법:
    # 전체 병합
    python ai/finetuning/scripts/merge_training_data.py

    # 특정 어댑터만
    python ai/finetuning/scripts/merge_training_data.py --adapter v2_generate

    # dry-run (병합 없이 현황만 확인)
    python ai/finetuning/scripts/merge_training_data.py --dry-run

    # 백업 생성
    python ai/finetuning/scripts/merge_training_data.py --backup
"""

import argparse
import hashlib
import json
import io
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training"

# ── 병합 설정 ──

MERGE_CONFIG = {
    "v2_generate": {
        "base": DATA_DIR / "v2_generate" / "aihub_generate.jsonl",
        "synthetic": DATA_DIR / "v2_generate" / "synthetic_generate.jsonl",
        "output": DATA_DIR / "v2_generate" / "aihub_generate.jsonl",
        "target": 1000,
    },
    "v2_summary": {
        "base": DATA_DIR / "v2_summary" / "aihub_summary.jsonl",
        "synthetic": DATA_DIR / "v2_summary" / "synthetic_summary.jsonl",
        "output": DATA_DIR / "v2_summary" / "aihub_summary.jsonl",
        "target": 1000,
    },
    "v2_qa": {
        "base": DATA_DIR / "v2_qa" / "aihub_qa.jsonl",
        "synthetic": DATA_DIR / "v2_qa" / "synthetic_qa.jsonl",
        "output": DATA_DIR / "v2_qa" / "aihub_qa.jsonl",
        "target": 1000,
    },
}


def load_jsonl(path: Path) -> list[dict]:
    """JSONL 파일 로드"""
    if not path.exists():
        return []
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    return samples


def save_jsonl(samples: list[dict], path: Path):
    """JSONL 파일 저장"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")


def get_content_hash(sample: dict) -> str:
    """assistant 응답 기반 해시 (중복 검사용)"""
    content = sample.get("messages", [{}])[-1].get("content", "")
    # 앞 500자만 사용 (성능 + 충분한 유니크)
    return hashlib.md5(content[:500].encode("utf-8")).hexdigest()


def merge_adapter(
    adapter: str,
    config: dict,
    dry_run: bool = False,
    backup: bool = False,
) -> dict:
    """단일 어댑터 데이터 병합"""
    base_path = config["base"]
    synth_path = config["synthetic"]
    output_path = config["output"]
    target = config["target"]

    print(f"\n  === {adapter} ===")

    # 데이터 로드
    base_data = load_jsonl(base_path)
    synth_data = load_jsonl(synth_path)

    print(f"  기존 데이터: {len(base_data)}건 ({base_path.name})")
    print(f"  합성 데이터: {len(synth_data)}건 ({synth_path.name})")

    if not synth_data:
        print(f"  [경고] 합성 데이터 파일이 없거나 비어있습니다.")
        return {"base": len(base_data), "synthetic": 0, "merged": len(base_data), "duplicates": 0}

    # 기존 데이터 해시 집합
    existing_hashes = set()
    for sample in base_data:
        existing_hashes.add(get_content_hash(sample))

    # 중복 제거하며 합성 데이터 추가
    new_samples = []
    duplicates = 0
    for sample in synth_data:
        h = get_content_hash(sample)
        if h in existing_hashes:
            duplicates += 1
            continue
        existing_hashes.add(h)
        new_samples.append(sample)

    # 목표 수에 맞춤
    need = target - len(base_data)
    if need <= 0:
        print(f"  기존 데이터가 이미 목표({target})를 달성했습니다.")
        new_samples = []
    elif len(new_samples) > need:
        new_samples = new_samples[:need]

    merged = base_data + new_samples

    print(f"  중복 제거: {duplicates}건")
    print(f"  추가: {len(new_samples)}건")
    print(f"  최종: {len(merged)}건 (목표: {target})")

    if not dry_run:
        # 백업
        if backup and output_path.exists():
            backup_path = output_path.with_suffix(".jsonl.bak")
            import shutil
            shutil.copy2(output_path, backup_path)
            print(f"  백업: {backup_path}")

        # 저장
        save_jsonl(merged, output_path)
        print(f"  저장 완료: {output_path}")

    return {
        "base": len(base_data),
        "synthetic": len(new_samples),
        "merged": len(merged),
        "duplicates": duplicates,
    }


def main():
    parser = argparse.ArgumentParser(description="학습 데이터 병합")
    parser.add_argument("--adapter", type=str, choices=["v2_generate", "v2_summary", "v2_qa", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true", help="병합 없이 현황만 확인")
    parser.add_argument("--backup", action="store_true", help="기존 파일 백업 후 병합")
    args = parser.parse_args()

    print("=" * 70)
    print("  학습 데이터 병합")
    print("=" * 70)
    if args.dry_run:
        print("  [DRY RUN] 병합 없이 현황만 확인합니다.")

    adapters = (
        [args.adapter] if args.adapter != "all"
        else ["v2_generate", "v2_summary", "v2_qa"]
    )

    results = {}
    for adapter in adapters:
        config = MERGE_CONFIG[adapter]
        result = merge_adapter(adapter, config, dry_run=args.dry_run, backup=args.backup)
        results[adapter] = result

    # 총괄 요약
    print(f"\n  {'=' * 50}")
    print(f"  총괄 요약")
    print(f"  {'=' * 50}")
    print(f"  {'어댑터':<15} {'기존':>6} {'추가':>6} {'최종':>6} {'목표':>6}")
    print(f"  {'-' * 50}")

    total_merged = 0
    for adapter in adapters:
        r = results[adapter]
        target = MERGE_CONFIG[adapter]["target"]
        status = "OK" if r["merged"] >= target else "부족"
        print(f"  {adapter:<15} {r['base']:>6} {r['synthetic']:>6} {r['merged']:>6} {target:>6}  {status}")
        total_merged += r["merged"]

    print(f"  {'-' * 50}")
    print(f"  {'합계':<15} {'':>6} {'':>6} {total_merged:>6} {3000:>6}")

    print(f"\n  완료!")


if __name__ == "__main__":
    main()
