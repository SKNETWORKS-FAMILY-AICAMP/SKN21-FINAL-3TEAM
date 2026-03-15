"""
교차 규정 파인튜닝 데이터 생성 스크립트

멘토 피드백 반영:
- 단일 규정 QA만으로는 모델의 교차 판단/추론 능력이 부족
- 규정 1개(단순) → 2~3개(종합 추론) → 충돌/예외(심화) 다양한 난이도 필요
- Context(규정 원문) + Question + Answer 구조로 RAG 환경에 최적화

사용법:
    # 시나리오 목록만 미리보기
    python scripts/generate_cross_regulation_data.py --dry-run

    # 전체 생성 (시나리오당 10건, 총 ~310건)
    python scripts/generate_cross_regulation_data.py --count 10

    # 특정 유형만 생성
    python scripts/generate_cross_regulation_data.py --level cross_2 --count 5

    # 테스트 (시나리오당 1건)
    python scripts/generate_cross_regulation_data.py --count 1
"""

import argparse
import json
import os
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

# 프로젝트 루트
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ai.llm.prompts import JUDGMENT_SYSTEM_PROMPT

# ── 경로 ──
REGULATION_DIR = BASE_DIR / "data" / "regulations"
OUTPUT_DIR = BASE_DIR / "data" / "training" / "v1_judgment"

SEED = 42
random.seed(SEED)

# Windows 콘솔 UTF-8 출력 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ═══════════════════════════════════════════════════════════════
# 1. 규정 파서 — .txt 파일에서 조항별 추출
# ═══════════════════════════════════════════════════════════════


def parse_regulation_file(filepath: Path) -> dict:
    """
    규정 .txt 파일 → {name, articles: {조항명: 본문}} 파싱.
    예: {"제8조 (시간외근무수당)": "① 법정 근로시간... ⑥ 포괄임금제..."}
    """
    text = filepath.read_text(encoding="utf-8")
    lines = text.strip().split("\n")
    reg_name = lines[0].strip()  # 첫 줄 = 규정 이름

    articles = {}
    current_article = None
    current_lines = []

    for line in lines:
        match = re.match(r"^(제\d+조)\s*(\([^)]+\))?", line.strip())
        if match:
            # 이전 조항 저장
            if current_article:
                articles[current_article] = "\n".join(current_lines).strip()
            article_num = match.group(1)
            article_title = match.group(2) or ""
            current_article = f"{article_num} {article_title}".strip()
            current_lines = [line.strip()]
        elif current_article:
            # 장/부칙 헤더는 건너뛰기
            if re.match(r"^제\d+장\s", line.strip()) or line.strip().startswith("부칙"):
                if current_article:
                    articles[current_article] = "\n".join(current_lines).strip()
                    current_article = None
                    current_lines = []
            else:
                current_lines.append(line)

    # 마지막 조항
    if current_article:
        articles[current_article] = "\n".join(current_lines).strip()

    return {"name": reg_name, "articles": articles}


def load_all_regulations() -> dict:
    """data/regulations/*.txt 전체 로드 → {규정명: {name, articles}}"""
    regulations = {}
    for txt_file in sorted(REGULATION_DIR.glob("*.txt")):
        reg = parse_regulation_file(txt_file)
        regulations[reg["name"]] = reg
        print(f"  {reg['name']}: {len(reg['articles'])}개 조항")
    return regulations


# ═══════════════════════════════════════════════════════════════
# 2. 시나리오 정의 — 난이도별 교차 규정 조합
# ═══════════════════════════════════════════════════════════════

# 규정명 약칭 → 실제 파일명 매핑
REG_ALIASES = {
    "급여": "급여규정",
    "출장": "출장규정",
    "교육": "교육훈련규정",
    "복리": "복리후생규정",
    "징계": "징계규정",
    "개인정보": "개인정보처리규정",
    "윤리": "윤리강령",
    "인사": "인사규정",
    "IT보안": "IT보안규정",
}

