"""
판단 Agent 학습 데이터 리밸런싱 스크립트

목적:
- conditional 비율 줄이기 (45.9% → ~30%)
- no_regulation 비율 높이기 (새로 생성된 데이터 병합)
- 최종 목표 분포: conditional ~30%, yes ~25%, no ~25%, no_regulation ~20%

사용법:
    # 리밸런싱 실행 (새 데이터 파일 병합 + conditional 언더샘플링)
    python scripts/rebalance_judgment_data.py \
        --new-data data/training/v1_judgment/cross_regulation_v4_noreg.jsonl \
        --new-data data/training/v1_judgment/cross_regulation_v4_conflict.jsonl

    # 드라이런 (변경 없이 결과만 미리보기)
    python scripts/rebalance_judgment_data.py --dry-run \
        --new-data data/training/v1_judgment/cross_regulation_v4_noreg.jsonl

    # conditional 목표 비율 지정 (기본 0.30)
    python scripts/rebalance_judgment_data.py --cond-target 0.28 --new-data ...
"""

import argparse
import json
import random
import shutil
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "training" / "v1_judgment"
BACKUP_DIR = OUTPUT_DIR / "backup"
SEED = 42

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def load_jsonl(path: Path) -> list[dict]:
    data = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
    return data


def get_result(record: dict) -> str:
    """assistant 메시지에서 result 추출"""
    for msg in record.get("messages", []):
        if msg["role"] == "assistant":
            try:
                return json.loads(msg["content"]).get("result", "unknown")
            except (json.JSONDecodeError, KeyError):
                return "parse_error"
    return "unknown"


def print_distribution(data: list[dict], label: str):
    """분포 출력"""
    counter = Counter(get_result(r) for r in data)
    total = len(data)
    print(f"\n  {label} (총 {total}건)")
    for k, v in sorted(counter.items(), key=lambda x: -x[1]):
        bar = "█" * int(v / total * 40)
        print(f"    {k:15s}: {v:5d}건 ({v/total*100:5.1f}%) {bar}")
    return counter


def main():
    parser = argparse.ArgumentParser(description="판단 Agent 학습 데이터 리밸런싱")
    parser.add_argument(
        "--new-data",
        type=str,
        action="append",
        default=[],
        help="병합할 새 데이터 파일 (여러 번 지정 가능)",
    )
    parser.add_argument(
        "--cond-target",
        type=float,
        default=0.30,
        help="conditional 목표 비율 (기본: 0.30)",
    )
    parser.add_argument("--dry-run", action="store_true", help="변경 없이 미리보기만")
    args = parser.parse_args()

    print("=" * 60)
    print("  판단 Agent 학습 데이터 리밸런싱")
    print("=" * 60)

    # ── 1. 기존 데이터 로드 ──
    train_path = OUTPUT_DIR / "train.jsonl"
    eval_path = OUTPUT_DIR / "eval.jsonl"

    train = load_jsonl(train_path)
    eval_ = load_jsonl(eval_path)
    existing = train + eval_
    print(f"\n[1] 기존 데이터 로드: train {len(train)}건 + eval {len(eval_)}건 = {len(existing)}건")
    before_dist = print_distribution(existing, "기존 분포")

    # ── 2. 새 데이터 병합 ──
    new_data = []
    for path_str in args.new_data:
        p = Path(path_str)
        if not p.is_absolute():
            p = BASE_DIR / p
        loaded = load_jsonl(p)
        print(f"\n[2] 새 데이터 로드: {p.name} → {len(loaded)}건")
        print_distribution(loaded, f"  {p.name}")
        new_data.extend(loaded)

    if new_data:
        print(f"\n  새 데이터 합계: {len(new_data)}건")

    combined = existing + new_data
    print(f"\n  병합 후 전체: {len(combined)}건")
    combined_dist = print_distribution(combined, "병합 후 분포")

    # ── 3. Conditional 언더샘플링 ──
    cond_target_ratio = args.cond_target
    total_after_merge = len(combined)

    # 현재 conditional 수
    cond_count = combined_dist.get("conditional", 0)
    non_cond = [r for r in combined if get_result(r) != "conditional"]
    cond_all = [r for r in combined if get_result(r) == "conditional"]

    # 목표: conditional이 전체의 cond_target_ratio가 되도록
    # non_cond_count / (non_cond_count + target_cond) = (1 - cond_target_ratio)
    # target_cond = non_cond_count * cond_target_ratio / (1 - cond_target_ratio)
    non_cond_count = len(non_cond)
    target_cond = int(non_cond_count * cond_target_ratio / (1 - cond_target_ratio))

    if target_cond >= cond_count:
        print(f"\n[3] 언더샘플링 불필요 (conditional {cond_count}건 ≤ 목표 {target_cond}건)")
        rebalanced = combined
    else:
        remove_count = cond_count - target_cond
        print(f"\n[3] Conditional 언더샘플링:")
        print(f"    현재: {cond_count}건 → 목표: {target_cond}건 (제거: {remove_count}건)")

        random.seed(SEED)
        random.shuffle(cond_all)
        cond_kept = cond_all[:target_cond]

        rebalanced = non_cond + cond_kept
        print(f"    리밸런싱 후: {len(rebalanced)}건")

    final_dist = print_distribution(rebalanced, "최종 분포")

    # ── 4. Train/Eval 분할 ──
    random.seed(SEED)
    random.shuffle(rebalanced)
    split_idx = int(len(rebalanced) * 0.9)
    new_train = rebalanced[:split_idx]
    new_eval = rebalanced[split_idx:]

    print(f"\n[4] Train/Eval 분할: train {len(new_train)}건, eval {len(new_eval)}건")
    print_distribution(new_train, "train 분포")
    print_distribution(new_eval, "eval 분포")

    if args.dry_run:
        print(f"\n  [DRY RUN] 변경 없이 종료합니다.")
        return

    # ── 5. 백업 & 저장 ──
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_train = BACKUP_DIR / "train_before_rebalance.jsonl"
    backup_eval = BACKUP_DIR / "eval_before_rebalance.jsonl"

    shutil.copy2(train_path, backup_train)
    shutil.copy2(eval_path, backup_eval)
    print(f"\n[5] 백업 완료:")
    print(f"    {backup_train}")
    print(f"    {backup_eval}")

    # 저장
    for data, path in [(new_train, train_path), (new_eval, eval_path)]:
        with open(path, "w", encoding="utf-8") as f:
            for record in data:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n  저장 완료:")
    print(f"    {train_path} ({len(new_train)}건)")
    print(f"    {eval_path} ({len(new_eval)}건)")
    print(f"\n  리밸런싱 완료!")


if __name__ == "__main__":
    main()
