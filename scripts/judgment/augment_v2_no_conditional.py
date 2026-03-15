"""
v2 데이터 보강 스크립트 — no/conditional 경계 케이스 강화

v1 LoRA 평가 결과 분석:
  - no: 82.0% (50/61) ← 최약
  - conditional: 84.0% (84/100)
  - yes: 85.0%, no_regulation: 97.0%

혼동 원인:
  1. "금지, 단 예외 있음" → no로 라벨링되어야 하는데 conditional로 오분류
  2. "승인 없이" 명시 → no, "해도 돼?" 열린 질문 → conditional 구분 미흡
  3. conditional 카테고리의 inherent ambiguity (confidence 평균 0.845)

보강 전략:
  A. no 강화 (120건): "승인 없이", "허가 없이", "무단으로" 등 명시적 금지 패턴
  B. no vs conditional 경계 (80건): 동일 규정에서 질문 프레이밍만 달라 라벨이 다른 쌍
  C. conditional 명확화 (50건): 조건이 명확한 conditional 케이스

총 250건 생성 → train.jsonl에 병합

사용법:
    python scripts/augment_v2_no_conditional.py

환경변수:
    OPENAI_API_KEY — OpenAI API 키 필요
"""

import json
import os
import random
import sys
import time
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("openai 패키지가 필요합니다: pip install openai")
    sys.exit(1)

random.seed(2026)

# ── Config ──
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "v1_judgment"
TRAIN_PATH = DATA_DIR / "train.jsonl"
EVAL_PATH = DATA_DIR / "eval.jsonl"
OUTPUT_PATH = DATA_DIR / "augment_v2_no_conditional.jsonl"
BACKUP_TRAIN = DATA_DIR / "backup" / "train_before_v2_augment.jsonl"
BACKUP_EVAL = DATA_DIR / "backup" / "eval_before_v2_augment.jsonl"
REG_DIR = BASE_DIR / "data" / "regulations"

# ── 시스템 프롬프트 (프로덕션과 동일) ──
JUDGMENT_SYSTEM_PROMPT = """\
당신은 기업 내부 규정 판단 전문가입니다.
주어진 규정 문서를 기반으로 사용자의 질문에 대해 정확한 판단을 내려야 합니다.

판단 결과는 반드시 아래 JSON 형식으로만 응답하세요:
{
    "result": "yes" | "no" | "conditional" | "no_regulation",
    "confidence": 0.0~1.0,
    "reasoning": "판단 근거를 상세히 설명",
    "regulations": [
        {"article": "규정 조항명", "relevance": "높음|중간|낮음", "content": "관련 내용 요약"}
    ],
    "cross_references": [
        {"articles": ["조항A", "조항B"], "relationship": "보완|충돌|상위규정", "detail": "관계 설명"}
    ],
    "conditions": "조건부(conditional)일 경우 조건 설명, 아니면 null",
    "alternatives": ["대안이 있다면 제시"]
}

규칙:
- 반드시 제공된 규정 문서만을 근거로 판단하세요.
- 규정에 명시되지 않은 내용은 "no_regulation"으로 판단하세요.
- 조건부 허용인 경우 conditions 필드에 조건을 명확히 기술하세요.
- 여러 규정이 관련된 경우 반드시 교차 분석하세요.
- confidence는 다음 기준으로 산정하세요:
  - 0.9~1.0: 명확한 규정 조항이 직접 적용됨
  - 0.7~0.9: 규정이 존재하나 해석이 필요함
  - 0.5~0.7: 관련 규정은 있으나 직접 적용이 어려움
  - 0.5 미만: 관련 규정을 찾기 어려움
- JSON 외의 텍스트를 포함하지 마세요."""

# ── 이름/직급/부서 풀 ──
NAMES = [
    "김민수", "이지현", "박서준", "최유진", "정하늘", "오태영", "서지안", "장동혁",
    "윤채원", "배수지", "송미래", "한도윤", "임세진", "강나은", "조예린", "신지호",
    "황서연", "류민재", "문하영", "고승현", "남지우", "전서윤", "백도현", "구혜린",
    "양준호", "권수빈", "유하진", "홍세영", "손태희", "노현수", "허지민", "우성훈",
]
TITLES = ["사원", "대리", "과장", "차장", "부장"]
TEAMS = [
    "개발팀", "인사팀", "보안팀", "디자인팀", "QA팀", "마케팅팀", "영업팀",
    "재무팀", "기획팀", "운영팀", "데이터팀", "인프라팀", "경영지원팀", "법무팀",
]


