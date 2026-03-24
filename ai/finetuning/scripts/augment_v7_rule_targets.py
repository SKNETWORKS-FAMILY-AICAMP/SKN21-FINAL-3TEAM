"""
Planner v7 Rule-Target 보강 — Rule Guide 의존 패턴을 학습 데이터로 전환

목적: eval_planner_holdout.py의 후처리 rule에 의존하는 오류 패턴을
      학습 데이터에 직접 포함시켜 rule 없이도 모델이 올바르게 출력하도록 함.

타겟 Rule:
  Rule 14: 시간표현 + 문서생성 → doc_generate (30건)
  Rule 3:  영어 혼용 + 문서생성 → doc_generate (10건)
  Rule 4:  "도와줘" 단독 → general (10건)
  Rule 6,8: 취소/변경/수정 + 일정 → schedule_add (15건)
  Rule 9:  멀티스텝 마지막 doc_generate 강화 (10건)
  Rule 16: "A랑 B 둘 다" → 2-step parallel (10건)
  Rule 2:  초단문 → general (5건)

사용법:
  python ai/finetuning/scripts/augment_v7_rule_targets.py
  python ai/finetuning/scripts/augment_v7_rule_targets.py --merge  # v5 train에 합치기
  python ai/finetuning/scripts/augment_v7_rule_targets.py --dry-run  # 미리보기만
"""

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
V5_TRAIN = ROOT / "data" / "training" / "v5_planner" / "train.jsonl"
V7_DIR = ROOT / "data" / "training" / "v7_planner"

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
  예: "연차 규정 알려줘", "출장비 기준이 어떻게 돼?", "야근 수당 몇 시부터?", "이거 해도 돼?"
- doc_retrieve: 특정 문서/파일/보고서/회의록을 찾거나 검색하는 것.
  예: "회의록 찾아줘", "매출 보고서 검색", "기획서 조회해줘"
- 핵심 차이: 규정/수당/복리후생 관련 = judgment, 문서/파일/보고서/자료 검색 = doc_retrieve

## 출력 형식 (반드시 이 JSON 형식만 출력)
{
  "plan": [
    {
      "step_id": 1,
      "intent": "intent_name",
      "query": "이 단계에서 처리할 구체적 요청",
      "depends_on": []
    }
  ]
}