SCENARIOS = {
    # ────────────────────────────────────────────────────
    # Level A: 복합 규정 2개 참조 (50~60%)
    # ────────────────────────────────────────────────────
    "cross_2": [
        {
            "regulations": ["급여", "출장"],
            "articles": {"급여": ["제8조"], "출장": ["제6조", "제8조"]},
            "theme": "출장 중 시간외근무수당과 출장비 정산",
            "hint": "출장 중 야근했을 때 시간외근무수당과 출장 일비를 동시에 받을 수 있는지",
        },
        {
            "regulations": ["급여", "출장"],
            "articles": {"급여": ["제12조", "제14조"], "출장": ["제13조", "제14조"]},
            "theme": "출장비 정산과 급여 공제 관계",
            "hint": "출장비 선급 후 기한 내 미정산 시 급여에서 공제되는 절차",
        },
        {
            "regulations": ["급여", "징계"],
            "articles": {"급여": ["제9조", "제10조"], "징계": ["제4조", "제5조"]},
            "theme": "징계받은 직원의 상여금과 성과급",
            "hint": "감봉/정직 징계 중 상여금이나 성과급을 받을 수 있는지",
        },
        {
            "regulations": ["급여", "징계"],
            "articles": {"급여": ["제5조", "제6조"], "징계": ["제4조", "제5조"]},
            "theme": "직위해제 시 급여/직책수당 처리",
            "hint": "직위해제된 팀장의 기본급, 직책수당 지급 기준",
        },
        {
            "regulations": ["징계", "개인정보"],
            "articles": {"징계": ["제7조"], "개인정보": ["제18조"]},
            "theme": "개인정보 유출 직원의 징계 처리",
            "hint": "개인정보 침해사고 발생 시 관여 직원에 대한 징계 수준과 절차",
        },
        {
            "regulations": ["징계", "윤리"],
            "articles": {"징계": ["제7조", "제6조"], "윤리": ["제7조", "제8조"]},
            "theme": "금품수수 적발 시 징계",
            "hint": "거래처로부터 금품 수수한 직원의 윤리강령 위반과 징계 기준",
        },
        {
            "regulations": ["교육", "복리"],
            "articles": {"교육": ["제7조", "제10조"], "복리": ["제15조"]},
            "theme": "외부 교육비와 복지포인트 사용",
            "hint": "사외교육비를 교육훈련 지원과 복지포인트 중 어디서 받는지",
        },
        {
            "regulations": ["교육", "급여"],
            "articles": {"교육": ["제8조"], "급여": ["제7조"]},
            "theme": "자격증 취득 시 축하금과 월 수당",
            "hint": "자격증 취득 축하금과 매월 자격수당을 동시에 받을 수 있는지",
        },
        {
            "regulations": ["출장", "교육"],
            "articles": {"출장": ["제4조", "제6조", "제7조"], "교육": ["제7조"]},
            "theme": "교육 목적 출장의 비용 처리",
            "hint": "지방 사외교육 참석 시 교통비/숙박비는 출장비인지 교육비인지",
        },
        {
            "regulations": ["개인정보", "윤리"],
            "articles": {"개인정보": ["제12조", "제11조"], "윤리": ["제11조", "제10조"]},
            "theme": "퇴직 시 개인정보 접근 권한과 기밀유지",
            "hint": "퇴직 직원의 개인정보 접근 권한 말소 절차와 기밀유지 의무 범위",
        },
        {
            "regulations": ["복리", "징계"],
            "articles": {"복리": ["제15조", "제4조"], "징계": ["제4조", "제5조"]},
            "theme": "징계 기간 중 복리후생 적용 범위",
            "hint": "정직 기간에도 건강검진, 복지포인트를 받을 수 있는지",
        },
        {
            "regulations": ["복리", "급여"],
            "articles": {"복리": ["제12조", "제13조"], "급여": ["제4조"]},
            "theme": "교통비/식대 중복 지원 여부",
            "hint": "통근버스 미운행 지역 직원의 교통비 지급과 급여 구성의 관계",
        },
        # ── 인사규정 관련 교차 ──
        {
            "regulations": ["인사", "IT보안"],
            "articles": {"인사": ["제9조"], "IT보안": ["제19조"]},
            "theme": "원격근무 시 VPN/MFA 보안 요건",
            "hint": "재택근무 승인받은 직원이 VPN 없이 카페 Wi-Fi로 회사 시스템에 접속하려는 경우",
        },
        {
            "regulations": ["인사", "IT보안"],
            "articles": {"인사": ["제11조"], "IT보안": ["제26조"]},
            "theme": "퇴직 직원의 소스코드 접근과 비밀유지",
            "hint": "퇴직 예정 직원이 개인 GitHub에 회사 프로젝트 코드를 백업하려는 경우",
        },
        {
            "regulations": ["인사", "IT보안"],
            "articles": {"인사": ["제12조"], "IT보안": ["제27조"]},
            "theme": "겸업 금지와 오픈소스 기여 허용 범위",
            "hint": "개발자가 퇴근 후 외부 오픈소스 프로젝트에 코드를 기여하는 것이 겸업에 해당하는지",
        },
        {
            "regulations": ["인사", "IT보안"],
            "articles": {"인사": ["제6조"], "IT보안": ["제17조"]},
            "theme": "수습 직원의 시스템 접근 권한 부여",
            "hint": "수습 기간 중인 신입 개발자에게 운영 DB 접근 권한을 부여할 수 있는지",
        },
        {
            "regulations": ["인사", "개인정보"],
            "articles": {"인사": ["제4조"], "개인정보": ["제10조", "제11조"]},
            "theme": "채용 과정 개인정보 수집과 파기",
            "hint": "불합격자의 이력서와 개인정보를 얼마나 보관하고 어떻게 파기해야 하는지",
        },
        {
            "regulations": ["인사", "급여"],
            "articles": {"인사": ["제7조"], "급여": ["제8조"]},
            "theme": "유연근무제와 시간외근무수당 산정",
            "hint": "선택적 근로시간제를 적용받는 직원이 야간에 근무한 경우 가산수당 지급 기준",
        },
        # ── IT보안규정 관련 교차 ──
        {
            "regulations": ["IT보안", "징계"],
            "articles": {"IT보안": ["제30조"], "징계": ["제7조"]},
            "theme": "IT보안 규정 위반 시 징계 절차",
            "hint": "소스코드 저장소에 API 키를 커밋한 직원에 대한 징계 수준과 절차",
        },
        {
            "regulations": ["IT보안", "교육"],
            "articles": {"IT보안": ["제29조"], "교육": ["제6조"]},
            "theme": "정보보호 교육 미이수와 시스템 접근 제한",
            "hint": "법정 정보보호교육을 미이수한 직원의 시스템 접근 제한 범위와 교육 이수 의무",
        },
        # ── Phase 1 마무리: IT보안 후반부 + 미커버 조합 ──
        {
            "regulations": ["IT보안", "개인정보"],
            "articles": {"IT보안": ["제24조"], "개인정보": ["제12조"]},
            "theme": "접속기록 보관 의무와 개인정보 처리 로그",
            "hint": "개인정보처리시스템 접속기록 보관기간과 IT보안규정 로그 관리 기준의 관계",
        },
        {
            "regulations": ["IT보안", "개인정보"],
            "articles": {"IT보안": ["제23조"], "개인정보": ["제11조"]},
            "theme": "백업 데이터의 개인정보 보호 및 파기",
            "hint": "백업 데이터에 포함된 개인정보의 보유기간 만료 시 백업에서도 삭제해야 하는지",
        },
        {
            "regulations": ["IT보안", "급여"],
            "articles": {"IT보안": ["제22조"], "급여": ["제8조"]},
            "theme": "심야 장애 대응과 시간외근무수당",
            "hint": "새벽 2시 서버 장애로 긴급 출근한 개발자의 야근수당과 대체휴무 적용",
        },
        {
            "regulations": ["IT보안", "윤리"],
            "articles": {"IT보안": ["제20조"], "윤리": ["제10조"]},
            "theme": "인터넷 접속 제한과 회사 자산 사적 이용",
            "hint": "업무 시간 중 개인정보처리 단말에서 개인 SNS를 접속하는 것이 규정 위반인지",
        },
        {
            "regulations": ["IT보안", "복리"],
            "articles": {"IT보안": ["제28조"], "복리": ["제5조"]},
            "theme": "보안사고 대응 중 부상과 산재/의료비 지원",
            "hint": "보안사고 긴급 대응 중 야근으로 건강 악화 시 회사 의료비 지원 대상인지",
        },
        {
            "regulations": ["출장", "IT보안"],
            "articles": {"출장": ["제9조"], "IT보안": ["제19조"]},
            "theme": "해외출장 중 보안장비 반입과 원격접근",
            "hint": "해외출장 시 노트북 반입 규정과 호텔 Wi-Fi에서 VPN 접속 요건",
        },
        {
            "regulations": ["징계", "인사"],
            "articles": {"징계": ["제5조", "제9조"], "인사": ["제6조"]},
            "theme": "수습 직원의 징계와 본채용 거부",
            "hint": "수습 기간 중 경징계를 받은 직원의 본채용 거부 사유 해당 여부",
        },
        {
            "regulations": ["교육", "인사"],
            "articles": {"교육": ["제6조", "제9조"], "인사": ["제10조"]},
            "theme": "법정교육 미이수와 인사평가 불이익",
            "hint": "법정 의무교육을 미이수한 직원에게 인사평가 불이익을 줄 수 있는지",
        },
    ],

    # ────────────────────────────────────────────────────
    # Level B: 복합 규정 3개 참조 (종합 추론)
    # ────────────────────────────────────────────────────
    "cross_3": [
        {
            "regulations": ["급여", "출장", "복리"],
            "articles": {"급여": ["제8조"], "출장": ["제9조", "제11조"], "복리": ["제15조"]},
            "theme": "해외출장 중 경비/수당/복지 종합",
            "hint": "해외출장 중 시간외근무수당 + 해외출장 일비/식비 + 복지포인트 사용 가능 범위",
        },
        {
            "regulations": ["징계", "개인정보", "윤리"],
            "articles": {"징계": ["제7조", "제8조"], "개인정보": ["제18조"], "윤리": ["제11조", "제19조"]},
            "theme": "정보유출 + 기밀 위반 + 은폐 시 종합 처리",
            "hint": "고객 개인정보를 외부에 유출하고 이를 은폐한 직원의 징계 가중 사유까지 종합 판단",
        },
        {
            "regulations": ["급여", "징계", "복리"],
            "articles": {"급여": ["제9조", "제10조"], "징계": ["제4조", "제5조"], "복리": ["제15조", "제10조"]},
            "theme": "징계자의 급여/복지 종합 처리",
            "hint": "정직 징계를 받은 직원의 상여금, 성과급, 자녀학자금, 복지포인트 적용 범위",
        },
        {
            "regulations": ["교육", "복리", "급여"],
            "articles": {"교육": ["제8조", "제9조"], "복리": ["제15조"], "급여": ["제7조"]},
            "theme": "자격증/학위 취득 시 종합 지원 한도",
            "hint": "대학원 진학 시 학비 지원 + 자격증 취득 축하금 + 매월 자격수당 동시 적용 가능한지",
        },
        {
            "regulations": ["출장", "교육", "급여"],
            "articles": {"출장": ["제4조", "제6조", "제7조"], "교육": ["제7조"], "급여": ["제8조"]},
            "theme": "교육출장 비용 + 수당 종합 정산",
            "hint": "지방 사외교육(2박3일) 참석 시 출장비(교통/숙박) + 교육비 + 시간외수당 정산 방법",
        },
        {
            "regulations": ["윤리", "징계", "급여"],
            "articles": {"윤리": ["제6조", "제7조"], "징계": ["제7조"], "급여": ["제9조"]},
            "theme": "겸직/부정청탁 적발 시 종합 처리",
            "hint": "무단 겸직이 적발된 직원의 중징계 수준과 상여금/성과급에 미치는 영향",
        },
        {
            "regulations": ["개인정보", "교육", "징계"],
            "articles": {"개인정보": ["제12조"], "교육": ["제6조"], "징계": ["제6조"]},
            "theme": "보안교육 미이수 + 접근권한 위반",
            "hint": "법정 개인정보보호교육을 미이수한 직원이 개인정보시스템에 무단 접근한 경우의 처리",
        },
        # ── 인사/IT보안 포함 3개 규정 교차 ──
        {
            "regulations": ["인사", "IT보안", "개인정보"],
            "articles": {"인사": ["제9조"], "IT보안": ["제19조"], "개인정보": ["제12조"]},
            "theme": "원격근무 중 개인정보시스템 접근 종합 보안 요건",
            "hint": "재택근무 중 개인정보 처리 업무를 수행할 때 VPN/MFA/접근권한 종합 절차",
        },
        {
            "regulations": ["인사", "IT보안", "징계"],
            "articles": {"인사": ["제11조"], "IT보안": ["제26조"], "징계": ["제7조"]},
            "theme": "소스코드 유출과 비밀유지 위반 시 종합 처리",
            "hint": "퇴직 직원이 재직 중 개인 이메일로 소스코드를 유출한 사실이 적발된 경우의 처리",
        },
        {
            "regulations": ["IT보안", "인사", "급여"],
            "articles": {"IT보안": ["제21조"], "인사": ["제7조"], "급여": ["제8조"]},
            "theme": "긴급 변경관리와 야간 근무 시간외수당",
            "hint": "새벽 긴급 장애로 서버 변경작업 수행 시 사후승인 절차와 시간외근무수당 지급",
        },
        {
            "regulations": ["인사", "IT보안", "윤리"],
            "articles": {"인사": ["제12조"], "IT보안": ["제27조"], "윤리": ["제6조"]},
            "theme": "오픈소스 기여와 겸업·이해충돌 종합 판단",
            "hint": "직원이 퇴근 후 경쟁사의 오픈소스 프로젝트에 회사 업무 관련 기술을 기여하려는 경우",
        },
        # ── Phase 1 마무리: IT보안 후반부 포함 3개 교차 ──
        {
            "regulations": ["IT보안", "개인정보", "징계"],
            "articles": {"IT보안": ["제24조", "제28조"], "개인정보": ["제18조"], "징계": ["제7조"]},
            "theme": "접속기록 미관리로 인한 개인정보 유출사고와 징계",
            "hint": "접속기록 점검을 소홀히 하여 비정상 대량 조회를 탐지하지 못해 개인정보가 유출된 경우의 책임과 징계",
        },
        {
            "regulations": ["IT보안", "인사", "교육"],
            "articles": {"IT보안": ["제20조", "제29조"], "인사": ["제9조"], "교육": ["제6조"]},
            "theme": "재택근무 직원의 보안교육 미이수와 인터넷 접속 제한",
            "hint": "재택근무 중인 직원이 보안교육을 미이수하여 인터넷 접속 제한 조치를 받은 경우의 업무 수행 가능 여부",
        },
        {
            "regulations": ["IT보안", "출장", "개인정보"],
            "articles": {"IT보안": ["제23조", "제19조"], "출장": ["제9조"], "개인정보": ["제12조"]},
            "theme": "해외출장 중 노트북 분실과 데이터 백업·개인정보 유출 대응",
            "hint": "해외출장 중 업무용 노트북(개인정보 포함)을 분실했을 때의 백업 복구와 유출 신고 절차",
        },
    ],

    # ────────────────────────────────────────────────────
    # Level C: 충돌/예외 시나리오 (심화 추론)
    # ────────────────────────────────────────────────────
    "conflict": [
        {
            "regulations": ["급여", "징계"],
            "articles": {"급여": ["제9조", "제10조"], "징계": ["제5조"]},
            "theme": "정직 중 상여금 vs 성과급 - 규정 해석 차이",
            "hint": "정직 기간에 상여금은 명시적으로 미지급이나, 전년도 성과급은 별도 평가 기준이므로 지급해야 하는지",
            "conflict_type": "동일 징계에 대해 상여금/성과급 규정이 각각 다르게 적용",
        },
        {
            "regulations": ["출장", "급여"],
            "articles": {"출장": ["제6조"], "급여": ["제6조"]},
            "theme": "보직자의 출장 교통비 기준 - 직급별 차이",
            "hint": "팀장(M1)의 출장 교통비가 KTX 일반석(출장규정)인데, 직책수당을 받는 보직자로서 특실 이용은 가능한지",
            "conflict_type": "출장규정의 직급 기준과 급여규정의 직책 기준 불일치",
        },
        {
            "regulations": ["교육", "복리"],
            "articles": {"교육": ["제10조"], "복리": ["제15조"]},
            "theme": "온라인교육비 vs 복지포인트 중복 사용 가능 여부",
            "hint": "연간 50만원 온라인교육비와 50만원 복지포인트를 같은 Udemy 강의에 이중으로 사용 가능한지",
            "conflict_type": "두 지원제도의 중복 적용 범위가 명확하지 않음",
        },
        {
            "regulations": ["교육", "급여"],
            "articles": {"교육": ["제8조"], "급여": ["제7조"]},
            "theme": "자격증 축하금 반환 vs 자격수당 - 퇴사 시",
            "hint": "자격증 취득 후 1년 6개월 만에 퇴사 시 축하금 50% 반환 의무가 있는데, 그동안 받은 자격수당은 반환하는지",
            "conflict_type": "교육규정의 반환 의무와 급여규정의 수당 지급이 별개 조항",
        },
        {
            "regulations": ["징계", "윤리"],
            "articles": {"징계": ["제9조"], "윤리": ["제15조", "제16조"]},
            "theme": "내부고발자 보호 vs 본인 관여 시 징계 감경",
            "hint": "윤리 위반을 내부고발했지만 본인도 경미하게 관여한 경우, 제보자 보호 대상인지 징계 대상인지",
            "conflict_type": "윤리강령의 보호 규정과 징계규정의 감경 사유 충돌",
        },
        {
            "regulations": ["개인정보", "윤리", "징계"],
            "articles": {"개인정보": ["제17조"], "윤리": ["제15조"], "징계": ["제11조"]},
            "theme": "징계 조사 중 본인 개인정보 삭제 요구",
            "hint": "징계 조사를 받는 직원이 자기 개인정보(접속 로그 등) 삭제를 요구하면 응해야 하는지",
            "conflict_type": "정보주체 권리와 사내 징계 조사 절차의 충돌",
        },
        {
            "regulations": ["복리", "출장"],
            "articles": {"복리": ["제5조"], "출장": ["제12조"]},
            "theme": "해외출장 중 상해 - 보험 vs 의료비 중복 적용",
            "hint": "해외출장 중 다쳐서 입원했을 때 해외여행자보험 보상금과 회사 의료비 지원이 중복 적용되는지",
            "conflict_type": "출장규정의 보험과 복리후생의 의료비 지원 범위 중복",
        },
        # ── 인사/IT보안 관련 충돌 시나리오 ──
        {
            "regulations": ["인사", "IT보안"],
            "articles": {"인사": ["제9조"], "IT보안": ["제19조"]},
            "theme": "원격근무 허용 vs VPN/MFA 장비 미비 시 접속 불가",
            "hint": "인사규정상 원격근무가 승인되었지만 회사 지급 VPN 장비가 아직 없는 직원이 개인 VPN으로 접속하려는 경우",
            "conflict_type": "인사규정의 원격근무 허용과 IT보안규정의 회사 지급 VPN 필수 요건 불일치",
        },
        {
            "regulations": ["인사", "IT보안"],
            "articles": {"인사": ["제12조"], "IT보안": ["제27조"]},
            "theme": "겸업 금지 예외 vs 오픈소스 기여 승인 절차 차이",
            "hint": "인사규정은 오픈소스 활동을 사전 신고로 허용하지만 IT보안규정은 팀장 승인+법무팀 검토가 필요한 경우",
            "conflict_type": "인사규정(사전 신고만)과 IT보안규정(팀장+법무팀 승인)의 승인 수준 차이",
        },
        {
            "regulations": ["IT보안", "징계"],
            "articles": {"IT보안": ["제30조"], "징계": ["제4조", "제5조"]},
            "theme": "IT보안 위반 제재 등급 vs 징계규정 절차 불일치",
            "hint": "IT보안규정은 즉시 해고까지 규정하지만 징계규정은 인사위원회 의결을 거쳐야 하는 경우",
            "conflict_type": "IT보안규정의 제재 범위와 징계규정의 절차적 요건 충돌",
        },
        # ── Phase 2: conflict 시나리오 확장 (10개 추가) ──
        {
            "regulations": ["인사", "교육"],
            "articles": {"인사": ["제6조"], "교육": ["제8조", "제10조"]},
            "theme": "수습기간 교육비 지원 반환 의무 충돌",
            "hint": "수습기간 중 회사 비용으로 외부교육을 받았으나 수습 해제(본채용 거부)된 경우 교육비 반환 의무가 있는지",
            "conflict_type": "인사규정의 수습 해제와 교육규정의 교육비 반환 조건 불일치",
        },
        {
            "regulations": ["복리", "개인정보"],
            "articles": {"복리": ["제5조"], "개인정보": ["제10조", "제17조"]},
            "theme": "건강검진 결과 열람 권한 vs 개인정보 보호",
            "hint": "회사 단체 건강검진 결과를 부서장이 열람하여 업무 배치에 반영하려는 경우 개인정보 침해인지",
            "conflict_type": "복리후생규정의 건강검진 관리와 개인정보규정의 민감정보 보호 충돌",
        },
        {
            "regulations": ["인사", "윤리"],
            "articles": {"인사": ["제12조"], "윤리": ["제6조", "제7조"]},
            "theme": "배우자 거래처 근무 시 이해충돌 신고 vs 겸직 신고",
            "hint": "배우자가 회사 주요 거래처에 근무하는 직원이 이해충돌 신고만 하면 되는지, 겸직과 별도로 처리하는지",
            "conflict_type": "인사규정의 겸직 신고 절차와 윤리강령의 이해충돌 신고 절차 이중 적용",
        },
        {
            "regulations": ["교육", "징계"],
            "articles": {"교육": ["제6조", "제9조"], "징계": ["제6조"]},
            "theme": "법정교육 미이수 면책 사유 vs 징계 면제",
            "hint": "프로젝트 마감 업무 과중으로 법정 의무교육을 기한 내 이수하지 못한 직원에 대한 징계 여부",
            "conflict_type": "교육규정의 이수 의무와 징계규정의 면책 사유(업무상 불가피) 적용 범위 차이",
        },
        {
            "regulations": ["복리", "인사"],
            "articles": {"복리": ["제15조", "제10조"], "인사": ["제8조"]},
            "theme": "육아휴직 복직 후 복지포인트 소급 적용 여부",
            "hint": "1년 육아휴직 후 복직한 직원의 휴직 기간 중 미사용 복지포인트와 자녀학자금 소급 지급 가능 여부",
            "conflict_type": "복리후생규정의 재직자 기준과 인사규정의 휴직 기간 처리 불일치",
        },
        {
            "regulations": ["급여", "인사"],
            "articles": {"급여": ["제4조", "제10조"], "인사": ["제10조"]},
            "theme": "인사평가 최하등급에 따른 연봉 삭감 가능 여부",
            "hint": "인사평가 2년 연속 D등급을 받은 직원의 기본급을 삭감할 수 있는지, 성과급만 차등인지",
            "conflict_type": "급여규정의 기본급 보장과 인사규정의 저성과자 관리 조치 범위 충돌",
        },
        {
            "regulations": ["윤리", "개인정보"],
            "articles": {"윤리": ["제15조", "제16조"], "개인정보": ["제17조", "제11조"]},
            "theme": "내부고발 제보자 신원 보호 vs 징계 조사 개인정보 처리",
            "hint": "내부고발로 징계 조사가 개시되었을 때 피조사자가 제보자의 신원 공개를 요구하는 경우",
            "conflict_type": "윤리강령의 제보자 보호와 개인정보규정의 정보주체 권리 충돌",
        },
        {
            "regulations": ["IT보안", "교육"],
            "articles": {"IT보안": ["제29조"], "교육": ["제8조", "제10조"]},
            "theme": "보안 자격증 교육비 vs 사외교육비 한도 이중 적용",
            "hint": "CISSP 자격증 취득을 위한 200만원 교육비를 IT보안교육 예산과 사외교육비 지원 양쪽에서 받을 수 있는지",
            "conflict_type": "IT보안규정의 보안교육 지원과 교육규정의 사외교육비 한도 중복 적용 문제",
        },
        {
            "regulations": ["출장", "복리"],
            "articles": {"출장": ["제12조", "제9조"], "복리": ["제5조"]},
            "theme": "해외출장 중 질병 - 출장보험 vs 의료비 지원 우선순위",
            "hint": "해외출장 중 급성 맹장염으로 현지 입원한 직원의 치료비를 출장보험과 회사 의료비 지원 중 어디서 처리하는지",
            "conflict_type": "출장규정의 여행자보험과 복리후생규정의 의료비 지원 우선순위 미명시",
        },
        {
            "regulations": ["급여", "복리"],
            "articles": {"급여": ["제7조", "제8조"], "복리": ["제12조", "제15조"]},
            "theme": "자격수당과 복지포인트 학습비 중복 수혜",
            "hint": "자격증 유지를 위한 보수교육비를 매월 자격수당에서 충당해야 하는지, 별도로 복지포인트를 사용할 수 있는지",
            "conflict_type": "급여규정의 자격수당 목적과 복리후생규정의 자기개발비 지원 범위 중복",
        },
    ],
}

