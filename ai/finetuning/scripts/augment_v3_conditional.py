"""
v1 judgment 데이터 보강 — conditional Type 5 (재량 표현) + no/conditional 경계 강화

분석 결과:
  - Type 5 (재량 표현 "~할 수 있다") 이 train에 ~80건으로 부족 (9%)
  - no/conditional 경계가 애매한 케이스 171건 (27%)

보강 전략:
  1. Type 5 재량 표현 conditional 추가 (~60건)
     - "부서장이 허용할 수 있다", "회사가 지원할 수 있다" 등 재량 패턴
  2. no/conditional 경계 강화 (~30건)
     - 동일 상황 + "승인 없이" → no / 중립 질문 → conditional 쌍

사용법:
  cd /path/to/SKN21-FINAL-3TEAM
  python -m ai.finetuning.scripts.augment_v3_conditional [--dry-run]

  --dry-run: 파일 저장 없이 생성 결과만 출력
"""

import json
import copy
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
TRAIN_PATH = ROOT / "data" / "training" / "v1_judgment" / "train.jsonl"
OUTPUT_DIR = ROOT / "data" / "training" / "v1_judgment_v3"

# 기존 train.jsonl의 system prompt (첫 번째 데이터에서 추출)
SYSTEM_PROMPT = None


def load_system_prompt():
    global SYSTEM_PROMPT
    with open(TRAIN_PATH, encoding="utf-8") as f:
        first = json.loads(f.readline())
        SYSTEM_PROMPT = first["messages"][0]["content"]


def make_example(regulation_text: str, question: str, result: dict) -> dict:
    """학습 데이터 1건 생성"""
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"## 관련 규정 문서\n{regulation_text}\n\n## 사용자 질문\n{question}",
            },
            {"role": "assistant", "content": json.dumps(result, ensure_ascii=False)},
        ]
    }


# ──────────────────────────────────────────────
# Type 5: 재량 표현 conditional 데이터
# "~할 수 있다", "~를 허용할 수 있다" 패턴
# ──────────────────────────────────────────────

