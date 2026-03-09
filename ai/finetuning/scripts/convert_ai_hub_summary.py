"""
AI Hub 요약문 데이터 → v2_summary 학습 데이터 변환 스크립트

소스: AI Hub "요약문 및 레포트 생성 데이터" (SN 582)
타겟: data/training/v2_summary/aihub_summary.jsonl (700개)

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

# ── 카테고리별 목표 배분 (700개) ──

CATEGORY_TARGETS = {
    "뉴스": 180,
    "보도자료": 160,
    "보고서": 160,
    "간행물": 100,
    "사설": 100,
}
# 제외: 회의록(국회 속기록), 연설문, 역사기록물, 문학, 나레이션 — 기업 문서 도메인 부적합

# ── 사용자 요청 변형 (15가지) ──

USER_REQUEST_VARIATIONS = [
    "이 문서 요약해줘",
    "요약 부탁해",
    "핵심 정리해줘",
    "간단히 요약해줘",
    "핵심 내용만 정리",
    "이거 정리 좀 해줘",
    "주요 내용 요약",
    "문서 요약 해줘",
    "이 내용 요약해줄래?",
    "요약본 만들어줘",
    "브리핑 해줘",
    "3줄 요약 해줘",
    "핵심만 뽑아줘",
    "간략하게 정리해줘",
    "이거 한번 정리해볼래?",
]

CATEGORY_SPECIFIC_REQUESTS = {
    "보고서": ["보고서 요약 부탁해", "이 보고서 핵심 정리", "보고서 내용 요약해줘"],
    "간행물": ["이 문서 요약해줘", "핵심 내용 정리해줘"],
    "보도자료": ["보도자료 요약해줘", "보도 내용 정리해줘"],
    "뉴스": ["이 뉴스 요약해줘", "뉴스 핵심 정리해줘", "기사 내용 요약"],
    "사설": ["사설 요약해줘", "핵심 논점 정리해줘"],
}

# 원문 길이 필터 (자)
MIN_PASSAGE_LEN = 300
MAX_PASSAGE_LEN = 3000


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

        limit = max_per_cat if max_per_cat > 0 else target * 7

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
    """카테고리별로 원문 길이 필터링 후 목표 수만큼 선별.

    우선순위: 2~3sent 폴더 (summary2 있음) > 20per 폴더 (summary3 있음)
    """
    by_category = {}
    for doc in docs:
        cat = doc["category"]
        passage = doc["passage"]

        # 길이 필터 (passage만 있으면 됨 — GPT-4o가 요약 생성)
        if not (min_len <= len(passage) <= max_len):
            continue

        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(doc)

    # 카테고리별 현황 출력
    print(f"\n  [필터링 후 카테고리별 현황 ({min_len}~{max_len}자)]")
    for cat in sorted(by_category.keys()):
        count = len(by_category[cat])
        target = targets.get(cat, 0)
        status = "OK" if count >= target else "부족"
        print(f"    {cat}: {count:,}건 (목표: {target}, {status})")

    # 목표 수만큼 랜덤 선별 (2~3sent 우선)
    random.seed(seed)
    selected = {}
    for cat, target in targets.items():
        pool = by_category.get(cat, [])
        if not pool:
            print(f"    [경고] {cat}: 데이터 없음 (목표 {target}건)")
            continue

        # 2~3sent 우선 정렬 (summary2가 있는 것 먼저)
        pool_sorted = sorted(pool, key=lambda d: (0 if d["summary2"] else 1))

        # 포인트 필터 탈락 보상을 위해 target * 3 선별
        over_target = target * 3
        if len(pool_sorted) < over_target:
            print(f"    [참고] {cat}: {len(pool_sorted)}건 사용 가능 (목표 {target}, 선별 {len(pool_sorted)})")
            selected[cat] = pool_sorted
        else:
            candidates = pool_sorted[:min(over_target * 2, len(pool_sorted))]
            selected[cat] = random.sample(candidates, over_target)

    total = sum(len(v) for v in selected.values())
    print(f"\n  총 선별: {total}건")
    return selected


def call_openai(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_tokens: int = 1024,
    max_retries: int = 3,
) -> str | None:
    """OpenAI API 호출"""
    try:
        from openai import OpenAI
    except ImportError:
        print("[오류] openai 패키지가 필요합니다: pip install openai")
        sys.exit(1)

    client = OpenAI()

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
    if "## 주요 포인트" not in summary:
        errors.append("'## 주요 포인트' 섹션 없음")
    if "## 키워드" not in summary:
        errors.append("'## 키워드' 섹션 없음")
    if "- " not in summary:
        errors.append("불릿 포인트 없음")

    # 포인트 개수 검증 (3~5개)
    if "## 주요 포인트" in summary and "## 키워드" in summary:
        points_section = summary.split("## 주요 포인트")[1].split("## 키워드")[0]
        bullet_count = points_section.count("\n- ")
        if not points_section.startswith("- "):
            bullet_count += points_section.lstrip().startswith("- ")
        # \n- 로 시작하는 줄 + 섹션 첫 줄이 - 로 시작하는 경우
        bullets = [line.strip() for line in points_section.strip().splitlines() if line.strip().startswith("- ")]
        if len(bullets) < 3 or len(bullets) > 5:
            errors.append(f"포인트 개수 부적합: {len(bullets)}개 (3~5개 필요)")

    # 키워드 개수 검증 (3~7개)
    if "## 키워드" in summary:
        kw_part = summary.split("## 키워드")[-1].strip()
        keywords = [kw.strip() for kw in kw_part.split(",") if kw.strip()]
        if len(keywords) < 3 or len(keywords) > 7:
            errors.append(f"키워드 개수 부적합: {len(keywords)}개 (3~7개 필요)")

    # 메타 지시문 복사 감지
    meta_patterns = [
        "핵심 요약 2-3문장",
        "빈 줄",
        "불릿(-)",
        "명사/명사구",
        "쉼표로 구분",
    ]
    for pattern in meta_patterns:
        if pattern in summary:
            errors.append(f"메타 지시문 복사: '{pattern}'")
            break
    # "포인트" + "작성하세요" 동시 존재
    if "포인트" in summary and "작성하세요" in summary:
        errors.append("메타 지시문 복사: '포인트'+'작성하세요'")

    return len(errors) == 0, errors


def build_user_prompt(passage: str, category: str) -> str:
    """프로덕션 형식의 user 프롬프트"""
    if category in CATEGORY_SPECIFIC_REQUESTS and random.random() < 0.3:
        request = random.choice(CATEGORY_SPECIFIC_REQUESTS[category])
    else:
        request = random.choice(USER_REQUEST_VARIATIONS)

    return f"다음 문서를 요약해주세요.\n\n사용자 요청: {request}\n\n문서 내용:\n{passage}"



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
    parser.add_argument("--total", type=int, default=700, help="총 변환 목표 건수")
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

    # 목표 수 비례 조정
    ratio = args.total / 700
    adjusted_targets = {cat: max(1, int(n * ratio)) for cat, n in CATEGORY_TARGETS.items()}

    # 1. 데이터 로드 (필요한 만큼만)
    print(f"\n[1/3] 데이터 로드")
    data_dir = Path(args.input)
    docs = load_aihub_data(data_dir, adjusted_targets)

    if not docs:
        print("[오류] 로드된 데이터가 없습니다.")
        sys.exit(1)

    # 2. 데이터 선별
    print(f"\n[2/3] 데이터 선별")
    print(f"  조정된 목표: {adjusted_targets}")

    selected = filter_and_select(docs, adjusted_targets, args.min_len, args.max_len, args.seed)

    # 3. 변환 & 저장
    print(f"\n[3/3] 변환 & 저장")
    convert_and_save(selected, Path(args.output), targets=adjusted_targets, model=args.model, append=args.append)

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
            if "## 주요 포인트" in content and "## 키워드" in content:
                valid_format += 1

        pct = valid_format / len(lines) * 100 if lines else 0
        print(f"  마크다운 형식 적합: {valid_format}/{len(lines)} ({pct:.1f}%)")

    print(f"\n  완료!")


if __name__ == "__main__":
    main()
