"""
v2_generate 합성 데이터 생성 스크립트

GPT-4o를 활용하여 완전 합성 데이터 524개를 생성합니다.
- meeting_minutes: 344개
- report: 90개
- proposal: 90개

2단계 파이프라인:
  Step A: GPT-4o -> 비즈니스 시나리오(passage) 생성
  Step B: GPT-4o -> 프로덕션 프롬프트(동적 필드 방식)로 JSON 응답 생성

사용법:
    python ai/finetuning/scripts/synthesize_generate.py --dry-run
    python ai/finetuning/scripts/synthesize_generate.py
    python ai/finetuning/scripts/synthesize_generate.py --template meeting_minutes --count 50
    python ai/finetuning/scripts/synthesize_generate.py --append
"""

import argparse
import json
import io
import os
import random
import re
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "training" / "v2_generate"

# ── 프로덕션 동적 시스템 프롬프트 (convert_to_dynamic_fields.py와 100% 일치) ──

DYNAMIC_SYSTEM_PROMPT = (
    "당신은 기업 문서 작성 전문가입니다.\n"
    "사용자가 제공하는 [필드 명세]에 따라 문서 내용을 JSON으로 생성하세요.\n\n"
    "규칙:\n"
    "- [필드 명세]에 정의된 필드만 JSON 키로 사용하세요.\n"
    "- 각 필드의 설명을 참고하여 적절한 값을 생성하세요.\n"
    "- 입력 내용에 해당 정보가 없으면 빈 문자열 또는 빈 배열로 두세요.\n"
    "- 배열 필드는 반드시 JSON 배열 형태로 출력하세요.\n"
    "- 반드시 JSON만 출력하세요. 설명 텍스트나 마크다운을 포함하지 마세요."
)

# ── 템플릿별 필드 명세 (convert_to_dynamic_fields.py와 100% 일치) ──

FIELD_SPECS = {
    "meeting_minutes": {
        "doc_type_name": "회의록",
        "input_label": "회의 내용",
        "fields": [
            ("title", "회의 주제를 반영한 구체적인 제목"),
            ("date", "회의 날짜 (YYYY-MM-DD 형식, 없으면 오늘 날짜)"),
            ("attendees", "참석자 이름 배열 (없으면 빈 배열)"),
            ("summary", "회의에서 논의된 주요 내용을 파트별로 3~5문장으로 요약"),
            ("decisions", "결정된 사항 목록 (배열, 없으면 빈 배열)"),
            ("action_items", '후속 조치 목록 배열. 각 항목은 {"content", "assignee", "due_date"} 형태'),
            ("risks", '리스크 목록 배열. 각 항목은 {"description", "level"(상/중/하), "regulation"} 형태'),
        ],
    },
    "report": {
        "doc_type_name": "업무보고서",
        "input_label": "업무 내용",
        "fields": [
            ("title", "업무 내용을 반영한 구체적인 보고서 제목"),
            ("author", "작성자 이름 (없으면 빈 문자열)"),
            ("date", "작성 날짜 (YYYY-MM-DD 형식)"),
            ("department", "부서명 (없으면 빈 문자열)"),
            ("position", "직급 (없으면 빈 문자열)"),
            ("report_to", "보고 대상 (없으면 빈 문자열)"),
            ("report_type", "'일일', '주간', '월간', '수시' 중 하나"),
            ("overview", "업무 내용을 요약한 보고 개요 (3~5문장)"),
            ("main_content", "업무 세부 내용을 항목별로 구체적으로 작성"),
            ("tasks", '진행 업무 목록 배열. 각 항목은 {"item", "assignee", "progress", "start_date", "end_date"} 형태'),
            ("issues", "이슈 및 건의사항 (없으면 빈 문자열)"),
            ("next_plan", "향후 계획 (구체적으로 작성)"),
        ],
    },
    "proposal": {
        "doc_type_name": "제안서",
        "input_label": "제안 내용",
        "fields": [
            ("title", "제안 내용을 반영한 구체적인 제안서 제목"),
            ("submit_date", "제출 날짜 (YYYY-MM-DD, 없으면 오늘 날짜)"),
            ("submit_to", "제출처 (없으면 빈 문자열)"),
            ("company", "제안사 이름 (없으면 빈 문자열)"),
            ("manager", "담당자 이름 (없으면 빈 문자열)"),
            ("contact", "연락처 (없으면 빈 문자열)"),
            ("proposal_name", "제안명 (title과 유사하게)"),
            ("background", "제안 배경 (2~3문장)"),
            ("proposal_date", "제안 날짜 (YYYY-MM-DD)"),
            ("period", "제안 기간 (예: 2026년 3월 ~ 6월)"),
            ("proposer", "제안사명"),
            ("manager_contact", "담당자 / 연락처"),
            ("purpose", "제안 목적 및 필요성 (3~5문장)"),
            ("analysis", "현황 분석 (3~5문장)"),
            ("content", "제안 내용을 항목별로 구체적으로 작성"),
            ("schedule", '추진 일정 배열. 각 항목은 {"item", "phase1", "phase2", "phase3", "phase4"} 형태'),
            ("budget", '예산 배열. 각 항목은 {"item", "quantity", "unit_price", "amount"} 형태'),
            ("budget_total", "합계 금액"),
            ("expected_effect", "기대 효과 (3~5문장)"),
        ],
    },
}

