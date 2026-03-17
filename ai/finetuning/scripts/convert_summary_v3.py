"""
v3_summary 학습 데이터 포맷 변환 스크립트 (v2 수정본)

원본: 핵심 요약 / ## 주요 포인트 / ## 키워드
변환: 분류: / 태그: / 요약:  (DOC_SUMMARY_SLLM_PROMPT 포맷)

수정사항 (v2 → v3):
  1. 요약: ## 주요 포인트 헤더/불릿 잔재 제거 → 평문 2~5문장
  2. 태그: 공백 포함 키워드 → 언더스코어 또는 붙여쓰기
  3. 태그: 3~7개로 클리핑
  4. 요약: 개행 없는 단일 라인

사용법:
    python ai/finetuning/scripts/convert_summary_v3.py
    python ai/finetuning/scripts/convert_summary_v3.py --dry-run
"""
import json
import re
import argparse
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parents[3] / "data" / "training" / "v2_summary"

# === sLLM 프롬프트 ===
NEW_SYSTEM_PROMPT = """\
당신은 기업 문서 요약 전문가입니다.
주어진 문서를 분석하여 분류, 태그, 요약을 생성합니다.

반드시 아래 형식으로 출력하세요:

분류: 문서타입
태그: #태그1 #태그2 #태그3
요약: 요약문

규칙:
- 분류는 다음 중 하나를 선택하세요: 회의록, 보고서, 제안서, 계약서, 정책문서, 인사문서, 기타
- 태그는 문서의 핵심 주제·키워드를 #으로 시작하여 3~7개 작성하세요.
- 태그는 구체적으로 작성하세요. (예: #회의 → #Q3매출회의, #보고서 → #인프라이전보고)
- 요약은 문서의 핵심 내용을 2~5문장으로 작성하세요.
- 핵심 수치, 결정사항, 일정 등 사실 중심으로 요약하세요.
- 원문에 없는 내용을 추가하지 마세요.
- 한국어로 답변하세요.\
"""

# === 분류 규칙 ===
CATEGORY_RULES = [
    ("회의록", ["회의", "안건", "참석자", "의결", "회의록", "토론", "발언", "의사록",
                "회의 일시", "회의 장소", "회의 안건"]),
    ("계약서", ["계약", "체결", "갑을", "조항", "계약서", "약정", "위약금", "계약금"]),
    ("제안서", ["제안", "제안서", "프로포절", "사업계획", "입찰", "수주", "제안요청"]),
    ("인사문서", ["채용", "퇴직", "급여", "승진", "연봉", "직원", "인사발령",
                 "직무기술서", "근로계약"]),
    ("정책문서", ["정책", "규정", "지침", "법률", "조례", "시행령", "법안", "규제",
                "개정", "입법", "제도", "법적", "시행규칙"]),
    ("보고서", ["보고", "실적", "분석", "현황", "성과", "매출", "통계", "조사",
              "연구", "발표", "결과", "전망", "추이", "증가", "감소", "추진",
              "분기", "연간", "월간"]),
]


def classify_category(user_text: str, assistant_text: str) -> str:
    """입력 + 출력 텍스트에서 분류 추론 (인사 키워드 엄격화)"""
    combined = user_text[:800] + " " + assistant_text[:300]

    # 회의록 키워드가 가장 명확하므로 우선 체크
    for category, keywords in CATEGORY_RULES:
        if category == "인사문서":
            # "인사" 단독은 매칭하지 않음 (오분류 방지)
            # "채용", "퇴직" 등 구체적 키워드만 매칭
            if any(kw in combined for kw in keywords):
                return category
        else:
            if any(kw in combined for kw in keywords):
                return category
    return "기타"


