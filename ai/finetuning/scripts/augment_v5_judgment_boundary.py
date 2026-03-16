"""
Planner v5 데이터 보강 — judgment/doc_retrieve 경계 강화

v4 Held-out 오답 분석:
  1. judgment 단일인데 doc_retrieve로 오분류 (12건)
     - "규정 알려줘", "기준이 어떻게 돼?" → judgment인데 doc_retrieve로 분류
  2. 과잉 분리 (10건)
     - "육아휴직 중에 알바해도 되나요?" → [judgment] 인데 [doc_retrieve, judgment]으로 분리

보강 전략:
  A) judgment 단일 패턴 추가 (60건) — "규정" 키워드 있지만 judgment인 예제
  B) doc_retrieve 단일 패턴 추가 (30건) — 명확한 문서 검색 패턴 (대조군)
  C) 과잉 분리 방지 (30건) — 단일 judgment인데 2-step으로 쪼개면 안 되는 예제

사용법:
  cd /path/to/SKN21-FINAL-3TEAM
  python -m ai.finetuning.scripts.augment_v5_judgment_boundary
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
V4_TRAIN = ROOT / "data" / "training" / "v4_planner" / "train.jsonl"
V5_DIR = ROOT / "data" / "training" / "v5_planner"
V5_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """당신은 업무 자동화 시스템의 Task Planner입니다.
사용자 요청을 분석하여 실행 가능한 단계별 계획을 JSON으로 출력하세요.

## 사용 가능한 intent (6개)
- judgment: 사규/규정 기반 판단 ("~해도 되나요?", "규정 확인")
- doc_retrieve: 문서 검색/조회/요약 ("~문서 찾아줘", "~내용 알려줘")
- doc_generate: 문서 생성 ("보고서 만들어줘", "회의록 작성해줘")
- schedule_add: 일정 등록 ("~에 회의 잡아줘", "휴가 등록")
- schedule_view: 일정 조회 ("다음 주 일정 보여줘")
- general: 일반 질문 (위에 해당하지 않는 경우)

## judgment vs doc_retrieve 구분 기준
- judgment: 규정의 해석, 판단, 적용 여부, 가능/불가 판단, 기준 설명
  예: "연차 규정 알려줘", "출장비 기준이 어떻게 돼?", "이거 해도 돼?"
- doc_retrieve: 특정 문서/파일을 검색하거나 찾는 것
  예: "회의록 찾아줘", "매출 자료 검색해줘", "보고서 조회해줘"

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


def make_example(user_input, steps):
    """학습 데이터 1건 생성"""
    plan = {"plan": steps}
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": json.dumps(plan, ensure_ascii=False)},
        ]
    }


def make_single(user_input, intent):
    """단일 step 예제"""
    return make_example(user_input, [
        {"step_id": 1, "intent": intent, "query": user_input, "depends_on": []}
    ])


# ═══════════════════════════════════════════════════════════════
# A) judgment 단일 패턴 (60건)
#    핵심: "규정", "기준", "수당" 키워드가 있어도 judgment
# ═══════════════════════════════════════════════════════════════

