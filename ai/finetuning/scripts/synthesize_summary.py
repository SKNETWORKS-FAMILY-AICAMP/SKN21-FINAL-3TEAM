"""
v2_summary 합성 데이터 생성 스크립트

GPT-4o를 활용하여 완전 합성 요약 데이터를 생성합니다.
AI Hub 300개를 보완하여 다양한 문서 유형과 길이를 커버.

길이별 생성 모드:
  --length-range all       : 기존 전체 700건 (짧은~중간, 단일호출)
  --length-range medium_plus : 중간+ 3K~5K 150건 (멀티턴)
  --length-range long      : 긴 5K~10K 250건 (멀티턴)

2단계 파이프라인:
  Step A: GPT-4o -> 문서 원문 생성 (필요시 멀티턴 이어쓰기)
  Step B: GPT-4o -> 프로덕션 요약 prompt로 마크다운 요약 생성

사용법:
    python ai/finetuning/scripts/synthesize_summary.py --dry-run
    python ai/finetuning/scripts/synthesize_summary.py --length-range medium_plus
    python ai/finetuning/scripts/synthesize_summary.py --length-range long
    python ai/finetuning/scripts/synthesize_summary.py --length-range medium_plus --append
"""

import argparse
import json
import io
import os
import random
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env", override=True)

from ai.llm.prompts import DOC_SUMMARY_SLLM_PROMPT

OUTPUT_DIR = BASE_DIR / "data" / "training" / "v2_summary"

# ── sLLM 시스템 프롬프트 (ai/llm/prompts.py에서 import) ──
SYSTEM_PROMPT = DOC_SUMMARY_SLLM_PROMPT

# ── 카테고리별 합성 목표 (기본: 전체 700건) ──

CATEGORY_TARGETS = {
    "회의록": 100,
    "보고서": 100,
    "간행물": 60,
    "뉴스/보도자료": 80,
    "사설/연설문": 60,
    "이메일": 100,
    "사내공지": 80,
    "계약서/법률문서": 120,
}

# 중간+ (3K~5K) 150건 — 긴 문서 가능한 카테고리만
CATEGORY_TARGETS_MEDIUM_PLUS = {
    "보고서": 35,
    "간행물": 25,
    "계약서/법률문서": 30,
    "사설/연설문": 20,
    "회의록": 20,
    "뉴스/보도자료": 20,
}

# 긴 (5K~10K) 250건 — 긴 문서에 적합한 카테고리
CATEGORY_TARGETS_LONG = {
    "보고서": 60,
    "계약서/법률문서": 60,
    "간행물": 40,
    "회의록": 35,
    "사설/연설문": 30,
    "뉴스/보도자료": 25,
}

# 카테고리별 문서 길이 구간 (실제 기업 문서 기준) — 기본 모드
CATEGORY_LENGTH_RANGES = {
    "회의록":       (300, 8000),
    "보고서":       (1000, 10000),
    "간행물":       (1000, 8000),
    "뉴스/보도자료": (300, 5000),
    "사설/연설문":   (500, 6000),
    "이메일":       (300, 2000),
    "사내공지":     (300, 2000),
    "계약서/법률문서": (2000, 10000),
}

# 길이별 생성 모드 설정
LENGTH_MODE_CONFIG = {
    "medium_plus": {
        "char_min": 3000,
        "char_max": 5000,
        "max_tokens_per_call": 8192,
        "max_rounds": 3,
    },
    "long": {
        "char_min": 5000,
        "char_max": 10000,
        "max_tokens_per_call": 8192,
        "max_rounds": 7,
    },
}

# ── 업종 풀 ──

INDUSTRIES = [
    "IT/소프트웨어", "제조업", "금융/은행", "유통/물류", "의료/헬스케어",
    "건설/부동산", "교육", "미디어/광고", "에너지/환경", "공공/정부",
    "컨설팅", "식품/외식", "자동차", "통신", "바이오/제약",
]

# ── 카테고리별 문서 생성 프롬프트 ──