# ── 필수 필드 (검증용) ──

REQUIRED_FIELDS = {
    "meeting_minutes": ["title", "date", "attendees", "summary", "decisions", "action_items"],
    "report": ["title", "author", "date", "department", "report_type", "overview", "main_content", "tasks"],
    "proposal": [
        "title", "submit_date", "submit_to", "company", "manager",
        "proposal_name", "background", "purpose", "content", "schedule", "budget",
    ],
}

# ── 시나리오 다양성 풀 ──

INDUSTRIES = [
    "IT/소프트웨어", "제조업", "금융/은행", "유통/물류", "의료/헬스케어",
    "건설/부동산", "교육", "미디어/광고", "에너지/환경", "공공/정부",
    "컨설팅", "식품/외식", "자동차", "통신", "바이오/제약",
]

MEETING_TOPICS = [
    "신규 프로젝트 킥오프", "주간 스프린트 리뷰", "예산 심의", "인사 회의",
    "보안 감사 결과 공유", "제품 출시 전략", "클레임 대응 논의",
    "시스템 장애 복구 회의", "분기 실적 리뷰", "파트너십 협상 논의",
    "조직개편 논의", "연말 성과 평가", "신규 채용 면접 결과",
    "고객 VOC 대응 회의", "마케팅 캠페인 전략", "품질 관리 점검",
    "IT 인프라 업그레이드 논의", "컴플라이언스 점검 회의", "공급망 리스크 관리",
    "디지털 전환 추진 회의", "신사업 검토 회의", "연구개발 과제 리뷰",
    "사내 교육 프로그램 기획", "해외 진출 전략 회의", "환경안전 점검 회의",
    "연간 사업 계획 수립", "원가 절감 방안 논의", "법률 검토 회의",
    "고객사 요구사항 분석", "프로젝트 중간 보고", "서비스 장애 대응 후 복구",
    "데이터 보안 정책 수립", "채용 전략 회의", "제휴사 미팅 결과 공유",
    "사옥 이전 계획", "복지 제도 개편 논의", "내부 감사 결과 보고",
]

REPORT_TOPICS = [
    "주간 업무 보고", "프로젝트 진행 현황", "시장 조사 보고", "고객 VOC 분석",
    "시스템 운영 보고", "마케팅 캠페인 결과", "재무 분석", "인력 현황",
    "품질 관리 보고", "IT 인프라 점검", "보안 취약점 점검 보고", "경쟁사 동향 분석",
    "매출 실적 보고", "신규 고객 유치 현황", "물류 운영 보고", "연구개발 진행 보고",
    "교육 실시 결과", "고객 만족도 조사", "설비 가동률 보고", "원자재 수급 현황",
]