JUDGMENT_SINGLE = [
    # 규정 해석/확인 패턴
    "연차 사용 규정 알려줘",
    "연차 규정이 어떻게 되지?",
    "연차 규정 확인해줘",
    "야근 수당 규정 알려줘",
    "야근 수당 몇 시부터 적용돼?",
    "출장비 정산 기준이 어떻게 돼?",
    "출장비 규정 알려줘",
    "재택근무 규정이 어떻게 되지?",
    "재택근무 주 몇 회까지 가능해?",
    "퇴직금 계산 기준 좀",
    "퇴직금 산정 기준 알려줘",
    "육아휴직 규정 알려줘",
    "육아휴직 중에 알바해도 되나요?",
    "점심시간에 외출해도 돼?",
    "지각하면 어떻게 되나요?",
    "결근하면 불이익이 있나요?",
    "병가 사용 기준이 뭐야?",
    "경조사 휴가 규정 확인해줘",
    "경조사 휴가 며칠이야?",
    "교육비 지원 규정 알려줘",
    "교육비 지원 가능한지 확인해줘",
    # 수당/급여 기준
    "시간외근무 수당 기준 알려줘",
    "휴일근무 수당 어떻게 계산해?",
    "통상임금 산정 기준이 뭐야?",
    "성과급 지급 기준 알려줘",
    "인센티브 지급 조건이 뭐야?",
    "상여금 지급 기준 확인해줘",
    "식대 지원 기준 알려줘",
    "교통비 지원 규정 확인해줘",
    "복리후생 어떤 거 있어?",
    # 가능/불가 판단
    "법인카드 사적 사용하면 어떻게 돼?",
    "법인카드로 회식비 결제 가능해?",
    "개인 노트북 사용해도 돼?",
    "외부 클라우드 서비스 사용 가능한가요?",
    "USB 사용 가능한지 확인해줘",
    "사내 와이파이로 개인 기기 연결해도 돼?",
    "회사 이메일로 개인 메일 보내도 되나요?",
    "근무 중 사적 전화 가능한가요?",
    # 징계/절차
    "징계 절차가 어떻게 되는지 알려줘",
    "무단결근 시 징계 기준이 뭐야?",
    "보안 위반 시 처벌 기준 알려줘",
    "사규 위반하면 어떤 처분을 받아?",
    # 비교/차이
    "연차 규정이랑 병가 규정 차이가 뭐야?",
    "정규직이랑 계약직 복지 차이 알려줘",
    "육아휴직이랑 출산휴가 기간 차이 알려줘",
    # 자연스러운 구어체
    "우리 회사 연차 어떻게 돼?",
    "야근 수당 받을 수 있어?",
    "출장 가면 일비 얼마야?",
    "해외 출장비 한도가 얼마인지 알려줘",
    "주말 출근하면 대체휴무 가능해?",
    "반차 사용 가능한가요?",
    "조퇴하면 급여에서 차감되나요?",
    "경조사비 얼마 나와?",
    "건강검진 휴가 인정되나?",
    "자기개발비 지원 가능한가요?",
    "사내 동호회 지원금 기준 알려줘",
    "학자금 지원 규정 확인해줘",
    "사우회 규정이 뭐야?",
    "복지포인트 사용 기준 알려줘",
    "명절 선물 지급 기준 확인해줘",
    "생일 휴가 규정 있어?",
]

# ═══════════════════════════════════════════════════════════════
# B) doc_retrieve 단일 패턴 (30건)
#    핵심: 문서/파일 자체를 "찾는" 것 (해석/판단 아님)
# ═══════════════════════════════════════════════════════════════

DOC_RETRIEVE_SINGLE = [
    "지난주 회의록 찾아줘",
    "3월 매출 보고서 검색해줘",
    "인사팀 공유 문서 찾아봐",
    "프로젝트 기획서 조회해줘",
    "거래처 계약서 찾아줘",
    "채용 공고 자료 검색해줘",
    "온보딩 가이드 어디서 볼 수 있어?",
    "경쟁사 분석 자료 찾아줘",
    "신입사원 교육 자료 검색",
    "제품 스펙 문서 찾아줘",
    "마케팅 전략 문서 조회해줘",
    "지난 분기 실적 보고서 찾아봐",
    "예산 계획서 검색해줘",
    "감사 보고서 찾아줘",
    "BOM 문서 검색해줘",
    "직원 핸드북 찾아줘",
    "출장 보고서 조회해줘",
    "영업 실적 자료 검색",
    "고객 분석 리포트 찾아줘",
    "디자인 가이드 문서 조회해줘",
    "기술 스택 문서 찾아봐",
    "보안 감사 보고서 검색해줘",
    "작년 연말 정산 자료 찾아줘",
    "팀 업무 분장표 조회해줘",
    "공급업체 평가 보고서 찾아줘",
    "회의 안건 자료 검색해줘",
    "프로젝트 일정표 찾아줘",
    "인수인계서 조회해줘",
    "품질 관리 매뉴얼 찾아줘",
    "내부 감사 결과 보고서 검색해줘",
]

# ═══════════════════════════════════════════════════════════════
# C) 과잉 분리 방지 — judgment 단일 (30건)
#    "규정 확인" + "~해도 돼?" 가 합쳐져 있지만 1-step judgment
# ═══════════════════════════════════════════════════════════════