# 노이즈 시나리오 — 관련+무관 규정 혼합 (모델이 관련 규정만 선별하는 능력 학습)
NOISE_SCENARIOS = [
    {
        "regulations": ["급여", "출장"],
        "articles": {"급여": ["제8조"], "출장": ["제8조"]},
        "theme": "출장 중 식비와 접대비 중복 정산",
        "hint": "출장 중 거래처 접대 식사를 한 경우 식비와 접대비가 겹치는지",
    },
    {
        "regulations": ["징계"],
        "articles": {"징계": ["제6조", "제9조"]},
        "theme": "경징계 자진 신고 시 감경 여부",
        "hint": "경미한 복무규율 위반이지만 자진 신고한 직원의 징계 감경 가능 여부",
    },
    {
        "regulations": ["교육", "급여"],
        "articles": {"교육": ["제8조"], "급여": ["제7조"]},
        "theme": "자격증 취득 지원 종합",
        "hint": "정보보안기사 자격증 응시료 지원과 합격 후 축하금 및 수당",
    },
    {
        "regulations": ["복리"],
        "articles": {"복리": ["제7조", "제8조"]},
        "theme": "결혼 시 경조금과 경조휴가",
        "hint": "본인 결혼 시 경조금 금액과 휴가 일수",
    },
    {
        "regulations": ["개인정보"],
        "articles": {"개인정보": ["제10조", "제11조"]},
        "theme": "개인정보 보유기간과 파기 방법",
        "hint": "퇴직자 인사정보의 보유기간과 파기 절차",
    },
    {
        "regulations": ["인사"],
        "articles": {"인사": ["제8조", "제9조"]},
        "theme": "연차휴가 중 원격근무 가능 여부",
        "hint": "연차휴가 중 급한 업무 요청을 받아 재택에서 잠깐 일한 경우 휴가 처리",
    },
    {
        "regulations": ["IT보안"],
        "articles": {"IT보안": ["제25조", "제26조"]},
        "theme": "코드 리뷰 없이 배포 가능 여부",
        "hint": "긴급 핫픽스를 코드 리뷰 없이 바로 배포해도 되는지",
    },
    # ── Phase 1 마무리: distractor 비율 보정용 noise 시나리오 확장 ──
    {
        "regulations": ["IT보안"],
        "articles": {"IT보안": ["제20조", "제22조"]},
        "theme": "서버 인터넷 접속 제한과 장애 모니터링",
        "hint": "운영 서버에서 외부 API 호출이 필요한 경우 프록시 설정 절차",
    },
    {
        "regulations": ["IT보안"],
        "articles": {"IT보안": ["제23조", "제24조"]},
        "theme": "백업 데이터 복구 테스트와 로그 보관",
        "hint": "반기 복구 테스트 미실시 시 조치사항과 로그 보관 기간 기준",
    },
    {
        "regulations": ["IT보안"],
        "articles": {"IT보안": ["제28조"]},
        "theme": "보안사고 발생 시 보고 절차",
        "hint": "랜섬웨어 감염이 의심되는 경우 직원이 취해야 할 즉각 조치와 보고 채널",
    },
    {
        "regulations": ["급여"],
        "articles": {"급여": ["제4조", "제5조"]},
        "theme": "기본급 체계와 호봉 산정",
        "hint": "경력직 입사자의 호봉 산정 기준과 이전 경력 인정 범위",
    },
    {
        "regulations": ["출장"],
        "articles": {"출장": ["제4조", "제6조"]},
        "theme": "국내 출장 교통비 기준",
        "hint": "KTX 노선이 없는 지방 출장 시 자가용 유류비 정산 가능 여부",
    },
    {
        "regulations": ["윤리"],
        "articles": {"윤리": ["제6조", "제7조"]},
        "theme": "이해충돌 신고 의무",
        "hint": "배우자가 거래처 직원인 경우 이해충돌 신고 대상인지",
    },
    {
        "regulations": ["윤리"],
        "articles": {"윤리": ["제15조", "제16조"]},
        "theme": "내부고발 절차와 신원보호",
        "hint": "동료의 횡령을 목격한 직원의 내부고발 절차와 불이익 금지 보장",
    },
    {
        "regulations": ["교육"],
        "articles": {"교육": ["제6조", "제7조"]},
        "theme": "법정 의무교육 종류와 이수 기한",
        "hint": "직장 내 성희롱 예방교육과 산업안전보건교육의 연간 이수 시간",
    },
    {
        "regulations": ["인사"],
        "articles": {"인사": ["제4조", "제5조"]},
        "theme": "채용 절차와 서류 제출",
        "hint": "최종 면접 합격 후 건강검진서와 신원조회서 제출 기한",
    },
    {
        "regulations": ["인사"],
        "articles": {"인사": ["제7조", "제8조"]},
        "theme": "근로시간과 연차휴가 산정",
        "hint": "입사 1년 미만 직원의 월별 연차 발생 기준과 사용 방법",
    },
    {
        "regulations": ["징계"],
        "articles": {"징계": ["제4조", "제7조"]},
        "theme": "징계 종류와 중징계 사유",
        "hint": "무단결근 3일 이상 시 적용되는 징계 종류와 절차",
    },
    {
        "regulations": ["개인정보"],
        "articles": {"개인정보": ["제17조", "제18조"]},
        "theme": "개인정보 유출사고 대응 절차",
        "hint": "직원 개인정보가 해킹으로 유출된 경우 72시간 내 통지 의무와 신고 절차",
    },
    {
        "regulations": ["복리"],
        "articles": {"복리": ["제10조", "제11조"]},
        "theme": "자녀 학자금 지원 범위",
        "hint": "대학생 자녀의 등록금 지원 한도와 대학원 포함 여부",
    },
]


