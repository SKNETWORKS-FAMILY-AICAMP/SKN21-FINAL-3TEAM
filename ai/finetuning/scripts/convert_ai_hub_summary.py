"""
AI Hub 요약문 데이터 → v2_summary 학습 데이터 변환 스크립트

소스: AI Hub "요약문 및 레포트 생성 데이터" (SN 582)
타겟: data/training/v2_summary/aihub_summary.jsonl (300개)

AI Hub 데이터 구조 (파일 1건 = JSON 1건):
  {
    "Meta(Acqusition)": {"doc_type": "minute", ...},
    "Meta(Refine)": {"passage": "원문 텍스트"},
    "Annotation": {"summary1": "...", "summary2": "...", "summary3": "..."}
  }
  - 2~3sent 폴더: summary1 + summary2 (2-3문장 추출요약)
  - 20per 폴더: summary1 + summary3 (20% 추출요약)
  - 두 폴더의 passage는 서로 다른 문서

사용법:
    python ai/finetuning/scripts/convert_aihub_summary.py
    python ai/finetuning/scripts/convert_aihub_summary.py --total 100
    python ai/finetuning/scripts/convert_aihub_summary.py --model gpt-4o
"""

import argparse
import json
import os
import random
import sys
import io
import time
from pathlib import Path

# Windows 콘솔 한글 출력
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env", override=True)

from ai.llm.prompts import DOC_SUMMARY_SLLM_PROMPT

# AI Hub 데이터 경로 (실제 구조에 맞춤)
RAW_BASE = BASE_DIR / "data" / "raw" / "ai_hub" / "022.요약문 및 레포트 생성 데이터" / "01.데이터"
TRAIN_LABEL_DIR = RAW_BASE / "1.Training" / "라벨링데이터" / "TL1"
OUTPUT_DIR = BASE_DIR / "data" / "training" / "v2_summary"

# ── sLLM 시스템 프롬프트 (ai/llm/prompts.py에서 import) ──
SYSTEM_PROMPT = DOC_SUMMARY_SLLM_PROMPT

# ── 카테고리 매핑 (폴더명 → 한글) ──

FOLDER_TO_CATEGORY = {
    "01.news_r": "뉴스",
    "02.briefing": "보도자료",
    "03.his_cul": "역사기록물",
    "04.paper": "보고서",
    "05.minute": "회의록",
    "06.edit": "사설",
    "07.public": "간행물",
    "08.speech": "연설문",
    "09.literature": "문학",
    "10.narration": "나레이션",
}

# ── 카테고리별 목표 배분 (300개) ──

CATEGORY_TARGETS = {
    "뉴스": 77,
    "보도자료": 69,
    "보고서": 69,
    "간행물": 43,
    "사설": 43,
}
# 제외: 회의록(국회 속기록), 연설문, 역사기록물, 문학, 나레이션 — 기업 문서 도메인 부적합

# ── 길이 구간별 목표 ──
# AI Hub 원문은 최대 ~1500자이므로 해당 범위 내에서 균등 분배
# 중간/긴 문서는 합성 데이터(700개)에서 커버
LENGTH_BINS = [
    {"name": "짧은", "min": 500, "max": 800, "target": 100},
    {"name": "중간", "min": 800, "max": 1200, "target": 100},
    {"name": "긴",   "min": 1200, "max": 1500, "target": 100},
]

# 원문 길이 필터 (자)
MIN_PASSAGE_LEN = 500
MAX_PASSAGE_LEN = 1500