## 규칙
1. depends_on: 이 단계가 실행되기 전에 완료되어야 하는 step_id 목록
2. depends_on이 비어있으면 즉시 실행 가능 (병렬 처리 가능)
3. 단순 요청은 1단계로 처리
4. 최대 4단계까지만 분해
5. JSON만 출력하고 다른 설명은 하지 마세요"""


def make_example(user_input: str, plan: list[dict]) -> dict:
    """학습 데이터 1건 생성"""
    plan_json = json.dumps({"plan": plan}, ensure_ascii=False)
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": plan_json},
        ]
    }


def step(step_id: int, intent: str, query: str, depends_on: list[int] = None) -> dict:
    return {
        "step_id": step_id,
        "intent": intent,
        "query": query,
        "depends_on": depends_on or [],
    }


# ═══════════════════════════════════════════════════════════════
# Rule 14: 시간표현 + 문서생성 → doc_generate (schedule_view 아님!)
# ═══════════════════════════════════════════════════════════════
def gen_rule14_time_doc_generate():
    time_exprs = [
        "이번 달", "저번 달", "지난달", "다음 달", "이번 주", "저번 주",
        "지난주", "다음 주", "이번 분기", "저번 분기", "지난 분기",
        "다음 분기", "올해", "작년", "내년", "상반기", "하반기",
        "1월", "2월", "3월", "4분기", "금주", "전월", "당월",
    ]
    doc_types = [
        "보고서", "회의록", "제안서", "기획서", "JD", "인수인계서",
        "분석 보고서", "실적 보고서", "월간 보고서", "주간 보고서",
        "프로젝트 제안서", "마케팅 기획서", "예산 보고서",
    ]
    verbs = [
        "만들어줘", "작성해줘", "써줘", "뽑아줘", "생성해줘",
        "작성해주세요", "만들어주세요",
    ]

    examples = []
    seen = set()
    random.shuffle(time_exprs)
    random.shuffle(doc_types)

    for _ in range(30):
        t = random.choice(time_exprs)
        d = random.choice(doc_types)
        v = random.choice(verbs)
        query = f"{t} {d} {v}"
        if query in seen:
            continue
        seen.add(query)
        examples.append(make_example(
            query,
            [step(1, "doc_generate", query)],
        ))
    return examples


# ═══════════════════════════════════════════════════════════════
# Rule 3: 영어 혼용 + 문서생성 → doc_generate
# ═══════════════════════════════════════════════════════════════
def gen_rule3_english_doc():
    patterns = [
        ("meeting minutes 작성해줘", "meeting minutes 작성"),
        ("weekly report 만들어줘", "weekly report 생성"),
        ("monthly report 작성해주세요", "monthly report 작성"),
        ("project proposal 만들어줘", "project proposal 생성"),
        ("minutes 정리해줘", "minutes 정리 및 작성"),
        ("status report 뽑아줘", "status report 작성"),
        ("팀 weekly report 써줘", "팀 weekly report 작성"),
        ("QBR report 만들어줘", "QBR report 생성"),
        ("sprint retrospective 회의록 만들어줘", "sprint retrospective 회의록 작성"),
        ("daily standup minutes 작성해줘", "daily standup minutes 작성"),
    ]
    return [
        make_example(q, [step(1, "doc_generate", s)])
        for q, s in patterns
    ]


# ═══════════════════════════════════════════════════════════════
# Rule 4: "도와줘/도움" 단독 (구체적 동사 없음) → general
# ═══════════════════════════════════════════════════════════════
def gen_rule4_ambiguous_help():
    patterns = [
        "도와줘",
        "좀 도와줘",
        "도움이 필요해",
        "도와주세요",
        "도움 좀",
        "업무 관련 도움 좀",
        "회의 관련해서 좀 도와줘",
        "보고서 관련 도움 필요해",
        "일정 관련 도와줘",
        "헬프",
    ]
    return [
        make_example(q, [step(1, "general", q)])
        for q in patterns
    ]


# ═══════════════════════════════════════════════════════════════
# Rule 6, 8: 취소/변경/수정 + 일정 → schedule_add (schedule_view 아님!)
# ═══════════════════════════════════════════════════════════════
def gen_rule6_8_schedule_modify():
    patterns = [
        ("내일 회의 취소해줘", "내일 회의 취소"),
        ("오후 미팅 취소해주세요", "오후 미팅 취소"),
        ("금요일 면접 일정 취소해줘", "금요일 면접 일정 취소"),
        ("회의 시간 변경해줘", "회의 시간 변경"),
        ("내일 미팅 3시로 변경해줘", "내일 미팅 3시로 변경"),
        ("월요일 회의 시간 수정해줘", "월요일 회의 시간 수정"),
        ("다음 주 워크숍 일정 변경해주세요", "다음 주 워크숍 일정 변경"),
        ("팀 미팅 취소하고 싶어", "팀 미팅 취소"),
        ("수요일 스케줄 변경해줘", "수요일 스케줄 변경"),
        ("오늘 일정 수정 좀", "오늘 일정 수정"),
        ("점심 미팅 취소", "점심 미팅 취소"),
        ("내일 면담 시간 변경해줘", "내일 면담 시간 변경"),
        ("화요일 회의 2시에서 4시로 변경", "화요일 회의 시간 변경"),
        ("이번 주 교육 일정 취소해줘", "이번 주 교육 일정 취소"),
        ("프로젝트 미팅 시간 수정해주세요", "프로젝트 미팅 시간 수정"),
    ]
    return [
        make_example(q, [step(1, "schedule_add", s)])
        for q, s in patterns
    ]


# ═══════════════════════════════════════════════════════════════
# Rule 9: 멀티스텝에서 마지막 step이 doc_generate여야 하는 패턴
# ═══════════════════════════════════════════════════════════════
def gen_rule9_multistep_last_docgen():
    patterns = [
        (
            "매출 자료 찾아서 분석 보고서 만들어줘",
            [step(1, "doc_retrieve", "매출 자료 검색"),
             step(2, "doc_generate", "분석 보고서 작성", [1])],
        ),
        (
            "경쟁사 자료 검색하고 비교 제안서 작성해줘",
            [step(1, "doc_retrieve", "경쟁사 자료 검색"),
             step(2, "doc_generate", "비교 제안서 작성", [1])],
        ),
        (
            "프로젝트 기획서 찾아서 회의록 만들어줘",
            [step(1, "doc_retrieve", "프로젝트 기획서 검색"),
             step(2, "doc_generate", "회의록 작성", [1])],
        ),
        (
            "이전 보고서 조회하고 이번 달 보고서 써줘",
            [step(1, "doc_retrieve", "이전 보고서 조회"),
             step(2, "doc_generate", "이번 달 보고서 작성", [1])],
        ),
        (
            "고객사 요구사항 찾아서 제안서 뽑아줘",
            [step(1, "doc_retrieve", "고객사 요구사항 검색"),
             step(2, "doc_generate", "제안서 작성", [1])],
        ),
        (
            "지난 회의록 검색해서 후속 보고서 만들어줘",
            [step(1, "doc_retrieve", "지난 회의록 검색"),
             step(2, "doc_generate", "후속 보고서 작성", [1])],
        ),
        (
            "예산 계획서 찾고 분기 보고서 작성해줘",
            [step(1, "doc_retrieve", "예산 계획서 검색"),
             step(2, "doc_generate", "분기 보고서 작성", [1])],
        ),
        (
            "인수인계서 조회해서 업무 매뉴얼 만들어줘",
            [step(1, "doc_retrieve", "인수인계서 조회"),
             step(2, "doc_generate", "업무 매뉴얼 작성", [1])],
        ),
        (
            "시장 조사 보고서 찾아서 마케팅 기획서 작성해줘",
            [step(1, "doc_retrieve", "시장 조사 보고서 검색"),
             step(2, "doc_generate", "마케팅 기획서 작성", [1])],
        ),
        (
            "감사 보고서 검색하고 개선 제안서 만들어줘",
            [step(1, "doc_retrieve", "감사 보고서 검색"),
             step(2, "doc_generate", "개선 제안서 작성", [1])],
        ),
    ]
    return [make_example(q, p) for q, p in patterns]


# ═══════════════════════════════════════════════════════════════
# Rule 16: "A랑 B 둘 다 찾아줘" → 2-step parallel
# ═══════════════════════════════════════════════════════════════
def gen_rule16_parallel_retrieve():
    patterns = [
        (
            "마케팅 보고서랑 인사 규정 둘 다 찾아줘",
            [step(1, "doc_retrieve", "마케팅 보고서 검색"),
             step(2, "doc_retrieve", "인사 규정 검색")],
        ),
        (
            "매출 자료하고 경쟁사 분석 둘 다 검색해줘",
            [step(1, "doc_retrieve", "매출 자료 검색"),
             step(2, "doc_retrieve", "경쟁사 분석 검색")],
        ),
        (
            "프로젝트 기획서랑 예산 계획서 각각 찾아줘",
            [step(1, "doc_retrieve", "프로젝트 기획서 검색"),
             step(2, "doc_retrieve", "예산 계획서 검색")],
        ),
        (
            "회의록이랑 출장 보고서 같이 찾아줘",
            [step(1, "doc_retrieve", "회의록 검색"),
             step(2, "doc_retrieve", "출장 보고서 검색")],
        ),
        (
            "인수인계서하고 업무 매뉴얼 둘 다 조회해줘",
            [step(1, "doc_retrieve", "인수인계서 조회"),
             step(2, "doc_retrieve", "업무 매뉴얼 조회")],
        ),
        (
            "거래처 계약서랑 견적서 함께 검색해줘",
            [step(1, "doc_retrieve", "거래처 계약서 검색"),
             step(2, "doc_retrieve", "견적서 검색")],
        ),
        (
            "분기 실적이랑 연간 보고서 각각 찾아줘",
            [step(1, "doc_retrieve", "분기 실적 검색"),
             step(2, "doc_retrieve", "연간 보고서 검색")],
        ),
        (
            "교육 자료하고 온보딩 가이드 둘 다 찾아줘",
            [step(1, "doc_retrieve", "교육 자료 검색"),
             step(2, "doc_retrieve", "온보딩 가이드 검색")],
        ),
        (
            "채용 공고랑 JD 둘 다 검색해줘",
            [step(1, "doc_retrieve", "채용 공고 검색"),
             step(2, "doc_retrieve", "JD 검색")],
        ),
        (
            "감사 보고서이랑 리스크 분석 자료 같이 찾아줘",
            [step(1, "doc_retrieve", "감사 보고서 검색"),
             step(2, "doc_retrieve", "리스크 분석 자료 검색")],
        ),
    ]
    return [make_example(q, p) for q, p in patterns]


# ═══════════════════════════════════════════════════════════════
# Rule 2: 초단문 (≤3글자) → general
# ═══════════════════════════════════════════════════════════════
def gen_rule2_ultra_short():
    patterns = [
        "ㅎㅇ",
        "ㄱㄱ",
        "ㅇㅇ",
        "뭐",
        "음",
    ]
    return [
        make_example(q, [step(1, "general", q)])
        for q in patterns
    ]


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Planner v7 Rule-Target 보강 데이터 생성")
    parser.add_argument("--merge", action="store_true",
                        help="v5 train에 합쳐서 v7 train/eval 생성")
    parser.add_argument("--dry-run", action="store_true",
                        help="데이터 미리보기만 (파일 저장 안 함)")
    parser.add_argument("--seed", type=int, default=42,
                        help="랜덤 시드 (기본 42)")
    args = parser.parse_args()

    random.seed(args.seed)

    # 각 Rule별 데이터 생성
    generators = {
        "rule14_time_docgen": gen_rule14_time_doc_generate,
        "rule3_english_doc": gen_rule3_english_doc,
        "rule4_ambiguous_help": gen_rule4_ambiguous_help,
        "rule6_8_schedule_modify": gen_rule6_8_schedule_modify,
        "rule9_multistep_docgen": gen_rule9_multistep_last_docgen,
        "rule16_parallel_retrieve": gen_rule16_parallel_retrieve,
        "rule2_ultra_short": gen_rule2_ultra_short,
    }

    all_examples = []
    print("=" * 50)
    print(" Planner v7 Rule-Target 보강 데이터 생성")
    print("=" * 50)

    for name, gen_fn in generators.items():
        examples = gen_fn()
        all_examples.extend(examples)
        print(f"  {name}: {len(examples)}건")

    print(f"\n  총 보강 데이터: {len(all_examples)}건")

    if args.dry_run:
        print("\n[미리보기 — Rule별 샘플]")
        for name, gen_fn in generators.items():
            examples = gen_fn()
            if examples:
                user_msg = examples[0]["messages"][1]["content"]
                asst_msg = examples[0]["messages"][2]["content"]
                plan = json.loads(asst_msg)
                intents = [s["intent"] for s in plan["plan"]]
                print(f"\n  [{name}]")
                print(f"    input: {user_msg}")
                print(f"    → {intents}")
        return

    # 파일 저장
    V7_DIR.mkdir(parents=True, exist_ok=True)
    augment_path = V7_DIR / "augment_v7_rule_targets.jsonl"

    with open(augment_path, "w", encoding="utf-8") as f:
        for item in all_examples:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"\n  저장: {augment_path}")

    # v5 + augment → v7 합치기
    if args.merge:
        if not V5_TRAIN.exists():
            print(f"  WARNING: {V5_TRAIN} 없음 — 합치기 건너뜀")
            return

        with open(V5_TRAIN, "r", encoding="utf-8") as f:
            v5_data = [json.loads(line) for line in f if line.strip()]

        v7_data = v5_data + all_examples
        random.shuffle(v7_data)

        # eval 분리 (5%)
        n_eval = max(10, int(len(v7_data) * 0.05))
        eval_data = v7_data[:n_eval]
        train_data = v7_data[n_eval:]

        train_path = V7_DIR / "train.jsonl"
        eval_path = V7_DIR / "eval.jsonl"

        with open(train_path, "w", encoding="utf-8") as f:
            for item in train_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        with open(eval_path, "w", encoding="utf-8") as f:
            for item in eval_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        print(f"\n  v7 데이터 생성 완료:")
        print(f"    train: {train_path} ({len(train_data)}건)")
        print(f"    eval:  {eval_path} ({n_eval}건)")
        print(f"    총합:  v5({len(v5_data)}) + augment({len(all_examples)}) = {len(v7_data)}건")
    else:
        print(f"\n  --merge 옵션으로 v5 train과 합칠 수 있습니다.")


if __name__ == "__main__":
    main()