# ═══════════════════════════════════════════════════════════════
# 3. 규정 Context 구성
# ═══════════════════════════════════════════════════════════════


def find_article(reg_data: dict, article_key: str) -> tuple[str, str] | None:
    """규정 데이터에서 '제N조'를 포함하는 조항 찾기 → (조항명, 본문)"""
    for full_name, text in reg_data["articles"].items():
        if article_key in full_name:
            return full_name, text
    return None


def build_regulation_context(regulations: dict, scenario: dict) -> str:
    """시나리오에 맞는 규정 조항을 Context 문자열로 구성"""
    parts = []

    for reg_alias in scenario["regulations"]:
        reg_name = REG_ALIASES.get(reg_alias)
        if not reg_name or reg_name not in regulations:
            continue

        reg_data = regulations[reg_name]
        target_articles = scenario["articles"].get(reg_alias, [])

        for article_key in target_articles:
            result = find_article(reg_data, article_key)
            if result:
                full_name, text = result
                parts.append(f"### {reg_name} — {full_name}")
                parts.append(text)
                parts.append("")

    return "\n".join(parts)


def build_noise_context(regulations: dict, scenario: dict, num_noise: int = 2) -> str:
    """관련 규정 + 무관 규정(노이즈)을 섞어서 Context 구성"""
    # 관련 규정
    related = build_regulation_context(regulations, scenario)

    # 무관 규정 랜덤 선택
    related_regs = set(scenario["regulations"])
    available = [a for a in REG_ALIASES if a not in related_regs]
    noise_picks = random.sample(available, min(num_noise, len(available)))

    noise_parts = []
    for alias in noise_picks:
        reg_name = REG_ALIASES[alias]
        reg_data = regulations.get(reg_name)
        if not reg_data:
            continue
        article_keys = list(reg_data["articles"].keys())
        if article_keys:
            picked = random.sample(article_keys, min(2, len(article_keys)))
            for ak in picked:
                noise_parts.append(f"### {reg_name} — {ak}")
                noise_parts.append(reg_data["articles"][ak])
                noise_parts.append("")

    return related + "\n" + "\n".join(noise_parts)


