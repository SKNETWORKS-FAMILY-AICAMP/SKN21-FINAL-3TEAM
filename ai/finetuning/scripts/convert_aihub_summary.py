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
    python ai/finetuning/scripts/convert_aihub_summary.py --llm-enhance
"""

import argparse
import json
import random
import re
import sys
import io
import time
from collections import Counter
from pathlib import Path

# Windows 콘솔 한글 출력
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# AI Hub 데이터 경로 (실제 구조에 맞춤)
RAW_BASE = BASE_DIR / "data" / "raw" / "aihub" / "022.요약문 및 레포트 생성 데이터" / "01.데이터"
TRAIN_LABEL_DIR = RAW_BASE / "1.Training" / "라벨링데이터" / "TL1"
OUTPUT_DIR = BASE_DIR / "data" / "training" / "v2_summary"

# ── 프로덕션 시스템 프롬프트 (ai/llm/prompts.py와 100% 일치) ──

SYSTEM_PROMPT = (
    "당신은 기업 문서 요약 전문가입니다.\n"
    "주어진 문서를 분석하여 핵심 내용을 정리합니다.\n\n"
    "규칙:\n"
    "- 문서의 핵심 요약을 먼저 2-3문장으로 작성하세요.\n"
    "- 주요 포인트를 마크다운 불릿 리스트로 정리하세요.\n"
    "- 중요 키워드를 별도로 나열하세요.\n"
    "- 원문에 없는 내용을 추가하지 마세요.\n"
    "- 한국어로 답변하세요."
)

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
    "회의록": 180,
    "보고서": 100,
    "간행물": 80,
    "뉴스": 100,
    "보도자료": 90,
    "사설": 50,
    "연설문": 60,
    "역사기록물": 20,
    "나레이션": 15,
    "문학": 5,
}

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
    "회의록": ["이 회의록 요약해줘", "회의 내용 정리해줘", "회의 결과 요약", "회의록 핵심만 뽑아줘"],
    "보고서": ["보고서 요약 부탁해", "이 보고서 핵심 정리", "보고서 내용 요약해줘"],
    "간행물": ["이 문서 요약해줘", "핵심 내용 정리해줘"],
    "보도자료": ["보도자료 요약해줘", "보도 내용 정리해줘"],
    "연설문": ["연설 내용 요약해줘", "연설 핵심 정리해줘"],
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

        limit = max_per_cat if max_per_cat > 0 else target * 3

        cat_docs = []
        for sub_folder in sorted(cat_folder.iterdir()):
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

        # 길이 필터
        if not (min_len <= len(passage) <= max_len):
            continue

        # summary2 또는 summary3 중 하나는 있어야 함
        has_summary = (
            (doc["summary2"] and len(doc["summary2"].strip()) >= 20)
            or (doc["summary3"] and len(doc["summary3"].strip()) >= 20)
        )
        if not has_summary:
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

        if len(pool_sorted) < target:
            print(f"    [경고] {cat}: {len(pool_sorted)}건만 사용 가능 (목표 {target}건)")
            selected[cat] = pool_sorted
        else:
            # 상위 target*2개에서 랜덤 선택 (다양성 확보)
            candidates = pool_sorted[:min(target * 3, len(pool_sorted))]
            selected[cat] = random.sample(candidates, target)

    total = sum(len(v) for v in selected.values())
    print(f"\n  총 선별: {total}건")
    return selected


def extract_keywords_simple(passage: str, top_n: int = 5) -> list[str]:
    """간이 키워드 추출 (TF 기반, 한국어)"""
    stopwords = {
        "있다", "하다", "되다", "이다", "것", "수", "등", "및", "또는", "그", "이",
        "위해", "대한", "통해", "따라", "대해", "있는", "하는", "되는", "것으로",
        "있으며", "하였다", "되었다", "합니다", "있습니다", "됩니다", "것입니다",
        "위한", "관련", "경우", "해당", "기반", "현재", "이후", "이전", "사항",
    }
    words = re.findall(r"[가-힣]{2,}", passage)
    word_counts = Counter(words)
    keywords = [
        word for word, _ in word_counts.most_common()
        if word not in stopwords and len(word) >= 2
    ]
    return keywords[:top_n]


def extract_bullet_points(text: str, max_points: int = 5) -> list[str]:
    """텍스트에서 핵심 포인트를 문장 단위로 추출"""
    if not text or not text.strip():
        return []
    sentences = re.split(r"[.!?。]\s*", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
    return sentences[:max_points]


def build_assistant_response(doc: dict) -> str:
    """프로덕션 형식의 assistant 응답 (마크다운) 구성.

    형식:
        핵심 요약 2-3문장

        ## 주요 포인트
        - 포인트1
        - 포인트2

        ## 키워드
        키워드1, 키워드2, ...
    """
    passage = doc["passage"]
    summary2 = doc.get("summary2", "").strip()
    summary3 = doc.get("summary3", "").strip()
    summary1 = doc.get("summary1", "").strip()

    # 1. 핵심 요약 (summary2 > summary1 > passage 앞부분)
    if summary2 and len(summary2) >= 20:
        core_summary = summary2
    elif summary1 and len(summary1) >= 20:
        core_summary = summary1
    else:
        core_summary = passage[:200].strip() + "..."

    # 2. 주요 포인트
    if summary3 and len(summary3) >= 30:
        bullet_points = extract_bullet_points(summary3)
    else:
        # summary3 없으면 passage에서 추출
        bullet_points = extract_bullet_points(passage)

    if not bullet_points:
        bullet_points = [passage[:100].strip()]

    bullets_str = "\n".join(f"- {p}" for p in bullet_points)

    # 3. 키워드
    keywords = extract_keywords_simple(passage, top_n=5)
    keywords_str = ", ".join(keywords) if keywords else "내용 요약"

    return f"{core_summary}\n\n## 주요 포인트\n{bullets_str}\n\n## 키워드\n{keywords_str}"


def build_user_prompt(passage: str, category: str) -> str:
    """프로덕션 형식의 user 프롬프트"""
    if category in CATEGORY_SPECIFIC_REQUESTS and random.random() < 0.3:
        request = random.choice(CATEGORY_SPECIFIC_REQUESTS[category])
    else:
        request = random.choice(USER_REQUEST_VARIATIONS)

    return f"다음 문서를 요약해주세요.\n\n사용자 요청: {request}\n\n문서 내용:\n{passage}"


def enhance_keywords_with_llm(passage: str, keywords: list[str]) -> list[str]:
    """OpenAI API로 키워드 추출 (GPT 결과만 사용, TF는 fallback)"""
    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "주어진 문서에서 핵심 키워드 5개를 추출하세요.\n"
                    "규칙:\n"
                    "- 명사 또는 명사구만 출력 (조사, 어미 제거)\n"
                    "- 문서의 주제를 대표하는 단어만 선택\n"
                    "- 쉼표로 구분하여 키워드만 출력하세요."
                )},
                {"role": "user", "content": f"문서:\n{passage[:1500]}"},
            ],
            temperature=0.3,
            max_tokens=100,
        )
        result = response.choices[0].message.content.strip()
        llm_keywords = [kw.strip() for kw in result.split(",") if kw.strip()]
        if len(llm_keywords) >= 3:
            return llm_keywords[:5]
        # LLM 결과 부족하면 TF로 보충
        merged = list(dict.fromkeys(llm_keywords + keywords))
        return merged[:5]
    except Exception as e:
        print(f"    [LLM 키워드 실패, TF fallback] {e}")
        return keywords


def convert_and_save(
    selected: dict[str, list[dict]],
    output_path: Path,
    llm_enhance: bool = False,
):
    """선별된 데이터를 v2_summary JSONL 형식으로 변환 저장"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    errors = 0
    llm_calls = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for category, docs in selected.items():
            print(f"\n  [{category}] {len(docs)}건 변환 중...")

            for i, doc in enumerate(docs):
                try:
                    # 프로덕션 형식 구성
                    user_prompt = build_user_prompt(doc["passage"], category)
                    response = build_assistant_response(doc)

                    # LLM 키워드 보강 (전체 적용)
                    if llm_enhance:
                        keywords = extract_keywords_simple(doc["passage"])
                        keywords = enhance_keywords_with_llm(doc["passage"], keywords)
                        llm_calls += 1
                        # 키워드 부분 교체 (re.sub 대신 문자열 치환 — 키워드에 \숫자 포함 시 안전)
                        kw_str = ", ".join(keywords)
                        if "## 키워드\n" in response:
                            before = response.split("## 키워드\n")[0]
                            response = before + "## 키워드\n" + kw_str
                        if llm_calls % 50 == 0:
                            time.sleep(2)
                            print(f"    LLM 호출 {llm_calls}건 완료...")

                    sample = {
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                            {"role": "assistant", "content": response},
                        ]
                    }

                    f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                    count += 1

                    if (i + 1) % 100 == 0:
                        print(f"    {i+1}/{len(docs)}건 완료")

                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"    [에러] {category} #{i}: {e}")

    print(f"\n  변환 완료: {count}건 -> {output_path}")
    if errors:
        print(f"  에러: {errors}건")
    if llm_calls:
        print(f"  LLM 호출: {llm_calls}건")


def main():
    parser = argparse.ArgumentParser(description="AI Hub -> v2_summary 변환")
    parser.add_argument("--input", type=str, default=str(TRAIN_LABEL_DIR), help="AI Hub TL1 디렉토리")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR / "aihub_summary.jsonl"), help="출력 파일")
    parser.add_argument("--total", type=int, default=700, help="총 변환 목표 건수")
    parser.add_argument("--llm-enhance", action="store_true", help="LLM 키워드 보강 (OpenAI API 필요)")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    parser.add_argument("--min-len", type=int, default=MIN_PASSAGE_LEN, help="최소 원문 길이")
    parser.add_argument("--max-len", type=int, default=MAX_PASSAGE_LEN, help="최대 원문 길이")
    args = parser.parse_args()

    print("=" * 70)
    print("  AI Hub -> v2_summary 변환")
    print("=" * 70)
    print(f"  입력: {args.input}")
    print(f"  출력: {args.output}")
    print(f"  목표: {args.total}건")
    print(f"  LLM 보강: {'ON' if args.llm_enhance else 'OFF'}")
    print(f"  원문 길이: {args.min_len}~{args.max_len}자")

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
    convert_and_save(selected, Path(args.output), args.llm_enhance)

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