def load_aihub_data(label_dir: Path, targets: dict[str, int], max_per_cat: int = 0) -> list[dict]:
    """AI Hub 중첩 JSON 파일을 카테고리별 필요 수만큼만 로드.

    전체 14만 건을 로드하면 너무 느리므로, 카테고리별로 목표 x3 만큼만 로드하고 중단.
    max_per_cat이 0이면 목표 x3으로 자동 계산.
    """
    all_docs = []

    if not label_dir.exists():
        print(f"[오류] 데이터 디렉토리 없음: {label_dir}")
        print(f"       AI Hub에서 데이터를 다운로드하세요:")
        print(f"       https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=582")
        sys.exit(1)

    # 카테고리 역매핑 (한글 → 폴더명)
    cat_to_folder = {v: k for k, v in FOLDER_TO_CATEGORY.items()}

    for cat_folder in sorted(label_dir.iterdir()):
        if not cat_folder.is_dir():
            continue

        category = FOLDER_TO_CATEGORY.get(cat_folder.name, cat_folder.name)
        target = targets.get(category, 0)
        if target == 0:
            continue

        limit = max_per_cat if max_per_cat > 0 else target * 15

        cat_docs = []
        # 2~3sent 우선 로드 (summary2 있음, passage에서 불릿 추출 용이)
        sub_folders = sorted(cat_folder.iterdir(), key=lambda p: (0 if "sent" in p.name else 1, p.name))
        for sub_folder in sub_folders:
            if not sub_folder.is_dir():
                continue

            source_type = sub_folder.name  # "2~3sent" or "20per"
            json_files = list(sub_folder.glob("*.json"))
            random.shuffle(json_files)  # 랜덤 순서로 로드

            loaded = 0
            for fp in json_files:
                if len(cat_docs) >= limit:
                    break
                try:
                    with open(fp, encoding="utf-8") as f:
                        raw = json.load(f)

                    meta_refine = raw.get("Meta(Refine)", {})
                    annotation = raw.get("Annotation", {})

                    passage = meta_refine.get("passage", "")
                    if not passage or not isinstance(passage, str):
                        continue

                    doc = {
                        "passage": passage,
                        "category": category,
                        "summary1": annotation.get("summary1") or "",
                        "summary2": annotation.get("summary2") or "",
                        "summary3": annotation.get("summary3") or "",
                        "source_folder": source_type,
                    }
                    cat_docs.append(doc)
                    loaded += 1
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

            if loaded > 0:
                print(f"  {cat_folder.name}/{source_type}: {loaded:,}건 로드")

            if len(cat_docs) >= limit:
                break

        all_docs.extend(cat_docs)
        print(f"  -> {category}: {len(cat_docs):,}건 (목표 {target}, 풀 {limit})")

    print(f"  총 로드: {len(all_docs):,}건")
    return all_docs


def filter_and_select(
    docs: list[dict],
    targets: dict[str, int],
    min_len: int = MIN_PASSAGE_LEN,
    max_len: int = MAX_PASSAGE_LEN,
    seed: int = 42,
) -> dict[str, list[dict]]:
    """길이 구간별 + 카테고리별로 원문 필터링 후 목표 수만큼 선별.

    LENGTH_BINS 기준으로 각 길이 구간별 목표를 맞추고,
    부족한 구간은 있는 만큼만 뽑는다.
    """
    random.seed(seed)

    # 전체 길이 필터 + 길이 구간별 분류
    by_bin = {b["name"]: [] for b in LENGTH_BINS}
    filtered_total = 0

    for doc in docs:
        passage = doc["passage"]
        plen = len(passage)
        if not (min_len <= plen <= max_len):
            continue
        filtered_total += 1
        for b in LENGTH_BINS:
            if b["min"] <= plen < b["max"]:
                by_bin[b["name"]].append(doc)
                break
        else:
            # max 경계값 포함
            if plen == max_len:
                by_bin[LENGTH_BINS[-1]["name"]].append(doc)

    # 길이 구간별 현황 출력
    print(f"\n  [필터링 후 길이 구간별 현황 ({min_len}~{max_len}자)]")
    print(f"  총 필터 통과: {filtered_total}건")
    for b in LENGTH_BINS:
        count = len(by_bin[b["name"]])
        status = "OK" if count >= b["target"] else f"부족 (있는 만큼 사용)"
        print(f"    {b['name']} ({b['min']}~{b['max']}자): {count}건 (목표: {b['target']}, {status})")

    # 길이 구간별 카테고리 분포 출력
    for b in LENGTH_BINS:
        cat_counts = {}
        for doc in by_bin[b["name"]]:
            cat_counts[doc["category"]] = cat_counts.get(doc["category"], 0) + 1
        print(f"    {b['name']} 카테고리 분포: {cat_counts}")

    # 길이 구간별로 목표 수만큼 랜덤 선별
    selected = {}
    total_selected = 0

    for b in LENGTH_BINS:
        pool = by_bin[b["name"]]
        target = b["target"]

        # 2~3sent 우선 정렬
        pool_sorted = sorted(pool, key=lambda d: (0 if d["summary2"] else 1))

        actual = min(target, len(pool_sorted))
        if actual < target:
            print(f"    [{b['name']}] {actual}건만 사용 가능 (목표 {target})")

        picked = random.sample(pool_sorted, actual) if actual > 0 else []

        # 선별된 것을 카테고리별로 분배
        for doc in picked:
            cat = doc["category"]
            if cat not in selected:
                selected[cat] = []
            selected[cat].append(doc)

        total_selected += actual

    # 카테고리별 최종 선별 현황
    print(f"\n  [최종 선별 카테고리별 현황]")
    for cat in sorted(selected.keys()):
        print(f"    {cat}: {len(selected[cat])}건")
    print(f"\n  총 선별: {total_selected}건")
    return selected


