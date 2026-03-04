"""
v1_judgment 학습 데이터 전체 보강 스크립트 (Issue #9)

GPT-4o-mini를 사용하여 ~500건의 신규 학습 데이터를 생성합니다:
1. 7개 추가 규정(급여/출장/교육/복리후생/징계/개인정보/윤리) 기반 샘플 350건
2. no_regulation 샘플 100건
3. cross_reference(교차 참조) 샘플 50건

생성된 데이터는 기존 데이터와 합산 후 90:10 비율로 분할하여
train_augmented.jsonl / eval_augmented.jsonl로 저장합니다.

사용법:
    python scripts/augment_v1_judgment.py

환경변수:
    OPENAI_API_KEY — OpenAI API 키 필요
"""

import json
import random
import re
import sys
import time
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("openai 패키지가 필요합니다: pip install openai")
    sys.exit(1)

random.seed(42)

# ── Section A: Config & Constants ──────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
TRAIN_PATH = BASE_DIR / "data" / "training" / "v1_judgment" / "train.jsonl"
EVAL_PATH = BASE_DIR / "data" / "training" / "v1_judgment" / "eval.jsonl"
OUTPUT_TRAIN = BASE_DIR / "data" / "training" / "v1_judgment" / "train_augmented.jsonl"
OUTPUT_EVAL = BASE_DIR / "data" / "training" / "v1_judgment" / "eval_augmented.jsonl"
REJECTED_PATH = BASE_DIR / "data" / "training" / "v1_judgment" / "rejected.jsonl"

# 생성 목표
TARGET_PER_REGULATION = 50   # 7개 × 50 = 350건
TARGET_NO_REGULATION = 100
TARGET_CROSS_REF = 50

# 시스템 프롬프트 (ai/llm/prompts.py의 JUDGMENT_SYSTEM_PROMPT와 동일)
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
- 여러 규정이 관련된 경우 반드시 교차 분석하세요:
  - 규정 간 충돌이 있으면 상위 규정을 우선 적용하고 cross_references에 기록하세요.
  - 규정이 서로 보완하면 종합 판단을 내리세요.
- 이전 판단 이력이 제공된 경우 일관성을 유지하되, 규정 근거가 다르면 차이를 설명하세요.
- confidence는 다음 기준으로 산정하세요:
  - 0.9~1.0: 명확한 규정 조항이 직접 적용됨
  - 0.7~0.9: 규정이 존재하나 해석이 필요함
  - 0.5~0.7: 관련 규정은 있으나 직접 적용이 어려움
  - 0.5 미만: 관련 규정을 찾기 어려움