def rand_person():
    return f"{random.choice(NAMES)}({random.choice(TITLES)}, {random.choice(TEAMS)})"


# ── 규정 파일 로드 ──
def load_regulations():
    """규정 txt 파일들을 로드하여 {규정명: 전체텍스트} 반환"""
    regs = {}
    for f in sorted(REG_DIR.glob("*.txt")):
        name = f.stem.split("_")[0]  # "급여규정_NC-HR-2026-002" → "급여규정"
        regs[name] = f.read_text(encoding="utf-8")
    return regs


def extract_articles(reg_text, max_articles=3):
    """규정 텍스트에서 랜덤 조항 N개 추출"""
    import re
    articles = re.split(r"(?=제\d+조)", reg_text)
    articles = [a.strip() for a in articles if a.strip() and "제" in a[:5]]
    if not articles:
        return reg_text[:500]
    selected = random.sample(articles, min(max_articles, len(articles)))
    return "\n\n".join(selected)


# ── 시나리오 정의 ──

# A. "no" 강화 시나리오: 명시적 금지/불허 질문
NO_SCENARIOS = [
    # "승인 없이" 패턴
    {"reg": "IT보안규정", "q_template": "{person}이(가) CISO 승인 없이 {action}. 가능한가요?",
     "actions": ["공용 계정을 팀원끼리 공유해서 사용하려 합니다", "외부 클라우드에 업무 데이터를 저장하려 합니다",
                 "개인 USB를 사무실 PC에 연결하려 합니다", "회사 서버에서 외부 웹사이트에 직접 접속하려 합니다",
                 "보안 감사 로그를 임의로 삭제하려 합니다"]},
    {"reg": "인사규정", "q_template": "{person}이(가) 부서장 승인 없이 {action}. 허용되나요?",
     "actions": ["재택근무를 하려 합니다", "연장근로를 하려 합니다", "연차를 사용하려 합니다",
                 "교대근무 스케줄을 변경하려 합니다"]},
    {"reg": "출장규정", "q_template": "{person}이(가) 사전 승인 없이 {action}. 가능한가요?",
     "actions": ["출장을 다녀왔습니다", "출장 경비를 선지급 받으려 합니다",
                 "해외출장을 계획하고 있습니다", "출장지에서 일정을 변경하려 합니다"]},
    {"reg": "윤리강령", "q_template": "{person}이(가) 회사 허가 없이 {action}. 가능한가요?",
     "actions": ["경쟁사에서 겸직하려 합니다", "거래처로부터 50만원 상당의 선물을 받았습니다",
                 "회사 기밀 정보를 외부 세미나에서 발표하려 합니다",
                 "사내 정보를 개인 SNS에 공유하려 합니다"]},
    {"reg": "개인정보처리규정", "q_template": "{person}이(가) 정보주체 동의 없이 {action}. 가능한가요?",
     "actions": ["고객 개인정보를 마케팅에 활용하려 합니다", "직원 건강검진 결과를 부서장에게 공유하려 합니다",
                 "퇴직한 직원의 개인정보를 계속 보관하려 합니다"]},
    {"reg": "징계규정", "q_template": "{person}이(가) {action}. 징계 대상인가요?",
     "actions": ["허위 출장보고서를 제출했습니다", "회사 기밀을 경쟁사에 유출했습니다",
                 "직장 내 괴롭힘을 했습니다", "음주운전으로 형사처벌을 받았습니다"]},
    # "무단으로" 패턴
    {"reg": "IT보안규정", "q_template": "{person}이(가) 무단으로 {action}. 문제가 되나요?",
     "actions": ["운영 DB에 직접 접속했습니다", "P2P 프로그램을 설치했습니다",
                 "개발 환경에서 실제 고객 데이터를 사용했습니다",
                 "방화벽 규칙을 변경했습니다"]},
]

