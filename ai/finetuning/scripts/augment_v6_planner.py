"""
Planner v6 오답 타겟 보강 — GPT-4o로 약점 패턴 집중 생성

v5 Held-out 오답 분석:
  - 3-step Step Collapse (64.3%) → "~해서 ~하고 ~해줘" 패턴이 2-step으로 축소됨
  - complex (73.7%) → 접속사 3개 이상 복합 요청
  - edge_case (78.9%) → 비정형/구어체/초성/영어 혼용

생성 전략:
  1. Step Collapse 방지 데이터 30건 — "A해서 B하고 C해줘" 패턴, 반드시 3-step
  2. Complex 강화 15건 — 4가지 intent 조합 다양화
  3. Edge case 강화 10건 — 구어체/비정형 3-step
  4. Negative contrastive 5건 — "이건 2-step이 아니라 3-step" 교육

사용법:
  export OPENAI_API_KEY=sk-xxxxx
  python ai/finetuning/scripts/augment_v6_planner.py --count 60
  python ai/finetuning/scripts/augment_v6_planner.py --no-gpt  # 쿼리만 확인
"""

import argparse
import json
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
V5_TRAIN = ROOT / "data" / "training" / "v5_planner" / "train.jsonl"
V6_DIR = ROOT / "data" / "training" / "v6_planner"
V6_AUGMENT = V6_DIR / "augment_v6.jsonl"

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