- JSON 외의 텍스트를 포함하지 마세요.\
"""

# 이름/직급/부서 풀
NAMES = [
    "김민수", "이지현", "박서준", "최유진", "정하늘", "오태영", "서지안", "장동혁",
    "윤채원", "배수지", "송미래", "한도윤", "임세진", "강나은", "조예린", "신지호",
    "황서연", "류민재", "문하영", "고승현", "남지우", "전서윤", "백도현", "구혜린",
    "양준호", "권수빈", "유하진", "홍세영", "손태희", "노현수", "허지민", "우성훈",
    "차은서", "봉준영", "피수연", "감도영", "마서진", "탁민호", "하윤정", "길태수",
]
TITLES = ["사원", "대리", "과장", "차장", "부장"]
TEAMS = [
    "개발팀", "인사팀", "보안팀", "디자인팀", "QA팀", "마케팅팀", "영업팀",
    "재무팀", "기획팀", "운영팀", "데이터팀", "인프라팀", "경영지원팀", "법무팀",
]


def rand_person():
    return f"{random.choice(NAMES)}({random.choice(TITLES)}, {random.choice(TEAMS)})"


# ── Section B: 7개 추가 규정 텍스트 ──────────────────────────────

ADDITIONAL_REGULATIONS = {
    "급여규정": {
        "제1조 (목적)": (
            "본 규정은 회사 임직원의 급여에 관한 사항을 정함으로써 공정하고 합리적인 "
            "보상 체계를 확립함을 목적으로 한다."
        ),
        "제2조 (적용범위)": (
            "본 규정은 회사에 소속된 정규직 및 계약직 직원에게 적용한다. "
            "인턴 및 파견직의 급여는 별도의 계약에 따른다."
        ),
        "제3조 (급여구성)": (
            "급여는 기본급, 직무수당, 성과급으로 구성한다.\n"
            "기본급은 직급별 호봉표에 따라 결정하며, 매년 1월 인사평가 결과를 반영하여 조정한다.\n"
            "직무수당은 업무의 전문성, 난이도, 위험도 등을 고려하여 직무별로 차등 지급한다.\n"
            "성과급은 반기별 개인 및 팀 성과 평가 결과에 따라 기본급의 0~200% 범위에서 지급한다."
        ),
        "제4조 (급여지급)": (
            "급여는 매월 25일에 지급하며, 지급일이 휴일인 경우 전 영업일에 지급한다.\n"
            "급여는 직원 본인 명의의 금융계좌로 이체하는 것을 원칙으로 한다.\n"
            "급여 명세서는 매월 지급일에 전자 형태로 제공한다."
        ),
        "제5조 (초과근무수당)": (
            "소정근로시간을 초과하여 근무한 경우 「근로기준법」에 따라 통상임금의 50%를 가산하여 지급한다.\n"
            "초과근무는 사전에 팀장의 승인을 받아야 하며, 월 52시간을 초과할 수 없다.\n"
            "휴일근무 시 통상임금의 100%를 가산하여 지급한다."
        ),
        "제6조 (퇴직금)": (
            "1년 이상 계속 근로한 직원에 대해 퇴직 시 퇴직금을 지급한다.\n"
            "퇴직금은 30일분 이상의 평균임금에 근속연수를 곱하여 산정한다.\n"
            "회사는 퇴직연금(DB형 또는 DC형)을 운영하며, 직원은 입사 시 선택할 수 있다."
        ),
    },
    "출장규정": {
        "제1조 (목적)": (
            "본 규정은 회사 직원의 국내외 출장에 관한 절차, 경비 지급 기준 등을 정함을 목적으로 한다."
        ),
        "제2조 (출장구분)": (
            "출장은 일일출장과 숙박출장으로 구분한다.\n"
            "일일출장은 당일 귀환이 가능한 출장이며, 숙박출장은 1박 이상의 출장을 말한다.\n"
            "해외출장은 별도의 해외출장 절차에 따른다."
        ),
        "제3조 (출장승인)": (
            "출장은 출발 3일 전까지 출장 신청서를 작성하여 소속 팀장의 사전 승인을 받아야 한다.\n"
            "긴급 출장의 경우 구두 승인 후 2일 이내에 서면 신청서를 제출한다.\n"
            "해외출장은 임원 승인을 추가로 받아야 한다."
        ),
        "제4조 (출장경비)": (
            "출장경비는 교통비, 숙박비, 식비, 일비로 구분하여 지급한다.\n"
            "국내 일일출장: 교통비 실비 + 식비 2만원 + 일비 2만원.\n"
            "국내 숙박출장: 교통비 실비 + 숙박비(1일 10만원 한도) + 식비 3만원/일 + 일비 2만원/일.\n"
            "해외출장: 출장 지역별 경비 기준표에 따라 지급한다."
        ),
        "제5조 (출장정산)": (
            "출장 종료 후 5영업일 이내에 출장보고서와 함께 경비를 정산하여야 한다.\n"
            "증빙서류(영수증, 교통카드 내역 등)를 첨부하여야 하며, 증빙이 없는 경비는 지급하지 않는다.\n"
            "법인카드 사용을 원칙으로 하며, 부득이한 경우 개인 선지급 후 정산한다."
        ),
    },
    "교육훈련규정": {
        "제1조 (목적)": (
            "본 규정은 직원의 직무능력 향상 및 자기개발을 지원하기 위한 교육훈련에 관한 사항을 정함을 목적으로 한다."
        ),
        "제2조 (교육구분)": (
            "교육훈련은 사내교육, 사외교육, 온라인교육, 자기개발교육으로 구분한다.\n"
            "사내교육은 회사가 주관하는 집합교육, 세미나, 워크숍 등을 말한다.\n"
            "사외교육은 외부 전문기관에 위탁하는 교육을 말한다.\n"
            "자기개발교육은 직원 개인이 자율적으로 수강하는 교육을 말한다."
        ),
        "제3조 (교육비지원)": (
            "사외교육 및 자기개발교육의 경우 연간 200만원 한도 내에서 교육비를 지원한다.\n"
            "직무 관련 자격증 취득 시 응시료 전액 및 합격 축하금 30만원을 지급한다.\n"
            "교육비 지원은 소속 팀장 및 인사팀의 사전 승인을 받아야 한다.\n"
            "교육 수료 후 30일 이내에 수료증 또는 이수 확인서를 제출하여야 한다."
        ),
        "제4조 (의무교육)": (
            "전 직원은 연 1회 이상 다음 의무교육을 이수하여야 한다:\n"
            "① 정보보호 교육 (4시간), ② 개인정보보호 교육 (2시간), ③ 직장 내 성희롱 예방교육 (1시간),\n"
            "④ 직장 내 괴롭힘 예방교육 (1시간), ⑤ 장애인 인식개선 교육 (1시간).\n"
            "의무교육 미이수 시 인사평가에 불이익이 있을 수 있다."
        ),
        "제5조 (교육의무기간)": (
            "회사 비용으로 해외연수 또는 장기교육(3개월 이상)을 받은 직원은 교육 종료 후 "
            "교육기간의 2배에 해당하는 기간 동안 의무 근무하여야 한다.\n"
            "의무기간 내 퇴직 시 교육비의 잔여 비율을 반환하여야 한다."
        ),
    },
    "복리후생규정": {
        "제1조 (목적)": (
            "본 규정은 직원의 생활 안정 및 복지 증진을 위한 복리후생 제도에 관한 사항을 정함을 목적으로 한다."
        ),
        "제2조 (경조금)": (
            "직원 본인 결혼 시 축의금 20만원, 자녀 결혼 시 10만원을 지급한다.\n"
            "직원 본인 또는 배우자의 부모 사망 시 조의금 20만원 및 조화를 제공한다.\n"
            "형제자매 사망 시 조의금 10만원을 지급한다.\n"
            "경조휴가는 별도의 경조휴가 기준표에 따라 부여한다."
        ),
        "제3조 (건강검진)": (
            "전 직원에 대해 연 1회 종합건강검진을 실시하며, 비용은 회사가 부담한다.\n"
            "35세 이상 직원은 정밀검진 항목을 추가할 수 있다.\n"
            "건강검진일은 유급으로 처리한다."
        ),
        "제4조 (학자금지원)": (
            "근속 1년 이상 직원의 자녀에 대해 학자금을 지원한다.\n"
            "중학교·고등학교: 수업료 및 입학금 전액, 대학교: 등록금의 50%(학기당 200만원 한도).\n"
            "학자금 지원은 자녀 2인까지 적용한다."
        ),
        "제5조 (사내동호회)": (
            "5인 이상의 직원으로 구성된 사내 동호회에 대해 월 10만원의 활동비를 지원한다.\n"
            "동호회 등록은 인사팀에 신청하며, 분기별 활동 보고서를 제출하여야 한다.\n"
            "1인이 가입 가능한 동호회는 2개까지로 제한한다."
        ),
        "제6조 (주거안정)": (
            "무주택 직원에 대해 주택자금 대출(최대 5,000만원, 연이율 2%)을 지원한다.\n"
            "전세자금의 경우 최대 3,000만원까지 무이자 대출을 지원하며, 근속연수에 따라 한도를 조정한다.\n"
            "사택 또는 기숙사를 운영하는 경우 입주 우선순위는 원거리 통근자, 신입사원 순으로 한다."
        ),
    },
    "징계규정": {
        "제1조 (목적)": (
            "본 규정은 직원의 복무 기강 확립을 위한 징계의 종류, 사유, 절차에 관한 사항을 정함을 목적으로 한다."
        ),
        "제2조 (징계의종류)": (
            "징계는 경고, 감봉, 정직, 해고의 4단계로 구분한다.\n"
            "경고: 서면 경고장을 발부하며, 인사기록에 1년간 보관한다.\n"
            "감봉: 3개월 이내의 기간 동안 급여의 10% 이내를 감액한다.\n"
            "정직: 1개월 이상 3개월 이내의 기간 동안 출근을 정지하며, 해당 기간의 급여를 지급하지 않는다.\n"
            "해고: 근로관계를 종료하며, 「근로기준법」 제26조에 따라 30일 전에 예고한다."
        ),
        "제3조 (징계사유)": (
            "다음 각 호에 해당하는 경우 징계할 수 있다:\n"
            "① 정당한 사유 없이 무단결근 3일 이상인 경우\n"
            "② 직무상 지득한 비밀을 누설한 경우\n"
            "③ 회사의 명예를 현저히 훼손한 경우\n"
            "④ 직장 내 성희롱, 괴롭힘을 행한 경우\n"
            "⑤ 정보보호 규정을 중대하게 위반한 경우\n"
            "⑥ 업무상 횡령, 배임 등 부정행위를 한 경우\n"
            "⑦ 고의 또는 중대한 과실로 회사에 중대한 손해를 끼친 경우"
        ),
        "제4조 (징계위원회)": (
            "징계는 징계위원회의 의결을 거쳐 결정한다.\n"
            "징계위원회는 인사담당 임원을 위원장으로 하고, 3인 이상 5인 이내의 위원으로 구성한다.\n"
            "징계 대상자에게는 징계위원회 개최 7일 전까지 서면으로 통보하고, 소명 기회를 부여한다."
        ),
        "제5조 (징계감면)": (
            "징계 대상자가 과거 공적이 현저하거나, 뉘우침이 명백한 경우 징계를 감경할 수 있다.\n"
            "징계 후 1년 이내에 동일 또는 유사한 사유로 재징계 시 가중 처분할 수 있다.\n"
            "징계 처분에 대해 이의가 있는 경우 처분 통보일로부터 14일 이내에 재심을 청구할 수 있다."
        ),
    },
    "개인정보처리규정": {
        "제1조 (목적)": (
            "본 규정은 「개인정보 보호법」 및 관련 법령에 따라 회사가 처리하는 개인정보의 보호에 관한 사항을 "
            "정함을 목적으로 한다."
        ),
        "제2조 (개인정보수집)": (
            "개인정보는 적법하고 정당한 방법으로 정보주체의 동의를 받아 수집하여야 한다.\n"
            "수집 목적에 필요한 최소한의 개인정보만을 수집하며, 민감정보 및 고유식별정보는 "
            "별도의 동의를 받아야 한다.\n"
            "수집 시 개인정보의 수집·이용 목적, 수집 항목, 보유 및 이용 기간, 동의 거부권 및 "
            "불이익에 대해 명확히 고지하여야 한다."
        ),
        "제3조 (개인정보이용및제공)": (
            "개인정보는 수집 목적 범위 내에서만 이용하며, 제3자 제공 시 정보주체의 별도 동의를 받아야 한다.\n"
            "업무 위탁 시 수탁자에 대해 개인정보 보호 의무를 계약서에 명시하고, 관리·감독하여야 한다.\n"
            "국외 이전 시 「개인정보 보호법」 제28조의8에 따른 보호조치를 이행하여야 한다."
        ),
        "제4조 (개인정보파기)": (
            "보유 기간이 경과하거나 처리 목적이 달성된 개인정보는 지체 없이 파기하여야 한다.\n"
            "전자적 파일은 복원 불가능한 방법(덮어쓰기, 물리적 파괴 등)으로 삭제한다.\n"
            "인쇄물은 파쇄기를 이용하여 파기하며, 파기 기록을 5년간 보관한다."
        ),
        "제5조 (개인정보보호책임자)": (
            "회사는 개인정보보호책임자(CPO)를 지정하여 개인정보 처리에 관한 업무를 총괄하게 한다.\n"
            "CPO는 연 1회 이상 개인정보 처리 실태를 점검하고, 개선 사항을 조치하여야 한다.\n"
            "개인정보 유출 사고 발생 시 72시간 이내에 정보주체에 통지하고, "
            "한국인터넷진흥원(KISA)에 신고하여야 한다."
        ),
    },
    "윤리강령": {
        "제1조 (목적)": (
            "본 강령은 회사 임직원이 직무 수행 시 준수하여야 할 윤리적 기준과 행동 규범을 "
            "정함으로써 투명하고 공정한 기업문화를 확립함을 목적으로 한다."
        ),
        "제2조 (공정거래)": (
            "임직원은 거래처와의 관계에서 공정하고 투명하게 업무를 수행하여야 한다.\n"
            "입찰, 계약, 발주 시 특정 업체에 부당한 특혜를 제공하여서는 아니 된다.\n"
            "경쟁사에 대한 비방, 허위 정보 유포, 부당 담합 행위를 금지한다."
        ),
        "제3조 (금품수수금지)": (
            "임직원은 직무 관련 여부와 관계없이 이해관계자로부터 금품, 향응, 선물 등을 "
            "수수하여서는 아니 된다.\n"
            "사회 통념상 허용되는 범위(5만원 이하의 선물, 3만원 이하의 식사)는 예외로 하되, "
            "반복적 수수는 금지한다.\n"
            "부득이하게 금품을 수수한 경우 즉시 윤리경영팀에 신고하고 반환 조치를 취하여야 한다."
        ),
        "제4조 (이해충돌방지)": (
            "임직원은 회사의 이익과 개인의 이익이 상충하는 상황을 회피하여야 한다.\n"
            "가족 또는 친인척이 운영하는 업체와의 거래 시 사전에 상급자에게 보고하고 승인을 받아야 한다.\n"
            "회사의 기밀 정보를 이용한 개인적 이익 추구(내부자 거래 등)를 엄격히 금지한다."
        ),
        "제5조 (내부고발보호)": (
            "회사의 법령 위반, 윤리 위반 행위를 발견한 직원은 윤리경영팀 또는 익명 신고 채널을 통해 "
            "신고할 수 있다.\n"
            "내부고발자의 신원은 철저히 보호하며, 신고를 이유로 불이익을 주어서는 아니 된다.\n"
            "허위 또는 악의적 신고는 징계 사유에 해당한다."
        ),
    },
}


# ── Section B: Regulation Parser ──────────────────────────────────

def parse_regulations():
    """추가 규정 텍스트에서 개별 조항을 추출하여 리스트로 반환"""
    articles = []
    for reg_name, reg_articles in ADDITIONAL_REGULATIONS.items():
        for article_id, content in reg_articles.items():
            articles.append({
                "article_id": article_id,
                "title": article_id,
                "content": content,
                "regulation_name": reg_name,
            })
    return articles


# ── Section C: GPT-4o-mini 생성 엔진 ──────────────────────────────

def call_gpt(client: OpenAI, system_msg: str, user_msg: str, max_retries: int = 3) -> str | None:
    """GPT-4o-mini API 호출 (rate limit 재시도 포함)"""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.9,
                max_tokens=1500,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait = 2 ** attempt * 5
                print(f"    Rate limit, {wait}초 대기...")
                time.sleep(wait)
            else:
                print(f"    API 오류: {e}")
                return None
    return None


GENERATION_SYSTEM_PROMPT = """\
너는 기업 내부 규정 판단 AI 학습 데이터를 생성하는 전문가야.
주어진 규정 조항을 바탕으로 현실적인 직원의 질문과 판단 결과를 생성해야 해.