DOCUMENT_GENERATION_PROMPTS = {
    "회의록": (
        "{industry} 업종의 회의 기록을 작성해주세요.\n"
        "참석자 이름, 논의 내용, 결정사항, 후속 조치를 포함하세요.\n"
        "{length_range}자로 작성하세요."
    ),
    "보고서": (
        "{industry} 업종의 업무 보고서를 작성해주세요.\n"
        "업무 진행 현황, 실적 수치, 이슈사항, 향후 계획을 포함하세요.\n"
        "{length_range}자로 작성하세요."
    ),
    "간행물": (
        "{industry} 관련 간행물/백서의 일부를 작성해주세요.\n"
        "전문적인 분석과 데이터, 정책 제안을 포함하세요.\n"
        "{length_range}자로 작성하세요."
    ),
    "뉴스/보도자료": (
        "{industry} 업종 관련 보도자료를 작성해주세요.\n"
        "육하원칙에 맞게 사실적으로 작성하고, 인용문을 포함하세요.\n"
        "{length_range}자로 작성하세요."
    ),
    "사설/연설문": (
        "{industry} 관련 주제로 사설 또는 연설문을 작성해주세요.\n"
        "명확한 주장과 논거를 포함하세요.\n"
        "{length_range}자로 작성하세요."
    ),
    "이메일": (
        "{industry} 업종의 업무 이메일을 작성해주세요.\n"
        "발신자, 수신자, 제목, 인사말, 본론, 마무리를 포함한 완전한 이메일 형식으로 작성하세요.\n"
        "업무 협조 요청, 보고, 일정 조율 등의 내용을 포함하세요.\n"
        "{length_range}자로 작성하세요."
    ),
    "사내공지": (
        "{industry} 업종 기업의 사내 공지사항을 작성해주세요.\n"
        "제목, 시행일, 대상, 세부 내용, 문의처를 포함하세요.\n"
        "인사 발령, 제도 변경, 시설 안내, 보안 공지 등의 주제로 작성하세요.\n"
        "{length_range}자로 작성하세요."
    ),
    "계약서/법률문서": (
        "{industry} 관련 계약서 또는 법률 문서의 일부를 작성해주세요.\n"
        "당사자, 계약 목적, 주요 조항, 의무사항, 위약금, 분쟁 해결 등을 포함하세요.\n"
        "{length_range}자로 작성하세요."
    ),
}

# ── 요약 생성 프롬프트 ──

# Step B에서도 sLLM 시스템 프롬프트를 그대로 사용
# → GPT-4o가 sLLM과 동일한 형식으로 요약 생성
SUMMARY_GENERATION_SYSTEM = DOC_SUMMARY_SLLM_PROMPT


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
    temperature: float = 0.9,
    max_tokens: int = 2048,
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


def generate_document(category: str, industry: str, model: str = "gpt-4o",
                      length_mode: str | None = None) -> str | None:
    """Step A: 카테고리별 문서 원문 생성

    length_mode가 지정되면 멀티턴 이어쓰기로 긴 문서를 생성합니다.
    None이면 기존 단일호출 방식 (짧은/중간 문서).
    """
    doc_system = (
        "당신은 한국 기업 문서 작성 전문가입니다.\n"
        "주어진 조건에 맞는 현실적인 업무 문서를 생성하세요.\n"
        "구체적인 이름, 수치, 날짜를 포함하여 사실적으로 작성하세요.\n"
        "반드시 지정된 글자수 범위를 지켜주세요.\n"
        "한국어로 작성하세요."
    )

    prompt_template = DOCUMENT_GENERATION_PROMPTS.get(category, DOCUMENT_GENERATION_PROMPTS["보고서"])

    if length_mode and length_mode in LENGTH_MODE_CONFIG:
        # ── 멀티턴 이어쓰기 모드 ──
        config = LENGTH_MODE_CONFIG[length_mode]
        char_min = config["char_min"]
        char_max = config["char_max"]
        max_tokens = config["max_tokens_per_call"]
        max_rounds = config["max_rounds"]

        target_len = random.randint(char_min, char_max)
        length_range = "%d~%d" % (char_min, char_max)
        user_prompt = prompt_template.format(industry=industry, length_range=length_range)
        user_prompt += "\n\n최대한 상세하고 길게 작성하세요. 각 섹션을 구체적으로 서술하세요."

        client = _get_client()
        messages = [
            {"role": "system", "content": doc_system},
            {"role": "user", "content": user_prompt},
        ]
        full_text = ""

        for round_idx in range(max_rounds):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.9,
                    max_tokens=max_tokens,
                )
                chunk = response.choices[0].message.content.strip()
                full_text += chunk

                if len(full_text) >= target_len:
                    break

                # 이어쓰기 요청
                messages.append({"role": "assistant", "content": chunk})
                cont_msg = "아직 %d자입니다. %d자 이상 필요합니다. 이어서 계속 작성하세요. 새로운 섹션과 세부사항을 추가하세요." % (len(full_text), target_len)
                messages.append({"role": "user", "content": cont_msg})

            except Exception as e:
                print("    [멀티턴 API 에러 round %d] %s" % (round_idx + 1, e))
                time.sleep(2)
                if round_idx == 0:
                    return None

        if len(full_text) < char_min * 0.7:
            return None
        return full_text

    else:
        # ── 기존 단일호출 모드 (짧은/중간 문서) ──
        cat_min, cat_max = CATEGORY_LENGTH_RANGES.get(category, (1000, 5000))
        target_len = random.randint(cat_min, cat_max)
        range_min = max(cat_min, int(target_len * 0.8))
        range_max = min(cat_max, int(target_len * 1.2))
        length_range = "%d~%d" % (range_min, range_max)
        user_prompt = prompt_template.format(industry=industry, length_range=length_range)

        # GPT-4o 한국어: 1자 ≈ 1.5~2 토큰
        if range_max > 5000:
            max_tokens = 12000
        elif range_max > 3000:
            max_tokens = 8192
        else:
            max_tokens = 4096

        return call_openai(doc_system, user_prompt, model=model, temperature=0.9, max_tokens=max_tokens)