## 절대 규칙
1. depends_on: 선행 step_id 목록. 비어있으면 즉시 실행 가능(병렬).
2. [금지 1 - 과도한 압축 금지]: 문서를 찾고(doc_retrieve) 그 내용을 바탕으로 판단(judgment)을 요구하면 절대 judgment 하나로 압축 금지. 두 단계 필요.
3. [금지 2 - Intent 혼동 방지]: 단순 검색은 doc_retrieve, judgment는 가부 판단만.
4. [금지 3 - 과잉 분리 금지]: 같은 대상 판단은 한 step으로.
5. 단순 요청 1단계, 최대 4단계.
6. JSON만 출력."""

# ── 1. Step Collapse 방지 템플릿 (3-step 필수) ──
TEMPLATES_COLLAPSE = [
    # doc_retrieve → judgment → doc_generate
    "{규정문서} 찾아서 {판단질문} 확인하고 {생성}",
    "{규정문서} 검색해서 {판단질문} 보고 {생성}",
    # doc_retrieve → doc_retrieve → doc_generate
    "{문서A} 찾고 {문서B}도 찾아서 {생성}",
    "{문서A} 검색하고 {문서B}도 조회해서 {생성}",
    # judgment → schedule_view → schedule_add
    "{규정} 확인하고 {일정확인} 봐서 {일정등록}",
    # schedule_view → doc_retrieve → schedule_add
    "{일정확인} 보고 {문서A} 찾아서 {일정등록}",
    # doc_retrieve → judgment → schedule_add
    "{규정문서} 찾아서 {판단질문} 확인하고 {일정등록}",
    # judgment → doc_retrieve → doc_generate
    "{규정} 확인하고 {문서A} 찾아서 {생성}",
]

# ── 2. Complex 강화 (다양한 intent 조합) ──
TEMPLATES_COMPLEX = [
    # 4-step
    "{규정문서} 찾아서 {판단질문} 확인하고 {생성} 그리고 {일정등록}",
    "{규정} 확인하고 {문서A} 검색해서 {생성} 그리고 {일정등록}도",
    # 3-step 새 조합
    "{일정확인} 확인하고 {문서A} 찾아서 {생성}",
    "{문서A} 찾아서 분석하고 {일정등록} 그리고 {생성}",
    "{규정} 확인하고 {규정문서} 찾아서 비교 {생성}",
]

# ── 3. Edge case (구어체/비정형 3-step) ──
TEMPLATES_EDGE = [
    "야 {규정문서} 좀 찾아보고 {판단질문} 되는지 봐서 {생성_구어}",
    "음 {문서A} 검색해주고 {문서B}도 같이 찾아서 {생성_구어}",
    "그 {규정} 있잖아 확인하고 빈 날 봐서 {일정등록}",
    "{규정문서} 찾아줘 그리고 {판단질문} 해도 되는지도 보고 {생성_구어}",
    "좀 급한데 {문서A} 찾고 {문서B} 검색해서 빨리 {생성_구어}",
]

SLOTS = {
    "규정": [
        "연차 규정", "출장비 규정", "재택근무 규정", "야근 수당 규정",
        "교육비 지원 규정", "복리후생 규정", "법인카드 규정", "보안 정책",
        "경조사 휴가 규정", "퇴직금 산정 기준", "인사 규정", "복장 규정",
        "채용 규정", "성과급 지급 기준", "외부 교육 지원 규정",
    ],
    "규정문서": [
        "출장비 규정 문서", "연차 관련 규정", "재택근무 내규",
        "법인카드 사용 기준", "보안 정책 문서", "교육비 규정",
        "복리후생 내규", "인사 규정 문서", "경조사 관련 규정",
    ],
    "판단질문": [
        "해외출장 가능한지", "신청 가능한지", "위반인지 아닌지",
        "지원받을 수 있는지", "사용 가능한지", "적용 가능한지",
        "문제 없는지", "가능 여부", "허용되는지",
    ],
    "문서A": [
        "프로젝트 기획서", "마케팅 보고서", "매출 데이터", "경쟁사 분석 자료",
        "거래처 계약서", "인수인계서", "감사 보고서", "고객사 요구사항",
        "예산 계획서", "실적 보고서", "분기 보고서", "회의록",
    ],
    "문서B": [
        "벤치마킹 자료", "시장 조사 보고서", "관련 데이터", "참고 문서",
        "이전 프로젝트 자료", "경쟁사 자료", "내부 분석 보고서",
    ],
    "생성": [
        "보고서 만들어줘", "제안서 작성해줘", "회의록 만들어줘",
        "기획서 초안 잡아줘", "JD 작성해줘", "비교 문서 작성해줘",
        "인수인계서 만들어줘", "분석 보고서 만들어줘",
    ],
    "생성_구어": [
        "보고서 뽑아줘", "제안서 좀 만들어", "회의록 써줘",
        "기획서 하나 만들어줘", "보고서 좀 작성해줘",
    ],
    "일정확인": [
        "이번 주 일정", "다음 주 일정", "이번 달 일정", "팀장 일정",
        "팀 스케줄", "이번 주 빈 날",
    ],
    "일정등록": [
        "미팅 잡아줘", "일정 등록해줘", "워크숍 넣어줘", "면담 잡아줘",
        "교육 일정 넣어줘", "회의 등록해줘", "일정 추가해줘",
    ],
}


def fill_template(template):
    """템플릿의 {슬롯}을 랜덤으로 채움"""
    result = template
    for slot_name, options in SLOTS.items():
        while "{" + slot_name + "}" in result:
            result = result.replace("{" + slot_name + "}", random.choice(options), 1)
    return result


def generate_queries(count):
    """카테고리별로 쿼리 생성"""
    queries = []
    seen = set()

    # 비율: collapse 50%, complex 25%, edge 25%
    n_collapse = int(count * 0.50)
    n_complex = int(count * 0.25)
    n_edge = count - n_collapse - n_complex

    def add_queries(templates, n, category):
        added = 0
        attempts = 0
        while added < n and attempts < n * 10:
            template = random.choice(templates)
            query = fill_template(template)
            attempts += 1
            if query not in seen:
                seen.add(query)
                queries.append({"query": query, "category": category})
                added += 1

    add_queries(TEMPLATES_COLLAPSE, n_collapse, "collapse_prevention")
    add_queries(TEMPLATES_COMPLEX, n_complex, "complex_augment")
    add_queries(TEMPLATES_EDGE, n_edge, "edge_augment")

    random.shuffle(queries)
    return queries


def generate_with_gpt(query, api_key):
    """GPT-4o-mini로 plan 생성"""
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


def validate_plan(plan_json, min_steps=3):
    """plan 품질 검증"""
    try:
        plan = json.loads(plan_json)
        steps = plan.get("plan", [])
        if len(steps) < min_steps:
            return False, f"{len(steps)}-step (need {min_steps}+)"

        valid_intents = {"judgment", "doc_retrieve", "doc_generate",
                         "schedule_add", "schedule_view", "general"}
        for s in steps:
            if s.get("intent") not in valid_intents:
                return False, f"invalid intent: {s.get('intent')}"
            if "query" not in s or not s["query"]:
                return False, "empty query"

        return True, f"{len(steps)}-step OK"
    except (json.JSONDecodeError, KeyError) as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(
        description="Planner v6 오답 타겟 보강 데이터 생성")
    parser.add_argument("--count", type=int, default=60,
                        help="생성할 데이터 수 (기본 60)")
    parser.add_argument("--no-gpt", action="store_true",
                        help="GPT 없이 쿼리만 출력")
    parser.add_argument("--merge", action="store_true",
                        help="v5 train에 합쳐서 v6 train 생성")
    args = parser.parse_args()

    random.seed(42)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key and not args.no_gpt:
        print("ERROR: OPENAI_API_KEY 환경변수 필요")
        print("  --no-gpt 로 쿼리만 확인 가능")
        return

    # 쿼리 생성
    query_items = generate_queries(args.count)
    print(f"\n쿼리 {len(query_items)}개 생성:")
    from collections import Counter
    cat_counts = Counter(q["category"] for q in query_items)
    for cat, cnt in cat_counts.most_common():
        print(f"  {cat}: {cnt}건")

    if args.no_gpt:
        print("\n[쿼리 샘플]")
        for i, item in enumerate(query_items[:10]):
            print(f"  [{i+1}] ({item['category']}) {item['query']}")
        print(f"\n--no-gpt 모드: 쿼리만 출력. GPT 생성은 OPENAI_API_KEY 설정 후 재실행.")
        return

    # GPT로 plan 생성
    V6_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    skipped = 0

    for i, item in enumerate(query_items, 1):
        query = item["query"]
        category = item["category"]
        min_steps = 3  # 모든 카테고리 최소 3-step

        try:
            plan_json = generate_with_gpt(query, api_key)
            valid, reason = validate_plan(plan_json, min_steps=min_steps)

            if valid:
                example = {
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": query},
                        {"role": "assistant", "content": plan_json},
                    ]
                }
                results.append(example)
                print(f"  [{i:3d}/{len(query_items)}] OK  ({reason}) [{category}] {query[:50]}")
            else:
                skipped += 1
                print(f"  [{i:3d}/{len(query_items)}] SKIP ({reason}) [{category}] {query[:50]}")
        except Exception as e:
            skipped += 1
            print(f"  [{i:3d}/{len(query_items)}] ERROR: {e}")

    # 저장
    print(f"\n결과: {len(results)}건 생성, {skipped}건 스킵")

    if results:
        with open(V6_AUGMENT, "w", encoding="utf-8") as f:
            for item in results:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"저장: {V6_AUGMENT}")

    # v5 + augment → v6 합치기
    if args.merge or True:  # 항상 합침
        if not V5_TRAIN.exists():
            print(f"WARNING: {V5_TRAIN} 없음 — 합치기 건너뜀")
            return

        with open(V5_TRAIN, "r", encoding="utf-8") as f:
            v5_data = [json.loads(l) for l in f if l.strip()]

        v6_data = v5_data + results
        random.shuffle(v6_data)

        # eval 분리 (5%)
        n_eval = max(10, int(len(v6_data) * 0.05))
        eval_data = v6_data[:n_eval]
        train_data = v6_data[n_eval:]

        V6_DIR.mkdir(parents=True, exist_ok=True)
        train_path = V6_DIR / "train.jsonl"
        eval_path = V6_DIR / "eval.jsonl"

        with open(train_path, "w", encoding="utf-8") as f:
            for item in train_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        with open(eval_path, "w", encoding="utf-8") as f:
            for item in eval_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        print(f"\nv6 데이터 생성 완료:")
        print(f"  train: {train_path} ({len(train_data)}건)")
        print(f"  eval:  {eval_path} ({n_eval}건)")
        print(f"  총합:  v5({len(v5_data)}) + augment({len(results)}) = {len(v6_data)}건")


if __name__ == "__main__":
    main()