def parse_old_format(assistant_content: str) -> dict:
    """기존 포맷에서 요약/키워드 추출 — 꼼꼼한 파싱"""
    text = assistant_content.strip()

    # ── 핵심 요약 추출 ──
    summary = ""
    summary_match = re.search(r"핵심 요약\s*\n+(.+?)(?=\n##|\Z)", text, re.DOTALL)
    if summary_match:
        raw = summary_match.group(1).strip()
        # ## 주요 포인트로 바로 시작하면 핵심 요약 텍스트 없음
        if not raw.startswith("##"):
            summary = raw

    # 핵심 요약 텍스트가 없으면 주요 포인트에서 생성
    if not summary:
        points_match = re.search(r"## 주요 포인트\s*\n+(.+?)(?=\n##|\Z)", text, re.DOTALL)
        if points_match:
            points_text = points_match.group(1).strip()
            bullets = []
            for line in points_text.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    bullet = line[2:].strip()
                    # 불릿 텍스트를 문장으로 정리
                    if not bullet.endswith((".", "다", "음")):
                        bullet = bullet.rstrip(".,;") + "."
                    bullets.append(bullet)
            # 상위 3개를 합쳐서 요약 생성
            summary = " ".join(bullets[:3])

    # ── 요약 정제 ──
    # 1) ## 헤더 잔재 제거
    summary = re.sub(r"##\s*주요 포인트\s*", "", summary)
    summary = re.sub(r"##\s*키워드\s*", "", summary)
    # 2) 불릿 마커 제거
    summary = re.sub(r"\n\s*-\s*", " ", summary)
    summary = re.sub(r"^\s*-\s*", "", summary)
    # 3) 개행 → 공백
    summary = re.sub(r"\s*\n\s*", " ", summary)
    # 4) 다중 공백 정리
    summary = re.sub(r"\s{2,}", " ", summary).strip()

    # ── 키워드 추출 ──
    keywords = []
    kw_match = re.search(r"## 키워드\s*\n+(.+?)(?:\n\n|\Z)", text, re.DOTALL)
    if kw_match:
        kw_text = kw_match.group(1).strip()
        # 쉼표/콤마 구분
        raw_keywords = re.split(r"[,，、]", kw_text)
        for kw in raw_keywords:
            kw = kw.strip()
            if kw:
                # 공백 포함 키워드 → 붙여쓰기
                kw = kw.replace(" ", "")
                keywords.append(kw)

    # 태그 3~7개로 클리핑
    if len(keywords) > 7:
        keywords = keywords[:7]
    elif len(keywords) < 3:
        # 요약에서 추가 키워드 추출 시도
        nouns = re.findall(r"[가-힣]{2,4}(?:문서|보고|회의|계약|정책|시장|경제|기업|기술|교육)", summary)
        for n in nouns:
            if n not in keywords and len(keywords) < 3:
                keywords.append(n)

    return {"summary": summary, "keywords": keywords}


def build_new_format(category: str, keywords: list, summary: str) -> str:
    """새 포맷으로 조합 — 단일 라인, 깔끔한 구조"""
    tags_str = " ".join(f"#{kw}" for kw in keywords)
    return f"분류: {category}\n태그: {tags_str}\n요약: {summary}"


