"""
v2_summary 합성 데이터 생성 스크립트

GPT-4o를 활용하여 완전 합성 요약 데이터 300개를 생성합니다.
기존 AI Hub 700개를 보완하여 새로운 문서 유형(이메일, 사내공지, 계약서 등) 추가.

카테고리별 배분:
  회의록 50, 보고서 50, 간행물 30, 뉴스/보도자료 40,
  사설/연설문 30, 이메일 40, 사내공지 30, 계약서/법률문서 30

2단계 파이프라인:
  Step A: GPT-4o -> 문서 원문 생성
  Step B: GPT-4o -> 프로덕션 요약 prompt로 마크다운 요약 생성

사용법:
    python ai/finetuning/scripts/synthesize_summary.py --dry-run
    python ai/finetuning/scripts/synthesize_summary.py
    python ai/finetuning/scripts/synthesize_summary.py --count 50
    python ai/finetuning/scripts/synthesize_summary.py --append
"""

import argparse
import json
import io
import os
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from ai.llm.prompts import DOC_SUMMARY_SLLM_PROMPT

OUTPUT_DIR = BASE_DIR / "data" / "training" / "v2_summary"

# ── sLLM 시스템 프롬프트 (ai/llm/prompts.py에서 import) ──
SYSTEM_PROMPT = DOC_SUMMARY_SLLM_PROMPT

# ── 카테고리별 합성 목표 ──

CATEGORY_TARGETS = {
    "회의록": 50,
    "보고서": 50,
    "간행물": 30,
    "뉴스/보도자료": 40,
    "사설/연설문": 30,
    "이메일": 40,
    "사내공지": 30,
    "계약서/법률문서": 30,
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
        "500~2000자로 작성하세요."
    ),
    "보고서": (
        "{industry} 업종의 업무 보고서를 작성해주세요.\n"
        "업무 진행 현황, 실적 수치, 이슈사항, 향후 계획을 포함하세요.\n"
        "500~2000자로 작성하세요."
    ),
    "간행물": (
        "{industry} 관련 간행물/백서의 일부를 작성해주세요.\n"
        "전문적인 분석과 데이터, 정책 제안을 포함하세요.\n"
        "500~2000자로 작성하세요."
    ),
    "뉴스/보도자료": (
        "{industry} 업종 관련 보도자료를 작성해주세요.\n"
        "육하원칙에 맞게 사실적으로 작성하고, 인용문을 포함하세요.\n"
        "500~2000자로 작성하세요."
    ),
    "사설/연설문": (
        "{industry} 관련 주제로 사설 또는 연설문을 작성해주세요.\n"
        "명확한 주장과 논거를 포함하세요.\n"
        "500~2000자로 작성하세요."
    ),
    "이메일": (
        "{industry} 업종의 업무 이메일을 작성해주세요.\n"
        "발신자, 수신자, 제목, 인사말, 본론, 마무리를 포함한 완전한 이메일 형식으로 작성하세요.\n"
        "업무 협조 요청, 보고, 일정 조율 등의 내용을 포함하세요.\n"
        "300~1000자로 작성하세요."
    ),
    "사내공지": (
        "{industry} 업종 기업의 사내 공지사항을 작성해주세요.\n"
        "제목, 시행일, 대상, 세부 내용, 문의처를 포함하세요.\n"
        "인사 발령, 제도 변경, 시설 안내, 보안 공지 등의 주제로 작성하세요.\n"
        "300~1000자로 작성하세요."
    ),
    "계약서/법률문서": (
        "{industry} 관련 계약서 또는 법률 문서의 일부를 작성해주세요.\n"
        "당사자, 계약 목적, 주요 조항, 의무사항, 위약금, 분쟁 해결 등을 포함하세요.\n"
        "500~1500자로 작성하세요."
    ),
}

# ── 사용자 요청 변형 (기존 convert_aihub_summary.py와 동일 풀 활용) ──

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
    "회의록": ["이 회의록 요약해줘", "회의 내용 정리해줘", "회의 결과 요약"],
    "보고서": ["보고서 요약 부탁해", "이 보고서 핵심 정리", "보고서 내용 요약해줘"],
    "이메일": ["이 이메일 요약해줘", "메일 내용 정리해줘", "이메일 핵심만"],
    "사내공지": ["이 공지 요약해줘", "공지사항 정리해줘"],
    "계약서/법률문서": ["계약서 핵심 정리해줘", "이 계약 내용 요약해줘"],
}

# ── 요약 생성 프롬프트 ──

SUMMARY_GENERATION_SYSTEM = (
    "주어진 문서를 요약하세요.\n\n"
    "출력 형식 (반드시 이 형식을 따르세요):\n"
    "1. 핵심 요약 2-3문장\n"
    "2. 빈 줄\n"
    "3. ## 주요 포인트\n"
    "4. - 불릿 포인트 3~5개\n"
    "5. 빈 줄\n"
    "6. ## 키워드\n"
    "7. 키워드1, 키워드2, 키워드3, 키워드4, 키워드5\n\n"
    "규칙:\n"
    "- 원문에 없는 내용을 추가하지 마세요.\n"
    "- 키워드는 명사/명사구만 (조사, 어미 제거).\n"
    "- 마크다운 형식 외 다른 설명을 포함하지 마세요."
)


