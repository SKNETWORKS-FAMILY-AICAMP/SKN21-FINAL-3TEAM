"""
판단 데이터 정제 스크립트

검증(validate_judgment_data.py)에서 발견된 이슈를 자동 수정합니다:

1. 중복 제거 — 질문 유사도 85% 이상인 쌍에서 하나 제거
2. CONTENT_MISMATCH 재검증 — user context 기준으로 정확하게 재검증
3. IT보안규정 추출 — 540건 데이터에서 제20~30조 원문을 .txt로 추출
4. 정제 리포트 — before/after 비교

사용법:
    # 미리보기 (파일 수정 안 함)
    python scripts/clean_judgment_data.py --dry-run

    # 실행 (정제된 파일 생성)
    python scripts/clean_judgment_data.py

    # IT보안규정 .txt 추출만
    python scripts/clean_judgment_data.py --extract-regulations
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REGULATION_DIR = BASE_DIR / "data" / "regulations"
TRAINING_DIR = BASE_DIR / "data" / "training" / "v1_judgment"

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ═══════════════════════════════════════════════════════════════
# 1. 데이터 로드
# ═══════════════════════════════════════════════════════════════


def load_jsonl(filepath: Path) -> list[dict]:
    records = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def save_jsonl(records: list[dict], filepath: Path):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def extract_question(record: dict) -> str:
    try:
        user_content = record["messages"][1]["content"]
        parts = user_content.split("## 사용자 질문")
        if len(parts) > 1:
            return parts[1].strip()
    except (KeyError, IndexError):
        pass
    return ""


# ═══════════════════════════════════════════════════════════════
# 2. 중복 제거
# ═══════════════════════════════════════════════════════════════


def find_duplicates(records: list[dict], threshold: float = 0.85) -> set[int]:
    """중복 인덱스 집합 반환 (각 쌍에서 뒤쪽 인덱스 제거)"""
    questions = []
    for i, r in enumerate(records):
        q = extract_question(r)
        tokens = set(re.findall(r"[가-힣]+|[a-zA-Z]+|\d+", q))
        questions.append((i, q, tokens))

    remove_indices = set()

    for a in range(len(questions)):
        if a in remove_indices:
            continue
        for b in range(a + 1, len(questions)):
            if b in remove_indices:
                continue
            _, _, set_a = questions[a]
            _, _, set_b = questions[b]
            if not set_a or not set_b:
                continue
            intersection = len(set_a & set_b)
            union = len(set_a | set_b)
            if union > 0 and intersection / union >= threshold:
                remove_indices.add(b)

    return remove_indices


# ═══════════════════════════════════════════════════════════════
# 3. user context 기준 재검증
# ═══════════════════════════════════════════════════════════════


def extract_context_articles(user_content: str) -> dict[str, str]:
    """
    user content에서 규정 조항별 원문 추출.
    Returns: {"제N조": "원문 텍스트"}
    """
    articles = {}
    # ### 제N조 (조항명)\n본문 패턴
    matches = list(
        re.finditer(
            r"### (제\d+조\s*\([^)]+\))\n(.*?)(?=### 제\d+조|## 사용자 질문|$)",
            user_content,
            re.DOTALL,
        )
    )

    # ### 규정명 — 제N조 패턴 (교차규정 데이터)
    if not matches:
        matches = list(
            re.finditer(
                r"### .+?—\s*(제\d+조\s*\([^)]+\))\n(.*?)(?=### |## 사용자 질문|$)",
                user_content,
                re.DOTALL,
            )
        )

    for m in matches:
        key = m.group(1).strip()
        text = m.group(2).strip()
        # "제N조" 번호 추출
        num_m = re.search(r"제(\d+)조", key)
        if num_m:
            articles[f"제{num_m.group(1)}조"] = text

    return articles


def validate_against_context(record: dict) -> list[str]:
    """
    answer의 인용이 user context와 일치하는지 검증.
    Returns: 이슈 리스트
    """
    issues = []

    try:
        user_content = record["messages"][1]["content"]
        answer = json.loads(record["messages"][2]["content"])
    except (KeyError, IndexError, json.JSONDecodeError):
        return ["PARSE_ERROR"]

    context_articles = extract_context_articles(user_content)

    for reg in answer.get("regulations", []):
        article = reg.get("article", "")
        content = reg.get("content", "")
        num_m = re.search(r"제(\d+)조", article)
        if not num_m:
            continue

        article_key = f"제{num_m.group(1)}조"

        # 1. 인용 조항이 context에 있는지
        if article_key not in context_articles:
            issues.append(f"HALLUCINATION: {article} — context에 없는 조항 인용")
            continue

        # 2. content 요약이 context 원문과 일치하는지
        original = context_articles[article_key]
        if content and len(content) >= 10:
            keywords = re.findall(r"[가-힣]{2,}", content)
            if len(keywords) >= 3:
                matched = sum(1 for kw in keywords if kw in original)
                ratio = matched / len(keywords)
                if ratio < 0.15:
                    issues.append(
                        f"CONTENT_MISMATCH: {article} — "
                        f"content 키워드 {ratio:.0%} 일치"
                    )

    return issues


# ═══════════════════════════════════════════════════════════════
# 4. IT보안규정 추출
# ═══════════════════════════════════════════════════════════════


def extract_it_security_regulation(records: list[dict]) -> str:
    """
    training data에서 제13조~제30조 (IT보안규정) 원문 추출.
    여러 레코드에서 수집해서 가장 완전한 버전 사용.
    """
    # 조항별 최장 텍스트 수집
    article_texts = {}

    for r in records:
        user = r["messages"][1]["content"]
        matches = re.finditer(
            r"### (제\d+조\s*\([^)]+\))\n(.*?)(?=### 제\d+조|## 사용자 질문|$)",
            user,
            re.DOTALL,
        )
        for m in matches:
            key = m.group(1).strip()
            text = m.group(2).strip()
            num = int(re.search(r"(\d+)", key).group(1))
            # IT보안규정 범위: 제13조~제30조
            if 13 <= num <= 30:
                if key not in article_texts or len(text) > len(article_texts[key]):
                    article_texts[key] = text

    # 인사규정 범위: 제1조~제12조
    hr_texts = {}
    for r in records:
        user = r["messages"][1]["content"]
        matches = re.finditer(
            r"### (제\d+조\s*\([^)]+\))\n(.*?)(?=### 제\d+조|## 사용자 질문|$)",
            user,
            re.DOTALL,
        )
        for m in matches:
            key = m.group(1).strip()
            text = m.group(2).strip()
            num = int(re.search(r"(\d+)", key).group(1))
            if 1 <= num <= 12:
                if key not in hr_texts or len(text) > len(hr_texts[key]):
                    hr_texts[key] = text

    return article_texts, hr_texts


def build_regulation_file(
    name: str, doc_num: str, articles: dict[str, str]
) -> str:
    """규정 .txt 파일 내용 생성"""
    lines = [
        name,
        f"문서번호: {doc_num}",
        "시행일자: 2026-01-01",
        "주식회사 듀듀 테크놀로지",
        "",
    ]

    sorted_articles = sorted(
        articles.items(),
        key=lambda x: int(re.search(r"(\d+)", x[0]).group(1)),
    )

    for key, text in sorted_articles:
        lines.append(key)
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 5. 메인
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="판단 데이터 정제")
    parser.add_argument("--dry-run", action="store_true", help="미리보기 (파일 수정 안 함)")
    parser.add_argument("--extract-regulations", action="store_true", help="IT보안규정 .txt 추출만")
    parser.add_argument(
        "--dup-threshold",
        type=float,
        default=0.85,
        help="중복 판단 유사도 임계값 (기본: 0.85)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  판단 데이터 정제")
    print("=" * 70)

    # ── 데이터 로드 ──
    train_path = TRAINING_DIR / "train.jsonl"
    eval_path = TRAINING_DIR / "eval.jsonl"

    train = load_jsonl(train_path)
    eval_data = load_jsonl(eval_path)
    print(f"\n  로드: train {len(train)}건, eval {len(eval_data)}건")

    # ═══════════════════════════════════════════════════
    # Step 1: IT보안규정 + 인사규정 .txt 추출
    # ═══════════════════════════════════════════════════
    print(f"\n{'─' * 70}")
    print("  Step 1: 누락 규정 추출 (training data → .txt)")
    print(f"{'─' * 70}")

    it_articles, hr_articles = extract_it_security_regulation(train + eval_data)

    print(f"\n  IT보안규정 (제13조~제30조): {len(it_articles)}개 조항 추출")
    for key in sorted(it_articles.keys(), key=lambda x: int(re.search(r"(\d+)", x).group(1))):
        print(f"    {key} ({len(it_articles[key])}자)")

    print(f"\n  인사규정 (제1조~제12조): {len(hr_articles)}개 조항 추출")
    for key in sorted(hr_articles.keys(), key=lambda x: int(re.search(r"(\d+)", x).group(1))):
        print(f"    {key} ({len(hr_articles[key])}자)")

    if not args.dry_run:
        # IT보안규정 저장
        if it_articles:
            it_content = build_regulation_file(
                "IT보안규정", "NC-IT-2026-002", it_articles
            )
            it_path = REGULATION_DIR / "IT보안규정_NC-IT-2026-002.txt"
            it_path.write_text(it_content, encoding="utf-8")
            print(f"\n  저장: {it_path}")

        # 인사규정 저장
        if hr_articles:
            hr_content = build_regulation_file(
                "인사규정", "NC-HR-2026-001", hr_articles
            )
            hr_path = REGULATION_DIR / "인사규정_NC-HR-2026-001.txt"
            hr_path.write_text(hr_content, encoding="utf-8")
            print(f"  저장: {hr_path}")

    if args.extract_regulations:
        return

    # ═══════════════════════════════════════════════════
    # Step 2: 중복 제거
    # ═══════════════════════════════════════════════════
    print(f"\n{'─' * 70}")
    print(f"  Step 2: 중복 제거 (유사도 ≥ {args.dup_threshold:.0%})")
    print(f"{'─' * 70}")

    # train 중복
    train_dups = find_duplicates(train, args.dup_threshold)
    print(f"\n  train: {len(train_dups)}건 중복 발견")

    # 중복 샘플 출력
    if train_dups:
        sample_dups = sorted(train_dups)[:5]
        for idx in sample_dups:
            q = extract_question(train[idx])
            print(f"    [{idx}] 제거: {q[:80]}...")

    # eval 중복
    eval_dups = find_duplicates(eval_data, args.dup_threshold)
    print(f"  eval: {len(eval_dups)}건 중복 발견")

    # ═══════════════════════════════════════════════════
    # Step 3: user context 기준 재검증
    # ═══════════════════════════════════════════════════
    print(f"\n{'─' * 70}")
    print("  Step 3: user context 기준 재검증")
    print(f"{'─' * 70}")

    train_issues = {}
    issue_counter = Counter()
    for i, r in enumerate(train):
        issues = validate_against_context(r)
        if issues:
            train_issues[i] = issues
            for iss in issues:
                code = iss.split(":")[0]
                issue_counter[code] += 1

    print(f"\n  train 검증 결과:")
    print(f"    이슈 있는 레코드: {len(train_issues)}건")
    for code, cnt in issue_counter.most_common():
        print(f"    {code}: {cnt}건")

    eval_issues = {}
    for i, r in enumerate(eval_data):
        issues = validate_against_context(r)
        if issues:
            eval_issues[i] = issues

    print(f"  eval 검증 결과: 이슈 {len(eval_issues)}건")

    # 진짜 할루시네이션(context에 없는 조항 인용) → 제거 대상
    train_hallucination = {
        i for i, issues in train_issues.items()
        if any("HALLUCINATION" in iss for iss in issues)
    }
    eval_hallucination = {
        i for i, issues in eval_issues.items()
        if any("HALLUCINATION" in iss for iss in issues)
    }
    print(f"\n  진짜 할루시네이션 (제거 대상):")
    print(f"    train: {len(train_hallucination)}건")
    print(f"    eval: {len(eval_hallucination)}건")

    # ═══════════════════════════════════════════════════
    # Step 4: 정제 적용
    # ═══════════════════════════════════════════════════
    print(f"\n{'─' * 70}")
    print("  Step 4: 정제 적용")
    print(f"{'─' * 70}")

    # 제거 대상 합산
    train_remove = train_dups | train_hallucination
    eval_remove = eval_dups | eval_hallucination

    train_clean = [r for i, r in enumerate(train) if i not in train_remove]
    eval_clean = [r for i, r in enumerate(eval_data) if i not in eval_remove]

    print(f"\n  train: {len(train)} → {len(train_clean)}건 (제거: {len(train_remove)}건)")
    print(f"    중복 제거: {len(train_dups)}건")
    print(f"    할루시네이션 제거: {len(train_hallucination)}건")
    print(f"    중복+할루 겹침: {len(train_dups & train_hallucination)}건")

    print(f"\n  eval: {len(eval_data)} → {len(eval_clean)}건 (제거: {len(eval_remove)}건)")

    # CONTENT_MISMATCH (context 기준)
    train_cm = sum(
        1 for issues in train_issues.values()
        if any("CONTENT_MISMATCH" in iss for iss in issues)
    )
    print(f"\n  CONTENT_MISMATCH (context 기준): train {train_cm}건")
    print(f"  → 이전 검증(.txt 기준)에서 779건이었으나, context 기준으로 재검증")

    if not args.dry_run:
        # 원본 백업
        backup_dir = TRAINING_DIR / "backup"
        backup_dir.mkdir(exist_ok=True)

        import shutil
        shutil.copy2(train_path, backup_dir / "train_original.jsonl")
        shutil.copy2(eval_path, backup_dir / "eval_original.jsonl")
        print(f"\n  원본 백업: {backup_dir}/")

        # 정제된 파일 저장
        save_jsonl(train_clean, train_path)
        save_jsonl(eval_clean, eval_path)
        print(f"  저장: {train_path} ({len(train_clean)}건)")
        print(f"  저장: {eval_path} ({len(eval_clean)}건)")

    # ═══════════════════════════════════════════════════
    # Step 5: before/after 리포트
    # ═══════════════════════════════════════════════════
    print(f"\n{'─' * 70}")
    print("  Step 5: Before / After 비교")
    print(f"{'─' * 70}")

    def count_stats(records):
        result_dist = Counter()
        xref_nonempty = 0
        multi_reg = 0
        for r in records:
            try:
                a = json.loads(r["messages"][2]["content"])
                result_dist[a.get("result", "?")] += 1
                if a.get("cross_references"):
                    xref_nonempty += 1
                if len(a.get("regulations", [])) >= 2:
                    multi_reg += 1
            except (json.JSONDecodeError, KeyError, IndexError):
                pass
        return result_dist, xref_nonempty, multi_reg

    before_dist, before_xref, before_multi = count_stats(train + eval_data)
    after_dist, after_xref, after_multi = count_stats(train_clean + eval_clean)

    total_before = len(train) + len(eval_data)
    total_after = len(train_clean) + len(eval_clean)

    print(f"\n  {'항목':<25s} {'Before':>10s} {'After':>10s} {'변화':>10s}")
    print(f"  {'─' * 55}")
    print(f"  {'총 레코드':<25s} {total_before:>10d} {total_after:>10d} {total_after - total_before:>+10d}")
    print(f"  {'중복 제거':<25s} {'':>10s} {'':>10s} {-(len(train_dups) + len(eval_dups)):>+10d}")
    print(f"  {'할루시네이션 제거':<25s} {'':>10s} {'':>10s} {-(len(train_hallucination) + len(eval_hallucination)):>+10d}")

    for result in ["yes", "no", "conditional"]:
        b = before_dist.get(result, 0)
        a = after_dist.get(result, 0)
        pct_b = b / total_before * 100 if total_before else 0
        pct_a = a / total_after * 100 if total_after else 0
        print(f"  {'result=' + result:<25s} {b:>7d}({pct_b:4.1f}%) {a:>7d}({pct_a:4.1f}%)")

    print(f"  {'교차참조 비어있지 않음':<25s} {before_xref:>10d} {after_xref:>10d}")
    print(f"  {'다중 규정 인용':<25s} {before_multi:>10d} {after_multi:>10d}")

    print(f"\n{'=' * 70}")
    if args.dry_run:
        print("  [DRY RUN] 파일 변경 없음. --dry-run 제거하고 다시 실행하세요.")
    else:
        print("  정제 완료!")
        print(f"  원본 백업: {backup_dir}/")
        print(f"  다음 단계: python scripts/validate_judgment_data.py 로 재검증")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