# ═══════════════════════════════════════════════════════════════
# 4. LLM 기반 QA 생성
# ═══════════════════════════════════════════════════════════════

# ── RAFT (Retrieval-Augmented Fine-Tuning) 적용 ──
# 논문: arxiv 2403.10131
# 핵심: Oracle(관련) 문서 + Distractor(방해꾼) 문서를 함께 제공하여
#       모델이 관련 문서만 골라 추론하는 능력을 학습
# P_RAFT: Oracle 문서가 포함되는 비율 (80% 권장)
# 나머지 20%는 Distractor만 → "no_regulation" 대응 능력 학습

P_RAFT = 0.8  # 80%는 Oracle+Distractor, 20%는 Oracle만 또는 Distractor만

GENERATION_PROMPT_TEMPLATE = """\
당신은 기업 규정 기반 QA 학습 데이터를 생성하는 전문가입니다.

아래 규정 조항들을 읽고, 주어진 주제에 맞는 **현실적인 직장 상황 질문 1개**와 **규정 기반 JSON 답변 1개**를 생성하세요.

## 규정 조항
{regulation_context}

## 생성 주제
{theme}

## 상황 힌트
{hint}

## 생성 규칙

**질문:**
- 실제 직원이 할 법한 자연스러운 상황 질문 (조항 번호를 직접 언급하지 마세요)
- 반드시 구체적인 가상 직원명, 직급, 부서를 포함하세요 (예: "박서연(과장, 마케팅팀)이...")
- 단순 정보 확인이 아닌, 판단이 필요한 복합적 상황을 만드세요

**답변 JSON:**
- reasoning은 반드시 **Chain-of-Thought(단계별 추론)** 방식으로 작성하세요:
  1) 제공된 규정 중 질문과 관련 있는 규정을 먼저 식별하세요
  2) 관련 없는 규정이 있다면 왜 무관한지 간단히 언급하세요
  3) 관련 규정의 구체적 조항을 인용하며 판단 근거를 설명하세요
  4) 최종 판단(result)과 그 이유를 명확히 서술하세요
- regulations 배열에 참조한 **모든** 규정 조항을 포함하세요 (최소 {min_regulations}개)
- cross_references 배열에 규정 간 관계를 반드시 기술하세요
- **result가 "conditional"이면 conditions 필드에 조건을 반드시 상세히 기술하세요** (null 금지)
{extra_instruction}

```json
{{
    "result": "yes | no | conditional | no_regulation",
    "confidence": 0.0~1.0,
    "reasoning": "단계별 추론: 1) 관련 규정 식별 → 2) 무관 규정 배제 → 3) 조항 인용 판단 → 4) 최종 결론",
    "regulations": [
        {{"article": "규정명 제N조 (조항명)", "relevance": "높음|중간|낮음", "content": "핵심 내용 요약"}}
    ],
    "cross_references": [
        {{"articles": ["조항A", "조항B"], "relationship": "보완|충돌|상위규정", "detail": "관계 설명"}}
    ],
    "conditions": "조건부일 경우 조건을 반드시 상세히 설명 (conditional이면 필수!), 아니면 null",
    "alternatives": ["대안 제시"]
}}
```

아래 형식으로만 응답하세요:

QUESTION:
(질문)

ANSWER:
(JSON만, 코드블록 없이)
"""