PROPOSAL_TOPICS = [
    "디지털 전환 추진", "ERP 시스템 도입", "보안 강화 방안", "ESG 경영 도입",
    "AI 기반 업무 자동화", "클라우드 마이그레이션", "신사업 진출 계획",
    "사내 교육 체계 개편", "원가 절감 방안", "해외 시장 진출",
    "스마트 팩토리 구축", "고객 관계 관리(CRM) 시스템 도입", "재택근무 제도 도입",
    "데이터 분석 플랫폼 구축", "사무실 환경 개선", "신제품 개발 계획",
    "통합 물류 시스템 구축", "사내 복지 제도 개선", "지식 관리 시스템 도입",
    "브랜드 리뉴얼 추진",
]

TEMPLATE_TARGETS = {
    "meeting_minutes": 344,
    "report": 90,
    "proposal": 90,
}


# ── 시나리오 생성 프롬프트 ──

SCENARIO_SYSTEM_PROMPTS = {
    "meeting_minutes": (
        "당신은 기업 회의 시나리오 작성 전문가입니다.\n"
        "주어진 업종과 주제에 맞는 현실적인 회의 내용을 생성하세요.\n\n"
        "규칙:\n"
        "- 대화체가 아닌 서술형으로 작성하세요 (회의 기록 형식).\n"
        "- 참석자 이름(한국식), 구체적 수치, 날짜를 포함하세요.\n"
        "- 의사결정 사항, 후속 조치, 리스크를 포함하세요.\n"
        "- 500~1500자 사이로 작성하세요.\n"
        "- 한국어로 작성하세요."
    ),
    "report": (
        "당신은 기업 업무 시나리오 작성 전문가입니다.\n"
        "주어진 업종과 주제에 맞는 현실적인 업무 보고 내용을 생성하세요.\n\n"
        "규칙:\n"
        "- 보고서에 넣을 업무 내용을 서술형으로 작성하세요.\n"
        "- 담당자 이름, 진행률, 일정, 수치 데이터를 포함하세요.\n"
        "- 이슈사항과 향후 계획도 포함하세요.\n"
        "- 500~1500자 사이로 작성하세요.\n"
        "- 한국어로 작성하세요."
    ),
    "proposal": (
        "당신은 기업 제안 시나리오 작성 전문가입니다.\n"
        "주어진 업종과 주제에 맞는 현실적인 제안 내용을 생성하세요.\n\n"
        "규칙:\n"
        "- 제안 배경, 목적, 현황 분석, 구체적 방안을 포함하세요.\n"
        "- 예산 규모, 일정, 기대 효과를 구체적으로 포함하세요.\n"
        "- 회사명, 담당자명 등 구체적 정보를 포함하세요.\n"
        "- 500~1500자 사이로 작성하세요.\n"
        "- 한국어로 작성하세요."
    ),
}


def build_dynamic_user_prompt(template: str, passage: str) -> str:
    """동적 필드 명세 방식의 user prompt 생성 (convert_to_dynamic_fields.py와 동일)"""
    spec = FIELD_SPECS[template]
    doc_type = spec["doc_type_name"]
    input_label = spec["input_label"]

    field_lines = []
    for field_name, field_desc in spec["fields"]:
        field_lines.append(f"- {field_name}: {field_desc}")
    field_spec_str = "\n".join(field_lines)

    return (
        f"다음 내용을 바탕으로 문서를 JSON 형식으로 작성해주세요.\n\n"
        f"[문서 유형] {doc_type}\n\n"
        f"[필드 명세]\n{field_spec_str}\n\n"
        f"[{input_label}]\n{passage}"
    )


def call_openai(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4o",
    temperature: float = 0.9,
    max_tokens: int = 2048,
    json_mode: bool = False,
    max_retries: int = 3,
) -> str | None:
    """OpenAI API 호출"""
    try:
        from openai import OpenAI
    except ImportError:
        print("[오류] openai 패키지가 필요합니다: pip install openai")
        sys.exit(1)

    client = OpenAI()
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"    [API 에러 (시도 {attempt+1}/{max_retries})] {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return None