def call_openai(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4o",
    temperature: float = 0.9,
    max_tokens: int = 2048,
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


def generate_document(category: str, industry: str, model: str = "gpt-4o") -> str | None:
    """Step A: 카테고리별 문서 원문 생성"""
    doc_system = (
        "당신은 한국 기업 문서 작성 전문가입니다.\n"
        "주어진 조건에 맞는 현실적인 업무 문서를 생성하세요.\n"
        "구체적인 이름, 수치, 날짜를 포함하여 사실적으로 작성하세요.\n"
        "한국어로 작성하세요."
    )

    prompt_template = DOCUMENT_GENERATION_PROMPTS.get(category, DOCUMENT_GENERATION_PROMPTS["보고서"])
    user_prompt = prompt_template.format(industry=industry)

    return call_openai(doc_system, user_prompt, model=model, temperature=0.9, max_tokens=2048)


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
    """요약 형식 검증"""
    errors = []
    if "## 주요 포인트" not in summary:
        errors.append("'## 주요 포인트' 섹션 없음")
    if "## 키워드" not in summary:
        errors.append("'## 키워드' 섹션 없음")
    if "- " not in summary:
        errors.append("불릿 포인트 없음")

    # 키워드 섹션 확인
    if "## 키워드" in summary:
        kw_part = summary.split("## 키워드")[-1].strip()
        keywords = [kw.strip() for kw in kw_part.split(",") if kw.strip()]
        if len(keywords) < 3:
            errors.append(f"키워드 부족: {len(keywords)}개")

    return len(errors) == 0, errors


def build_user_prompt(passage: str, category: str) -> str:
    """프로덕션 형식의 user 프롬프트 (기존 aihub_summary와 동일)"""
    if category in CATEGORY_SPECIFIC_REQUESTS and random.random() < 0.3:
        request = random.choice(CATEGORY_SPECIFIC_REQUESTS[category])
    else:
        request = random.choice(USER_REQUEST_VARIATIONS)

    return f"다음 문서를 요약해주세요.\n\n사용자 요청: {request}\n\n문서 내용:\n{passage}"


def synthesize_all(
    targets: dict[str, int],
    output_path: Path,
    model: str = "gpt-4o",
    seed: int = 42,
    append: bool = False,
) -> int:
    """전체 합성 데이터 생성"""
    random.seed(seed)

    mode = "a" if append else "w"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_success = 0
    total_failed = 0

    with open(output_path, mode, encoding="utf-8") as f:
        for category, count in targets.items():
            print(f"\n  [{category}] {count}건 생성 시작...")
            cat_success = 0
            cat_failed = 0

            for i in range(count):
                industry = random.choice(INDUSTRIES)
                print(f"    [{i+1}/{count}] {industry}", end=" ", flush=True)

                # Step A: 문서 원문 생성
                passage = generate_document(category, industry, model=model)
                if not passage or len(passage) < 100:
                    print("- 원문 생성 실패")
                    cat_failed += 1
                    continue

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
                cat_success += 1
                print("- OK")

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
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR / "synthetic_summary.jsonl"))
    parser.add_argument("--count", type=int, default=0, help="총 생성 수 (0=기본값 300)")
    parser.add_argument("--model", type=str, default="gpt-4o")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--append", action="store_true", help="기존 파일에 추가")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 계획만 확인")
    args = parser.parse_args()

    if not args.dry_run and not os.getenv("OPENAI_API_KEY"):
        print("[오류] OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    # 목표 수 결정
    if args.count > 0:
        ratio = args.count / 300
        targets = {k: max(1, int(v * ratio)) for k, v in CATEGORY_TARGETS.items()}
    else:
        targets = dict(CATEGORY_TARGETS)

    total_target = sum(targets.values())

    print("=" * 70)
    print("  v2_summary 합성 데이터 생성")
    print("=" * 70)
    print(f"  출력: {args.output}")
    print(f"  모델: {args.model}")
    print(f"  목표: {total_target}건")
    for cat, cnt in targets.items():
        print(f"    {cat}: {cnt}건")

    if args.dry_run:
        est_cost = total_target * 2 * 0.02
        print(f"\n[DRY RUN]")
        print(f"  예상 API 호출: {total_target * 2}회 (원문 + 요약)")
        print(f"  예상 비용: ~${est_cost:.1f}")
        return

    # 생성 시작
    output_path = Path(args.output)
    total_success = synthesize_all(
        targets, output_path,
        model=args.model, seed=args.seed, append=args.append,
    )

    # 결과 요약
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        print(f"\n  [결과 요약]")
        print(f"  총 데이터: {len(lines)}건")

        valid_format = 0
        for line in lines:
            sample = json.loads(line)
            content = sample["messages"][2]["content"]
            if "## 주요 포인트" in content and "## 키워드" in content:
                valid_format += 1

        pct = valid_format / len(lines) * 100 if lines else 0
        print(f"  마크다운 형식 적합: {valid_format}/{len(lines)} ({pct:.1f}%)")

    print(f"\n  완료! 총 성공: {total_success}건")


if __name__ == "__main__":
    main()