def convert_sample(sample: dict) -> dict:
    """단일 샘플 변환"""
    messages = sample["messages"]
    user_content = messages[1]["content"]
    assistant_content = messages[2]["content"]

    parsed = parse_old_format(assistant_content)
    category = classify_category(user_content, assistant_content)
    new_assistant = build_new_format(category, parsed["keywords"], parsed["summary"])

    return {
        "messages": [
            {"role": "system", "content": NEW_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": new_assistant},
        ]
    }


def validate_converted(sample: dict) -> list:
    """변환된 샘플 검증"""
    issues = []
    content = sample["messages"][2]["content"]
    lines = content.split("\n")

    # 3줄 구조
    if len(lines) != 3:
        issues.append(f"줄 수 {len(lines)} (3줄이어야 함)")

    if not lines[0].startswith("분류:"):
        issues.append("분류: 로 시작하지 않음")
    if len(lines) < 2 or not lines[1].startswith("태그:"):
        issues.append("태그: 없음")
    if len(lines) < 3 or not lines[2].startswith("요약:"):
        issues.append("요약: 없음")

    # 분류 유효성
    VALID = {"회의록", "보고서", "제안서", "계약서", "정책문서", "인사문서", "기타"}
    cat = lines[0].replace("분류:", "").strip()
    if cat not in VALID:
        issues.append(f"유효하지 않은 분류: {cat}")

    # 태그 검증
    if len(lines) >= 2:
        tag_line = lines[1].replace("태그:", "").strip()
        tags = [t for t in tag_line.split() if t.startswith("#")]
        if len(tags) < 3:
            issues.append(f"태그 부족 ({len(tags)}개)")
        if len(tags) > 7:
            issues.append(f"태그 초과 ({len(tags)}개)")
        # 태그에 공백 체크
        for t in tags:
            if " " in t.lstrip("#"):
                issues.append(f"태그에 공백: {t}")

    # 요약 검증
    if len(lines) >= 3:
        summary = lines[2].replace("요약:", "").strip()
        if len(summary) < 20:
            issues.append(f"요약 너무 짧음 ({len(summary)}자)")
        if "## " in summary:
            issues.append("요약에 ## 헤더 잔재")
        if "\n" in summary:
            issues.append("요약에 개행")
        if summary.startswith("- "):
            issues.append("요약이 불릿으로 시작")

    return issues


def main():
    parser = argparse.ArgumentParser(description="v3_summary 학습 데이터 포맷 변환")
    parser.add_argument("--dry-run", action="store_true", help="미리보기만")
    args = parser.parse_args()

    stats = {
        "total": 0, "success": 0, "issues": 0,
        "categories": Counter(), "issue_details": [],
    }

    for filename in ["train.jsonl", "eval.jsonl"]:
        filepath = BASE_DIR / filename
        if not filepath.exists():
            print(f"  [SKIP] {filename} 없음")
            continue

        with open(filepath, encoding="utf-8") as f:
            samples = [json.loads(line) for line in f]

        converted = []
        file_issues = 0

        for i, sample in enumerate(samples):
            new_sample = convert_sample(sample)
            issues = validate_converted(new_sample)

            stats["total"] += 1
            category = new_sample["messages"][2]["content"].split("\n")[0].replace("분류: ", "")
            stats["categories"][category] += 1

            if issues:
                file_issues += 1
                stats["issues"] += 1
                stats["issue_details"].append((filename, i, issues))
            else:
                stats["success"] += 1

            converted.append(new_sample)

        if not args.dry_run:
            # 원본 백업
            backup_path = filepath.with_name(filename + ".orig")
            if not backup_path.exists():
                import shutil
                shutil.copy2(filepath, backup_path)
                print(f"  [BACKUP] {filename} → {backup_path.name}")

            # 변환 저장
            with open(filepath, "w", encoding="utf-8") as f:
                for s in converted:
                    f.write(json.dumps(s, ensure_ascii=False) + "\n")
            print(f"  [SAVED] {filename}: {len(converted)}건")
        else:
            print(f"  [DRY-RUN] {filename}: {len(converted)}건, 이슈 {file_issues}건")

    # 결과 리포트
    print(f"\n{'='*50}")
    print(f"변환 결과")
    print(f"{'='*50}")
    print(f"  전체: {stats['total']}건")
    print(f"  성공: {stats['success']}건")
    print(f"  이슈: {stats['issues']}건")
    print(f"\n  분류 분포:")
    for cat, cnt in stats["categories"].most_common():
        pct = cnt / stats["total"] * 100
        print(f"    {cat}: {cnt}건 ({pct:.1f}%)")

    if stats["issue_details"]:
        print(f"\n  이슈 상세 (최대 20건):")
        for filename, idx, issues in stats["issue_details"][:20]:
            print(f"    [{filename}:{idx}] {', '.join(issues)}")

    # 샘플 출력 (원본 → 변환)
    print(f"\n{'='*50}")
    print("변환 샘플")
    print(f"{'='*50}")
    orig_path = BASE_DIR / "train.jsonl.orig"
    read_path = orig_path if orig_path.exists() else BASE_DIR / "train.jsonl"
    with open(read_path, encoding="utf-8") as f:
        originals = [json.loads(line) for line in f]

    for i in [0, 1, 87, 300, 700]:  # 1,87 = 핵심요약 누락 케이스
        if i >= len(originals):
            continue
        conv = convert_sample(originals[i])
        print(f"\n--- [{i}] 원본 (앞 150자) ---")
        print(originals[i]["messages"][2]["content"][:150])
        print(f"\n--- [{i}] 변환 결과 ---")
        print(conv["messages"][2]["content"])
        issues = validate_converted(conv)
        if issues:
            print(f"  ⚠ 이슈: {issues}")


if __name__ == "__main__":
    main()