EXTRA_INSTRUCTION_CROSS = """\
- 여러 규정을 **종합**하여 결론을 내리세요 (한 규정만으로는 답이 안 되는 질문)
- 제공된 규정 중 질문과 무관한 규정이 포함되어 있을 수 있습니다 — 관련 규정만 인용하세요
- reasoning에서 무관한 규정은 왜 해당되지 않는지 간단히 언급하세요"""

EXTRA_INSTRUCTION_CONFLICT = """\
- 규정 간 **충돌, 예외, 해석 차이**가 있는 상황입니다
- cross_references의 relationship에 "충돌" 또는 "상위규정"을 적절히 사용하세요
- 조건부(conditional) 판단이 자연스러운 경우가 많습니다 — **conditions에 조건을 반드시 기술하세요**
- 제공된 규정 중 질문과 무관한 규정이 포함되어 있을 수 있습니다 — 관련 규정만 인용하세요"""

EXTRA_INSTRUCTION_NOISE = """\
- 제공된 규정 중 **질문과 무관한 규정(Distractor)이 의도적으로 포함**되어 있습니다
- 관련 있는 규정만 regulations 배열에 포함하세요
- reasoning에서 반드시 어떤 규정이 무관하고 왜 무관한지 구체적으로 설명하세요"""


def call_llm(prompt: str, max_retries: int = 3) -> str:
    """OpenAI API 호출"""
    try:
        from openai import OpenAI
    except ImportError:
        print("\n  [ERROR] openai 패키지 필요: pip install openai")
        sys.exit(1)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # .env 파일 시도
        env_path = BASE_DIR / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("OPENAI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    os.environ["OPENAI_API_KEY"] = api_key
                    break

    if not api_key:
        print("\n  [ERROR] OPENAI_API_KEY가 설정되지 않았습니다.")
        print("  .env 파일에 OPENAI_API_KEY=sk-... 를 추가하거나")
        print("  환경변수를 설정해주세요.")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 기업 규정 기반 학습 데이터 생성 전문가입니다. "
                        "지시에 따라 정확한 형식으로 질문과 JSON 답변을 생성하세요.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.85,
                max_tokens=2000,
            )
            return response.choices[0].message.content
        except Exception as e:
            wait = 2**attempt
            print(f"    [WARN] API 오류 (재시도 {attempt + 1}/{max_retries}, {wait}s 대기): {e}")
            if attempt < max_retries - 1:
                time.sleep(wait)

    return ""