_openai_client = None

def _get_client():
    global _openai_client
    if _openai_client is None:
        try:
            from openai import OpenAI
        except ImportError:
            print("[오류] openai 패키지가 필요합니다: pip install openai")
            sys.exit(1)
        _openai_client = OpenAI()
    return _openai_client

def call_openai(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_tokens: int = 1024,
    max_retries: int = 3,
) -> str | None:
    """OpenAI API 호출"""
    client = _get_client()

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"    [API 에러 (시도 {attempt+1}/{max_retries})] {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return None


def generate_summary_with_gpt(passage: str, model: str = "gpt-4o") -> str | None:
    """GPT-4o로 DOC_SUMMARY_SLLM_PROMPT 형식의 요약 생성"""
    return call_openai(
        SYSTEM_PROMPT,
        f"다음 문서를 요약하세요:\n\n{passage}",
        model=model,
        temperature=0.7,
        max_tokens=1024,
    )


def validate_summary(summary: str) -> tuple[bool, list[str]]:
    """요약 형식 검증"""
    errors = []

    if "태그:" not in summary:
        errors.append("'태그:' 없음")
    if "요약:" not in summary:
        errors.append("'요약:' 없음")

    # 태그 개수 검증 (3~7개)
    if "태그:" in summary:
        tag_line = summary.split("태그:")[1].split("\n")[0].strip()
        tags = [t.strip().lstrip("#").strip() for t in tag_line.split("#") if t.strip()]
        if len(tags) < 3 or len(tags) > 7:
            errors.append(f"태그 개수 부적합: {len(tags)}개 (3~7개 필요)")

    # 요약 길이 검증
    if "요약:" in summary:
        summary_text = summary.split("요약:", 1)[1].strip()
        if len(summary_text) < 30:
            errors.append(f"요약 너무 짧음: {len(summary_text)}자 (30자 이상 필요)")

    # 메타 지시문 복사 감지
    meta_patterns = [
        "2~3문장",
        "3~7개",
        "원문에 없는",
    ]
    for pattern in meta_patterns:
        if pattern in summary:
            errors.append(f"메타 지시문 복사: '{pattern}'")
            break

    return len(errors) == 0, errors


def build_user_prompt(passage: str, category: str) -> str:
    """프로덕션 형식의 user 프롬프트 (summarize_document()와 동일 형식)"""
    return f"다음 문서를 요약해주세요.\n\n문서 내용:\n{passage}"