def generate_summary(passage: str, model: str = "gpt-4o") -> str | None:
    """Step B: 프로덕션 프롬프트로 요약 생성"""
    return call_openai(
        SUMMARY_GENERATION_SYSTEM,
        f"다음 문서를 요약하세요:\n\n{passage}",
        model=model,
        temperature=0.7,
        max_tokens=1024,
    )


def validate_summary(summary: str) -> tuple[bool, list[str]]:
    """요약 형식 검증 (태그 + 요약 형식)"""
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


def synthesize_all(
    targets: dict[str, int],
    output_path: Path,
    model: str = "gpt-4o",
    seed: int = 42,
    append: bool = False,
    length_mode: str | None = None,
) -> int:
    """전체 합성 데이터 생성"""
    random.seed(seed)

    mode = "a" if append else "w"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_success = 0
    total_failed = 0
    min_chars = 0
    if length_mode and length_mode in LENGTH_MODE_CONFIG:
        min_chars = LENGTH_MODE_CONFIG[length_mode]["char_min"]

    with open(output_path, mode, encoding="utf-8") as f:
        for category, count in targets.items():
            print(f"\n  [{category}] {count}건 생성 시작...")
            cat_success = 0
            cat_failed = 0

            for i in range(count):
                industry = random.choice(INDUSTRIES)
                print(f"    [{i+1}/{count}] {industry}", end=" ", flush=True)

                # Step A: 문서 원문 생성
                passage = generate_document(category, industry, model=model,
                                            length_mode=length_mode)
                if not passage or len(passage) < 100:
                    print("- 원문 생성 실패")
                    cat_failed += 1
                    continue

                # 길이 검증 (멀티턴 모드)
                if min_chars > 0 and len(passage) < min_chars * 0.7:
                    print("- 길이 미달 (%d자 < %d자)" % (len(passage), min_chars))
                    cat_failed += 1
                    continue

                doc_len = len(passage)

                # Step B: 요약 생성
                summary = generate_summary(passage, model=model)
                if not summary:
                    print("- 요약 생성 실패")
                    cat_failed += 1
                    continue

                # 검증
                is_valid, errors = validate_summary(summary)
                if not is_valid:
                    print(f"- 검증 실패: {errors}")
                    cat_failed += 1
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
                cat_success += 1
                print("- OK (%d자)" % doc_len)

                # Rate limiting
                if (i + 1) % 10 == 0:
                    time.sleep(1)
                    print(f"    --- {i+1}건 완료 (성공: {cat_success}, 실패: {cat_failed}) ---")

            print(f"  [{category}] 결과: 성공 {cat_success}, 실패 {cat_failed}")
            total_success += cat_success
            total_failed += cat_failed

    print(f"\n  전체 결과: 성공 {total_success}, 실패 {total_failed}")
    return total_success


