"""
AI Hub 데이터 탐색/분석 스크립트

AI Hub에서 다운로드한 원본 JSON 데이터를 분석합니다:
  - 카테고리별 건수 집계
  - 원문(passage) 길이 분포
  - 필드 구조 검증
  - 활용 가능 데이터 규모 확인

사용법:
    # 요약문 및 레포트 생성 데이터 분석
    python ai/finetuning/scripts/aihub_explore.py --dataset summary_report

    # 행정 문서 기계독해 데이터 분석
    python ai/finetuning/scripts/aihub_explore.py --dataset admin_mrc

    # 전체 분석
    python ai/finetuning/scripts/aihub_explore.py --dataset all

데이터 저장 위치:
    data/raw/aihub/summary_report/   ← 요약문 및 레포트 생성 데이터 (SN 582)
    data/raw/aihub/admin_mrc/        ← 행정 문서 대상 기계독해 (SN 569)
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, stdev

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
RAW_DIR = BASE_DIR / "data" / "raw" / "aihub"

# ── 요약문 및 레포트 생성 데이터 분석 ──

# AI Hub 데이터 필드: doc_id, doc_category, doc_type, passage, Summary1, Summary2, Summary3
# 활용 대상 카테고리:
#   - 회의록 (34,000건) → v2_summary 140개, v2_generate 210개
#   - 보고서 (10,000건) → v2_summary 140개 중 일부, v2_generate 175개
#   - 간행물 (10,000건) → v2_summary 140개 중 일부, v2_generate 175개 중 일부
#   - 뉴스/보도자료/사설 → v2_summary 120개

TARGET_CATEGORIES_SUMMARY = {
    "회의록": 140,
    "보고서": 70,
    "간행물": 70,
    "뉴스": 40,
    "보도자료": 40,
    "사설": 40,
}

TARGET_CATEGORIES_GENERATE = {
    "회의록": 210,       # → meeting_minutes
    "보고서": 90,        # → report
    "간행물": 85,        # → report (일부)
    "보도자료": 90,      # → proposal
    "사설": 85,          # → proposal (일부)
}


def load_json_files(data_dir: Path) -> list[dict]:
    """디렉토리의 JSON 파일들을 로드합니다.

    지원 형식:
      - 단일 JSON 파일 (배열 또는 {'data': [...]} 래퍼)
      - 여러 JSON 파일
      - JSONL 파일
    """
    all_docs = []

    if not data_dir.exists():
        print(f"[오류] 디렉토리 없음: {data_dir}")
        print(f"       AI Hub에서 데이터를 다운로드한 뒤 해당 디렉토리에 저장하세요.")
        return all_docs

    json_files = list(data_dir.glob("**/*.json"))
    jsonl_files = list(data_dir.glob("**/*.jsonl"))

    for fp in json_files:
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                all_docs.extend(data)
            elif isinstance(data, dict):
                # 일반적인 AI Hub 래퍼: {"data": [...]} 또는 {"documents": [...]}
                for key in ("data", "documents", "document", "items"):
                    if key in data and isinstance(data[key], list):
                        all_docs.extend(data[key])
                        break
                else:
                    # 단일 문서
                    all_docs.append(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"  [경고] 파일 로드 실패: {fp.name} — {e}")

    for fp in jsonl_files:
        try:
            with open(fp, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        all_docs.append(json.loads(line))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"  [경고] JSONL 로드 실패: {fp.name} — {e}")

    return all_docs


def analyze_summary_report(data_dir: Path):
    """요약문 및 레포트 생성 데이터 분석"""
    print("=" * 70)
    print("  요약문 및 레포트 생성 데이터 분석")
    print("=" * 70)

    docs = load_json_files(data_dir)
    if not docs:
        print("\n  데이터가 없습니다.")
        print(f"  다운로드: https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=582")
        print(f"  저장 위치: {data_dir}")
        return

    print(f"\n  총 문서 수: {len(docs):,}건")

    # 1. 필드 구조 확인
    print(f"\n  [필드 구조]")
    if docs:
        sample = docs[0]
        print(f"  첫 번째 문서의 키: {list(sample.keys())}")

    # 모든 필드명 수집
    all_keys = Counter()
    for doc in docs:
        for key in doc.keys():
            all_keys[key] += 1

    print(f"  전체 필드:")
    for key, count in all_keys.most_common():
        pct = count / len(docs) * 100
        print(f"    {key}: {count:,}건 ({pct:.1f}%)")

    # 2. 카테고리별 분포
    print(f"\n  [카테고리별 분포]")
    category_field = _find_field(docs, ["doc_category", "category", "문서유형", "유형", "type"])
    if category_field:
        cat_counter = Counter()
        for doc in docs:
            cat = doc.get(category_field, "미분류")
            cat_counter[cat] += 1

        for cat, count in cat_counter.most_common():
            print(f"    {cat}: {count:,}건")
    else:
        print(f"  카테고리 필드를 찾을 수 없습니다.")

    # 3. 원문(passage) 길이 분포
    print(f"\n  [원문 길이 분포]")
    passage_field = _find_field(docs, ["passage", "text", "원문", "content", "body"])
    if passage_field:
        lengths = []
        for doc in docs:
            text = doc.get(passage_field, "")
            if isinstance(text, str) and text.strip():
                lengths.append(len(text))

        if lengths:
            print(f"    유효 문서: {len(lengths):,}건")
            print(f"    최소: {min(lengths):,}자")
            print(f"    최대: {max(lengths):,}자")
            print(f"    평균: {mean(lengths):,.0f}자")
            print(f"    중앙값: {median(lengths):,.0f}자")
            if len(lengths) > 1:
                print(f"    표준편차: {stdev(lengths):,.0f}자")

            # 길이 구간별 분포
            bins = [0, 200, 500, 1000, 2000, 3000, 5000, float("inf")]
            bin_labels = ["~200", "200~500", "500~1K", "1K~2K", "2K~3K", "3K~5K", "5K+"]
            bin_counts = [0] * len(bin_labels)
            for l in lengths:
                for i in range(len(bins) - 1):
                    if bins[i] <= l < bins[i + 1]:
                        bin_counts[i] += 1
                        break

            print(f"\n    길이 분포:")
            for label, count in zip(bin_labels, bin_counts):
                bar = "#" * (count * 50 // max(bin_counts)) if max(bin_counts) > 0 else ""
                print(f"      {label:>8}: {count:>6,}건 {bar}")

    # 4. Summary 필드 확인
    print(f"\n  [요약 필드 확인]")
    for summary_key in ["Summary1", "Summary2", "Summary3", "summary1", "summary2", "summary3"]:
        count = sum(1 for doc in docs if doc.get(summary_key))
        if count > 0:
            # 길이 분포
            s_lengths = [len(doc[summary_key]) for doc in docs if isinstance(doc.get(summary_key), str) and doc[summary_key]]
            if s_lengths:
                print(f"    {summary_key}: {count:,}건 (평균 {mean(s_lengths):.0f}자, 중앙 {median(s_lengths):.0f}자)")

    # 5. 활용 가능 데이터 규모 (500~2000자 원문)
    print(f"\n  [활용 가능 데이터 (500~2000자 원문)]")
    if passage_field and category_field:
        for cat in sorted(cat_counter.keys()):
            usable = sum(
                1 for doc in docs
                if doc.get(category_field) == cat
                and isinstance(doc.get(passage_field), str)
                and 500 <= len(doc[passage_field]) <= 2000
            )
            total = cat_counter[cat]
            print(f"    {cat}: {usable:,}건 / {total:,}건 ({usable/total*100:.1f}%)")

    # 6. 활용 가능 데이터 (1000~3000자 원문, v2_generate용)
    print(f"\n  [활용 가능 데이터 (1000~3000자 원문, v2_generate용)]")
    if passage_field and category_field:
        for cat in sorted(cat_counter.keys()):
            usable = sum(
                1 for doc in docs
                if doc.get(category_field) == cat
                and isinstance(doc.get(passage_field), str)
                and 1000 <= len(doc[passage_field]) <= 3000
            )
            total = cat_counter[cat]
            print(f"    {cat}: {usable:,}건 / {total:,}건 ({usable/total*100:.1f}%)")

    # 7. 샘플 출력
    print(f"\n  [샘플 데이터 (첫 2건)]")
    for i, doc in enumerate(docs[:2]):
        print(f"\n  --- 샘플 {i+1} ---")
        for key, value in doc.items():
            if isinstance(value, str):
                display = value[:200] + "..." if len(value) > 200 else value
                print(f"    {key}: {display}")
            else:
                print(f"    {key}: {value}")


def analyze_admin_mrc(data_dir: Path):
    """행정 문서 기계독해 데이터 분석"""
    print("=" * 70)
    print("  행정 문서 대상 기계독해 데이터 분석")
    print("=" * 70)

    docs = load_json_files(data_dir)
    if not docs:
        print("\n  데이터가 없습니다.")
        print(f"  다운로드: https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=569")
        print(f"  저장 위치: {data_dir}")
        return

    print(f"\n  총 문서 수: {len(docs):,}건")

    # MRC 데이터 구조 분석
    # 일반적인 SQuAD 스타일: {data: [{title, paragraphs: [{context, qas: [{question, answers: [{text, answer_start}]}]}]}]}

    # 1. 키 구조 확인
    print(f"\n  [키 구조]")
    if docs:
        sample = docs[0]
        print(f"  최상위 키: {list(sample.keys())}")

    # SQuAD 형식 체크
    squad_data = None
    if len(docs) == 1 and "data" in docs[0]:
        squad_data = docs[0]["data"]
        print(f"  SQuAD 형식 감지: {len(squad_data)}개 문서 그룹")
    elif all("paragraphs" in d for d in docs[:5] if isinstance(d, dict)):
        squad_data = docs
        print(f"  SQuAD 형식 (리스트): {len(squad_data)}개 문서 그룹")

    if squad_data:
        # SQuAD 형식 분석
        total_contexts = 0
        total_qas = 0
        context_lengths = []
        qa_types = Counter()
        categories = Counter()
        answer_lengths = []

        for article in squad_data:
            title = article.get("title", "")
            # 카테고리 추출 시도
            cat = article.get("category", article.get("doc_category", ""))
            if cat:
                categories[cat] += 1

            for para in article.get("paragraphs", []):
                context = para.get("context", "")
                total_contexts += 1
                if context:
                    context_lengths.append(len(context))

                for qa in para.get("qas", []):
                    total_qas += 1
                    q_type = qa.get("question_type", qa.get("type", ""))
                    if q_type:
                        qa_types[q_type] += 1

                    for ans in qa.get("answers", []):
                        ans_text = ans.get("text", "")
                        if ans_text:
                            answer_lengths.append(len(ans_text))

        print(f"\n  총 컨텍스트: {total_contexts:,}개")
        print(f"  총 QA 쌍: {total_qas:,}개")

        if context_lengths:
            print(f"\n  [컨텍스트 길이 분포]")
            print(f"    최소: {min(context_lengths):,}자")
            print(f"    최대: {max(context_lengths):,}자")
            print(f"    평균: {mean(context_lengths):,.0f}자")
            print(f"    중앙값: {median(context_lengths):,.0f}자")

        if answer_lengths:
            print(f"\n  [답변 길이 분포]")
            print(f"    최소: {min(answer_lengths):,}자")
            print(f"    최대: {max(answer_lengths):,}자")
            print(f"    평균: {mean(answer_lengths):,.0f}자")

        if qa_types:
            print(f"\n  [QA 유형 분포]")
            for qt, count in qa_types.most_common():
                print(f"    {qt}: {count:,}건")

        if categories:
            print(f"\n  [카테고리 분포]")
            for cat, count in categories.most_common():
                print(f"    {cat}: {count:,}건")

        # 활용 가능 데이터 (200~800자 context)
        usable = sum(1 for l in context_lengths if 200 <= l <= 800)
        print(f"\n  [활용 가능 데이터 (200~800자 context)]")
        print(f"    {usable:,}건 / {total_contexts:,}건 ({usable/total_contexts*100:.1f}%)")

        # 샘플 출력
        if squad_data:
            print(f"\n  [샘플 QA]")
            shown = 0
            for article in squad_data[:3]:
                for para in article.get("paragraphs", [])[:1]:
                    ctx = para.get("context", "")[:200]
                    print(f"\n  Context: {ctx}...")
                    for qa in para.get("qas", [])[:2]:
                        q = qa.get("question", "")
                        ans = qa.get("answers", [{}])[0].get("text", "") if qa.get("answers") else ""
                        print(f"    Q: {q}")
                        print(f"    A: {ans}")
                        shown += 1
                    if shown >= 4:
                        break
                if shown >= 4:
                    break
    else:
        # 비-SQuAD 형식
        all_keys = Counter()
        for doc in docs:
            if isinstance(doc, dict):
                for key in doc.keys():
                    all_keys[key] += 1

        print(f"\n  필드:")
        for key, count in all_keys.most_common():
            print(f"    {key}: {count:,}건")

        # 샘플 출력
        print(f"\n  [샘플 (첫 2건)]")
        for i, doc in enumerate(docs[:2]):
            print(f"\n  --- 샘플 {i+1} ---")
            for key, value in doc.items():
                if isinstance(value, str):
                    display = value[:200] + "..." if len(value) > 200 else value
                    print(f"    {key}: {display}")
                elif isinstance(value, list):
                    print(f"    {key}: [{len(value)}개 항목]")
                else:
                    print(f"    {key}: {value}")


def _find_field(docs: list[dict], candidates: list[str]) -> str | None:
    """문서 리스트에서 존재하는 필드명을 찾습니다."""
    if not docs:
        return None
    sample = docs[0]
    for field in candidates:
        if field in sample:
            return field
    return None


def main():
    parser = argparse.ArgumentParser(description="AI Hub 데이터 탐색/분석")
    parser.add_argument(
        "--dataset",
        type=str,
        choices=["summary_report", "admin_mrc", "all"],
        default="all",
        help="분석할 데이터셋",
    )
    args = parser.parse_args()

    print(f"\nAI Hub 데이터 디렉토리: {RAW_DIR}")
    print(f"분석 대상: {args.dataset}\n")

    if args.dataset in ("summary_report", "all"):
        sr_dir = RAW_DIR / "summary_report"
        analyze_summary_report(sr_dir)

    if args.dataset in ("admin_mrc", "all"):
        mrc_dir = RAW_DIR / "admin_mrc"
        analyze_admin_mrc(mrc_dir)

    print(f"\n{'=' * 70}")
    print("  분석 완료")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