def convert_and_save(
    selected: dict[str, list[dict]],
    output_path: Path,
    targets: dict[str, int] = None,
    model: str = "gpt-4o",
    append: bool = False,
):
    """선별된 데이터를 GPT-4o 요약으로 변환 저장"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    errors = 0
    validation_fails = 0

    mode = "a" if append else "w"
    with open(output_path, mode, encoding="utf-8") as f:
        for category, docs in selected.items():
            cat_target = (targets or {}).get(category, len(docs))
            cat_count = 0
            print(f"\n  [{category}] {len(docs)}건 중 {cat_target}건 목표...")

            for i, doc in enumerate(docs):
                if cat_count >= cat_target:
                    break

                passage = doc["passage"]
                print(f"    [{cat_count+1}/{cat_target}] {passage[:30]}...", end=" ", flush=True)

                # GPT-4o로 요약 생성
                summary = generate_summary_with_gpt(passage, model=model)
                if not summary:
                    print("- API 실패")
                    errors += 1
                    continue

                # 형식 검증
                is_valid, err_list = validate_summary(summary)
                if not is_valid:
                    print(f"- 검증 실패: {err_list}")
                    validation_fails += 1
                    continue

                # 학습 데이터 저장
                user_prompt = build_user_prompt(passage, category)
                sample = {
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                        {"role": "assistant", "content": summary},
                    ]
                }

                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                f.flush()
                count += 1
                cat_count += 1
                print("- OK")

                # Rate limiting
                if cat_count % 10 == 0:
                    time.sleep(1)
                    print(f"    --- {cat_count}/{cat_target}건 완료 ---")

            print(f"  [{category}] 결과: {cat_count}건 완료")

    print(f"\n  변환 완료: {count}건 -> {output_path}")
    if validation_fails:
        print(f"  검증 실패: {validation_fails}건")
    if errors:
        print(f"  API 에러: {errors}건")


def main():
    parser = argparse.ArgumentParser(description="AI Hub -> v2_summary 변환")
    parser.add_argument("--input", type=str, default=str(TRAIN_LABEL_DIR), help="AI Hub TL1 디렉토리")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR / "aihub_summary.jsonl"), help="출력 파일")
    parser.add_argument("--total", type=int, default=300, help="총 변환 목표 건수")
    parser.add_argument("--model", type=str, default="gpt-4o", help="요약 생성 모델")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    parser.add_argument("--min-len", type=int, default=MIN_PASSAGE_LEN, help="최소 원문 길이")
    parser.add_argument("--max-len", type=int, default=MAX_PASSAGE_LEN, help="최대 원문 길이")
    parser.add_argument("--append", action="store_true", help="기존 파일에 추가")
    args = parser.parse_args()

    print("=" * 70)
    print("  AI Hub -> v2_summary 변환")
    print("=" * 70)
    print(f"  입력: {args.input}")
    print(f"  출력: {args.output}")
    print(f"  목표: {args.total}건")
    print(f"  모델: {args.model}")
    print(f"  원문 길이: {args.min_len}~{args.max_len}자")

    if not os.getenv("OPENAI_API_KEY"):
        print("[오류] OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    # 길이 구간별 목표 출력
    print(f"\n  길이 구간별 목표:")
    for b in LENGTH_BINS:
        print(f"    {b['name']} ({b['min']}~{b['max']}자): {b['target']}건")
    total_bin_target = sum(b["target"] for b in LENGTH_BINS)
    print(f"    합계: {total_bin_target}건")

    # 카테고리별 목표 (로드용)
    # 충분히 많이 로드해서 길이 구간별로 나눌 수 있도록 목표 x 비례 조정
    ratio = args.total / 300
    adjusted_targets = {cat: max(1, int(n * ratio)) for cat, n in CATEGORY_TARGETS.items()}

    # 1. 데이터 로드 (필요한 만큼만)
    print(f"\n[1/3] 데이터 로드")
    data_dir = Path(args.input)
    docs = load_aihub_data(data_dir, adjusted_targets)

    if not docs:
        print("[오류] 로드된 데이터가 없습니다.")
        sys.exit(1)

    # 2. 데이터 선별 (길이 구간별)
    print(f"\n[2/3] 데이터 선별 (길이 구간별)")

    selected = filter_and_select(docs, adjusted_targets, args.min_len, args.max_len, args.seed)

    # 3. 변환 & 저장
    print(f"\n[3/3] 변환 & 저장")
    convert_and_save(selected, Path(args.output), targets=None, model=args.model, append=args.append)

    # 4. 검증 요약
    output_path = Path(args.output)
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        print(f"\n  [검증 요약]")
        print(f"  총 데이터: {len(lines)}건")

        valid_format = 0
        for line in lines:
            sample = json.loads(line)
            content = sample["messages"][2]["content"]
            if "태그:" in content and "요약:" in content:
                valid_format += 1

        pct = valid_format / len(lines) * 100 if lines else 0
        print(f"  마크다운 형식 적합: {valid_format}/{len(lines)} ({pct:.1f}%)")

    print(f"\n  완료!")


if __name__ == "__main__":
    main()