def main():
    parser = argparse.ArgumentParser(description="v2_summary 합성 데이터 생성")
    parser.add_argument("--output", type=str, default=None,
                        help="출력 파일 (미지정 시 length-range에 따라 자동 결정)")
    parser.add_argument("--length-range", type=str, default="all",
                        choices=["all", "medium_plus", "long"],
                        help="생성 길이 모드: all(기존700), medium_plus(3K~5K 150건), long(5K~10K 250건)")
    parser.add_argument("--count", type=int, default=0, help="총 생성 수 (0=기본값)")
    parser.add_argument("--model", type=str, default="gpt-4o")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--append", action="store_true", help="기존 파일에 추가")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 계획만 확인")
    args = parser.parse_args()

    if not args.dry_run and not os.getenv("OPENAI_API_KEY"):
        print("[오류] OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    # 길이 모드별 타겟 & 기본 출력 파일 결정
    length_mode = None
    if args.length_range == "medium_plus":
        base_targets = CATEGORY_TARGETS_MEDIUM_PLUS
        length_mode = "medium_plus"
        default_output = str(OUTPUT_DIR / "synthetic_medium_plus.jsonl")
    elif args.length_range == "long":
        base_targets = CATEGORY_TARGETS_LONG
        length_mode = "long"
        default_output = str(OUTPUT_DIR / "synthetic_long.jsonl")
    else:
        base_targets = CATEGORY_TARGETS
        default_output = str(OUTPUT_DIR / "synthetic_summary.jsonl")

    output_file = args.output or default_output

    # 목표 수 결정
    if args.count > 0:
        total_base = sum(base_targets.values())
        ratio = args.count / total_base
        targets = {k: max(1, int(v * ratio)) for k, v in base_targets.items()}
    else:
        targets = dict(base_targets)

    total_target = sum(targets.values())
    mode_label = {
        "all": "전체 (짧은~중간)",
        "medium_plus": "중간+ (3K~5K)",
        "long": "긴 (5K~10K)",
    }[args.length_range]

    print("=" * 70)
    print("  v2_summary 합성 데이터 생성 — %s" % mode_label)
    print("=" * 70)
    print(f"  출력: {output_file}")
    print(f"  모델: {args.model}")
    print(f"  목표: {total_target}건")
    if length_mode:
        cfg = LENGTH_MODE_CONFIG[length_mode]
        print(f"  길이: {cfg['char_min']}~{cfg['char_max']}자 (멀티턴 max {cfg['max_rounds']}라운드)")
    for cat, cnt in targets.items():
        print(f"    {cat}: {cnt}건")

    if args.dry_run:
        if length_mode:
            avg_rounds = 2 if length_mode == "medium_plus" else 3.5
            est_calls = int(total_target * (avg_rounds + 1))  # 원문 멀티턴 + 요약
        else:
            est_calls = total_target * 2
        est_cost = est_calls * 0.01
        print(f"\n[DRY RUN]")
        print(f"  예상 API 호출: ~{est_calls}회")
        print(f"  예상 비용: ~${est_cost:.1f}")
        return

    # 생성 시작
    output_path = Path(output_file)
    total_success = synthesize_all(
        targets, output_path,
        model=args.model, seed=args.seed, append=args.append,
        length_mode=length_mode,
    )

    # 결과 요약
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        print(f"\n  [결과 요약]")
        print(f"  총 데이터: {len(lines)}건")

        valid_format = 0
        doc_lengths = []
        for line in lines:
            sample = json.loads(line)
            content = sample["messages"][2]["content"]
            if "태그:" in content and "요약:" in content:
                valid_format += 1
            # 입력(문서) 길이
            user_content = sample["messages"][1]["content"]
            doc_lengths.append(len(user_content))

        pct = valid_format / len(lines) * 100 if lines else 0
        print(f"  마크다운 형식 적합: {valid_format}/{len(lines)} ({pct:.1f}%)")

        if doc_lengths:
            print(f"  입력 길이: min={min(doc_lengths)}, max={max(doc_lengths)}, avg={sum(doc_lengths)//len(doc_lengths)}")
            short = sum(1 for l in doc_lengths if l < 1500)
            mid = sum(1 for l in doc_lengths if 1500 <= l < 5000)
            long_cnt = sum(1 for l in doc_lengths if l >= 5000)
            print(f"  분포: 짧은(<1.5K)={short}, 중간(1.5K~5K)={mid}, 긴(5K+)={long_cnt}")

    print(f"\n  완료! 총 성공: {total_success}건")


if __name__ == "__main__":
    main()