반드시 아래 JSON 형식으로만 응답해:
{
    "question": "직원의 질문 (이름(직급, 부서) 형태 포함)",
    "result": "yes" | "no" | "conditional",
    "confidence": 0.60~0.98 범위의 float,
    "reasoning": "판단 근거를 상세히 설명",
    "regulations": [
        {"article": "규정 조항명", "relevance": "높음|중간|낮음", "content": "관련 내용 요약"}
    ],
    "cross_references": [],
    "conditions": "조건부일 경우 조건 설명, 아니면 null",
    "alternatives": ["대안이 있다면 제시"]
}

규칙:
- result는 yes, no, conditional 중 하나로 다양하게 생성해. 비율은 대략 yes 40%, no 30%, conditional 30%.
- confidence는 result에 맞게 설정해:
  - yes: 0.85~0.98 범위
  - no: 0.80~0.95 범위
  - conditional: 0.60~0.85 범위
- 질문은 실제 직장에서 물어볼 법한 자연스러운 문장으로.
- 직원 이름은 다양한 한국 이름, 직급(사원~부장), 부서를 사용해.
- JSON 외의 텍스트를 포함하지 마.\
"""

NO_REG_GENERATION_PROMPT = """\
너는 기업 내부 규정 판단 AI 학습 데이터를 생성하는 전문가야.
"no_regulation" (관련 규정 없음) 판단 학습 데이터를 생성해야 해.