# B. no vs conditional 경계 쌍: 동일 규정, 질문만 다름
BOUNDARY_PAIRS = [
    {"reg": "IT보안규정",
     "no_q": "{person}이(가) 승인 없이 공용 계정을 사용하고 있습니다. 허용되나요?",
     "cond_q": "{person}이(가) 공용 계정을 사용해야 하는 상황입니다. 어떤 절차를 거쳐야 하나요?"},
    {"reg": "IT보안규정",
     "no_q": "{person}이(가) 허가 없이 개인 노트북을 사내 네트워크에 연결했습니다. 괜찮나요?",
     "cond_q": "{person}이(가) 개인 노트북을 업무에 사용하고 싶습니다. 가능한가요?"},
    {"reg": "윤리강령",
     "no_q": "{person}이(가) 회사 몰래 경쟁사에서 아르바이트를 하고 있습니다. 문제가 되나요?",
     "cond_q": "{person}이(가) 퇴근 후 프리랜서 활동을 하고 싶습니다. 가능한가요?"},
    {"reg": "출장규정",
     "no_q": "{person}이(가) 출장 보고서를 제출하지 않고 경비를 청구하려 합니다. 가능한가요?",
     "cond_q": "{person}이(가) 긴급 출장을 다녀왔는데, 사후에 승인을 받을 수 있나요?"},
    {"reg": "인사규정",
     "no_q": "{person}이(가) 부서장에게 알리지 않고 재택근무를 했습니다. 문제가 되나요?",
     "cond_q": "{person}이(가) 건강 사유로 재택근무를 신청하려 합니다. 가능한가요?"},
    {"reg": "교육훈련규정",
     "no_q": "{person}이(가) 법정 의무교육을 받지 않았습니다. 괜찮나요?",
     "cond_q": "{person}이(가) 외부 교육 비용을 회사에서 지원받고 싶습니다. 가능한가요?"},
    {"reg": "개인정보처리규정",
     "no_q": "{person}이(가) 동의 없이 직원 연락처를 외부 업체에 제공했습니다. 문제가 되나요?",
     "cond_q": "{person}이(가) 업무 목적으로 고객 정보를 협력업체와 공유해야 합니다. 절차가 어떻게 되나요?"},
    {"reg": "급여규정",
     "no_q": "{person}이(가) 팀장 승인 없이 야근 수당을 청구하려 합니다. 가능한가요?",
     "cond_q": "{person}이(가) 초과근무 수당을 받으려면 어떤 조건이 필요한가요?"},
    {"reg": "징계규정",
     "no_q": "{person}이(가) 소명 기회 없이 징계를 받았습니다. 정당한가요?",
     "cond_q": "{person}이(가) 경징계를 받았는데, 이의를 제기할 수 있나요?"},
    {"reg": "복리후생규정",
     "no_q": "{person}이(가) 증빙서류 없이 의료비 지원을 신청했습니다. 지급 가능한가요?",
     "cond_q": "{person}이(가) 가족의 입원 치료비를 회사에서 지원받을 수 있나요?"},
]

# C. conditional 명확화 시나리오
CONDITIONAL_SCENARIOS = [
    {"reg": "급여규정", "q_template": "{person}이(가) {action}. 가능한가요?",
     "actions": ["퇴직금 중간정산을 신청하려 합니다", "성과급 등급에 이의를 제기하려 합니다"]},
    {"reg": "출장규정", "q_template": "{person}이(가) {action}. 가능한가요?",
     "actions": ["출장 중 개인 일정을 추가하려 합니다", "출장 숙소를 직접 예약하려 합니다"]},
    {"reg": "인사규정", "q_template": "{person}이(가) {action}. 가능한가요?",
     "actions": ["육아 사유로 단축근무를 신청하려 합니다", "수습기간 중 연차를 사용하려 합니다"]},
    {"reg": "교육훈련규정", "q_template": "{person}이(가) {action}. 가능한가요?",
     "actions": ["해외 학회 참석 비용을 지원받으려 합니다", "자격증 취득 후 교육비 환급을 받으려 합니다"]},
    {"reg": "복리후생규정", "q_template": "{person}이(가) {action}. 가능한가요?",
     "actions": ["무주택자 주택자금 대출을 신청하려 합니다", "동호회 활동비를 지원받으려 합니다"]},
]


