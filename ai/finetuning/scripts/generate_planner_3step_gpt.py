"""
GPT Knowledge Distillation — Planner 3-step+ 데이터 생성

GPT-4o-mini로 3-4단계 복합 쿼리의 정답 plan을 생성하여 학습 데이터 보강.
Step Collapse(3-step→2-step 축소) 방지가 목표.

사용법:
  export OPENAI_API_KEY=sk-xxxxx
  python -m ai.finetuning.scripts.generate_planner_3step_gpt --count 100
"""

import argparse
import json
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
V5_TRAIN = ROOT / "data" / "training" / "v5_planner" / "train.jsonl"
OUTPUT = ROOT / "data" / "training" / "v5_planner" / "gpt_3step.jsonl"

SYSTEM_PROMPT = """당신은 업무 자동화 시스템의 Task Planner입니다.
사용자 요청을 분석하여 실행 가능한 단계별 계획을 JSON으로 출력하세요.

## 사용 가능한 intent (6개)
- judgment: 사규/규정 기반 판단 ("~해도 되나요?", "규정 확인", "규정 알려줘", "기준이 어떻게 돼?")
- doc_retrieve: 문서 검색/조회/요약 ("~문서 찾아줘", "~자료 검색", "회의록 조회")
- doc_generate: 문서 생성 ("보고서 만들어줘", "회의록 작성해줘")
- schedule_add: 일정 등록 ("~에 회의 잡아줘", "휴가 등록")
- schedule_view: 일정 조회 ("다음 주 일정 보여줘")
- general: 일반 질문 (위에 해당하지 않는 경우)

## judgment vs doc_retrieve 구분 기준 (중요!)
- judgment: 사내 규정/규칙/기준/수당/복리후생에 대한 질문. 규정 해석, 가능 여부 판단, 기준 설명 포함.
- doc_retrieve: 특정 문서/파일/보고서/회의록을 찾거나 검색하는 것.

## 출력 형식
{"plan": [{"step_id": 1, "intent": "intent_name", "query": "구체적 요청", "depends_on": []}]}

## 규칙
1. depends_on: 선행 step_id 목록
2. 단순 요청은 1단계, 최대 4단계
3. JSON만 출력"""

# 3-step 복합 쿼리 템플릿
TEMPLATES_3STEP = [
    "{규정} 확인하고 {문서} 찾아서 {생성}",
    "{문서} 찾아서 {분석} 정리하고 {생성}",
    "{규정} 확인하고 가능하면 {일정} 잡아줘, {생성}도",
    "{일정확인} 보고 {규정} 확인하고 {일정등록}",
    "{문서} 검색해서 {요약} 정리하고 {일정등록}",
    "{규정} 확인하고 {문서} 찾아서 {일정등록}",
    "{문서} 찾아서 {규정} 확인하고 {생성}",
    "{일정확인} 보고 비는 날 찾아서 {일정등록}",
]

SLOTS = {
    "규정": [
        "연차 규정", "출장비 규정", "재택근무 규정", "야근 수당 규정",
        "교육비 지원 규정", "복리후생 규정", "법인카드 규정", "보안 정책",
        "경조사 휴가 규정", "퇴직금 산정 기준", "인사 규정", "복장 규정",
    ],
    "문서": [
        "프로젝트 기획서", "마케팅 보고서", "매출 데이터", "경쟁사 분석 자료",
        "거래처 계약서", "인수인계서", "감사 보고서", "BOM 문서",
        "고객사 요구사항", "예산 계획서", "실적 보고서", "회의록",
    ],
    "생성": [
        "보고서 만들어줘", "제안서 작성해줘", "회의록 만들어줘", "기획서 초안 잡아줘",
        "JD 작성해줘", "인수인계서 만들어줘", "발표 자료 만들어줘", "비교 문서 작성해줘",
    ],
    "분석": [
        "핵심 내용", "요약", "주요 수치", "진행 상황", "변경사항",
    ],
    "요약": [
        "요약해주고", "핵심만 뽑아서", "정리해서", "분석하고",
    ],
    "일정": [
        "팀 미팅", "고객 미팅", "교육 일정", "워크숍", "면담",
    ],
    "일정확인": [
        "이번 주 일정", "다음 주 일정", "이번 달 일정", "팀장 일정",
    ],
    "일정등록": [
        "미팅 잡아줘", "일정 등록해줘", "워크숍 넣어줘", "면담 잡아줘",
        "교육 일정 넣어줘", "회의 등록해줘",
    ],
}


def fill_template(template):
    """템플릿의 {슬롯}을 랜덤으로 채움"""
    result = template
    for slot_name, options in SLOTS.items():
        if "{" + slot_name + "}" in result:
            result = result.replace("{" + slot_name + "}", random.choice(options), 1)
    return result


def generate_with_gpt(query, api_key):
    """GPT로 plan 생성"""
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    return response.choices[0].message.content


def make_example(query, plan_json):
    """학습 데이터 형식으로 변환"""
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
            {"role": "assistant", "content": plan_json},
        ]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100, help="생성할 데이터 수")
    parser.add_argument("--no-gpt", action="store_true", help="GPT 없이 템플릿만 생성")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key and not args.no_gpt:
        print("OPENAI_API_KEY 환경변수 필요. --no-gpt로 템플릿만 생성 가능.")
        return

    queries = []
    seen = set()
    while len(queries) < args.count:
        template = random.choice(TEMPLATES_3STEP)
        query = fill_template(template)
        if query not in seen:
            seen.add(query)
            queries.append(query)

    print(f"3-step 쿼리 {len(queries)}개 생성")

    results = []
    for i, query in enumerate(queries):
        if args.no_gpt:
            print(f"  [{i+1}/{len(queries)}] {query}")
            continue

        try:
            plan_json = generate_with_gpt(query, api_key)
            # 검증: 3-step 이상인지
            plan = json.loads(plan_json)
            steps = plan.get("plan", [])
            if len(steps) >= 3:
                results.append(make_example(query, plan_json))
                print(f"  [{i+1}] OK ({len(steps)}-step): {query[:50]}")
            else:
                print(f"  [{i+1}] SKIP ({len(steps)}-step): {query[:50]}")
        except Exception as e:
            print(f"  [{i+1}] ERROR: {e}")

    if results:
        with open(OUTPUT, "w", encoding="utf-8") as f:
            for item in results:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"\n저장: {OUTPUT} ({len(results)}건)")

        # v5 train에 합치기
        with open(V5_TRAIN, "r", encoding="utf-8") as f:
            v5_data = [json.loads(l) for l in f]
        v5_data.extend(results)
        with open(V5_TRAIN, "w", encoding="utf-8") as f:
            for item in v5_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"v5 train 업데이트: {len(v5_data)}건 (기존 + {len(results)}건)")
    elif args.no_gpt:
        print("\n--no-gpt 모드: 쿼리만 출력. GPT 생성은 OPENAI_API_KEY 설정 후 재실행.")


if __name__ == "__main__":
    main()