주어진 규정 조항이 있지만, 질문 내용과는 직접적으로 관련이 없는 상황을 만들어야 해.
예: 채용 규정을 제시했는데, 직원이 사내 식당 메뉴에 대해 질문하는 경우.

반드시 아래 JSON 형식으로만 응답해:
{
    "question": "직원의 질문 (이름(직급, 부서) 형태 포함)",
    "result": "no_regulation",
    "confidence": 0.30~0.55 범위의 float,
    "reasoning": "왜 관련 규정이 없는지 상세히 설명",
    "regulations": [
        {"article": "제시된 규정 조항명", "relevance": "낮음", "content": "해당 규정은 질문과 직접적으로 관련이 없습니다."}
    ],
    "cross_references": [],
    "conditions": null,
    "alternatives": ["적절한 부서/담당자에게 문의하라는 안내"]
}

규칙:
- 질문은 규정에 전혀 나와 있지 않은 주제여야 해 (점심 메뉴, 주차, 택시비, 꽃배달 등).
- 직원 이름은 다양한 한국 이름, 직급(사원~부장), 부서를 사용해.
- JSON 외의 텍스트를 포함하지 마.\
"""

CROSS_REF_GENERATION_PROMPT = """\
너는 기업 내부 규정 판단 AI 학습 데이터를 생성하는 전문가야.
여러 규정 조항을 교차 분석하는 판단 학습 데이터를 생성해야 해.