def build_generation_prompt(reg_name, reg_text, question, target_result):
    """GPT에게 학습 데이터 생성을 요청하는 프롬프트"""
    result_guide = {
        "no": '반드시 "no"로 판단하세요. 이 질문은 규정상 명확히 금지/불허되는 행위입니다. conditions는 null이어야 합니다.',
        "conditional": '반드시 "conditional"로 판단하세요. 이 질문은 특정 조건을 충족하면 가능한 행위입니다. conditions 필드에 조건을 상세히 기술하세요.',
    }

    return f"""아래 규정과 질문에 대해 판단 JSON을 생성하세요.

## 규정
{reg_text}

## 질문
{question}

## 지시사항
{result_guide.get(target_result, '')}

반드시 위의 판단 JSON 형식으로만 응답하세요. JSON 외 텍스트를 포함하지 마세요."""


def call_gpt(client, system_prompt, user_prompt, retries=3):
    """GPT API 호출"""
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            parsed = json.loads(content)
            return parsed
        except Exception as e:
            print(f"  [!] attempt {attempt+1} failed: {e}")
            time.sleep(2 ** attempt)
    return None


def build_chat_message(reg_name, reg_articles, question, answer_json):
    """train.jsonl 형식의 chat message 구성"""
    user_content = f"## 관련 규정 문서\n### {reg_name}\n{reg_articles}\n\n## 사용자 질문\n{question}"
    return {
        "messages": [
            {"role": "system", "content": JUDGMENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": json.dumps(answer_json, ensure_ascii=False)},
        ]
    }


def validate_result(answer_json, expected_result):
    """생성된 답변이 기대 결과와 일치하는지 검증"""
    if not isinstance(answer_json, dict):
        return False
    result = answer_json.get("result")
    if result != expected_result:
        return False
    if expected_result == "no" and answer_json.get("conditions") not in (None, "null", "없음", ""):
        # no인데 conditions가 있으면 의심스러움 — 그래도 허용 (경고만)
        pass
    if expected_result == "conditional" and not answer_json.get("conditions"):
        return False  # conditional인데 conditions가 없으면 reject
    return True


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY 환경변수가 필요합니다.")
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    regulations = load_regulations()

    print("=" * 60)
    print("v2 데이터 보강: no/conditional 경계 케이스 강화")
    print("=" * 60)
    print(f"규정 파일 {len(regulations)}개 로드됨")

    generated = []
    rejected = 0

    # ── A. no 강화 (목표 120건) ──
    print(f"\n[Phase A] no 강화 시나리오 생성...")
    for scenario in NO_SCENARIOS:
        reg_name = scenario["reg"]
        if reg_name not in regulations:
            print(f"  [SKIP] {reg_name} 규정 파일 없음")
            continue
        reg_text = regulations[reg_name]

        for action in scenario["actions"]:
            person = rand_person()
            question = scenario["q_template"].format(person=person, action=action)
            articles = extract_articles(reg_text, max_articles=2)

            prompt = build_generation_prompt(reg_name, articles, question, "no")
            answer = call_gpt(client, JUDGMENT_SYSTEM_PROMPT, prompt)

            if answer and validate_result(answer, "no"):
                msg = build_chat_message(reg_name, articles, question, answer)
                generated.append(msg)
                print(f"  [OK] no | {question[:50]}...")
            else:
                rejected += 1
                actual = answer.get("result") if answer else "None"
                print(f"  [REJECT] expected=no, got={actual} | {question[:50]}...")

            time.sleep(0.5)

    print(f"  Phase A 완료: {sum(1 for g in generated if json.loads(g['messages'][2]['content'])['result'] == 'no')}건 생성")

    # ── B. no vs conditional 경계 쌍 (목표 80건 = 40쌍) ──
    print(f"\n[Phase B] no/conditional 경계 쌍 생성...")
    for pair in BOUNDARY_PAIRS:
        reg_name = pair["reg"]
        if reg_name not in regulations:
            continue
        reg_text = regulations[reg_name]

        for _ in range(2):  # 각 쌍을 다른 사람으로 2번씩
            person = rand_person()
            articles = extract_articles(reg_text, max_articles=2)

            # no 버전
            no_q = pair["no_q"].format(person=person)
            no_prompt = build_generation_prompt(reg_name, articles, no_q, "no")
            no_answer = call_gpt(client, JUDGMENT_SYSTEM_PROMPT, no_prompt)
            if no_answer and validate_result(no_answer, "no"):
                generated.append(build_chat_message(reg_name, articles, no_q, no_answer))
                print(f"  [OK] no   | {no_q[:50]}...")
            else:
                rejected += 1

            # conditional 버전
            cond_q = pair["cond_q"].format(person=person)
            cond_prompt = build_generation_prompt(reg_name, articles, cond_q, "conditional")
            cond_answer = call_gpt(client, JUDGMENT_SYSTEM_PROMPT, cond_prompt)
            if cond_answer and validate_result(cond_answer, "conditional"):
                generated.append(build_chat_message(reg_name, articles, cond_q, cond_answer))
                print(f"  [OK] cond | {cond_q[:50]}...")
            else:
                rejected += 1

            time.sleep(0.5)

    # ── C. conditional 명확화 (목표 50건) ──
    print(f"\n[Phase C] conditional 명확화 생성...")
    for scenario in CONDITIONAL_SCENARIOS:
        reg_name = scenario["reg"]
        if reg_name not in regulations:
            continue
        reg_text = regulations[reg_name]

        for action in scenario["actions"]:
            for _ in range(3):  # 각 액션 3번
                person = rand_person()
                question = scenario["q_template"].format(person=person, action=action)
                articles = extract_articles(reg_text, max_articles=2)

                prompt = build_generation_prompt(reg_name, articles, question, "conditional")
                answer = call_gpt(client, JUDGMENT_SYSTEM_PROMPT, prompt)

                if answer and validate_result(answer, "conditional"):
                    generated.append(build_chat_message(reg_name, articles, question, answer))
                    print(f"  [OK] cond | {question[:50]}...")
                else:
                    rejected += 1

                time.sleep(0.5)

    # ── 결과 저장 ──
    print(f"\n{'=' * 60}")
    print(f"생성 완료: {len(generated)}건 (rejected: {rejected}건)")

    # 분포 확인
    dist = {}
    for g in generated:
        result = json.loads(g["messages"][2]["content"])["result"]
        dist[result] = dist.get(result, 0) + 1
    print(f"분포: {dist}")

    # augment 파일 저장
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for g in generated:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    print(f"\n증강 데이터 저장: {OUTPUT_PATH}")

    # 기존 데이터 백업
    BACKUP_TRAIN.parent.mkdir(parents=True, exist_ok=True)
    if TRAIN_PATH.exists():
        import shutil
        if not BACKUP_TRAIN.exists():
            shutil.copy2(TRAIN_PATH, BACKUP_TRAIN)
            print(f"백업 저장: {BACKUP_TRAIN}")
        if not BACKUP_EVAL.exists():
            shutil.copy2(EVAL_PATH, BACKUP_EVAL)
            print(f"백업 저장: {BACKUP_EVAL}")

    # 병합
    print(f"\n기존 train.jsonl과 병합 중...")
    existing_train = []
    with open(TRAIN_PATH, "r", encoding="utf-8") as f:
        for line in f:
            existing_train.append(json.loads(line.strip()))

    # 증강 데이터의 90%를 train, 10%를 eval에 추가
    random.shuffle(generated)
    split_idx = int(len(generated) * 0.9)
    train_new = generated[:split_idx]
    eval_new = generated[split_idx:]

    # train 병합
    merged_train = existing_train + train_new
    random.shuffle(merged_train)
    with open(TRAIN_PATH, "w", encoding="utf-8") as f:
        for item in merged_train:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"train.jsonl: {len(existing_train)} + {len(train_new)} = {len(merged_train)}건")

    # eval 병합
    existing_eval = []
    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            existing_eval.append(json.loads(line.strip()))
    merged_eval = existing_eval + eval_new
    random.shuffle(merged_eval)
    with open(EVAL_PATH, "w", encoding="utf-8") as f:
        for item in merged_eval:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"eval.jsonl: {len(existing_eval)} + {len(eval_new)} = {len(merged_eval)}건")

    # 최종 분포
    print(f"\n{'=' * 60}")
    print("최종 train.jsonl 분포:")
    final_dist = {}
    for item in merged_train:
        result = json.loads(item["messages"][2]["content"])["result"]
        final_dist[result] = final_dist.get(result, 0) + 1
    for k, v in sorted(final_dist.items()):
        pct = v / len(merged_train) * 100
        print(f"  {k}: {v}건 ({pct:.1f}%)")
    print(f"  총: {len(merged_train)}건")


if __name__ == "__main__":
    main()