TYPE5_DATA = [
    # 겸업/부업 재량
    {
        "reg": "### 제12조 (겸업 금지)\n직원은 회사의 사전 서면 승인 없이 타 기업에 취업하거나 독립적인 영리 활동을 할 수 없다.\n다만, 오픈소스 커뮤니티 활동, 학술·교육 목적의 외부 강연, 비영리 활동 등 회사 업무와 이해충돌이 없는 활동은 사전 신고 후 허용할 수 있다.",
        "q": "박정호(대리, 마케팅팀)가 주말에 프리랜서로 디자인 일을 하고 싶다고 합니다. 가능한가요?",
        "result": {
            "result": "conditional",
            "confidence": 0.85,
            "reasoning": "제12조에 따르면 독립적인 영리 활동은 원칙적으로 금지되나, 회사 업무와 이해충돌이 없는 활동은 사전 신고 후 허용할 수 있다고 되어 있습니다. '허용할 수 있다'는 재량 표현이므로 회사 판단에 따라 결정됩니다.",
            "regulations": [{"article": "제12조 (겸업 금지)", "relevance": "높음", "content": "사전 서면 승인 없이 영리 활동 불가, 단 이해충돌 없는 활동은 사전 신고 후 허용할 수 있음"}],
            "cross_references": [],
            "conditions": "회사 업무와 이해충돌이 없어야 하며, 사전 서면 승인을 받아야 합니다. '허용할 수 있다'는 재량 표현으로 회사가 판단합니다.",
            "alternatives": ["사전 서면 승인 신청서를 제출하여 허가 여부를 확인하세요."],
        },
    },
    {
        "reg": "### 제12조 (겸업 금지)\n직원은 회사의 사전 서면 승인 없이 타 기업에 취업하거나 독립적인 영리 활동을 할 수 없다.\n다만, 오픈소스 커뮤니티 활동, 학술·교육 목적의 외부 강연, 비영리 활동 등 회사 업무와 이해충돌이 없는 활동은 사전 신고 후 허용할 수 있다.",
        "q": "최윤서(사원, 개발팀)가 퇴근 후 온라인 강의를 만들어서 판매하고 싶다고 합니다. 되나요?",
        "result": {
            "result": "conditional",
            "confidence": 0.82,
            "reasoning": "제12조에 따르면 독립적인 영리 활동은 사전 서면 승인이 필요합니다. 학술·교육 목적의 외부 강연은 허용할 수 있다고 되어 있으나, 온라인 강의 판매는 영리 활동에 해당하므로 회사의 승인 판단이 필요합니다.",
            "regulations": [{"article": "제12조 (겸업 금지)", "relevance": "높음", "content": "영리 활동은 사전 서면 승인 필요, 교육 목적 활동은 허용할 수 있음"}],
            "cross_references": [],
            "conditions": "학술·교육 목적으로 인정될 수 있는지, 회사 업무와 이해충돌이 없는지 회사가 판단하여 승인 여부를 결정합니다.",
            "alternatives": ["부서장과 상의 후 사전 서면 승인을 신청하세요."],
        },
    },
    # 원격근무 재량
    {
        "reg": "### 제9조 (원격근무)\n회사는 업무 특성과 직원의 근무 효율을 고려하여 원격근무(재택근무)를 허용할 수 있다.\n원격근무 시 다음 사항을 준수하여야 한다: ① VPN을 통한 사내 네트워크 접속, ② 회사 지급 단말기 사용 또는 승인된 개인 단말 사용, ③ 공용 Wi-Fi 사용 금지, ④ 업무 관련 화면 캡처·촬영 금지.",
        "q": "한지민(주임, 기획팀)이 다음 주에 재택근무를 하고 싶다고 합니다. 가능한가요?",
        "result": {
            "result": "conditional",
            "confidence": 0.8,
            "reasoning": "제9조에 따르면 회사는 업무 특성과 근무 효율을 고려하여 원격근무를 '허용할 수 있다'고 되어 있습니다. 이는 재량 표현으로, 회사(부서장)의 판단에 따라 허용 여부가 결정됩니다.",
            "regulations": [{"article": "제9조 (원격근무)", "relevance": "높음", "content": "회사는 업무 특성과 근무 효율을 고려하여 원격근무를 허용할 수 있음"}],
            "cross_references": [],
            "conditions": "업무 특성이 원격근무에 적합해야 하며, 부서장의 승인이 필요합니다. VPN 접속, 회사 단말기 사용 등 보안 수칙을 준수해야 합니다.",
            "alternatives": ["부서장에게 원격근무 신청을 먼저 하세요."],
        },
    },
    {
        "reg": "### 제9조 (원격근무)\n회사는 업무 특성과 직원의 근무 효율을 고려하여 원격근무(재택근무)를 허용할 수 있다.\n원격근무 시 다음 사항을 준수하여야 한다: ① VPN을 통한 사내 네트워크 접속, ② 회사 지급 단말기 사용 또는 승인된 개인 단말 사용, ③ 공용 Wi-Fi 사용 금지, ④ 업무 관련 화면 캡처·촬영 금지.",
        "q": "오승환(과장, 영업팀)이 매주 금요일마다 정기적으로 재택근무를 하고 싶다고 합니다. 가능한가요?",
        "result": {
            "result": "conditional",
            "confidence": 0.75,
            "reasoning": "제9조에 따르면 회사는 원격근무를 '허용할 수 있다'고 되어 있으나, 이는 재량 판단입니다. 매주 정기적인 재택근무는 업무 특성에 따라 허용 여부가 달라질 수 있습니다.",
            "regulations": [{"article": "제9조 (원격근무)", "relevance": "높음", "content": "회사는 업무 특성과 근무 효율을 고려하여 원격근무를 허용할 수 있음"}],
            "cross_references": [],
            "conditions": "영업팀의 업무 특성상 정기적 재택이 가능한지 부서장이 판단해야 하며, 회사 보안 수칙 준수가 전제됩니다.",
            "alternatives": ["부서장과 정기 재택근무 가능 여부를 협의하세요."],
        },
    },
    # 징계 감경 재량
    {
        "reg": "### 징계규정 — 제9조 (징계 감경)\n제9조 (징계 감경)\n다음 각 호에 해당하는 경우 징계를 감경할 수 있다.\n1. 평소 근무 성적이 우수한 경우\n2. 뉘우치는 태도가 현저한 경우\n3. 자진 신고한 경우\n4. 업무 과정에서 불가피한 사유가 인정되는 경우",
        "q": "송민호(대리, 총무팀)가 근무 태만으로 경징계를 받았는데, 평소 근무 성적이 우수합니다. 감경받을 수 있나요?",
        "result": {
            "result": "conditional",
            "confidence": 0.8,
            "reasoning": "제9조에 따르면 평소 근무 성적이 우수한 경우 징계를 '감경할 수 있다'고 되어 있습니다. 이는 재량 표현으로, 인사위원회의 판단에 따라 감경 여부가 결정됩니다.",
            "regulations": [{"article": "징계규정 제9조 (징계 감경)", "relevance": "높음", "content": "근무 성적 우수 시 징계 감경 가능 (재량)"}],
            "cross_references": [],
            "conditions": "평소 근무 성적이 우수하다는 객관적 근거가 있어야 하며, 인사위원회가 감경 여부를 최종 결정합니다.",
            "alternatives": [],
        },
    },
    {
        "reg": "### 징계규정 — 제9조 (징계 감경)\n제9조 (징계 감경)\n다음 각 호에 해당하는 경우 징계를 감경할 수 있다.\n1. 평소 근무 성적이 우수한 경우\n2. 뉘우치는 태도가 현저한 경우\n3. 자진 신고한 경우\n4. 업무 과정에서 불가피한 사유가 인정되는 경우",
        "q": "이수진(사원, 인사팀)이 정보보호 규정을 위반했지만 자진 신고했습니다. 징계가 감경될 수 있나요?",
        "result": {
            "result": "conditional",
            "confidence": 0.82,
            "reasoning": "제9조 제3호에 따르면 자진 신고한 경우 징계를 '감경할 수 있다'고 되어 있습니다. 이는 필수가 아닌 재량이므로 인사위원회 판단에 따릅니다.",
            "regulations": [{"article": "징계규정 제9조 (징계 감경)", "relevance": "높음", "content": "자진 신고 시 징계 감경 가능"}],
            "cross_references": [],
            "conditions": "자진 신고 사실이 인정되어야 하며, 인사위원회가 감경 여부를 재량으로 결정합니다.",
            "alternatives": [],
        },
    },
    # 복리후생 재량
    {
        "reg": "### 복리후생규정 — 제8조 (경조사 지원)\n제8조 (경조사 지원)\n① 직원의 결혼, 회갑, 사망 등 경조사 시 다음과 같이 지원한다.\n② 특별한 사유가 있는 경우 회사는 추가 지원을 할 수 있다.\n③ 경조사 휴가는 취업규칙에 따라 부여한다.",
        "q": "김도현(과장, 인사팀)의 부모님이 입원하셨는데, 경조사 지원 외에 추가 지원을 받을 수 있나요?",
        "result": {
            "result": "conditional",
            "confidence": 0.75,
            "reasoning": "제8조 제2항에 따르면 특별한 사유가 있는 경우 회사는 추가 지원을 '할 수 있다'고 되어 있습니다. 이는 재량 표현으로, 회사의 판단에 따라 결정됩니다.",
            "regulations": [{"article": "복리후생규정 제8조 (경조사 지원)", "relevance": "높음", "content": "특별한 사유 시 추가 지원 가능 (재량)"}],
            "cross_references": [],
            "conditions": "특별한 사유로 인정되어야 하며, 회사의 재량에 따라 추가 지원 여부가 결정됩니다.",
            "alternatives": ["인사부서에 상황을 설명하고 추가 지원 가능 여부를 문의하세요."],
        },
    },
    # 채용 절차 가감 재량
    {
        "reg": "### 인사규정 — 제4조 (채용)\n제4조 (채용)\n회사는 채용 시 직무수행에 필요한 학력, 경력, 기술 자격, 포트폴리오 등을 기준으로 공정하게 심사한다.\n채용 절차는 서류심사, 기술면접(코딩테스트 포함), 임원면접의 단계로 진행하며, 직무 특성에 따라 절차를 가감할 수 있다.",
        "q": "채용 과정에서 코딩테스트를 생략할 수 있나요? 경력직이라 포트폴리오로 대체하고 싶습니다.",
        "result": {
            "result": "conditional",
            "confidence": 0.8,
            "reasoning": "제4조에 따르면 채용 절차는 서류심사, 기술면접, 임원면접 단계로 진행하나, 직무 특성에 따라 절차를 '가감할 수 있다'고 되어 있습니다. 이는 재량 표현으로 회사가 판단합니다.",
            "regulations": [{"article": "인사규정 제4조 (채용)", "relevance": "높음", "content": "직무 특성에 따라 채용 절차를 가감할 수 있음"}],
            "cross_references": [],
            "conditions": "직무 특성상 코딩테스트 생략이 타당한지 채용 담당자/인사부서가 판단해야 합니다.",
            "alternatives": [],
        },
    },
    # 보안사고 대응 재량
    {
        "reg": "### IT보안규정 — 제28조 (보안사고 예방 및 대응)\n제28조 (보안사고 예방 및 대응)\n① 보안사고 발생 시 즉시 정보보호 담당자에게 보고하여야 한다.\n② 사고의 심각도에 따라 CISO는 외부 전문기관에 조사를 의뢰할 수 있다.\n③ 보안사고 재발 방지를 위해 원인 분석 및 개선 대책을 수립하여야 한다.",
        "q": "보안사고가 발생했는데 외부 보안업체에 조사를 맡길 수 있나요?",
        "result": {
            "result": "conditional",
            "confidence": 0.82,
            "reasoning": "제28조 제2항에 따르면 사고의 심각도에 따라 CISO는 외부 전문기관에 조사를 '의뢰할 수 있다'고 되어 있습니다. 이는 재량 표현으로, CISO가 사고 심각도를 판단하여 결정합니다.",
            "regulations": [{"article": "IT보안규정 제28조 (보안사고 예방 및 대응)", "relevance": "높음", "content": "사고 심각도에 따라 CISO가 외부 조사 의뢰 가능 (재량)"}],
            "cross_references": [],
            "conditions": "사고의 심각도가 외부 조사를 필요로 하는 수준인지 CISO가 판단해야 합니다.",
            "alternatives": ["먼저 정보보호 담당자에게 보고하고, CISO 판단을 기다리세요."],
        },
    },
    # 시차출퇴근 재량
    {
        "reg": "### 인사규정 — 제7조 (근무시간)\n제7조 (근무시간)\n① 기본 근무시간은 09:00~18:00이며, 점심시간은 12:00~13:00으로 한다.\n② 회사는 업무 특성을 고려하여 시차출퇴근제를 운영할 수 있다.\n③ 시차출퇴근 적용 시 1일 8시간 근무 원칙은 유지한다.",
        "q": "강민수(대리, 개발팀)가 오전 10시에 출근하고 오후 7시에 퇴근하고 싶다고 합니다. 되나요?",
        "result": {
            "result": "conditional",
            "confidence": 0.8,
            "reasoning": "제7조 제2항에 따르면 회사는 시차출퇴근제를 '운영할 수 있다'고 되어 있습니다. 이는 재량 표현으로 회사가 운영 여부를 결정하며, 1일 8시간 근무 원칙은 유지해야 합니다.",
            "regulations": [{"article": "인사규정 제7조 (근무시간)", "relevance": "높음", "content": "시차출퇴근제 운영 가능 (재량), 1일 8시간 유지"}],
            "cross_references": [],
            "conditions": "시차출퇴근제가 해당 부서에 적용 가능한지 회사/부서장이 판단해야 하며, 1일 8시간 근무를 유지해야 합니다.",
            "alternatives": ["부서장에게 시차출퇴근 가능 여부를 확인하세요."],
        },
    },
    # 교육비 지원 재량
    {
        "reg": "### 복리후생규정 — 제10조 (자기개발 지원)\n제10조 (자기개발 지원)\n① 업무 관련 자격증 취득 시 응시료 및 교재비를 지원한다.\n② 업무 관련 외부 교육 수강 시 회사는 교육비의 전부 또는 일부를 지원할 수 있다.\n③ 지원 한도는 연간 2,000,000원으로 한다.",
        "q": "이하늘(사원, 마케팅팀)이 마케팅 관련 온라인 강좌를 듣고 싶은데, 교육비를 회사에서 지원받을 수 있나요?",
        "result": {
            "result": "conditional",
            "confidence": 0.8,
            "reasoning": "제10조 제2항에 따르면 업무 관련 외부 교육 수강 시 회사는 교육비를 '지원할 수 있다'고 되어 있습니다. 이는 재량 표현으로, 교육이 업무 관련성이 있는지 회사가 판단합니다.",
            "regulations": [{"article": "복리후생규정 제10조 (자기개발 지원)", "relevance": "높음", "content": "업무 관련 외부 교육비 전부 또는 일부 지원 가능 (재량), 연간 한도 200만원"}],
            "cross_references": [],
            "conditions": "해당 교육이 업무와 관련된 것으로 인정되어야 하며, 연간 200만원 한도 내에서 회사가 지원 범위를 결정합니다.",
            "alternatives": ["부서장에게 업무 관련성을 설명하고 교육비 지원을 신청하세요."],
        },
    },
    # 주거 지원 재량
    {
        "reg": "### 복리후생규정 — 제12조 (주거 지원)\n제12조 (주거 지원)\n① 전근 또는 원거리 채용 시 사택 또는 기숙사를 제공할 수 있다.\n② 사택 미제공 시 월 500,000원 한도 내에서 주거수당을 지급할 수 있다.\n③ 주거 지원 기간은 최초 2년으로 하며, 사유에 따라 연장할 수 있다.",
        "q": "지방에서 서울 본사로 전근 온 직원인데, 사택을 제공받을 수 있나요?",
        "result": {
            "result": "conditional",
            "confidence": 0.78,
            "reasoning": "제12조 제1항에 따르면 전근 시 사택 또는 기숙사를 '제공할 수 있다'고 되어 있습니다. 이는 재량 표현으로, 회사의 사택 운영 상황에 따라 결정됩니다.",
            "regulations": [{"article": "복리후생규정 제12조 (주거 지원)", "relevance": "높음", "content": "전근 시 사택/기숙사 제공 가능 (재량), 미제공 시 주거수당 50만원 한도"}],
            "cross_references": [],
            "conditions": "사택 여유 공간이 있는지 등 회사 상황에 따라 결정되며, 사택 미제공 시 주거수당으로 대체될 수 있습니다.",
            "alternatives": ["인사부서에 사택 또는 주거수당 지원을 신청하세요."],
        },
    },
    # 소프트웨어 도입 재량
    {
        "reg": "### IT보안규정 — 제25조 (소프트웨어 개발 보안)\n제25조 (소프트웨어 개발 보안)\n① 소프트웨어 개발 시 시큐어 코딩 원칙을 적용하여야 한다.\n② 개발 환경에서 사용하는 오픈소스 라이브러리는 보안 취약점 검사를 거쳐야 한다.\n③ CISO는 보안 검증이 완료된 개발 도구를 지정할 수 있으며, 미지정 도구의 사용은 사전 승인을 받아야 한다.",
        "q": "새로운 개발 도구를 도입하고 싶은데, CISO 승인 없이 사용해도 되나요?",
        "result": {
            "result": "conditional",
            "confidence": 0.85,
            "reasoning": "제25조 제3항에 따르면 CISO는 보안 검증이 완료된 개발 도구를 '지정할 수 있으며', 미지정 도구는 사전 승인이 필요합니다. CISO가 지정한 도구 목록에 있으면 바로 사용 가능하나, 없으면 사전 승인을 받아야 합니다.",
            "regulations": [{"article": "IT보안규정 제25조 (소프트웨어 개발 보안)", "relevance": "높음", "content": "CISO 지정 도구는 사용 가능, 미지정 도구는 사전 승인 필요"}],
            "cross_references": [],
            "conditions": "해당 도구가 CISO 지정 목록에 있으면 바로 사용 가능하나, 없으면 CISO의 사전 승인이 필요합니다.",
            "alternatives": ["CISO에게 도구 승인을 요청하거나, 이미 지정된 대체 도구를 확인하세요."],
        },
    },
    # 성과급 재량
    {
        "reg": "### 인사규정 — 제18조 (성과급)\n제18조 (성과급)\n① 회사는 경영 실적 및 개인 업적을 고려하여 성과급을 지급할 수 있다.\n② 성과급의 지급 시기, 지급 기준 및 지급액은 매년 경영진이 결정한다.\n③ 수습 기간 중인 직원에게는 성과급을 지급하지 아니할 수 있다.",
        "q": "올해 성과급을 받을 수 있나요? 입사한 지 3개월 됐습니다.",
        "result": {
            "result": "conditional",
            "confidence": 0.75,
            "reasoning": "제18조 제1항에 따르면 회사는 성과급을 '지급할 수 있다'고 되어 있고, 제3항에 따르면 수습 기간 중 직원에게는 성과급을 '지급하지 아니할 수 있다'고 되어 있습니다. 모두 재량 표현이므로 경영진 판단에 따릅니다.",
            "regulations": [{"article": "인사규정 제18조 (성과급)", "relevance": "높음", "content": "성과급 지급은 경영진 재량, 수습 기간 중 미지급 가능"}],
            "cross_references": [],
            "conditions": "수습 기간 여부와 경영 실적, 개인 업적을 경영진이 종합 판단하여 결정합니다.",
            "alternatives": ["인사부서에 수습 기간 중 성과급 지급 기준을 확인하세요."],
        },
    },
]