def parse_llm_response(response: str) -> tuple[str, str] | None:
    """LLM 응답에서 QUESTION과 ANSWER(JSON) 추출 + 검증"""
    if not response:
        return None

    # QUESTION 추출
    q_match = re.search(r"QUESTION:\s*\n(.+?)(?=\nANSWER:)", response, re.DOTALL)
    if not q_match:
        return None
    question = q_match.group(1).strip()

    # ANSWER 추출
    a_match = re.search(r"ANSWER:\s*\n(.+)", response, re.DOTALL)
    if not a_match:
        return None
    answer_raw = a_match.group(1).strip()

    # JSON 코드블록 제거
    json_match = re.search(r"```json?\s*\n(.+?)\n```", answer_raw, re.DOTALL)
    if json_match:
        answer_raw = json_match.group(1).strip()

    # JSON 검증
    try:
        parsed = json.loads(answer_raw)
    except json.JSONDecodeError:
        # { } 범위만 추출 시도
        brace_match = re.search(r"\{.+\}", answer_raw, re.DOTALL)
        if brace_match:
            try:
                parsed = json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                return None
        else:
            return None

    # 필수 필드 검증
    required = ["result", "confidence", "reasoning", "regulations"]
    for field in required:
        if field not in parsed:
            return None

    if parsed["result"] not in ("yes", "no", "conditional", "no_regulation"):
        return None

    # COND_NO_DESC 방지: conditional인데 conditions 없거나 "null" 문자열이면 파싱 실패 → 재시도
    if parsed["result"] == "conditional":
        cond_val = parsed.get("conditions")
        if not cond_val or cond_val == "null" or (isinstance(cond_val, str) and cond_val.strip().lower() == "null"):
            return None

    # 누락 필드 기본값
    parsed.setdefault("cross_references", [])
    parsed.setdefault("conditions", None)
    parsed.setdefault("alternatives", [])

    return question, json.dumps(parsed, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 5. 데이터 생성 루프
# ═══════════════════════════════════════════════════════════════


def add_distractors(regulations: dict, scenario: dict, base_context: str, num_distractors: int = 2) -> str:
    """
    RAFT: 기존 Context(Oracle)에 무관한 규정(Distractor)을 추가.
    P_RAFT 확률(80%)로 Oracle + Distractor, 나머지(20%)는 Distractor만.
    """
    # 무관 규정 선택 (시나리오에 이미 포함된 규정 제외)
    related_regs = set(scenario["regulations"])
    available = [a for a in REG_ALIASES if a not in related_regs]
    if not available:
        return base_context

    noise_picks = random.sample(available, min(num_distractors, len(available)))

    noise_parts = []
    for alias in noise_picks:
        reg_name = REG_ALIASES[alias]
        reg_data = regulations.get(reg_name)
        if not reg_data:
            continue
        article_keys = list(reg_data["articles"].keys())
        if article_keys:
            picked = random.sample(article_keys, min(2, len(article_keys)))
            for ak in picked:
                noise_parts.append(f"### {reg_name} — {ak}")
                noise_parts.append(reg_data["articles"][ak])
                noise_parts.append("")

    distractor_text = "\n".join(noise_parts)

    # RAFT 핵심: P_RAFT 확률로 Oracle+Distractor, (1-P_RAFT)로 Distractor만
    if random.random() < P_RAFT:
        # 80%: Oracle(관련 규정) + Distractor(무관 규정) — 관련 규정 식별 학습
        # 순서를 랜덤으로 섞어서 위치 편향 방지
        if random.random() < 0.5:
            return base_context + "\n" + distractor_text
        else:
            return distractor_text + "\n" + base_context
    else:
        # 20%: Distractor만 — "no_regulation" 대응 능력 학습
        return distractor_text


def generate_for_level(
    regulations: dict,
    level: str,
    scenarios: list[dict],
    count_per_scenario: int,
    noreg_boost: bool = False,
) -> list[dict]:
    """
    주어진 레벨/시나리오에서 QA 샘플 생성.
    RAFT 적용: 모든 시나리오에 Distractor 규정을 확률적으로 추가.
    noreg_boost=True: 강제 distractor-only → no_regulation 데이터 집중 생성.
    """
    samples = []

    for s_idx, scenario in enumerate(scenarios):
        regs_label = " + ".join(scenario["regulations"])
        boost_tag = " [NOREG-BOOST]" if noreg_boost else ""
        print(f"\n  [{level}][{s_idx + 1}/{len(scenarios)}]{boost_tag} {scenario['theme']}")
        print(f"    규정: {regs_label}")

        success = 0
        for i in range(count_per_scenario):
            # Extra instruction 결정
            if noreg_boost:
                extra = EXTRA_INSTRUCTION_NOISE  # distractor-only이므로 noise 인스트럭션 사용
            elif level == "noise":
                extra = EXTRA_INSTRUCTION_NOISE
            elif level == "conflict":
                extra = EXTRA_INSTRUCTION_CONFLICT
            else:
                extra = EXTRA_INSTRUCTION_CROSS

            # RAFT Context 구성
            oracle_context = build_regulation_context(regulations, scenario)

            if noreg_boost:
                # noreg-boost: 강제 distractor-only (Oracle 제외)
                related_regs = set(scenario["regulations"])
                available = [a for a in REG_ALIASES if a not in related_regs]
                if not available:
                    continue
                noise_picks = random.sample(available, min(3, len(available)))
                noise_parts = []
                for alias in noise_picks:
                    reg_name = REG_ALIASES[alias]
                    reg_data = regulations.get(reg_name)
                    if not reg_data:
                        continue
                    article_keys = list(reg_data["articles"].keys())
                    if article_keys:
                        picked = random.sample(article_keys, min(2, len(article_keys)))
                        for ak in picked:
                            noise_parts.append(f"### {reg_name} — {ak}")
                            noise_parts.append(reg_data["articles"][ak])
                            noise_parts.append("")
                context = "\n".join(noise_parts)
            elif level == "noise":
                # noise는 기존 방식 유지 (이미 무관 규정 포함 설계)
                context = build_noise_context(regulations, scenario, num_noise=2)
            else:
                # cross_2, cross_3, conflict → RAFT Distractor 주입
                context = add_distractors(
                    regulations, scenario, oracle_context, num_distractors=2
                )

            min_regs = len(scenario["regulations"])

            prompt = GENERATION_PROMPT_TEMPLATE.format(
                regulation_context=context,
                theme=scenario["theme"],
                hint=scenario["hint"],
                min_regulations=min_regs,
                extra_instruction=extra,
            )

            # LLM 호출 (파싱 실패 시 최대 2회 재시도)
            parsed = None
            for attempt in range(3):
                response = call_llm(prompt)
                parsed = parse_llm_response(response)
                if parsed:
                    break
                if attempt < 2:
                    print(f"    [{i + 1}] 파싱 실패, 재시도 {attempt + 1}/2...")
                    time.sleep(0.5)

            if not parsed:
                print(f"    [{i + 1}] 실패 (3회 파싱 오류)")
                continue

            question, answer_json = parsed

            # RAFT: Distractor만 제공된 경우(20%) result를 no_regulation로 강제
            # noreg_boost 모드에서는 항상 distractor-only
            is_distractor_only = noreg_boost or (
                level != "noise"
                and len(oracle_context) > 0
                and oracle_context not in context
            )
            if is_distractor_only:
                try:
                    ans = json.loads(answer_json)
                    if ans.get("result") != "no_regulation":
                        ans["result"] = "no_regulation"
                        ans["confidence"] = 0.9
                        ans["reasoning"] = (
                            f"단계별 추론: 1) 제공된 규정을 검토한 결과, "
                            f"'{scenario['theme']}'과 직접 관련된 규정이 포함되어 있지 않습니다. "
                            f"2) 제공된 규정들은 해당 질문의 판단에 필요한 조항을 포함하지 않습니다. "
                            f"3) 따라서 제공된 규정만으로는 정확한 판단이 불가능합니다. "
                            f"4) 관련 규정({' + '.join(scenario['regulations'])}) 확인이 필요합니다."
                        )
                        ans["regulations"] = []
                        ans["cross_references"] = []
                        ans["conditions"] = None
                        ans["alternatives"] = [
                            f"관련 규정({', '.join(REG_ALIASES.get(r, r) for r in scenario['regulations'])}) 원문 확인 필요"
                        ]
                        answer_json = json.dumps(ans, ensure_ascii=False)
                except (json.JSONDecodeError, KeyError):
                    pass

            # 학습 데이터 포맷
            user_msg = f"## 관련 규정 문서\n{context}\n\n## 사용자 질문\n{question}"

            sample = {
                "messages": [
                    {"role": "system", "content": JUDGMENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": answer_json},
                ],
                # 메타 (저장 시 제거)
                "_level": level,
                "_theme": scenario["theme"],
                "_raft": "distractor_only" if is_distractor_only else ("noise" if level == "noise" else "oracle+distractor"),
            }
            samples.append(sample)
            success += 1

            raft_tag = " [D-only]" if is_distractor_only else ""
            print(f"    [{i + 1}] OK{raft_tag}: {question[:55]}...")

            time.sleep(0.3)  # rate limit

        print(f"    → {success}/{count_per_scenario}건 성공")

    return samples


# ═══════════════════════════════════════════════════════════════
# 6. 저장 · 검증 · 병합
# ═══════════════════════════════════════════════════════════════


def save_jsonl(samples: list[dict], path: Path):
    """JSONL 저장 (메타 필드 제거)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for s in samples:
            record = {"messages": s["messages"]}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"\n  저장: {path} ({len(samples)}건)")


def validate(samples: list[dict]):
    """생성 데이터 검증 리포트"""
    total = len(samples)
    if total == 0:
        print("  검증할 데이터가 없습니다.")
        return

    json_ok = 0
    has_cross_ref = 0
    multi_reg = 0
    cond_no_desc = 0
    result_counter = Counter()
    level_counter = Counter()
    raft_counter = Counter()

    for s in samples:
        try:
            parsed = json.loads(s["messages"][2]["content"])
            json_ok += 1
            result_counter[parsed.get("result", "?")] += 1
            if parsed.get("cross_references"):
                has_cross_ref += 1
            if len(parsed.get("regulations", [])) > 1:
                multi_reg += 1
            # COND_NO_DESC 체크
            if parsed.get("result") == "conditional" and not parsed.get("conditions"):
                cond_no_desc += 1
        except (json.JSONDecodeError, IndexError, KeyError):
            pass
        level_counter[s.get("_level", "?")] += 1
        raft_counter[s.get("_raft", "?")] += 1

    print(f"\n{'=' * 60}")
    print(f"  검증 결과")
    print(f"{'=' * 60}")
    print(f"  총 건수       : {total}")
    print(f"  JSON 유효     : {json_ok}/{total} ({json_ok / total * 100:.1f}%)")
    print(f"  교차참조 포함 : {has_cross_ref}/{total} ({has_cross_ref / total * 100:.1f}%)")
    print(f"  다중규정 참조 : {multi_reg}/{total} ({multi_reg / total * 100:.1f}%)")
    print(f"  COND_NO_DESC  : {cond_no_desc}건 {'(문제없음)' if cond_no_desc == 0 else '(수정 필요!)'}")
    print(f"  Result 분포   : {dict(result_counter)}")
    print(f"  Level 분포    : {dict(level_counter)}")
    print(f"  RAFT 분포     : {dict(raft_counter)}")
    print(f"{'=' * 60}")


def merge_with_existing(cross_path: Path, existing_train: Path, existing_eval: Path):
    """기존 train/eval과 교차 규정 데이터를 병합하여 새 train/eval 생성"""
    # 기존 데이터 로드
    existing = []
    for p in [existing_train, existing_eval]:
        if p.exists():
            with open(p, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        existing.append(json.loads(line))

    # 교차 규정 데이터 로드
    cross = []
    if cross_path.exists():
        with open(cross_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    cross.append(json.loads(line))

    all_data = existing + cross
    random.seed(SEED)
    random.shuffle(all_data)

    # 90/10 분할
    split_idx = int(len(all_data) * 0.9)
    train = all_data[:split_idx]
    eval_ = all_data[split_idx:]

    # 저장
    merged_train = OUTPUT_DIR / "train_merged.jsonl"
    merged_eval = OUTPUT_DIR / "eval_merged.jsonl"

    for data, path in [(train, merged_train), (eval_, merged_eval)]:
        with open(path, "w", encoding="utf-8") as f:
            for record in data:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n  병합 완료:")
    print(f"    기존: {len(existing)}건")
    print(f"    교차: {len(cross)}건")
    print(f"    합계: {len(all_data)}건")
    print(f"    → {merged_train} ({len(train)}건)")
    print(f"    → {merged_eval} ({len(eval_)}건)")
    print(f"\n  확인 후 기존 파일 교체:")
    print(f"    mv {merged_train} {existing_train}")
    print(f"    mv {merged_eval} {existing_eval}")


# ═══════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="교차 규정 파인튜닝 데이터 생성 (멘토 피드백 반영)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
예시:
  python scripts/generate_cross_regulation_data.py --dry-run          # 시나리오 미리보기
  python scripts/generate_cross_regulation_data.py --count 1          # 테스트 (시나리오당 1건)
  python scripts/generate_cross_regulation_data.py --count 10         # 본 생성 (~310건)
  python scripts/generate_cross_regulation_data.py --level cross_2    # 2개 교차만
  python scripts/generate_cross_regulation_data.py --merge            # 기존 데이터와 병합
""",
    )
    parser.add_argument(
        "--level",
        choices=["cross_2", "cross_3", "conflict", "noise", "all"],
        default="all",
        help="생성할 데이터 유형 (기본: all)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="시나리오당 생성 건수 (기본: 10)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(OUTPUT_DIR / "cross_regulation.jsonl"),
        help="출력 파일 경로",
    )
    parser.add_argument("--dry-run", action="store_true", help="시나리오만 미리보기 (LLM 호출 안 함)")
    parser.add_argument("--merge", action="store_true", help="기존 train/eval과 병합")
    parser.add_argument(
        "--noreg-boost",
        action="store_true",
        help="no_regulation 부스트 모드: 모든 시나리오를 distractor-only 컨텍스트로 실행하여 no_regulation 데이터 집중 생성",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  교차 규정 파인튜닝 데이터 생성")
    print("  멘토 피드백: 규정 1개/2~3개/충돌 다양한 난이도")
    print("=" * 60)

    # ── 병합 모드 ──
    if args.merge:
        cross_path = Path(args.output)
        merge_with_existing(
            cross_path,
            OUTPUT_DIR / "train.jsonl",
            OUTPUT_DIR / "eval.jsonl",
        )
        return

    # ── 규정 로드 ──
    print("\n[1] 규정 파일 로드...")
    regulations = load_all_regulations()
    print(f"  총 {len(regulations)}개 규정")

    # ── Dry run ──
    if args.dry_run:
        print("\n[DRY RUN] 시나리오 목록:\n")
        total_scenarios = 0
        for level_name, scenario_list in SCENARIOS.items():
            print(f"  ▶ {level_name} ({len(scenario_list)}개 시나리오)")
            for s in scenario_list:
                regs = " + ".join(s["regulations"])
                print(f"    [{regs}] {s['theme']}")
                # Context 미리보기
                ctx = build_regulation_context(regulations, s)
                ctx_lines = ctx.count("\n")
                print(f"      → Context: {ctx_lines}줄, {len(ctx)}자")
            total_scenarios += len(scenario_list)

        print(f"\n  ▶ noise ({len(NOISE_SCENARIOS)}개 시나리오)")
        for s in NOISE_SCENARIOS:
            regs = " + ".join(s["regulations"])
            print(f"    [{regs}] {s['theme']} (+ 무관 규정 추가)")
        total_scenarios += len(NOISE_SCENARIOS)

        print(f"\n  총 {total_scenarios}개 시나리오 × {args.count}건 = 약 {total_scenarios * args.count}건")
        return

    # ── 데이터 생성 ──
    noreg_boost = getattr(args, 'noreg_boost', False)
    if noreg_boost:
        print(f"\n  [NOREG-BOOST] no_regulation 집중 생성 모드 활성화")
        print(f"    모든 시나리오를 distractor-only 컨텍스트로 실행합니다.")

    levels = ["cross_2", "cross_3", "conflict", "noise"] if args.level == "all" else [args.level]
    all_samples = []

    print(f"\n[2] 데이터 생성 (시나리오당 {args.count}건)...")
    for level in levels:
        if level == "noise":
            scenario_list = NOISE_SCENARIOS
        else:
            scenario_list = SCENARIOS.get(level, [])

        if scenario_list:
            samples = generate_for_level(
                regulations, level, scenario_list, args.count,
                noreg_boost=noreg_boost,
            )
            all_samples.extend(samples)
            print(f"\n  {level}: {len(samples)}건 완료")

    if not all_samples:
        print("\n  생성된 데이터가 없습니다.")
        return

    # ── 저장 ──
    print(f"\n[3] 저장...")
    output_path = Path(args.output)
    save_jsonl(all_samples, output_path)

    # ── 검증 ──
    print(f"\n[4] 검증...")
    validate(all_samples)

    print(f"\n  다음 단계:")
    print(f"  1. 생성된 데이터 품질 검수: {output_path}")
    print(f"  2. 기존 데이터와 병합:")
    print(f"     python scripts/generate_cross_regulation_data.py --merge")


if __name__ == "__main__":
    main()
