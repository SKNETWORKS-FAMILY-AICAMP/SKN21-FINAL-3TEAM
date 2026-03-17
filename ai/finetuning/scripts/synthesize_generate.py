"""
v2_generate 합성 데이터 생성 스크립트 (필드 풀 랜덤 조합 방식)

GPT-4o를 활용하여 합성 데이터 800개를 생성합니다.
- meeting_minutes: 400개
- report: 200개
- proposal: 200개

2단계 파이프라인:
  Step A: GPT-4o -> 비즈니스 시나리오(passage) 생성
  Step B: GPT-4o -> 필드 풀에서 랜덤 선택된 필드 명세로 JSON 응답 생성

필드 풀 방식:
  각 문서유형별 필드를 필수/메타/내용 3계층으로 분류.
  매 샘플마다: 필수 전부 + 내용 풀 2~4개 + 메타 풀 1~3개 = 총 6~10개 필드.
  sLLM이 "필드 명세를 읽고 따르는 능력" 자체를 학습.

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
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env", override=True)

from ai.llm.prompts import DOC_GENERATE_SLLM_PROMPT

OUTPUT_DIR = BASE_DIR / "data" / "training" / "v2_generate"

# -- sLLM 시스템 프롬프트 (ai/llm/prompts.py에서 import) --
DYNAMIC_SYSTEM_PROMPT = DOC_GENERATE_SLLM_PROMPT

# ============================================================
# 필드 풀 설계 (3계층: 필수 / 메타 / 내용)
# ============================================================
# 매 샘플: 필수 전부 + 내용 풀 2~4개 + 메타 풀 1~3개 = 총 6~10개
# 내용 풀 최소 2개 보장 (메타만 뽑히는 무의미한 샘플 방지)

FIELD_POOLS = {
    "meeting_minutes": {
        "doc_type_name": "회의록",
        "input_label": "회의 내용",
        "core": [
            ("title", "회의 주제를 반영한 구체적인 제목"),
            ("date", "회의 날짜 (YYYY-MM-DD 형식, 없으면 오늘 날짜)"),
            ("attendees", "참석자 이름 배열 (없으면 빈 배열)"),
        ],
        "meta": [
            ("time", "회의 시간 (예: '14:00~15:30')"),
            ("location", "회의 장소 (없으면 빈 문자열)"),
            ("meeting_type", "회의 유형 ('정기', '비정기', '긴급' 중 하나)"),
            ("author", "작성자 이름 (없으면 빈 문자열)"),
            ("moderator", "진행자/사회자 이름 (없으면 빈 문자열)"),
            ("department", "주관 부서명 (없으면 빈 문자열)"),
            ("duration", "회의 소요 시간 (예: '1시간 30분')"),
        ],
        "always_content": [
            ("content", "회의 내용을 상세하게 기술"),
            ("summary", "회의에서 논의된 주요 내용을 3~5문장으로 요약"),
        ],
        "priority_content": [
            ("decisions", "결정된 사항 목록 (배열, 없으면 빈 배열)"),
            ("action_items", '후속 조치 목록 배열. 각 항목은 {"content": "내용", "assignee": "담당자", "due_date": "기한"} 형태'),
        ],
        "content": [
            ("agenda", "회의 안건 목록 (배열)"),
            ("meeting_purpose", "회의 목적 (1~2문장)"),
            ("risks", '리스크 목록 배열. 각 항목은 {"description": "설명", "level": "상/중/하", "mitigation": "대응방안"} 형태'),
            ("next_meeting", "다음 회의 일정 (없으면 빈 문자열)"),
            ("notes", "비고 사항 (없으면 빈 문자열)"),
        ],
    },
    "report": {
        "doc_type_name": "업무보고서",
        "input_label": "업무 내용",
        "core": [
            ("title", "업무 내용을 반영한 구체적인 보고서 제목"),
            ("date", "작성 날짜 (YYYY-MM-DD 형식)"),
            ("author", "작성자 이름 (없으면 빈 문자열)"),
        ],
        "meta": [
            ("department", "부서명 (없으면 빈 문자열)"),
            ("position", "직급 (없으면 빈 문자열)"),
            ("report_to", "보고 대상 (없으면 빈 문자열)"),
            ("report_type", "'일일', '주간', '월간', '수시' 중 하나"),
            ("period", "보고 기간 (예: '2026년 2월 1주차')"),
            ("audience", "보고 대상/독자 (없으면 빈 문자열)"),
        ],
        "always_content": [
            ("overview", "업무 내용을 요약한 보고 개요 (3~5문장)"),
            ("main_content", "업무 세부 내용을 서술형 문자열로 구체적으로 작성"),
        ],
        "priority_content": [
            ("tasks", '진행 업무 목록 배열. 각 항목은 {"item": "업무명", "assignee": "담당자", "progress": "진행률", "start_date": "시작일", "end_date": "종료일"} 형태'),
            ("next_plan", "향후 계획 (구체적으로 작성)"),
            ("issues", "이슈 및 건의사항 (서술형 문자열, 없으면 빈 문자열)"),
        ],
        "content": [
            ("achievements", "주요 성과 목록 (배열)"),
            ("kpi_results", "KPI 달성 현황 (없으면 빈 문자열)"),
            ("conclusion", "결론 및 종합 의견"),
            ("recommendations", "권장 사항 목록 (배열)"),
        ],
    },
    "proposal": {
        "doc_type_name": "제안서",
        "input_label": "제안 내용",
        "core": [
            ("title", "제안 내용을 반영한 구체적인 제안서 제목"),
            ("submit_date", "제출 날짜 (YYYY-MM-DD, 없으면 오늘 날짜)"),
            ("purpose", "제안 목적 및 필요성 (3~5문장)"),
        ],
        "meta": [
            ("submit_to", "제출처 (없으면 빈 문자열)"),
            ("company", "제안사 이름 (없으면 빈 문자열)"),
            ("manager", "담당자 이름 (없으면 빈 문자열)"),
            ("contact", "연락처 (없으면 빈 문자열)"),
            ("proposer", "제안자/제안사명 (없으면 빈 문자열)"),
            ("period", "제안 기간 (예: '2026년 3월 ~ 6월')"),
        ],
        "always_content": [
            ("content", "제안 내용을 서술형 문자열로 구체적으로 작성"),
            ("expected_effect", "기대 효과 (3~5문장, 서술형 문자열)"),
        ],
        "priority_content": [
            ("schedule", '추진 일정 배열. 각 항목은 {"item": "추진항목", "phase1": "1단계 내용", "phase2": "2단계 내용", "phase3": "3단계 내용", "phase4": "4단계 내용"} 형태'),
            ("budget", '예산 배열. 각 항목은 {"item": "항목", "quantity": "수량", "unit_price": "단가", "amount": "금액"} 형태'),
            ("background", "제안 배경 (2~3문장, 서술형 문자열)"),
            ("current_situation", "현황 분석 (3~5문장, 서술형 문자열)"),
        ],
        "content": [
            ("scope", "사업 범위 (2~3문장)"),
            ("budget_total", "합계 금액 (없으면 빈 문자열)"),
            ("resources", "필요 자원 (인력, 장비 등)"),
            ("risks", '리스크 및 대응 방안 배열. 각 항목은 {"risk": "리스크", "mitigation": "대응방안"} 형태'),
            ("deliverables", "산출물 목록 (배열)"),
        ],
    },
}


def select_random_fields(template: str, rng: random.Random) -> list[tuple[str, str]]:
    """필드 풀에서 랜덤 조합 선택.

    규칙: 필수 전부 + priority 각 80% + 내용 나머지 + 메타 1~3개 = 총 6~10개
    priority_content: 시스템 템플릿 핵심 필드 (content/summary/decisions 등)
    """
    pool = FIELD_POOLS[template]
    core = list(pool["core"])
    meta = list(pool["meta"])
    always = list(pool.get("always_content", []))   # 100% 포함
    priority = list(pool.get("priority_content", []))  # 각 80% 포함
    content = list(pool["content"])

    # always_content: 항상 포함 (100%)
    selected_always = list(always)

    # priority_content: 각각 80% 확률로 포함
    selected_priority = [f for f in priority if rng.random() < 0.8]

    # 목표 필드 수: 6~10개
    target = rng.randint(6, 10)
    fixed = len(core) + len(selected_always) + len(selected_priority)
    remaining = max(0, target - fixed)

    # 메타 풀에서 1~3개 선택
    n_meta = min(rng.randint(1, 3), remaining, len(meta))
    selected_meta = rng.sample(meta, n_meta)
    remaining -= n_meta

    # 나머지 내용 풀에서 채우기
    n_content = min(remaining, len(content))
    selected_content = rng.sample(content, n_content) if n_content > 0 else []

    # 필수 + always + 메타 + priority + 내용 합치기 (최대 10개)
    selected = core + selected_meta + selected_always + selected_priority + selected_content
    return selected[:10]


def build_dynamic_user_prompt(template: str, passage: str, fields: list[tuple[str, str]]) -> str:
    """선택된 필드로 동적 user prompt 생성."""
    pool = FIELD_POOLS[template]
    doc_type = pool["doc_type_name"]
    input_label = pool["input_label"]

    field_lines = []
    for field_name, field_desc in fields:
        field_lines.append(f"- {field_name}: {field_desc}")
    field_spec_str = "\n".join(field_lines)

    return (
        f"다음 내용을 바탕으로 문서를 JSON 형식으로 작성해주세요.\n\n"
        f"[문서 유형] {doc_type}\n\n"
        f"[필드 명세]\n{field_spec_str}\n\n"
        f"[{input_label}]\n{passage}"
    )


# -- 시나리오 다양성 풀 --

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
    "meeting_minutes": 400,
    "report": 200,
    "proposal": 200,
}


# -- 시나리오 생성 프롬프트 --

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


# -- 빈 필드 학습용: 누락 가능 필드 --
# core/always_content/priority_content 제외 — 메타 풀 + 일반 내용 풀만
# (priority 필드는 select_random_fields의 80% 확률로 제어하므로 여기서 비우지 않음)
OMITTABLE_FIELDS = {
    "meeting_minutes": [
        "time", "location", "meeting_type", "author", "moderator", "department", "duration",
        "agenda", "meeting_purpose", "risks", "next_meeting", "notes",
    ],
    "report": [
        "department", "position", "report_to", "report_type", "period", "audience",
        "achievements", "issues", "kpi_results", "conclusion", "recommendations",
    ],
    "proposal": [
        "submit_to", "company", "manager", "contact", "proposer", "period",
        "background", "current_situation", "scope", "budget_total", "resources", "risks", "deliverables",
    ],
}


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


LENGTH_PROFILES = [
    ("50~200", 0.3),      # 짧은 입력: 폼에서 제목+한줄 메모 수준
    ("200~800", 0.4),     # 중간 입력: 챗봇 일반 입력
    ("800~1500", 0.2),    # 상세 기술
    ("1500~3000", 0.1),   # 긴 입력: 회의 전체 내용 붙여넣기
]


def _pick_length_range(rng) -> str:
    """가중 랜덤으로 입력 길이 범위 선택"""
    r = rng.random()
    cumulative = 0
    for length_range, weight in LENGTH_PROFILES:
        cumulative += weight
        if r <= cumulative:
            return length_range
    return "500~1500"


def generate_scenario(template: str, industry: str, topic: str, model: str = "gpt-4o", length_range: str = "500~1500") -> str | None:
    """Step A: GPT-4o로 비즈니스 시나리오 생성"""
    doc_type_map = {
        "meeting_minutes": "회의",
        "report": "업무 보고",
        "proposal": "제안",
    }
    doc_type = doc_type_map[template]

    # 짧은 입력은 메모/키워드 형태, 긴 입력은 상세 서술
    if length_range.startswith("50"):
        style_hint = "간단한 메모나 키워드 나열 형태로 작성하세요. 예: '팀미팅 진행, 예산 논의, 신규 프로젝트 결정'"
    elif length_range.startswith("200"):
        style_hint = "핵심 내용을 간결하게 서술형으로 작성하세요."
    else:
        style_hint = "구체적인 수치, 한국식 이름, 날짜를 포함하여 상세하게 작성하세요."

    user_prompt = (
        f"다음 조건으로 {industry} 업종의 {doc_type} 관련 원문 내용을 생성해주세요.\n\n"
        f"주제: {topic}\n"
        f"길이: {length_range}자\n"
        f"{style_hint}"
    )

    # 긴 시나리오(1500~3000자)는 한국어 토큰 특성상 max_tokens 확보 필요
    tokens = 4096 if length_range.startswith("1500") else 2048

    return call_openai(
        SCENARIO_SYSTEM_PROMPTS[template],
        user_prompt,
        model=model,
        temperature=0.9,
        max_tokens=tokens,
        json_mode=False,
    )


def generate_response(template: str, passage: str, fields: list[tuple[str, str]], model: str = "gpt-4o") -> str | None:
    """Step B: 선택된 필드 명세로 JSON 응답 생성"""
    user_prompt = build_dynamic_user_prompt(template, passage, fields)

    # 긴 입력 + 많은 필드 → JSON 응답도 길 수 있음
    tokens = 4096 if len(passage) > 1200 else 2048

    return call_openai(
        DYNAMIC_SYSTEM_PROMPT,
        user_prompt,
        model=model,
        temperature=0.7,
        max_tokens=tokens,
        json_mode=True,
    )


def validate_json_output(json_str: str, selected_fields: list[tuple[str, str]]) -> tuple[bool, dict | None, list[str]]:
    """생성된 JSON 검증 (선택된 필드 기준)"""
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

    # 선택된 필드가 JSON에 존재하는지 체크
    selected_names = [name for name, _ in selected_fields]
    missing = [f for f in selected_names if f not in data]
    if missing:
        errors.append(f"필드 누락: {missing}")

    # JSON에 선택되지 않은 필드가 있는지 체크 (과잉 필드)
    extra = [k for k in data.keys() if k not in selected_names]
    if extra:
        errors.append(f"과잉 필드: {extra}")

    return len(errors) == 0, data, errors


def build_scenario_pool(template: str, count: int, seed: int = 42) -> list[dict]:
    """시나리오 풀 생성 (업종 x 주제 랜덤 조합)"""
    rng = random.Random(seed)

    topic_map = {
        "meeting_minutes": MEETING_TOPICS,
        "report": REPORT_TOPICS,
        "proposal": PROPOSAL_TOPICS,
    }
    topics = topic_map[template]

    pool = []
    for _ in range(count):
        pool.append({
            "industry": rng.choice(INDUSTRIES),
            "topic": rng.choice(topics),
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
    rng = random.Random(seed)

    mode = "a" if append else "w"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0

    with open(output_path, mode, encoding="utf-8") as f:
        for i, scenario in enumerate(pool):
            industry = scenario["industry"]
            topic = scenario["topic"]

            # 매 샘플마다 필드 풀에서 랜덤 조합 선택
            selected_fields = select_random_fields(template, rng)
            field_names = [name for name, _ in selected_fields]

            # 입력 길이 다양화 (짧은 20% / 중간 50% / 긴 30%)
            length_range = _pick_length_range(rng)
            print(f"    [{i+1}/{count}] {industry} / {topic} ({len(selected_fields)}필드, {length_range}자)", end=" ", flush=True)

            # Step A: 시나리오 생성
            passage = generate_scenario(template, industry, topic, model=model, length_range=length_range)
            min_len = 30 if length_range.startswith("50") else 100
            if not passage or len(passage) < min_len:
                print("- 시나리오 실패")
                failed += 1
                continue

            # 입력 길이에 따라 sparse 비율 조정 (짧을수록 빈 필드 많이)
            # short: 정보 부족 → 60% sparse / long: 정보 풍부 → 10% sparse
            _sparse_by_length = {
                "50~200": 0.60,    # short: 빈 필드 많이 (할루시네이션 방지)
                "200~800": 0.30,   # mid: 표준
                "800~1500": 0.20,  # long: 대부분 채움
                "1500~3000": 0.10, # xlong: 거의 다 채움
            }
            _effective_sparse = _sparse_by_length.get(length_range, empty_field_ratio)
            is_sparse = rng.random() < _effective_sparse
            omit_fields = []
            if is_sparse:
                # 선택된 필드 중 OMITTABLE에 해당하는 것만 비울 수 있음
                omittable = [f for f in field_names if f in OMITTABLE_FIELDS.get(template, [])]
                if omittable:
                    k = rng.randint(1, min(3, len(omittable)))
                    omit_fields = rng.sample(omittable, k)
                    passage += (
                        f"\n\n[참고] 다음 정보는 원문에 포함되어 있지 않습니다: "
                        f"{', '.join(omit_fields)}. "
                        f"해당 필드는 빈 문자열 또는 빈 배열로 두세요."
                    )

            # Step B: JSON 응답 생성
            json_output = generate_response(template, passage, selected_fields, model=model)
            if not json_output:
                print("- JSON 생성 실패")
                failed += 1
                continue

            # 검증 (선택된 필드 기준)
            is_valid, parsed, errors = validate_json_output(json_output, selected_fields)

            # 과잉 필드는 제거하고 재검증
            if not is_valid and parsed and errors:
                extra_errors = [e for e in errors if "과잉 필드" in e]
                if extra_errors and parsed:
                    for k in list(parsed.keys()):
                        if k not in field_names:
                            del parsed[k]
                    json_output = json.dumps(parsed, ensure_ascii=False)
                    is_valid, parsed, errors = validate_json_output(json_output, selected_fields)

            if not is_valid:
                print(f"- 검증 실패: {errors}")
                failed += 1
                continue

            # 빈 필드 샘플: 지정 필드가 실제로 비었는지 확인
            if is_sparse and parsed and omit_fields:
                empty_count = 0
                for field in omit_fields:
                    val = parsed.get(field)
                    if val in ("", [], None, {}):
                        empty_count += 1
                if empty_count < len(omit_fields):
                    # GPT-4o가 지시를 무시하고 채운 필드 -> 후처리로 강제 비움
                    for field in omit_fields:
                        val = parsed.get(field)
                        if val not in ("", [], None, {}):
                            if isinstance(val, list):
                                parsed[field] = []
                            else:
                                parsed[field] = ""
                    json_output = json.dumps(parsed, ensure_ascii=False)

            # 학습 데이터 저장 (user prompt에는 [참고] 지시 제거)
            clean_passage = passage.split("\n\n[참고]")[0] if is_sparse else passage
            user_prompt = build_dynamic_user_prompt(template, clean_passage, selected_fields)
            sample = {
                "messages": [
                    {"role": "system", "content": DYNAMIC_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": json_output},
                ]
            }

            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            success += 1
            sparse_tag = " [sparse]" if is_sparse and omit_fields else ""
            print(f"- OK ({len(parsed)}키{sparse_tag})")

            # Rate limiting
            if (i + 1) % 10 == 0:
                time.sleep(1)
                print(f"    --- {i+1}건 완료 (성공: {success}, 실패: {failed}) ---")

    print(f"\n  [{template}] 결과: 성공 {success}, 실패 {failed}")
    return success


def main():
    parser = argparse.ArgumentParser(description="v2_generate 합성 데이터 생성 (필드 풀 방식)")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR / "synthetic_generate.jsonl"))
    parser.add_argument("--template", type=str, choices=["meeting_minutes", "report", "proposal", "all"], default="all")
    parser.add_argument("--count", type=int, default=0, help="총 생성 수 (0=기본값 800)")
    parser.add_argument("--model", type=str, default="gpt-4o")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--append", action="store_true", help="기존 파일에 추가")
    parser.add_argument("--empty-field-ratio", type=float, default=0.3, help="빈 필드 비율 (0.0~1.0)")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 필드 조합 미리보기")
    args = parser.parse_args()

    if not args.dry_run and not os.getenv("OPENAI_API_KEY"):
        print("[오류] OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    # 템플릿별 목표 수 결정
    if args.count > 0 and args.template != "all":
        targets = {args.template: args.count}
    elif args.count > 0:
        ratio = args.count / 800
        targets = {k: max(1, int(v * ratio)) for k, v in TEMPLATE_TARGETS.items()}
    else:
        targets = dict(TEMPLATE_TARGETS)

    templates_to_run = (
        [args.template] if args.template != "all"
        else ["meeting_minutes", "report", "proposal"]
    )

    total_target = sum(targets.get(t, 0) for t in templates_to_run)

    print("=" * 70)
    print("  v2_generate 합성 데이터 생성 (필드 풀 랜덤 조합 방식)")
    print("=" * 70)
    print(f"  출력: {args.output}")
    print(f"  모델: {args.model}")
    print(f"  목표: {total_target}건")
    for t in templates_to_run:
        print(f"    {t}: {targets.get(t, 0)}건")
    print(f"  빈 필드 비율: {args.empty_field_ratio:.0%}")

    if args.dry_run:
        print(f"\n[DRY RUN] 필드 조합 미리보기:")
        rng = random.Random(args.seed)
        for tmpl in templates_to_run:
            count = targets.get(tmpl, 0)
            pool_info = FIELD_POOLS[tmpl]
            print(f"\n  [{tmpl}] ({count}건 예정)")
            print(f"    필수: {[f[0] for f in pool_info['core']]}")
            print(f"    메타 풀({len(pool_info['meta'])}): {[f[0] for f in pool_info['meta']]}")
            print(f"    내용 풀({len(pool_info['content'])}): {[f[0] for f in pool_info['content']]}")
            print(f"    샘플 필드 조합 5개:")
            for j in range(5):
                fields = select_random_fields(tmpl, rng)
                names = [f[0] for f in fields]
                print(f"      {j+1}. ({len(names)}필드) {names}")

        est_cost = total_target * 2 * 0.025
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
        field_count_dist = {}
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
                parsed = json.loads(assistant_content)
                json_valid += 1
                n_keys = len(parsed)
                field_count_dist[n_keys] = field_count_dist.get(n_keys, 0) + 1
            except json.JSONDecodeError:
                pass

        pct = json_valid / len(lines) * 100 if lines else 0
        print(f"  템플릿 분포: {template_dist}")
        print(f"  JSON 유효율: {json_valid}/{len(lines)} ({pct:.1f}%)")
        print(f"  필드 수 분포: {dict(sorted(field_count_dist.items()))}")

    print(f"\n  완료! 총 성공: {total_success}건")


if __name__ == "__main__":
    main()