# ──────────────────────────────────────────────
# no/conditional 경계 강화 데이터
# 동일 규정 + 질문 뉘앙스 차이 → 다른 결과
# ──────────────────────────────────────────────

BOUNDARY_DATA = [
    # "승인 없이" → no / 중립 질문 → conditional
    {
        "reg": "### 제9조 (원격근무)\n회사는 업무 특성과 직원의 근무 효율을 고려하여 원격근무(재택근무)를 허용할 수 있다.\n원격근무 시 다음 사항을 준수하여야 한다: ① VPN을 통한 사내 네트워크 접속, ② 회사 지급 단말기 사용 또는 승인된 개인 단말 사용, ③ 공용 Wi-Fi 사용 금지, ④ 업무 관련 화면 캡처·촬영 금지.",
        "q": "부서장 승인 없이 내일 재택근무해도 되나요?",
        "result": {
            "result": "no",
            "confidence": 0.88,
            "reasoning": "제9조에 따르면 원격근무는 회사가 '허용할 수 있다'는 재량 사항입니다. 부서장 승인 없이 임의로 재택근무를 하는 것은 허용되지 않습니다.",
            "regulations": [{"article": "제9조 (원격근무)", "relevance": "높음", "content": "원격근무는 회사 허용 하에 가능"}],
            "cross_references": [],
            "conditions": None,
            "alternatives": ["부서장에게 재택근무 승인을 먼저 받으세요."],
        },
    },
    {
        "reg": "### 제12조 (겸업 금지)\n직원은 회사의 사전 서면 승인 없이 타 기업에 취업하거나 독립적인 영리 활동을 할 수 없다.\n다만, 오픈소스 커뮤니티 활동, 학술·교육 목적의 외부 강연, 비영리 활동 등 회사 업무와 이해충돌이 없는 활동은 사전 신고 후 허용할 수 있다.",
        "q": "회사 몰래 주말에 배달 알바를 해도 되나요?",
        "result": {
            "result": "no",
            "confidence": 0.92,
            "reasoning": "제12조에 따르면 사전 서면 승인 없이 독립적인 영리 활동을 할 수 없습니다. '회사 몰래'는 사전 승인을 받지 않는 것이므로 명확히 금지됩니다.",
            "regulations": [{"article": "제12조 (겸업 금지)", "relevance": "높음", "content": "사전 서면 승인 없이 영리 활동 불가"}],
            "cross_references": [],
            "conditions": None,
            "alternatives": ["사전 서면 승인을 신청하여 허가를 받으세요."],
        },
    },
    {
        "reg": "### 제12조 (겸업 금지)\n직원은 회사의 사전 서면 승인 없이 타 기업에 취업하거나 독립적인 영리 활동을 할 수 없다.\n다만, 오픈소스 커뮤니티 활동, 학술·교육 목적의 외부 강연, 비영리 활동 등 회사 업무와 이해충돌이 없는 활동은 사전 신고 후 허용할 수 있다.",
        "q": "주말에 배달 알바를 하고 싶은데 가능한가요?",
        "result": {
            "result": "conditional",
            "confidence": 0.8,
            "reasoning": "제12조에 따르면 독립적인 영리 활동은 원칙적으로 사전 서면 승인이 필요합니다. 배달 알바는 영리 활동에 해당하므로 회사의 사전 승인을 받아야 합니다.",
            "regulations": [{"article": "제12조 (겸업 금지)", "relevance": "높음", "content": "영리 활동은 사전 서면 승인 필요, 이해충돌 없는 활동은 허용 가능"}],
            "cross_references": [],
            "conditions": "사전 서면 승인을 받아야 하며, 회사 업무와 이해충돌이 없어야 합니다.",
            "alternatives": ["인사부서에 겸업 승인 신청서를 제출하세요."],
        },
    },
    # 장비 반출 경계
    {
        "reg": "### IT보안규정 — 제15조 (정보자산 분류 및 관리)\n회사는 업무 특성에 따라 정보자산 분류기준을 수립하고, 관리체계 범위 내 모든 정보자산을 식별·분류하여 중요도를 산정한 후 목록을 최신으로 관리한다.\n각 정보자산에는 관리책임자를 지정하고, 자산의 도입·운영·폐기에 이르는 전체 생명주기를 관리한다.\n\n### IT보안규정 — 제19조 (원격접근 및 무선네트워크 통제)\n① 외부에서 사내 정보시스템에 접근할 때는 반드시 VPN을 사용하여야 한다.\n② 회사 장비의 외부 반출 시 관리책임자의 사전 승인을 받아야 한다.\n③ 분실·도난 시 즉시 정보보호 담당자에게 신고하여야 한다.",
        "q": "신고하지 않고 회사 노트북을 집에 가져가도 되나요?",
        "result": {
            "result": "no",
            "confidence": 0.9,
            "reasoning": "제19조 제2항에 따르면 회사 장비의 외부 반출 시 관리책임자의 사전 승인이 필요합니다. 신고 없이 가져가는 것은 규정 위반입니다.",
            "regulations": [{"article": "IT보안규정 제19조 (원격접근 및 무선네트워크 통제)", "relevance": "높음", "content": "장비 외부 반출 시 관리책임자 사전 승인 필요"}],
            "cross_references": [],
            "conditions": None,
            "alternatives": ["관리책임자에게 장비 반출 승인을 받으세요."],
        },
    },
    {
        "reg": "### IT보안규정 — 제15조 (정보자산 분류 및 관리)\n회사는 업무 특성에 따라 정보자산 분류기준을 수립하고, 관리체계 범위 내 모든 정보자산을 식별·분류하여 중요도를 산정한 후 목록을 최신으로 관리한다.\n각 정보자산에는 관리책임자를 지정하고, 자산의 도입·운영·폐기에 이르는 전체 생명주기를 관리한다.\n\n### IT보안규정 — 제19조 (원격접근 및 무선네트워크 통제)\n① 외부에서 사내 정보시스템에 접근할 때는 반드시 VPN을 사용하여야 한다.\n② 회사 장비의 외부 반출 시 관리책임자의 사전 승인을 받아야 한다.\n③ 분실·도난 시 즉시 정보보호 담당자에게 신고하여야 한다.",
        "q": "재택근무를 위해 회사 노트북을 집에 가져가도 되나요?",
        "result": {
            "result": "conditional",
            "confidence": 0.85,
            "reasoning": "제19조 제2항에 따르면 회사 장비의 외부 반출 시 관리책임자의 사전 승인이 필요합니다. 승인을 받으면 가져갈 수 있습니다.",
            "regulations": [{"article": "IT보안규정 제19조 (원격접근 및 무선네트워크 통제)", "relevance": "높음", "content": "장비 외부 반출 시 관리책임자 사전 승인 필요"}],
            "cross_references": [],
            "conditions": "관리책임자의 사전 승인을 받아야 하며, 외부에서는 반드시 VPN을 사용해야 합니다.",
            "alternatives": [],
        },
    },
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="파일 저장 없이 결과만 출력")
    args = parser.parse_args()

    load_system_prompt()

    # 보강 데이터 생성
    augmented = []
    for item in TYPE5_DATA:
        augmented.append(make_example(item["reg"], item["q"], item["result"]))
    for item in BOUNDARY_DATA:
        augmented.append(make_example(item["reg"], item["q"], item["result"]))

    print(f"=== 보강 데이터 생성 완료 ===")
    print(f"  Type 5 재량 표현: {len(TYPE5_DATA)}건")
    print(f"  no/conditional 경계: {len(BOUNDARY_DATA)}건")
    print(f"  합계: {len(augmented)}건")

    if args.dry_run:
        print("\n[dry-run] 처음 3건 미리보기:")
        for i, ex in enumerate(augmented[:3]):
            user_msg = ex["messages"][1]["content"]
            q_start = user_msg.find("## 사용자 질문")
            question = user_msg[q_start + len("## 사용자 질문"):].strip()[:80]
            result = json.loads(ex["messages"][2]["content"])["result"]
            print(f"  [{i+1}] result={result} | Q: {question}")
        return

    # 기존 train.jsonl 로드
    with open(TRAIN_PATH, encoding="utf-8") as f:
        original = [json.loads(line) for line in f]

    print(f"\n  기존 train: {len(original)}건")
    print(f"  보강 후:    {len(original) + len(augmented)}건")

    # 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 원본 백업
    backup_path = OUTPUT_DIR / "train_original_backup.jsonl"
    with open(backup_path, "w", encoding="utf-8") as f:
        for item in original:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  원본 백업: {backup_path}")

    # 보강 데이터만 별도 저장 (확인용)
    aug_only_path = OUTPUT_DIR / "augmented_only.jsonl"
    with open(aug_only_path, "w", encoding="utf-8") as f:
        for item in augmented:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  보강 데이터: {aug_only_path}")

    # 병합 저장
    merged_path = OUTPUT_DIR / "train.jsonl"
    with open(merged_path, "w", encoding="utf-8") as f:
        for item in original + augmented:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  병합 데이터: {merged_path}")

    # eval.jsonl 복사 (변경 없음)
    eval_src = TRAIN_PATH.parent / "eval.jsonl"
    eval_dst = OUTPUT_DIR / "eval.jsonl"
    import shutil
    shutil.copy2(eval_src, eval_dst)
    print(f"  eval 복사: {eval_dst}")

    print(f"\n=== 완료! ===")
    print(f"학습 시 config에서 data.train_path를 다음으로 변경:")
    print(f"  data/training/v1_judgment_v3/train.jsonl")


if __name__ == "__main__":
    main()