ANTI_SPLIT_JUDGMENT = [
    "육아휴직 중에 부업해도 되나요?",
    "연차 당일 신청 가능한가요?",
    "출장 중 개인 일정 처리해도 돼?",
    "재택근무 중에 카페에서 일해도 되나요?",
    "수습 기간에 연차 사용 가능해?",
    "시용 기간 중 퇴사하면 불이익 있어?",
    "겸업 금지 규정에 유튜브도 포함돼?",
    "회사 장비를 집에 가져가도 되나요?",
    "근무 시간 중 병원 가도 되나요?",
    "연장 근로 거부할 수 있어?",
    "사내 메신저로 사적 대화해도 돼?",
    "회사 프린터로 개인 서류 출력해도 되나요?",
    "퇴근 후에도 보안 규정 적용되나요?",
    "경쟁사로 이직 가능한가요?",
    "인사 고과에 불만 있으면 이의 제기 가능해?",
    "휴가 중에 회사 업무 처리하면 수당 나와?",
    "출산휴가 후 바로 육아휴직 연결 가능해?",
    "배우자 출산휴가 며칠이야?",
    "군 복무 중 경력 인정되나요?",
    "파견 근무 시 원래 부서 복귀 보장돼?",
    "탄력 근무제 신청 가능한가요?",
    "시차 출퇴근제 사용 가능해?",
    "재택근무 시 초과근무 인정되나요?",
    "직급별 결재 한도가 얼마야?",
    "사유서 없이 지각 처리 가능한가요?",
    "개인정보 열람 요청 가능한가요?",
    "사내 고발 절차가 어떻게 되나요?",
    "노조 가입 가능한가요?",
    "사내 스터디 그룹 운영 가능해?",
    "이번 달 보고서 만들어줘",  # doc_generate 아닌 judgment로 오분류 방지용 대조
]

# 마지막 1건은 doc_generate 단일로 처리 (대조군)
ANTI_SPLIT_JUDGMENT_INTENTS = ["judgment"] * 29 + ["doc_generate"]


def main():
    # 기존 v4 데이터 로드
    with open(V4_TRAIN, "r", encoding="utf-8") as f:
        v4_data = [json.loads(line) for line in f]

    print(f"v4 train: {len(v4_data)}건")

    # 보강 데이터 생성
    augmented = []

    # A) judgment 단일
    for text in JUDGMENT_SINGLE:
        augmented.append(make_single(text, "judgment"))
    print(f"A) judgment 단일 추가: {len(JUDGMENT_SINGLE)}건")

    # B) doc_retrieve 단일
    for text in DOC_RETRIEVE_SINGLE:
        augmented.append(make_single(text, "doc_retrieve"))
    print(f"B) doc_retrieve 단일 추가: {len(DOC_RETRIEVE_SINGLE)}건")

    # C) 과잉 분리 방지
    for text, intent in zip(ANTI_SPLIT_JUDGMENT, ANTI_SPLIT_JUDGMENT_INTENTS):
        augmented.append(make_single(text, intent))
    print(f"C) 과잉 분리 방지 추가: {len(ANTI_SPLIT_JUDGMENT)}건")

    print(f"\n총 보강: {len(augmented)}건")

    # v4 + 보강 = v5
    v5_data = v4_data + augmented
    print(f"v5 train 최종: {len(v5_data)}건 (v4 {len(v4_data)} + 보강 {len(augmented)})")

    # 저장
    # v4 eval은 그대로 복사
    v4_eval = ROOT / "data" / "training" / "v4_planner" / "eval.jsonl"
    with open(v4_eval, "r", encoding="utf-8") as f:
        eval_data = [json.loads(line) for line in f]

    with open(V5_DIR / "train.jsonl", "w", encoding="utf-8") as f:
        for item in v5_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with open(V5_DIR / "eval.jsonl", "w", encoding="utf-8") as f:
        for item in eval_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\n저장 완료:")
    print(f"  {V5_DIR / 'train.jsonl'}: {len(v5_data)}건")
    print(f"  {V5_DIR / 'eval.jsonl'}: {len(eval_data)}건")

    # 통계
    j_count = 0
    d_count = 0
    for item in v5_data:
        asst = [m['content'] for m in item['messages'] if m['role'] == 'assistant'][0]
        try:
            plan = json.loads(asst)
            steps = plan.get('plan', [])
            intents = [s.get('intent', '') for s in steps]
            if intents == ['judgment']:
                j_count += 1
            elif intents == ['doc_retrieve']:
                d_count += 1
        except:
            pass

    print(f"\nv5 judgment 단일: {j_count}건 (v4: 46건)")
    print(f"v5 doc_retrieve 단일: {d_count}건 (v4: 57건)")


if __name__ == "__main__":
    main()