주어진 2~3개의 규정 조항을 종합적으로 고려하여 판단하는 시나리오를 만들어야 해.
cross_references 필드에 조항 간 관계(보완/충돌/상위규정)를 반드시 포함해.

반드시 아래 JSON 형식으로만 응답해:
{
    "question": "직원의 질문 (이름(직급, 부서) 형태 포함)",
    "result": "yes" | "conditional",
    "confidence": 0.65~0.95 범위의 float,
    "reasoning": "여러 규정을 교차 분석한 판단 근거를 상세히 설명",
    "regulations": [
        {"article": "규정 조항명1", "relevance": "높음|중간", "content": "관련 내용 요약"},
        {"article": "규정 조항명2", "relevance": "높음|중간", "content": "관련 내용 요약"}
    ],
    "cross_references": [
        {"articles": ["조항A", "조항B"], "relationship": "보완|충돌|상위규정", "detail": "관계 설명"}
    ],
    "conditions": "조건부일 경우 조건 설명, 아니면 null",
    "alternatives": ["대안이 있다면 제시"]
}

규칙:
- cross_references에 반드시 1개 이상의 교차 참조를 포함해.
- 조항 간 관계는 보완, 충돌, 상위규정 중 적절한 것을 선택해.
- 직원 이름은 다양한 한국 이름, 직급(사원~부장), 부서를 사용해.
- JSON 외의 텍스트를 포함하지 마.\
"""


def parse_gpt_response(raw: str) -> dict | None:
    """GPT 응답에서 JSON 추출"""
    if not raw:
        return None
    # ```json ... ``` 블록 추출 시도
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    # 최외곽 { } 추출
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None


def build_sample(article_title: str, article_content: str, gpt_data: dict) -> dict:
    """GPT 응답 데이터를 기존 JSONL 포맷의 messages 배열로 변환"""
    user_content = (
        f"## 관련 규정 문서\n"
        f"### {article_title}\n"
        f"{article_content}\n\n"
        f"## 사용자 질문\n"
        f"{gpt_data['question']}"
    )
    assistant_data = {
        "result": gpt_data["result"],
        "confidence": gpt_data["confidence"],
        "reasoning": gpt_data["reasoning"],
        "regulations": gpt_data.get("regulations", []),
        "cross_references": gpt_data.get("cross_references", []),
        "conditions": gpt_data.get("conditions"),
        "alternatives": gpt_data.get("alternatives", []),
    }
    return {
        "messages": [
            {"role": "system", "content": JUDGMENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": json.dumps(assistant_data, ensure_ascii=False)},
        ]
    }


def build_cross_ref_sample(articles: list[dict], gpt_data: dict) -> dict:
    """교차 참조 샘플: 여러 조항을 user content에 포함"""
    reg_sections = []
    for art in articles:
        reg_sections.append(f"### {art['title']}\n{art['content']}")
    user_content = (
        "## 관련 규정 문서\n"
        + "\n\n".join(reg_sections)
        + f"\n\n## 사용자 질문\n{gpt_data['question']}"
    )
    assistant_data = {
        "result": gpt_data["result"],
        "confidence": gpt_data["confidence"],
        "reasoning": gpt_data["reasoning"],
        "regulations": gpt_data.get("regulations", []),
        "cross_references": gpt_data.get("cross_references", []),
        "conditions": gpt_data.get("conditions"),
        "alternatives": gpt_data.get("alternatives", []),
    }
    return {
        "messages": [
            {"role": "system", "content": JUDGMENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": json.dumps(assistant_data, ensure_ascii=False)},
        ]
    }


def generate_regulation_samples(client: OpenAI, articles: list[dict]) -> list[dict]:
    """7개 규정 기반 샘플 생성 (~350건)"""
    samples = []
    for reg_name in ADDITIONAL_REGULATIONS:
        reg_articles = [a for a in articles if a["regulation_name"] == reg_name]
        generated = 0
        print(f"\n  [{reg_name}] 목표: {TARGET_PER_REGULATION}건")
        for i in range(TARGET_PER_REGULATION + 10):  # 여유분 포함
            if generated >= TARGET_PER_REGULATION:
                break
            art = reg_articles[i % len(reg_articles)]
            user_msg = (
                f"다음 규정 조항을 기반으로 판단 학습 데이터 1건을 생성해줘.\n\n"
                f"규정명: {art['regulation_name']}\n"
                f"조항: {art['title']}\n"
                f"내용:\n{art['content']}"
            )
            raw = call_gpt(client, GENERATION_SYSTEM_PROMPT, user_msg)
            gpt_data = parse_gpt_response(raw)
            if gpt_data and "question" in gpt_data and "result" in gpt_data:
                sample = build_sample(art["title"], art["content"], gpt_data)
                samples.append(sample)
                generated += 1
                if generated % 10 == 0:
                    print(f"    {generated}/{TARGET_PER_REGULATION}")
            time.sleep(0.3)  # rate limit 방지
        print(f"    완료: {generated}건")
    return samples


def generate_no_regulation(client: OpenAI, articles: list[dict]) -> list[dict]:
    """no_regulation 샘플 생성 (~100건)"""
    samples = []
    generated = 0
    print(f"\n  [no_regulation] 목표: {TARGET_NO_REGULATION}건")
    for i in range(TARGET_NO_REGULATION + 20):  # 여유분
        if generated >= TARGET_NO_REGULATION:
            break
        art = articles[i % len(articles)]
        user_msg = (
            f"다음 규정 조항이 제시되었지만, 이 규정과는 전혀 관련 없는 질문에 대한 "
            f"'no_regulation' 판단 데이터 1건을 생성해줘.\n\n"
            f"규정명: {art['regulation_name']}\n"
            f"조항: {art['title']}\n"
            f"내용:\n{art['content']}"
        )
        raw = call_gpt(client, NO_REG_GENERATION_PROMPT, user_msg)
        gpt_data = parse_gpt_response(raw)
        if gpt_data and gpt_data.get("result") == "no_regulation" and "question" in gpt_data:
            sample = build_sample(art["title"], art["content"], gpt_data)
            samples.append(sample)
            generated += 1
            if generated % 10 == 0:
                print(f"    {generated}/{TARGET_NO_REGULATION}")
        time.sleep(0.3)
    print(f"    완료: {generated}건")
    return samples


def generate_cross_reference(client: OpenAI, articles: list[dict]) -> list[dict]:
    """교차 참조 샘플 생성 (~50건)"""
    samples = []
    generated = 0
    print(f"\n  [cross_reference] 목표: {TARGET_CROSS_REF}건")
    # 서로 다른 규정에서 2~3개 조항 조합
    reg_names = list(ADDITIONAL_REGULATIONS.keys())
    for i in range(TARGET_CROSS_REF + 15):  # 여유분
        if generated >= TARGET_CROSS_REF:
            break
        n_arts = random.choice([2, 2, 3])  # 2개 조합이 더 빈번
        chosen_regs = random.sample(reg_names, min(n_arts, len(reg_names)))
        chosen_articles = []
        for rn in chosen_regs:
            reg_arts = [a for a in articles if a["regulation_name"] == rn]
            chosen_articles.append(random.choice(reg_arts))

        art_desc = "\n\n".join(
            f"규정명: {a['regulation_name']}\n조항: {a['title']}\n내용:\n{a['content']}"
            for a in chosen_articles
        )
        user_msg = (
            f"다음 여러 규정 조항을 교차 분석하는 판단 학습 데이터 1건을 생성해줘.\n"
            f"cross_references에 조항 간 관계를 반드시 포함해야 해.\n\n{art_desc}"
        )
        raw = call_gpt(client, CROSS_REF_GENERATION_PROMPT, user_msg)
        gpt_data = parse_gpt_response(raw)
        if (gpt_data
                and "question" in gpt_data
                and "result" in gpt_data
                and gpt_data.get("cross_references")):
            sample = build_cross_ref_sample(chosen_articles, gpt_data)
            samples.append(sample)
            generated += 1
            if generated % 10 == 0:
                print(f"    {generated}/{TARGET_CROSS_REF}")
        time.sleep(0.3)
    print(f"    완료: {generated}건")
    return samples


# ── Section D: QA Validation ──────────────────────────────────────

VALID_RESULTS = {"yes", "no", "conditional", "no_regulation"}


def validate_sample(sample: dict) -> tuple[bool, str]:
    """10-point 검증 체크리스트. (통과, 사유) 반환"""
    # 1. JSON 파싱 가능 (이미 dict)
    if not isinstance(sample, dict):
        return False, "1: not a dict"

    # 2. messages 배열 3개
    msgs = sample.get("messages")
    if not isinstance(msgs, list) or len(msgs) != 3:
        return False, "2: messages 배열이 3개가 아님"

    # 3. system content == JUDGMENT_SYSTEM_PROMPT
    if msgs[0].get("role") != "system" or msgs[0].get("content") != JUDGMENT_SYSTEM_PROMPT:
        return False, "3: system prompt 불일치"

    # 4. user content에 필수 섹션 포함
    user_content = msgs[1].get("content", "")
    if "## 관련 규정 문서" not in user_content or "## 사용자 질문" not in user_content:
        return False, "4: user content 필수 섹션 누락"

    # 5. assistant content가 유효한 JSON
    try:
        asst_data = json.loads(msgs[2].get("content", ""))
    except (json.JSONDecodeError, TypeError):
        return False, "5: assistant content JSON 파싱 실패"

    # 6. result 유효성
    if asst_data.get("result") not in VALID_RESULTS:
        return False, f"6: result 값 부적합 ({asst_data.get('result')})"

    # 7. confidence 범위
    conf = asst_data.get("confidence")
    if not isinstance(conf, (int, float)) or conf < 0.0 or conf > 1.0:
        return False, f"7: confidence 범위 초과 ({conf})"

    # 8. regulations가 list
    if not isinstance(asst_data.get("regulations"), list):
        return False, "8: regulations가 list가 아님"

    # 9. cross_references가 list
    if not isinstance(asst_data.get("cross_references"), list):
        return False, "9: cross_references가 list가 아님"

    # 10. reasoning 비어있지 않음
    if not asst_data.get("reasoning", "").strip():
        return False, "10: reasoning이 비어있음"

    return True, "pass"


# ── Section E: Main Pipeline ──────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def save_jsonl(samples: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")


def print_statistics(samples: list[dict], label: str):
    """분포 통계 출력"""
    result_dist: dict[str, int] = {}
    confidences: list[float] = []
    reg_names: dict[str, int] = {}
    cross_ref_count = 0

    for s in samples:
        try:
            data = json.loads(s["messages"][2]["content"])
            r = data.get("result", "unknown")
            result_dist[r] = result_dist.get(r, 0) + 1
            confidences.append(data.get("confidence", 0))
            if data.get("cross_references"):
                cross_ref_count += 1
            # 규정명 추출 (user content에서)
            user_content = s["messages"][1]["content"]
            for rn in list(ADDITIONAL_REGULATIONS.keys()) + ["IT규정"]:
                if rn in user_content:
                    reg_names[rn] = reg_names.get(rn, 0) + 1
        except Exception:
            pass

    print(f"\n  [{label}] 총 {len(samples)}건")
    print(f"  Result 분포:")
    for k in sorted(result_dist.keys()):
        pct = result_dist[k] / len(samples) * 100 if samples else 0
        print(f"    {k:<15} {result_dist[k]:>5}건 ({pct:.1f}%)")
    print(f"  Confidence: {len(set(round(c, 2) for c in confidences))}종류 "
          f"(min={min(confidences):.2f}, max={max(confidences):.2f})" if confidences else "")
    print(f"  Cross-reference 포함 샘플: {cross_ref_count}건")
    if reg_names:
        print(f"  추가 규정별 샘플:")
        for rn, cnt in sorted(reg_names.items()):
            print(f"    {rn}: {cnt}건")


def main():
    import os

    print("=" * 60)
    print("  v1_judgment 학습 데이터 전체 보강 (Issue #9)")
    print("=" * 60)

    # API 키 확인
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("\n[오류] OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        print("  export OPENAI_API_KEY='sk-...'")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # 1. 기존 데이터 로드
    print("\n[1/7] 기존 데이터 로드...")
    existing_train = load_jsonl(TRAIN_PATH)
    existing_eval = load_jsonl(EVAL_PATH)
    print(f"  train: {len(existing_train)}건, eval: {len(existing_eval)}건")
    existing_all = existing_train + existing_eval
    print(f"  기존 합계: {len(existing_all)}건")

    # 2. 규정 파싱
    print("\n[2/7] 7개 추가 규정 파싱...")
    articles = parse_regulations()
    print(f"  총 {len(articles)}개 조항 추출")
    for reg_name in ADDITIONAL_REGULATIONS:
        cnt = sum(1 for a in articles if a["regulation_name"] == reg_name)
        print(f"    {reg_name}: {cnt}개 조항")

    # 3. GPT-4o-mini로 생성
    print("\n[3/7] GPT-4o-mini로 데이터 생성...")
    new_samples = []

    reg_samples = generate_regulation_samples(client, articles)
    new_samples.extend(reg_samples)
    print(f"  규정 기반 샘플: {len(reg_samples)}건")

    no_reg_samples = generate_no_regulation(client, articles)
    new_samples.extend(no_reg_samples)
    print(f"  no_regulation 샘플: {len(no_reg_samples)}건")

    cross_ref_samples = generate_cross_reference(client, articles)
    new_samples.extend(cross_ref_samples)
    print(f"  cross_reference 샘플: {len(cross_ref_samples)}건")

    print(f"\n  총 생성: {len(new_samples)}건")

    # 4. 검증
    print("\n[4/7] 품질 검증...")
    valid_samples = []
    rejected_samples = []
    for s in new_samples:
        ok, reason = validate_sample(s)
        if ok:
            valid_samples.append(s)
        else:
            rejected_samples.append({"sample": s, "reason": reason})

    print(f"  통과: {len(valid_samples)}건")
    print(f"  불합격: {len(rejected_samples)}건")

    if rejected_samples:
        save_jsonl([r["sample"] for r in rejected_samples], REJECTED_PATH)
        print(f"  불합격 사유:")
        reason_counts: dict[str, int] = {}
        for r in rejected_samples:
            reason_counts[r["reason"]] = reason_counts.get(r["reason"], 0) + 1
        for reason, cnt in sorted(reason_counts.items()):
            print(f"    {reason}: {cnt}건")

    # 5. 합산 + 셔플
    print("\n[5/7] 기존 + 신규 데이터 합산 및 셔플...")
    all_samples = existing_all + valid_samples
    random.shuffle(all_samples)
    print(f"  전체: {len(all_samples)}건")

    # 6. 90:10 분할
    print("\n[6/7] Train/Eval 분할 (90:10)...")
    split_idx = int(len(all_samples) * 0.9)
    train_final = all_samples[:split_idx]
    eval_final = all_samples[split_idx:]
    print(f"  Train: {len(train_final)}건")
    print(f"  Eval:  {len(eval_final)}건")

    # 7. 저장
    print("\n[7/7] 저장...")
    save_jsonl(train_final, OUTPUT_TRAIN)
    save_jsonl(eval_final, OUTPUT_EVAL)
    print(f"  {OUTPUT_TRAIN}")
    print(f"  {OUTPUT_EVAL}")

    # 통계 출력
    print("\n" + "=" * 60)
    print("  최종 통계")
    print("=" * 60)
    print_statistics(train_final, "Train")
    print_statistics(eval_final, "Eval")

    # 기존 데이터도 검증 (기존 train에서 포맷 호환성 확인)
    print("\n[검증] 기존 load_jsonl 호환성 확인...")
    try:
        loaded = load_jsonl(OUTPUT_TRAIN)
        print(f"  train_augmented.jsonl 로드 성공: {len(loaded)}건")
        loaded = load_jsonl(OUTPUT_EVAL)
        print(f"  eval_augmented.jsonl 로드 성공: {len(loaded)}건")
    except Exception as e:
        print(f"  로드 실패: {e}")

    print("\n  완료!")


if __name__ == "__main__":
    main()