def generate_scenario(template: str, industry: str, topic: str, model: str = "gpt-4o") -> str | None:
    """Step A: GPT-4o로 비즈니스 시나리오 생성"""
    doc_type_map = {
        "meeting_minutes": "회의",
        "report": "업무 보고",
        "proposal": "제안",
    }
    doc_type = doc_type_map[template]

    user_prompt = (
        f"다음 조건으로 {industry} 업종의 {doc_type} 관련 원문 내용을 생성해주세요.\n\n"
        f"주제: {topic}\n"
        f"길이: 500~1500자\n"
        f"구체적인 수치, 한국식 이름, 날짜를 포함해주세요."
    )

    return call_openai(
        SCENARIO_SYSTEM_PROMPTS[template],
        user_prompt,
        model=model,
        temperature=0.9,
        max_tokens=2048,
        json_mode=False,
    )


def generate_response(template: str, passage: str, model: str = "gpt-4o") -> str | None:
    """Step B: 프로덕션 프롬프트로 JSON 응답 생성"""
    user_prompt = build_dynamic_user_prompt(template, passage)

    return call_openai(
        DYNAMIC_SYSTEM_PROMPT,
        user_prompt,
        model=model,
        temperature=0.7,
        max_tokens=2048,
        json_mode=True,
    )


def validate_json_output(json_str: str, template: str) -> tuple[bool, dict | None, list[str]]:
    """생성된 JSON 검증"""
    errors = []

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return False, None, [f"JSON 파싱 실패: {e}"]

    if not isinstance(data, dict):
        return False, None, ["최상위가 dict가 아님"]

    # 한국어 키 체크
    korean_keys = [k for k in data.keys() if re.search(r"[\uac00-\ud7a3]", k)]
    if korean_keys:
        errors.append(f"한국어 키 발견: {korean_keys}")

    # 필수 필드 체크
    required = REQUIRED_FIELDS.get(template, [])
    missing = [f for f in required if f not in data]
    if missing:
        errors.append(f"필수 필드 누락: {missing}")

    return len(errors) == 0, data, errors


def build_scenario_pool(template: str, count: int, seed: int = 42) -> list[dict]:
    """시나리오 풀 생성 (업종 x 주제 랜덤 조합)"""
    random.seed(seed)

    topic_map = {
        "meeting_minutes": MEETING_TOPICS,
        "report": REPORT_TOPICS,
        "proposal": PROPOSAL_TOPICS,
    }
    topics = topic_map[template]

    pool = []
    for _ in range(count):
        pool.append({
            "industry": random.choice(INDUSTRIES),
            "topic": random.choice(topics),
        })

    return pool


