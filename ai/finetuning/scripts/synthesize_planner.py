"""
Planner LoRA 학습 데이터 합성 스크립트

Kanana-1.5-8B 약점 보강에 초점:
  1. general intent → 빈 plan 대신 step 1개
  2. multi-step 요청 → 각각 별도 step으로 분리
  3. judgment vs doc_retrieve 경계 명확화
  4. complex 3-4단계 계획

사용법:
  python ai/finetuning/scripts/synthesize_planner.py
  python ai/finetuning/scripts/synthesize_planner.py --project-root /workspace/SKN21-FINAL-3TEAM
"""

import argparse
import json
import random
import subprocess
from pathlib import Path

PLANNER_SYSTEM_PROMPT = """당신은 업무 자동화 시스템의 Task Planner입니다.
사용자 요청을 분석하여 실행 가능한 단계별 계획을 JSON으로 출력하세요.

## 사용 가능한 intent (6개)
- judgment: 사규/규정 기반 판단 ("~해도 되나요?", "규정 확인")
- doc_retrieve: 문서 검색/조회/요약 ("~문서 찾아줘", "~내용 알려줘")
- doc_generate: 문서 생성 ("보고서 만들어줘", "회의록 작성해줘")
- schedule_add: 일정 등록 ("~에 회의 잡아줘", "휴가 등록")
- schedule_view: 일정 조회 ("다음 주 일정 보여줘")
- general: 일반 질문 (위에 해당하지 않는 경우)

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


# ── 템플릿 데이터 ─────────────────────────────────────────

# judgment: 규정 기반 판단 요청 (핵심: "~해도 되나요?", "~가능한가요?")
JUDGMENT_QUERIES = [
    "연차 사용 규정 알려줘",
    "출장비 정산 기준이 어떻게 돼?",
    "퇴직금 계산 기준 좀",
    "야근 수당 청구 가능한가요?",
    "재택근무 신청 조건이 뭐야?",
    "법인카드 사적 사용하면 어떻게 돼?",
    "경조사 휴가 며칠이야?",
    "수습 기간 중에 연차 쓸 수 있어?",
    "출장 시 숙박비 한도가 얼마야?",
    "교육비 지원 받으려면 조건이 뭐야?",
    "겸직 허용되나요?",
    "연장근무 수당 계산 방식 알려줘",
    "복리후생 포인트 사용 규정 어떻게 돼?",
    "인사평가 이의제기 절차가 있어?",
    "해외출장 일비 기준 좀 알려줘",
    "시간외근무 신청 절차가 어떻게 돼?",
    "휴직 중 급여 지급 기준은?",
    "전배 신청 조건이 뭐야?",
    "연차 소진 안 하면 어떻게 돼?",
    "회사 차량 사적 이용 가능해?",
    "주차비 지원 규정 있어?",
    "건강검진 휴가 인정되나?",
    "출산휴가 급여 기준 알려줘",
    "인수인계 기간 규정이 있나?",
    "보안서약서 관련 규정 알려줘",
    "직원 할인 혜택 범위가 어디까지야?",
    "징계 절차가 어떻게 되는지 알려줘",
    "연봉 협상 관련 규정 있어?",
    "연차 규정이랑 병가 규정 차이가 뭐야?",
    "야근 식대 지원 기준 알려줘",
]

# doc_retrieve: 문서 검색/조회/요약
DOC_RETRIEVE_QUERIES = [
    "지난 주 회의록 찾아줘",
    "마케팅 전략 보고서 검색해줘",
    "인사 규정 문서 보여줘",
    "Q1 실적 보고서 찾아줘",
    "프로젝트 기획서 요약해줘",
    "거래처 계약서 조회해줘",
    "작년 감사 보고서 찾아줘",
    "채용 공고 자료 검색해줘",
    "팀 업무 분장표 찾아줘",
    "고객 만족도 조사 결과 보여줘",
    "사내 교육 자료 찾아줘",
    "출장 보고서 목록 보여줘",
    "제품 스펙 문서 검색해줘",
    "이전 프로젝트 후기 찾아줘",
    "분기별 매출 데이터 조회해줘",
    "경쟁사 분석 자료 찾아줘",
    "내부 감사 체크리스트 보여줘",
    "보안 정책 문서 조회해줘",
    "직원 핸드북 찾아줘",
    "BOM 문서 검색해줘",
]

# doc_generate: 문서 생성
DOC_GENERATE_QUERIES = [
    "이번 달 보고서 만들어줘",
    "회의록 작성해줘",
    "JD 작성해줘 백엔드 개발자",
    "프로젝트 제안서 만들어줘",
    "주간 업무 보고서 작성해줘",
    "신입 온보딩 가이드 만들어줘",
    "마케팅 기획안 작성해줘",
    "고객 제안서 초안 만들어줘",
    "업무 인수인계서 작성해줘",
    "팀 회고 문서 만들어줘",
    "분기 실적 보고서 써줘",
    "IR 발표 자료 초안 만들어줘",
    "기술 스펙 문서 작성해줘",
    "요구사항 정의서 만들어줘",
    "프로젝트 회고록 써줘",
]

# schedule_add: 일정 등록
SCHEDULE_ADD_QUERIES = [
    "내일 오후 2시에 팀 회의 잡아줘",
    "금요일 오전 10시에 면접 일정 등록해줘",
    "다음 주 월요일 점심에 팀 점심 약속 잡아줘",
    "3월 20일에 출장 일정 등록해줘",
    "오늘 오후 4시에 1:1 미팅 잡아줘",
    "다음 달 첫째 주에 워크숍 일정 넣어줘",
    "목요일에 고객사 미팅 잡아줘",
    "이번 주 수요일 오후에 코드 리뷰 일정 등록",
    "연차 등록해줘 다음 주 화요일",
    "금요일 오전에 스프린트 리뷰 잡아줘",
    "내일 아침 9시에 스탠드업 미팅 넣어줘",
    "3월 말에 반차 등록해줘",
    "다음 주에 팀 빌딩 행사 일정 잡아줘",
    "오후 3시에 디자인 리뷰 미팅 등록",
    "내일 점심 후에 발표 연습 시간 잡아줘",
]

# schedule_view: 일정 조회
SCHEDULE_VIEW_QUERIES = [
    "다음 주 일정 보여줘",
    "오늘 남은 일정 뭐 있어?",
    "이번 달 회의 일정 조회해줘",
    "내일 스케줄 알려줘",
    "이번 주 금요일까지 일정 보여줘",
    "3월 전체 일정 보여줘",
    "다음 달 출장 일정 있어?",
    "오늘 오후 일정 뭐야?",
    "이번 주 회의 몇 개야?",
    "내 휴가 일정 보여줘",
    "이번 주 남은 미팅 일정 알려줘",
    "이번 달 팀 일정 전체 보여줘",
    "수요일 일정 조회해줘",
    "프로젝트 마감 일정 언제야?",
    "다음 주 비어있는 시간 알려줘",
]

# general: 일반 질문/인사 (Kanana 약점: 빈 plan 출력 방지)
GENERAL_QUERIES = [
    "고마워",
    "안녕",
    "ㅎㅇ",
    "도움이 많이 됐어 고마워!",
    "그거 아까 그거",
    "오늘 날씨 어때?",
    "요즘 AI 트렌드가 뭐야?",
    "넌 뭘 할 수 있어?",
    "잘 부탁해",
    "감사합니다",
    "ㄱㅅ",
    "ㅎㅇ ㅂㄱ",
    "뭐 해?",
    "심심한데",
    "좋은 아침!",
    "수고했어",
    "다음에 또 물어볼게",
    "별거 아닌데",
    "잠깐만",
    "회의 관련해서 좀 도와줘",
    "그거 좀 알아봐줘",
    "고민이 있는데",
    "점심 메뉴 추천해줘",
    "오늘 뭐 하지",
    "파이썬 공부 방법 알려줘",
]


# ── 복합 패턴 정의 ─────────────────────────────────────────

SEQUENTIAL_PATTERNS = [
    # (description, steps)
    ("검색 후 생성", [
        ("doc_retrieve", "{doc} 찾아줘", []),
        ("doc_generate", "그걸로 {output} 만들어줘", [1]),
    ]),
    ("검색 후 판단", [
        ("doc_retrieve", "{doc} 조회해줘", []),
        ("judgment", "{question}", [1]),
    ]),
    ("판단 후 일정", [
        ("judgment", "{regulation} 확인해줘", []),
        ("schedule_add", "{schedule}", [1]),
    ]),
    ("일정 조회 후 생성", [
        ("schedule_view", "{view_query}", []),
        ("doc_generate", "그 내용으로 {output} 작성해줘", [1]),
    ]),
    ("검색 후 요약 생성", [
        ("doc_retrieve", "{doc} 검색해줘", []),
        ("doc_generate", "요약 보고서 만들어줘", [1]),
    ]),
    ("판단 후 생성", [
        ("judgment", "{regulation} 확인해줘", []),
        ("doc_generate", "결과를 {output}로 정리해줘", [1]),
    ]),
]

PARALLEL_PATTERNS = [
    # 병렬 (depends_on 모두 빈 리스트)
    ("두 문서 검색", [
        ("doc_retrieve", "{doc1} 찾아줘", []),
        ("doc_retrieve", "{doc2} 찾아줘", []),
    ]),
    ("일정 조회 + 문서 검색", [
        ("schedule_view", "{view_query}", []),
        ("doc_retrieve", "{doc} 찾아줘", []),
    ]),
    ("두 규정 판단", [
        ("judgment", "{regulation1} 확인해줘", []),
        ("judgment", "{regulation2} 확인해줘", []),
    ]),
    ("일정 + 판단", [
        ("schedule_view", "{view_query}", []),
        ("judgment", "{regulation} 확인해줘", []),
    ]),
]

COMPLEX_PATTERNS = [
    # ── 기존 5개 ──
    ("검색 + 판단 + 일정", [
        ("doc_retrieve", "{doc} 찾아줘", []),
        ("judgment", "{question}", [1]),
        ("schedule_add", "{schedule}", [2]),
    ]),
    ("검색 + 검색 + 생성", [
        ("doc_retrieve", "{doc1} 검색해줘", []),
        ("doc_retrieve", "{doc2} 찾아줘", []),
        ("doc_generate", "종합 {output} 만들어줘", [1, 2]),
    ]),
    ("일정 + 검색 + 판단 + 생성", [
        ("schedule_view", "{view_query}", []),
        ("doc_retrieve", "{doc} 찾아줘", []),
        ("judgment", "{question}", [1, 2]),
        ("doc_generate", "결과 {output} 작성해줘", [3]),
    ]),
    ("검색 + 판단 + 생성", [
        ("doc_retrieve", "{doc} 조회해줘", []),
        ("judgment", "{question}", [1]),
        ("doc_generate", "{output} 만들어줘", [2]),
    ]),
    ("병렬검색 + 생성", [
        ("doc_retrieve", "{doc1} 찾아줘", []),
        ("doc_retrieve", "{doc2} 찾아줘", []),
        ("doc_generate", "비교 {output} 만들어줘", [1, 2]),
    ]),
    # ── 신규 추가 (Step Collapse 방지 중점) ──
    ("판단 + 검색 + 생성", [
        ("judgment", "{regulation} 확인해줘", []),
        ("doc_retrieve", "관련 {doc} 찾아줘", [1]),
        ("doc_generate", "{output} 작성해줘", [1, 2]),
    ]),
    ("일정조회 + 판단 + 일정등록", [
        ("schedule_view", "{view_query}", []),
        ("judgment", "{regulation} 가능한지 확인해줘", [1]),
        ("schedule_add", "{schedule}", [2]),
    ]),
    ("검색 + 생성 + 일정등록", [
        ("doc_retrieve", "{doc} 찾아줘", []),
        ("doc_generate", "내용으로 {output} 만들어줘", [1]),
        ("schedule_add", "{schedule}", []),
    ]),
    ("병렬판단 + 생성", [
        ("judgment", "{regulation1} 확인해줘", []),
        ("judgment", "{regulation2} 확인해줘", []),
        ("doc_generate", "두 결과 비교 {output} 만들어줘", [1, 2]),
    ]),
    ("검색 + 판단 + 일정 + 생성", [
        ("doc_retrieve", "{doc} 찾아줘", []),
        ("judgment", "{question}", [1]),
        ("schedule_add", "{schedule}", [2]),
        ("doc_generate", "결과 {output} 작성해줘", [2]),
    ]),
    ("병렬검색 + 판단 + 생성", [
        ("doc_retrieve", "{doc1} 검색해줘", []),
        ("doc_retrieve", "{doc2} 찾아줘", []),
        ("judgment", "두 내용 기반으로 {question}", [1, 2]),
        ("doc_generate", "비교 {output} 만들어줘", [3]),
    ]),
    ("일정조회 + 생성 + 등록", [
        ("schedule_view", "{view_query}", []),
        ("doc_generate", "빈 시간에 {output} 작성해줘", [1]),
        ("schedule_add", "{schedule}", [1]),
    ]),
]

# 슬롯 채우기용 데이터
DOCS = ["회의록", "보고서", "인사 규정", "출장 규정", "마케팅 전략 문서",
        "프로젝트 기획서", "감사 보고서", "교육 자료", "거래처 계약서",
        "제품 스펙 문서", "복지 규정", "채용 공고 자료", "예산 계획서",
        "분기 실적", "고객 만족도 조사", "경쟁사 분석 자료", "BOM 문서",
        "업무 분장표", "보안 정책 문서", "직원 핸드북"]

OUTPUTS = ["보고서", "회의록", "제안서", "JD", "요약 문서", "비교 문서",
           "기획안", "정리 문서", "인수인계서", "발표 자료"]

REGULATIONS = ["연차 규정", "출장 규정", "야근 수당 규정", "재택근무 규정",
               "법인카드 사용 규정", "경조사 휴가 규정", "교육비 지원 규정",
               "겸직 규정", "복리후생 규정", "시간외근무 규정"]

QUESTIONS = ["가능한지 확인해줘", "해당 사항이 있는지 판단해줘",
             "적용 가능한지 봐줘", "이 경우 어떻게 되는지 알려줘",
             "조건에 맞는지 확인해줘"]

SCHEDULES = ["다음 주에 회의 잡아줘", "금요일에 미팅 등록해줘",
             "이번 주에 일정 넣어줘", "내일 오후에 시간 잡아줘",
             "월요일에 미팅 일정 등록", "다음 달에 워크숍 잡아줘"]

VIEW_QUERIES = ["이번 주 일정", "다음 주 스케줄", "오늘 남은 일정",
                "이번 달 회의 일정", "금요일까지 일정"]

# 복합 질문 표현 (자연어)
SEQ_TEMPLATES = [
    "{action1} {connector} {action2}",
]

CONNECTORS = ["그리고", "한 다음에", "후에", "다음으로", "그 다음",
              "하고 나서"]

# 무접속사 복합 질문 패턴 (Step Collapse 방지 핵심)
# "{A}해서 {B}" 형태 — 접속사 없이 자연스럽게 이어지는 패턴
NO_CONNECTOR_TEMPLATES_2STEP = [
    "{part0} 확인해서 {part1}",
    "{part0} 찾아서 {part1}",
    "{part0} 보고 {part1}",
    "{part0} 검토해서 {part1}",
    "{part0} 조회해서 {part1}",
    "{part0} 바탕으로 {part1}",
    "{part0} 토대로 {part1}",
    "{part0} 참고해서 {part1}",
    "{part0}, {part1}",
    "{part0} 봐서 {part1}",
]

NO_CONNECTOR_TEMPLATES_3STEP = [
    "{part0} 확인하고 {part1} 후 {part2}",
    "{part0} 찾아서 {part1} 다음 {part2}",
    "{part0} 검토 후 {part1} {part2}",
    "{part0}, {part1}, 그리고 {part2}",
    "{part0} 바탕으로 {part1} {part2}",
]

# ── Anti-Collapse 하드코딩 예제 (Step Collapse 방지 핵심 데이터) ──
# "단일처럼 보이지만 반드시 multi-step이어야 하는" 패턴 직접 정의
ANTI_COLLAPSE_EXAMPLES = [
    # 검색 → 판단 (압축 금지)
    ("연차 규정 찾아서 내 경우 가능한지 판단해줘",
     [{"step_id": 1, "intent": "doc_retrieve", "query": "연차 규정 찾아줘", "depends_on": []},
      {"step_id": 2, "intent": "judgment", "query": "내 경우 연차 사용 가능한지 판단해줘", "depends_on": [1]}]),
    ("출장비 규정 확인해서 이번 건 청구 가능한지 봐줘",
     [{"step_id": 1, "intent": "doc_retrieve", "query": "출장비 규정 문서 찾아줘", "depends_on": []},
      {"step_id": 2, "intent": "judgment", "query": "이번 출장비 청구 가능한지 판단해줘", "depends_on": [1]}]),
    ("보안 정책 문서 보고 위반 여부 판단해줘",
     [{"step_id": 1, "intent": "doc_retrieve", "query": "보안 정책 문서 찾아줘", "depends_on": []},
      {"step_id": 2, "intent": "judgment", "query": "위반 여부 판단해줘", "depends_on": [1]}]),
    ("복리후생 규정 조회해서 적용 대상인지 확인해줘",
     [{"step_id": 1, "intent": "doc_retrieve", "query": "복리후생 규정 찾아줘", "depends_on": []},
      {"step_id": 2, "intent": "judgment", "query": "내가 적용 대상인지 확인해줘", "depends_on": [1]}]),
    ("인사 규정 찾아서 이 경우 해당되는지 봐줘",
     [{"step_id": 1, "intent": "doc_retrieve", "query": "인사 규정 문서 조회해줘", "depends_on": []},
      {"step_id": 2, "intent": "judgment", "query": "이 경우 인사 규정 해당 여부 판단해줘", "depends_on": [1]}]),
    ("법인카드 사용 규정 확인해서 이번 사용 가능한지 판단해줘",
     [{"step_id": 1, "intent": "doc_retrieve", "query": "법인카드 사용 규정 문서 찾아줘", "depends_on": []},
      {"step_id": 2, "intent": "judgment", "query": "이번 법인카드 사용 가능 여부 판단해줘", "depends_on": [1]}]),
    # 판단 → 생성 (압축 금지)
    ("연차 규정 확인해서 결과 정리 문서 만들어줘",
     [{"step_id": 1, "intent": "judgment", "query": "연차 규정 확인해줘", "depends_on": []},
      {"step_id": 2, "intent": "doc_generate", "query": "규정 확인 결과 정리 문서 만들어줘", "depends_on": [1]}]),
    ("출장 가능 여부 판단하고 그 결과로 보고서 작성해줘",
     [{"step_id": 1, "intent": "judgment", "query": "출장 규정 가능 여부 판단해줘", "depends_on": []},
      {"step_id": 2, "intent": "doc_generate", "query": "판단 결과 보고서 작성해줘", "depends_on": [1]}]),
    # 검색 → 생성 (압축 금지)
    ("회의록 찾아서 그 내용으로 보고서 만들어줘",
     [{"step_id": 1, "intent": "doc_retrieve", "query": "최근 회의록 찾아줘", "depends_on": []},
      {"step_id": 2, "intent": "doc_generate", "query": "회의록 내용으로 보고서 만들어줘", "depends_on": [1]}]),
    ("프로젝트 기획서 조회해서 요약 보고서 작성해줘",
     [{"step_id": 1, "intent": "doc_retrieve", "query": "프로젝트 기획서 찾아줘", "depends_on": []},
      {"step_id": 2, "intent": "doc_generate", "query": "기획서 내용으로 요약 보고서 작성해줘", "depends_on": [1]}]),
    ("마케팅 전략 문서 찾아서 제안서 초안 만들어줘",
     [{"step_id": 1, "intent": "doc_retrieve", "query": "마케팅 전략 문서 검색해줘", "depends_on": []},
      {"step_id": 2, "intent": "doc_generate", "query": "마케팅 전략 기반 제안서 초안 만들어줘", "depends_on": [1]}]),
    # 판단 → 일정 (압축 금지)
    ("재택근무 가능 여부 확인하고 일정 잡아줘",
     [{"step_id": 1, "intent": "judgment", "query": "재택근무 신청 가능 여부 확인해줘", "depends_on": []},
      {"step_id": 2, "intent": "schedule_add", "query": "재택근무 일정 등록해줘", "depends_on": [1]}]),
    ("연차 규정 맞는지 보고 연차 일정 잡아줘",
     [{"step_id": 1, "intent": "judgment", "query": "연차 신청 규정 확인해줘", "depends_on": []},
      {"step_id": 2, "intent": "schedule_add", "query": "연차 일정 등록해줘", "depends_on": [1]}]),
    # 일정조회 → 판단 (압축 금지)
    ("다음 주 일정 보고 출장 규정 확인해줘",
     [{"step_id": 1, "intent": "schedule_view", "query": "다음 주 일정 조회해줘", "depends_on": []},
      {"step_id": 2, "intent": "judgment", "query": "출장 규정 가능 여부 확인해줘", "depends_on": []}]),
    ("이번 주 스케줄 확인하고 연차 사용 가능한지 판단해줘",
     [{"step_id": 1, "intent": "schedule_view", "query": "이번 주 일정 조회해줘", "depends_on": []},
      {"step_id": 2, "intent": "judgment", "query": "연차 사용 가능 여부 판단해줘", "depends_on": [1]}]),
    # 3-step anti-collapse
    ("출장비 규정 찾아서 가능 여부 판단하고 정리 문서 만들어줘",
     [{"step_id": 1, "intent": "doc_retrieve", "query": "출장비 규정 찾아줘", "depends_on": []},
      {"step_id": 2, "intent": "judgment", "query": "출장비 청구 가능 여부 판단해줘", "depends_on": [1]},
      {"step_id": 3, "intent": "doc_generate", "query": "출장비 판단 결과 정리 문서 만들어줘", "depends_on": [2]}]),
    ("보안 정책 조회해서 위반 여부 확인하고 회의 일정 잡아줘",
     [{"step_id": 1, "intent": "doc_retrieve", "query": "보안 정책 문서 찾아줘", "depends_on": []},
      {"step_id": 2, "intent": "judgment", "query": "보안 정책 위반 여부 확인해줘", "depends_on": [1]},
      {"step_id": 3, "intent": "schedule_add", "query": "보안 점검 회의 일정 잡아줘", "depends_on": [2]}]),
    ("마케팅 전략 문서 찾아서 내용 정리하고 팀 미팅 일정 잡아줘",
     [{"step_id": 1, "intent": "doc_retrieve", "query": "마케팅 전략 문서 검색해줘", "depends_on": []},
      {"step_id": 2, "intent": "doc_generate", "query": "마케팅 전략 요약 문서 만들어줘", "depends_on": [1]},
      {"step_id": 3, "intent": "schedule_add", "query": "팀 마케팅 미팅 일정 등록해줘", "depends_on": []}]),
    ("인사 규정 확인 후 해당되면 연차 신청 일정 잡고 보고서도 만들어줘",
     [{"step_id": 1, "intent": "judgment", "query": "인사 규정 연차 신청 가능 여부 확인해줘", "depends_on": []},
      {"step_id": 2, "intent": "schedule_add", "query": "연차 신청 일정 등록해줘", "depends_on": [1]},
      {"step_id": 3, "intent": "doc_generate", "query": "연차 신청 결과 보고서 작성해줘", "depends_on": [1]}]),
    ("회의록이랑 기획서 찾아서 종합 보고서 만들어줘",
     [{"step_id": 1, "intent": "doc_retrieve", "query": "최근 회의록 찾아줘", "depends_on": []},
      {"step_id": 2, "intent": "doc_retrieve", "query": "프로젝트 기획서 찾아줘", "depends_on": []},
      {"step_id": 3, "intent": "doc_generate", "query": "회의록이랑 기획서 내용으로 종합 보고서 만들어줘", "depends_on": [1, 2]}]),
    ("다음 주 일정 확인해서 빈 시간에 미팅 잡고 회의 준비 문서 만들어줘",
     [{"step_id": 1, "intent": "schedule_view", "query": "다음 주 일정 조회해줘", "depends_on": []},
      {"step_id": 2, "intent": "schedule_add", "query": "빈 시간에 미팅 일정 등록해줘", "depends_on": [1]},
      {"step_id": 3, "intent": "doc_generate", "query": "회의 준비 문서 작성해줘", "depends_on": []}]),
]


# ── 생성 함수 ──────────────────────────────────────────────

def make_step(step_id: int, intent: str, query: str,
              depends_on: list[int]) -> dict:
    return {
        "step_id": step_id,
        "intent": intent,
        "query": query,
        "depends_on": depends_on,
    }


def make_sample(user_input: str, plan: list[dict]) -> dict:
    output = json.dumps({"plan": plan}, ensure_ascii=False)
    return {
        "messages": [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": output},
        ]
    }


def fill_slots(template: str) -> str:
    """슬롯을 랜덤 데이터로 채우기"""
    result = template
    if "{doc}" in result:
        result = result.replace("{doc}", random.choice(DOCS))
    if "{doc1}" in result:
        d1, d2 = random.sample(DOCS, 2)
        result = result.replace("{doc1}", d1).replace("{doc2}", d2)
    elif "{doc2}" in result:
        # doc2만 단독으로 사용된 경우 (병렬 패턴의 두 번째 step 등)
        result = result.replace("{doc2}", random.choice(DOCS))
    if "{output}" in result:
        result = result.replace("{output}", random.choice(OUTPUTS))
    if "{regulation}" in result:
        result = result.replace("{regulation}", random.choice(REGULATIONS))
    if "{regulation1}" in result:
        r1, r2 = random.sample(REGULATIONS, 2)
        result = result.replace("{regulation1}", r1).replace("{regulation2}", r2)
    if "{question}" in result:
        result = result.replace("{question}", random.choice(QUESTIONS))
    if "{schedule}" in result:
        result = result.replace("{schedule}", random.choice(SCHEDULES))
    if "{view_query}" in result:
        result = result.replace("{view_query}", random.choice(VIEW_QUERIES))
    return result


def generate_single_step(n: int) -> list[dict]:
    """단일 step 데이터 생성"""
    samples = []
    all_queries = [
        (JUDGMENT_QUERIES, "judgment"),
        (DOC_RETRIEVE_QUERIES, "doc_retrieve"),
        (DOC_GENERATE_QUERIES, "doc_generate"),
        (SCHEDULE_ADD_QUERIES, "schedule_add"),
        (SCHEDULE_VIEW_QUERIES, "schedule_view"),
        (GENERAL_QUERIES, "general"),
    ]

    per_intent = n // len(all_queries)
    remainder = n % len(all_queries)

    for queries, intent in all_queries:
        count = per_intent + (1 if remainder > 0 else 0)
        remainder -= 1
        selected = random.choices(queries, k=count)
        for q in selected:
            plan = [make_step(1, intent, q, [])]
            samples.append(make_sample(q, plan))

    random.shuffle(samples)
    return samples[:n]


def generate_sequential(n: int) -> list[dict]:
    """순차 의존성 데이터 생성"""
    samples = []
    for _ in range(n):
        pattern = random.choice(SEQUENTIAL_PATTERNS)
        _, steps = pattern
        plan = []
        parts = []
        for i, (intent, query_tmpl, deps) in enumerate(steps):
            query = fill_slots(query_tmpl)
            plan.append(make_step(i + 1, intent, query, deps))
            parts.append(query)

        connector = random.choice(CONNECTORS)
        user_input = f"{parts[0]} {connector} {parts[1]}"
        samples.append(make_sample(user_input, plan))

    return samples


def generate_parallel(n: int) -> list[dict]:
    """병렬 처리 데이터 생성"""
    samples = []
    for _ in range(n):
        pattern = random.choice(PARALLEL_PATTERNS)
        _, steps = pattern
        plan = []
        parts = []
        for i, (intent, query_tmpl, deps) in enumerate(steps):
            query = fill_slots(query_tmpl)
            plan.append(make_step(i + 1, intent, query, deps))
            parts.append(query)

        connectors = ["그리고", "또", "랑", "이랑", "하고", "도"]
        connector = random.choice(connectors)
        user_input = f"{parts[0]} {connector} {parts[1]}"
        samples.append(make_sample(user_input, plan))

    return samples


def generate_complex(n: int) -> list[dict]:
    """복합 3-4단계 데이터 생성"""
    samples = []
    for _ in range(n):
        pattern = random.choice(COMPLEX_PATTERNS)
        _, steps = pattern
        plan = []
        parts = []
        for i, (intent, query_tmpl, deps) in enumerate(steps):
            query = fill_slots(query_tmpl)
            plan.append(make_step(i + 1, intent, query, deps))
            parts.append(query)

        connectors = ["그리고", "한 다음에", "후에", "그 다음"]
        if len(parts) == 3:
            user_input = (f"{parts[0]} {random.choice(connectors)} "
                          f"{parts[1]} {random.choice(connectors)} {parts[2]}")
        elif len(parts) == 4:
            user_input = (f"{parts[0]} {random.choice(connectors)} "
                          f"{parts[1]}, {parts[2]} "
                          f"{random.choice(connectors)} {parts[3]}")
        else:
            user_input = " ".join(parts)

        samples.append(make_sample(user_input, plan))

    return samples


def generate_no_connector_complex(n: int) -> list[dict]:
    """무접속사 복합 질문 생성 (Step Collapse 핵심 방지)"""
    samples = []
    seq_patterns_nc = SEQUENTIAL_PATTERNS + [
        ("검색 후 판단 (무접속사)", [
            ("doc_retrieve", "{doc} 찾아줘", []),
            ("judgment", "{question}", [1]),
        ]),
        ("판단 후 생성 (무접속사)", [
            ("judgment", "{regulation} 확인해줘", []),
            ("doc_generate", "결과로 {output} 만들어줘", [1]),
        ]),
        ("검색 후 생성 (무접속사)", [
            ("doc_retrieve", "{doc} 검색해줘", []),
            ("doc_generate", "내용으로 {output} 작성해줘", [1]),
        ]),
        ("판단 후 일정 (무접속사)", [
            ("judgment", "{regulation} 가능한지 확인해줘", []),
            ("schedule_add", "{schedule}", [1]),
        ]),
    ]

    for _ in range(n * 2 // 3):
        pattern = random.choice(seq_patterns_nc)
        _, steps = pattern
        plan = []
        parts = []
        for i, (intent, query_tmpl, deps) in enumerate(steps):
            query = fill_slots(query_tmpl)
            plan.append(make_step(i + 1, intent, query, deps))
            parts.append(query)

        tmpl = random.choice(NO_CONNECTOR_TEMPLATES_2STEP)
        user_input = tmpl.format(part0=parts[0], part1=parts[1])
        samples.append(make_sample(user_input, plan))

    for _ in range(n - len(samples)):
        pattern = random.choice(COMPLEX_PATTERNS[:5])
        _, steps = pattern
        plan = []
        parts = []
        for i, (intent, query_tmpl, deps) in enumerate(steps):
            query = fill_slots(query_tmpl)
            plan.append(make_step(i + 1, intent, query, deps))
            parts.append(query)

        if len(parts) >= 3:
            tmpl = random.choice(NO_CONNECTOR_TEMPLATES_3STEP)
            user_input = tmpl.format(
                part0=parts[0], part1=parts[1], part2=parts[2])
        else:
            tmpl = random.choice(NO_CONNECTOR_TEMPLATES_2STEP)
            user_input = tmpl.format(part0=parts[0], part1=parts[1])
        samples.append(make_sample(user_input, plan))

    return samples[:n]


def generate_anti_collapse(n: int) -> list[dict]:
    """Anti-collapse 하드코딩 예제 (과도한 단계 압축 방지)"""
    samples = []
    base = [make_sample(ex[0], ex[1]) for ex in ANTI_COLLAPSE_EXAMPLES]
    # n개 채울 때까지 반복 샘플링
    while len(samples) < n:
        samples.extend(base)
    random.shuffle(samples)
    return samples[:n]


def generate_edge_cases(n: int) -> list[dict]:
    """엣지 케이스 생성 (오타, 초성, 모호한 입력)"""
    samples = []

    # 오타 변형
    typo_map = {
        "회의록": ["회이록", "회읮록", "회의룩"],
        "보고서": ["보곶서", "보고셔", "보고섯"],
        "규정": ["규졍", "규젇", "규정ㅇ"],
        "알려줘": ["알려쥬", "알렬줘", "알려죠"],
        "만들어줘": ["만들어쥬", "만들얼줘", "만들어져"],
        "찾아줘": ["차자줘", "찻아줘", "찾아쥬"],
    }

    for _ in range(n // 3):
        word = random.choice(list(typo_map.keys()))
        typo = random.choice(typo_map[word])
        if word in ("회의록", "보고서"):
            q = f"{typo} {random.choice(['찾아줘', '만들어줘'])}"
            intent = "doc_retrieve" if "찾" in q else "doc_generate"
        elif word == "규정":
            q = f"연차 {typo} {random.choice(typo_map.get('알려줘', ['알려줘']))}"
            intent = "judgment"
        else:
            q = f"회의록 {typo}"
            intent = "doc_retrieve"
        plan = [make_step(1, intent, q, [])]
        samples.append(make_sample(q, plan))

    # 초성 입력
    chosung_map = [
        ("ㅎㅇㄹ ㅊㅇ", "doc_retrieve", "회의록 찾기"),
        ("ㅂㄱㅅ ㅁㄷㄹ", "doc_generate", "보고서 만들기"),
        ("ㅇㅈ ㅈㅎ", "schedule_view", "일정 조회"),
        ("ㅎㅇ ㅈㅂ", "schedule_add", "회의 잡기"),
    ]
    for _ in range(n // 3):
        chosung, intent, query = random.choice(chosung_map)
        plan = [make_step(1, intent, query, [])]
        samples.append(make_sample(chosung, plan))

    # 모호한 입력 → general
    vague = [
        "그거", "아까 그거", "뭐였더라", "음...", "잠깐",
        "이거 좀", "저번에 말한 거", "글쎄",
    ]
    for _ in range(n - len(samples)):
        q = random.choice(vague)
        plan = [make_step(1, "general", q, [])]
        samples.append(make_sample(q, plan))

    return samples[:n]


# ── 메인 ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Planner LoRA 학습 데이터 합성")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--total", type=int, default=800,
                        help="총 학습 데이터 수 (v4는 --total 1500 권장)")
    parser.add_argument("--eval-ratio", type=float, default=0.1,
                        help="평가 데이터 비율")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--version", type=str, default="v3",
                        choices=["v3", "v4"],
                        help="출력 버전 (v3=기존 800건, v4=1500건 multi-step 강화)")
    args = parser.parse_args()

    random.seed(args.seed)

    # 프로젝트 루트
    if args.project_root:
        root = Path(args.project_root)
    else:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True)
            root = Path(result.stdout.strip())
        except Exception:
            root = Path.cwd()

    # v4는 출력 경로와 기본 total 변경
    if args.version == "v4":
        out_dir = root / "data" / "training" / "v4_planner"
        if args.total == 800:  # 기본값이면 v4 기본값으로 오버라이드
            args.total = 1500
    else:
        out_dir = root / "data" / "training" / "v3_planner"
    out_dir.mkdir(parents=True, exist_ok=True)

    total = args.total

    # v4: complex/no_connector/anti_collapse 비율 대폭 증가 (3-step+ 강화)
    if args.version == "v4":
        dist = {
            "single_step":      int(total * 0.17),  # 17%
            "sequential":       int(total * 0.18),  # 18%
            "parallel":         int(total * 0.12),  # 12%
            "complex":          int(total * 0.28),  # 28% ← 핵심 증가
            "no_connector":     int(total * 0.15),  # 15% ← 신규 (무접속사)
            "anti_collapse":    int(total * 0.06),  # 6%  ← 신규 (하드코딩)
            "edge_case":        0,
        }
        dist["edge_case"] = total - sum(dist.values())
    else:
        dist = {
            "single_step": int(total * 0.25),
            "sequential": int(total * 0.25),
            "parallel": int(total * 0.19),
            "complex": int(total * 0.25),
            "no_connector": 0,
            "anti_collapse": 0,
            "edge_case": total - int(total * 0.25) * 3 - int(total * 0.19),
        }

    print(f"Generating {total} planner training samples (version={args.version})...")
    print(f"Distribution: {dist}")

    all_samples = []
    all_samples.extend(generate_single_step(dist["single_step"]))
    all_samples.extend(generate_sequential(dist["sequential"]))
    all_samples.extend(generate_parallel(dist["parallel"]))
    all_samples.extend(generate_complex(dist["complex"]))
    if dist["no_connector"] > 0:
        all_samples.extend(generate_no_connector_complex(dist["no_connector"]))
    if dist["anti_collapse"] > 0:
        all_samples.extend(generate_anti_collapse(dist["anti_collapse"]))
    all_samples.extend(generate_edge_cases(dist["edge_case"]))

    random.shuffle(all_samples)

    # train/eval 분할
    eval_count = int(len(all_samples) * args.eval_ratio)
    eval_samples = all_samples[:eval_count]
    train_samples = all_samples[eval_count:]

    # 저장
    train_path = out_dir / "train.jsonl"
    eval_path = out_dir / "eval.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for s in train_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    with open(eval_path, "w", encoding="utf-8") as f:
        for s in eval_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"\nGenerated:")
    print(f"  Train: {len(train_samples)} samples → {train_path}")
    print(f"  Eval:  {len(eval_samples)} samples → {eval_path}")

    # 통계
    intent_count = {}
    for s in all_samples:
        output = json.loads(s["messages"][2]["content"])
        for step in output["plan"]:
            intent = step["intent"]
            intent_count[intent] = intent_count.get(intent, 0) + 1

    print(f"\nIntent distribution:")
    for intent, count in sorted(intent_count.items(), key=lambda x: -x[1]):
        print(f"  {intent}: {count}")

    # 카테고리별 step 수 분포
    step_counts = {}
    for s in all_samples:
        output = json.loads(s["messages"][2]["content"])
        n = len(output["plan"])
        step_counts[n] = step_counts.get(n, 0) + 1

    print(f"\nSteps distribution:")
    for n, count in sorted(step_counts.items()):
        print(f"  {n}-step: {count}")


if __name__ == "__main__":
    main()