def synthesize_template(
    template: str,
    count: int,
    output_path: Path,
    model: str = "gpt-4o",
    seed: int = 42,
    append: bool = False,
    empty_field_ratio: float = 0.3,
) -> int:
    """특정 템플릿의 합성 데이터 생성"""
    pool = build_scenario_pool(template, count, seed)
    random.seed(seed)

    mode = "a" if append else "w"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0

    with open(output_path, mode, encoding="utf-8") as f:
        for i, scenario in enumerate(pool):
            industry = scenario["industry"]
            topic = scenario["topic"]

            print(f"    [{i+1}/{count}] {industry} / {topic}", end=" ", flush=True)

            # Step A: 시나리오 생성
            passage = generate_scenario(template, industry, topic, model=model)
            if not passage or len(passage) < 100:
                print("- 시나리오 실패")
                failed += 1
                continue

            # ~30% 확률로 passage 일부 정보 제거 (빈 필드 학습용)
            if random.random() < empty_field_ratio:
                # passage 앞부분 30% 잘라내기 (일부 정보 누락 시뮬레이션)
                cut_point = len(passage) // 3
                passage = passage[cut_point:]

            # Step B: JSON 응답 생성
            json_output = generate_response(template, passage, model=model)
            if not json_output:
                print("- JSON 생성 실패")
                failed += 1
                continue

            # 검증
            is_valid, parsed, errors = validate_json_output(json_output, template)
            if not is_valid:
                print(f"- 검증 실패: {errors}")
                failed += 1
                continue

            # 학습 데이터 저장
            user_prompt = build_dynamic_user_prompt(template, passage)
            sample = {
                "messages": [
                    {"role": "system", "content": DYNAMIC_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": json_output},
                ]
            }

            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            success += 1
            print(f"- OK ({len(parsed)}키)")

            # Rate limiting
            if (i + 1) % 10 == 0:
                time.sleep(1)
                print(f"    --- {i+1}건 완료 (성공: {success}, 실패: {failed}) ---")

    print(f"\n  [{template}] 결과: 성공 {success}, 실패 {failed}")
    return success


def main():
    parser = argparse.ArgumentParser(description="v2_generate 합성 데이터 생성")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR / "synthetic_generate.jsonl"))
    parser.add_argument("--template", type=str, choices=["meeting_minutes", "report", "proposal", "all"], default="all")
    parser.add_argument("--count", type=int, default=0, help="총 생성 수 (0=기본값 524)")
    parser.add_argument("--model", type=str, default="gpt-4o")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--append", action="store_true", help="기존 파일에 추가")
    parser.add_argument("--empty-field-ratio", type=float, default=0.3, help="빈 필드 비율 (0.0~1.0)")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 시나리오 풀만 확인")
    args = parser.parse_args()

    if not args.dry_run and not os.getenv("OPENAI_API_KEY"):
        print("[오류] OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    # 템플릿별 목표 수 결정
    if args.count > 0 and args.template != "all":
        targets = {args.template: args.count}
    elif args.count > 0:
        ratio = args.count / 524
        targets = {k: max(1, int(v * ratio)) for k, v in TEMPLATE_TARGETS.items()}
    else:
        targets = dict(TEMPLATE_TARGETS)

    templates_to_run = (
        [args.template] if args.template != "all"
        else ["meeting_minutes", "report", "proposal"]
    )

    total_target = sum(targets.get(t, 0) for t in templates_to_run)

    print("=" * 70)
    print("  v2_generate 합성 데이터 생성")
    print("=" * 70)
    print(f"  출력: {args.output}")
    print(f"  모델: {args.model}")
    print(f"  목표: {total_target}건")
    for t in templates_to_run:
        print(f"    {t}: {targets.get(t, 0)}건")
    print(f"  빈 필드 비율: {args.empty_field_ratio:.0%}")

    if args.dry_run:
        print(f"\n[DRY RUN] 시나리오 풀 미리보기:")
        for tmpl in templates_to_run:
            count = targets.get(tmpl, 0)
            pool = build_scenario_pool(tmpl, min(count, 5), args.seed)
            print(f"\n  [{tmpl}] ({count}건 예정, 샘플 {len(pool)}건):")
            for s in pool:
                print(f"    - {s['industry']} / {s['topic']}")
        est_cost = total_target * 2 * 0.025  # ~$0.025 per call
        print(f"\n  예상 API 호출: {total_target * 2}회 (시나리오 + JSON)")
        print(f"  예상 비용: ~${est_cost:.1f}")
        return

    # 생성 시작
    output_path = Path(args.output)
    total_success = 0

    for i, tmpl in enumerate(templates_to_run):
        count = targets.get(tmpl, 0)
        if count == 0:
            continue
        print(f"\n  === {tmpl} ({count}건) ===")
        is_append = args.append or (i > 0)
        success = synthesize_template(
            tmpl, count, output_path,
            model=args.model, seed=args.seed + i,
            append=is_append,
            empty_field_ratio=args.empty_field_ratio,
        )
        total_success += success

    # 결과 요약
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        print(f"\n  [결과 요약]")
        print(f"  총 데이터: {len(lines)}건")

        template_dist = {"meeting_minutes": 0, "report": 0, "proposal": 0}
        json_valid = 0
        for line in lines:
            sample = json.loads(line)
            user_content = sample["messages"][1]["content"]
            assistant_content = sample["messages"][2]["content"]

            if "회의록" in user_content:
                template_dist["meeting_minutes"] += 1
            elif "제안서" in user_content:
                template_dist["proposal"] += 1
            else:
                template_dist["report"] += 1

            try:
                json.loads(assistant_content)
                json_valid += 1
            except json.JSONDecodeError:
                pass

        pct = json_valid / len(lines) * 100 if lines else 0
        print(f"  템플릿 분포: {template_dist}")
        print(f"  JSON 유효율: {json_valid}/{len(lines)} ({pct:.1f}%)")

    print(f"\n  완료! 총 성공: {total_success}건")


if __name__ == "__main__":
    main()
