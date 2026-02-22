"""
Intent 분류 v2 데이터 생성 스크립트

2개 LLM(GPT API + Claude API)으로 학습 데이터를 생성하고,
교차 검증 → QA → Train/Val/Test 분할까지 자동 수행.

분업: GPT 150개/intent + Claude 150개/intent = 300개/intent

사용법:
    # 1) .env에 API 키 설정
    #    OPENAI_API_KEY=sk-...
    #    ANTHROPIC_API_KEY=sk-ant-...  (없으면 Claude는 수동 생성)

    # 2) 전체 파이프라인 실행
    python ai/experiments_v2/generate_data.py

    # 3) 특정 단계만 실행
    python ai/experiments_v2/generate_data.py --step basic        # 기본 데이터만
    python ai/experiments_v2/generate_data.py --step boundary     # 경계 쌍만
    python ai/experiments_v2/generate_data.py --step adversarial  # 적대적만
    python ai/experiments_v2/generate_data.py --step validate     # 교차 검증만
    python ai/experiments_v2/generate_data.py --step qa           # QA 체크만
    python ai/experiments_v2/generate_data.py --step split        # 분할만

    # 특정 LLM만 실행
    python ai/experiments_v2/generate_data.py --step basic --llm gpt

사전: pip install openai anthropic python-dotenv
"""

import argparse
import json
import os
import random
import re
import time
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "intent_v2"
RAW_DIR = DATA_DIR / "raw"
SPLITS_DIR = DATA_DIR / "splits"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

for d in [RAW_DIR, SPLITS_DIR, RESULTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Intent 정의 ──
INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_qa",
]

INTENT_DEFINITIONS = {
    "judgment": "회사 규정/정책에 따라 어떤 행위가 가능한지, 위반인지 판단을 요청하는 문장",
    "doc_search": "특정 문서나 규정의 존재, 위치, 전문을 검색하거나 찾아달라는 문장",
    "doc_generate": "보고서, 회의록, JD, 제안서 등 새 문서를 작성/생성해달라는 문장",
    "doc_summary": "이미 존재하는 문서의 내용을 요약하거나 핵심만 정리해달라는 문장",
    "schedule_add": "새로운 일정, 미팅, 이벤트를 캘린더에 추가/등록해달라는 문장",
    "schedule_view": "기존 일정을 확인하거나 조회해달라는 문장",
    "general": "인사, 감사, 잡담, 봇 기능 질문 등 업무 intent에 해당하지 않는 일반 대화",
    "doc_qa": "문서 내용에서 특정 사실, 숫자, 결정사항 등을 질문하는 문장",
}

SEED_SENTENCES = {
    "judgment": [
        "인턴에게 서버 접근 권한 줘도 돼?",
        "연차 3일 연속으로 써도 되나요?",
        "재택근무 중에 카페에서 일해도 괜찮아?",
        "경쟁사 이직 시 위약금 있어?",
        "야근 수당 안 주면 규정 위반이야?",
        "개인 노트북으로 사내 시스템 접속해도 돼?",
        "수습 기간에 연차 쓸 수 있나?",
        "회사 차량 주말에 개인 용도로 써도 되나요?",
        "보안 구역에 외부인 데리고 들어가도 돼?",
        "퇴직금 중간 정산 신청 가능한가요?",
    ],
    "doc_search": [
        "연차 규정 몇 조에 나와있어?",
        "출장비 지급 기준 문서 찾아줘",
        "보안 규정 전문 보여줘",
        "복리후생 관련 규정 있어?",
        "인사평가 기준 문서 어디 있지?",
        "재택근무 가이드라인 찾아줘",
        "경조사 휴가 규정 알려줘",
        "직급별 결재 한도 문서 있나?",
        "성과급 지급 기준 규정 찾아봐",
        "신입사원 온보딩 매뉴얼 있어?",
    ],
    "doc_generate": [
        "이 내용으로 보고서 만들어줘",
        "오늘 회의 내용으로 회의록 작성해줘",
        "프론트엔드 개발자 JD 만들어줘",
        "AI 도입 제안서 작성해줘",
        "주간 업무 보고서 써줘",
        "이 데이터로 분석 보고서 만들어",
        "인턴 채용 공고 만들어줘",
        "프로젝트 기획서 작성해줘",
        "미팅 결과 정리해서 회의록 만들어",
        "퇴사자 인수인계 문서 작성해줘",
    ],
    "doc_summary": [
        "이 문서 요약해줘",
        "핵심만 정리해줘",
        "이 보고서 3줄로 요약해줘",
        "긴 문서인데 핵심 포인트만 뽑아줘",
        "이 회의록 요약 좀",
        "첨부한 파일 간단히 정리해줘",
        "이 제안서 핵심이 뭐야?",
        "문서 내용 한눈에 보게 정리해줘",
        "이거 읽기 귀찮은데 요약 좀",
        "이 규정 문서 주요 조항만 정리해줘",
    ],
    "schedule_add": [
        "내일 3시에 팀미팅 잡아줘",
        "금요일 오후 2시 면접 일정 추가해줘",
        "다음주 월요일 10시 스프린트 리뷰 등록해줘",
        "3월 5일에 워크숍 일정 넣어줘",
        "오늘 5시에 1:1 미팅 추가",
        "다음주 수요일 점심에 팀 회식 잡아",
        "매주 화요일 9시 스탠드업 미팅 등록",
        "이번주 목요일 4시에 고객 미팅 추가해줘",
        "내일 오전에 코드 리뷰 일정 잡아줘",
        "3월 말에 분기 회고 일정 넣어줘",
    ],
    "schedule_view": [
        "이번주 일정 보여줘",
        "내일 미팅 몇 시야?",
        "다음주 스케줄 확인해줘",
        "오늘 남은 일정 있어?",
        "3월 일정 전체 보여줘",
        "이번달 회의 일정 알려줘",
        "금요일에 뭐 있지?",
        "다음주 빈 시간 언제야?",
        "이번주 목요일 일정 확인",
        "오후에 약속 있었나?",
    ],
    "general": [
        "안녕하세요",
        "고마워",
        "오늘 날씨 어때?",
        "너 이름이 뭐야?",
        "잘 부탁해",
        "뭘 할 수 있어?",
        "도움 좀 줄래?",
        "아 그렇구나",
        "다음에 또 물어볼게",
        "수고했어",
    ],
    "doc_qa": [
        "지난 회의 결정사항이 뭐야?",
        "예산이 얼마로 잡혀있어?",
        "이 보고서에서 핵심 이슈가 뭐야?",
        "지난달 매출이 얼마였어?",
        "회의에서 누가 담당자로 정해졌어?",
        "이 문서에 기한이 언제라고 되어있어?",
        "프로젝트 목표가 뭐라고 써있어?",
        "지난 분기 성과 지표 알려줘",
        "이 계약서 해지 조건이 뭐야?",
        "보안 감사 결과 어떻게 나왔어?",
    ],
}

# ── 경계 쌍 정의 ──
BOUNDARY_PAIRS = [
    {
        "id": 1, "risk": "high",
        "intent_a": "doc_search", "intent_b": "doc_qa",
        "examples": (
            '"출장비 규정 찾아줘" → doc_search (문서를 찾고 싶다)\n'
            '"출장비 얼마야?" → doc_qa (문서 안의 금액을 알고 싶다)\n'
            '"보안 규정 있어?" → doc_search (문서 존재 확인)\n'
            '"보안 규정에 USB 관련 내용 뭐야?" → doc_qa (문서 내용 질문)'
        ),
    },
    {
        "id": 2, "risk": "high",
        "intent_a": "doc_search", "intent_b": "judgment",
        "examples": (
            '"연차 규정 알려줘" → doc_search (규정 내용을 보고 싶다)\n'
            '"연차 써도 돼?" → judgment (쓸 수 있는지 판단해달라)\n'
            '"보안 정책 찾아줘" → doc_search (정책 문서 검색)\n'
            '"USB 써도 되나?" → judgment (규정 위반 여부 판단)'
        ),
    },
    {
        "id": 3, "risk": "high",
        "intent_a": "doc_qa", "intent_b": "judgment",
        "examples": (
            '"보안 규정에 뭐라고 써있어?" → doc_qa (사실 확인)\n'
            '"USB 써도 돼?" → judgment (가능 여부 판단)\n'
            '"연차 몇 일 남았어?" → doc_qa (정보 조회)\n'
            '"연차 내일 써도 되나?" → judgment (허용 여부 판단)'
        ),
    },
    {
        "id": 4, "risk": "high",
        "intent_a": "doc_summary", "intent_b": "doc_qa",
        "examples": (
            '"이 문서 핵심이 뭐야?" → doc_summary (전체 요약)\n'
            '"이 문서에서 예산이 얼마야?" → doc_qa (특정 사항 질문)\n'
            '"회의록 요약해줘" → doc_summary (전체 정리)\n'
            '"회의에서 누가 담당자야?" → doc_qa (특정 정보)'
        ),
    },
    {
        "id": 5, "risk": "high",
        "intent_a": "doc_generate", "intent_b": "doc_summary",
        "examples": (
            '"회의 내용으로 보고서 작성해줘" → doc_generate (새 문서 생성)\n'
            '"회의 내용 정리해줘" → doc_summary (기존 내용 요약)\n'
            '"제안서 만들어줘" → doc_generate (새로 만들기)\n'
            '"제안서 핵심만 뽑아줘" → doc_summary (기존 것 요약)'
        ),
    },
    {
        "id": 6, "risk": "high",
        "intent_a": "schedule_add", "intent_b": "schedule_view",
        "examples": (
            '"다음주 미팅 잡아줘" → schedule_add (새 일정 등록)\n'
            '"다음주 미팅 언제야?" → schedule_view (기존 일정 확인)\n'
            '"금요일에 회의 넣어줘" → schedule_add (추가)\n'
            '"금요일에 뭐 있지?" → schedule_view (조회)'
        ),
    },
    {
        "id": 7, "risk": "medium",
        "intent_a": "doc_search", "intent_b": "doc_summary",
        "examples": (
            '"보안 규정 있어?" → doc_search (문서 존재/위치 확인)\n'
            '"보안 규정 요약해줘" → doc_summary (내용 요약)\n'
            '"인사 평가 기준 문서 찾아줘" → doc_search (검색)\n'
            '"인사 평가 기준 핵심만 알려줘" → doc_summary (요약)'
        ),
    },
    {
        "id": 8, "risk": "medium",
        "intent_a": "judgment", "intent_b": "general",
        "examples": (
            '"재택근무 해도 돼?" → judgment (규정 기반 판단)\n'
            '"오늘 점심 뭐 먹을까?" → general (일상 질문)\n'
            '"야근 수당 안 주면 위반이야?" → judgment (규정 판단)\n'
            '"요즘 힘들다" → general (일상 대화)'
        ),
    },
    {
        "id": 9, "risk": "medium",
        "intent_a": "doc_generate", "intent_b": "doc_qa",
        "examples": (
            '"JD 만들어줘" → doc_generate (새 문서 생성)\n'
            '"JD에 필수 조건이 뭐야?" → doc_qa (기존 문서 질문)\n'
            '"보고서 작성해줘" → doc_generate (생성)\n'
            '"보고서에 결론이 뭐라고 써있어?" → doc_qa (내용 질문)'
        ),
    },
    {
        "id": 10, "risk": "medium",
        "intent_a": "doc_search", "intent_b": "doc_generate",
        "examples": (
            '"제안서 양식 있어?" → doc_search (양식 검색)\n'
            '"제안서 만들어줘" → doc_generate (새로 생성)\n'
            '"회의록 템플릿 찾아줘" → doc_search (검색)\n'
            '"회의록 작성해줘" → doc_generate (생성)'
        ),
    },
]

# ── LLM 클라이언트 ──

class LLMClient:
    """듀얼 LLM 클라이언트 — GPT API + Claude API"""

    def __init__(self):
        self.gpt_client = None
        self.claude_client = None
        self._init_gpt()
        self._init_claude()

    def _init_gpt(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import OpenAI
                self.gpt_client = OpenAI(api_key=api_key)
                print("[OK] GPT API 연결됨")
            except Exception as e:
                print(f"[WARN] GPT API 연결 실패: {e}")
        else:
            print("[SKIP] OPENAI_API_KEY 없음")

    def _init_claude(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            try:
                from anthropic import Anthropic
                self.claude_client = Anthropic(api_key=api_key)
                print("[OK] Claude API 연결됨")
            except Exception as e:
                print(f"[WARN] Claude API 연결 실패: {e}")
        else:
            print("[SKIP] ANTHROPIC_API_KEY 없음 - Claude는 웹에서 수동 생성")

    def available_llms(self) -> list[str]:
        """사용 가능한 LLM 목록"""
        llms = []
        if self.gpt_client:
            llms.append("gpt")
        if self.claude_client:
            llms.append("claude")
        return llms

    def generate(self, llm: str, prompt: str, max_retries: int = 3) -> str:
        """LLM 호출하여 텍스트 응답 반환"""
        for attempt in range(max_retries):
            try:
                if llm == "gpt":
                    return self._call_gpt(prompt)
                elif llm == "claude":
                    return self._call_claude(prompt)
                else:
                    raise ValueError(f"Unknown LLM: {llm}")
            except Exception as e:
                print(f"  [{llm}] 시도 {attempt+1}/{max_retries} 실패: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"[{llm}] {max_retries}회 시도 모두 실패")

    def _call_gpt(self, prompt: str) -> str:
        resp = self.gpt_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=8000,
        )
        return resp.choices[0].message.content

    def _call_claude(self, prompt: str) -> str:
        resp = self.claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text


# ── 프롬프트 빌더 ──

def build_basic_prompt(intent: str) -> str:
    """기본 데이터 생성 프롬프트 (intent별 100개)"""
    seeds = "\n".join(f"{i+1}. {s}" for i, s in enumerate(SEED_SENTENCES[intent]))
    all_intents = "\n".join(
        f"- {k}: {v}" for k, v in INTENT_DEFINITIONS.items()
    )

    return f"""한국어 직장인 챗봇의 intent 분류 학습 데이터를 생성해주세요.

## Intent 정보
- **라벨**: {intent}
- **정의**: {INTENT_DEFINITIONS[intent]}

## 전체 Intent 목록 (다른 intent와 혼동하지 말 것)
{all_intents}

## Seed 예시 (이런 스타일 참고)
{seeds}

## 생성 규칙
1. **150개** 고유 문장 생성 (중복 없음)
2. 모든 문장은 반드시 **{intent}** intent에만 해당해야 함
3. 다른 intent로 해석될 수 있는 애매한 문장은 제외
4. 길이 분포:
   - 초단문 (2~4어절): 30개
   - 단문 (5~8어절): 45개
   - 중문 (9~15어절): 45개
   - 장문 (16어절 이상): 30개
5. 스타일 분포:
   - 반말/구어체: 60개
   - 존댓말: 45개
   - 격식체: 25개
   - 오타/줄임말 포함: 20개
6. 주제를 다양하게: 연차, 출장, 보안, 인사평가, 급여, 복리후생, 프로젝트, 회의 등

## 출력 형식
JSONL 형식으로만 출력 (설명 없이 데이터만):
{{"text": "문장", "label": "{intent}"}}
(150줄)"""


def build_boundary_prompt(pair: dict) -> str:
    """경계 쌍 생성 프롬프트 (쌍당 30개)"""
    all_intents = "\n".join(
        f"- {k}: {v}" for k, v in INTENT_DEFINITIONS.items()
    )

    return f"""한국어 직장인 챗봇의 intent 분류 경계 테스트 데이터를 생성해주세요.

## 경계 쌍
- **Intent A**: {pair["intent_a"]} — {INTENT_DEFINITIONS[pair["intent_a"]]}
- **Intent B**: {pair["intent_b"]} — {INTENT_DEFINITIONS[pair["intent_b"]]}

## 전체 Intent 목록
{all_intents}

## 핵심 규칙
이 두 intent는 **같은 주제**로 발화할 수 있지만 **사용자의 의도(화행)가 다릅니다**.
모델이 주제가 아니라 화행을 구분하도록 훈련하기 위한 데이터입니다.

## 생성 규칙
1. **{pair["intent_a"]}** 라벨 15개 + **{pair["intent_b"]}** 라벨 15개 = 총 30개
2. 같은 키워드/주제를 공유하되, 의도가 명확히 다른 문장
3. 사람이 봤을 때 라벨이 명확해야 함 (애매하면 제외)
4. 스타일: 반말/존댓말/오타 섞기
5. 주제 다양하게: 연차, 출장, 보안, 급여, 회의, 프로젝트 등

## 경계 구분 예시
{pair["examples"]}

## 출력 형식
JSONL 형식으로만 출력 (설명 없이):
{{"text": "문장", "label": "intent_라벨"}}
(30줄, A 15개 + B 15개 섞어서)"""


def build_adversarial_prompt() -> str:
    """적대적 테스트 생성 프롬프트 (전체 240개)"""
    all_intents = "\n".join(
        f"- {k}: {v}" for k, v in INTENT_DEFINITIONS.items()
    )

    return f"""한국어 직장인 챗봇의 intent 분류 적대적(adversarial) 테스트 데이터를 생성해주세요.
모델이 틀리기 쉬운 어려운 문장들입니다.

## Intent 목록
{all_intents}

## 생성 규칙
각 intent별로 30개씩, 총 240개 생성.
intent당 아래 7가지 유형을 골고루 포함 (유형별 ~4개):

1. **초단문** (2~3어절): "연차 되나?", "보고서 줘"
2. **오타/비표준**: "회이록 정리해조", "일졍 추가해줘어"
3. **격식체**: "연차 사용 가능 여부를 확인 요청드립니다"
4. **맥락 의존**: 문맥 없이는 애매하지만 의도는 명확 ("그거 돼?", "아까 그 문서")
5. **간접 표현**: 직접 요청 안 하고 돌려 말하기 ("연차 쓰고 싶은데...", "보고서가 필요한 상황이야")
6. **인터넷 언어**: "ㅂㄱㅅ 써줘", "일정 ㄱㄱ", "ㅎㅇㄹ 정리해줘"
7. **복합/긴 문장**: 여러 정보가 섞여있지만 핵심 intent는 하나

## 출력 형식
JSONL (설명 없이 데이터만):
{{"text": "문장", "label": "intent_라벨"}}
(240줄)"""


def build_validation_prompt(data: list[dict]) -> str:
    """교차 검증 프롬프트"""
    all_intents = "\n".join(
        f"- {k}: {v}" for k, v in INTENT_DEFINITIONS.items()
    )
    data_lines = "\n".join(json.dumps(d, ensure_ascii=False) for d in data)

    return f"""한국어 직장인 챗봇의 intent 분류 데이터를 검증해주세요.

## Intent 정의
{all_intents}

## 검증 규칙
각 문장의 라벨이 올바른지 판단해주세요.
- **agree**: 라벨이 올바름
- **disagree**: 라벨이 틀림 → 올바른 라벨을 suggested_label에 기입
- **ambiguous**: 애매함 → 가장 가능성 높은 라벨을 suggested_label에 기입

## 검증 대상 데이터
{data_lines}

## 출력 형식
JSONL로만 출력:
{{"text": "원문", "original_label": "원래라벨", "vote": "agree/disagree/ambiguous", "suggested_label": "제안라벨_or_null"}}"""


# ── 파싱 유틸리티 ──

def parse_jsonl_response(response: str) -> list[dict]:
    """LLM 응답에서 JSONL 파싱 (코드블록, 잡음 제거)"""
    # 코드블록 안의 내용 추출
    code_block = re.search(r"```(?:jsonl?)?\s*\n(.*?)```", response, re.DOTALL)
    if code_block:
        text = code_block.group(1)
    else:
        text = response

    results = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            item = json.loads(line)
            if "text" in item and "label" in item:
                results.append({"text": item["text"].strip(), "label": item["label"].strip()})
        except json.JSONDecodeError:
            continue

    return results


def save_jsonl(data: list[dict], path: Path):
    """JSONL 파일 저장"""
    with open(path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  -> {path.name} ({len(data)}개 저장)")


def load_jsonl(path: Path) -> list[dict]:
    """JSONL 파일 로드"""
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


# ── Step 별 실행 함수 ──

def step_basic(client: LLMClient, target_llm: str = None):
    """Step 1: 기본 데이터 생성 (intent별 100개 × LLM 3개)"""
    print("\n" + "=" * 60)
    print("  Step 1: 기본 데이터 생성")
    print("=" * 60)

    llms = [target_llm] if target_llm else client.available_llms()

    for llm in llms:
        print(f"\n--- {llm.upper()} ---")
        for intent in INTENT_LABELS:
            out_path = RAW_DIR / f"{llm}_{intent}.jsonl"
            if out_path.exists():
                existing = load_jsonl(out_path)
                if len(existing) >= 140:  # 140개 이상이면 skip
                    print(f"  [{intent}] 이미 존재 ({len(existing)}개) — skip")
                    continue

            print(f"  [{intent}] 생성 중...")
            prompt = build_basic_prompt(intent)

            try:
                response = client.generate(llm, prompt)

                # 디버그: 원본 응답 저장
                debug_path = RAW_DIR / f"{llm}_{intent}_raw.txt"
                with open(debug_path, "w", encoding="utf-8") as df:
                    df.write(response)

                items = parse_jsonl_response(response)

                # 라벨 필터링
                items = [d for d in items if d["label"] == intent]

                if len(items) == 0:
                    print(f"  [WARN] 파싱 결과 0개! 원본: {debug_path}")
                    print(f"  [WARN] 응답 첫 200자: {response[:200]}")

                save_jsonl(items, out_path)
            except Exception as e:
                print(f"  [{intent}] 실패: {e}")

            time.sleep(1)  # rate limit 방지


def step_boundary(client: LLMClient, target_llm: str = None):
    """Step 2: 경계 쌍 데이터 생성 (10쌍 × 30개 × LLM 3개)"""
    print("\n" + "=" * 60)
    print("  Step 2: 경계 쌍 데이터 생성")
    print("=" * 60)

    llms = [target_llm] if target_llm else client.available_llms()

    for llm in llms:
        print(f"\n--- {llm.upper()} ---")
        for pair in BOUNDARY_PAIRS:
            pair_name = f"{pair['intent_a']}_{pair['intent_b']}"
            out_path = RAW_DIR / f"{llm}_boundary_{pair['id']:02d}_{pair_name}.jsonl"
            if out_path.exists():
                existing = load_jsonl(out_path)
                if len(existing) >= 25:
                    print(f"  [쌍{pair['id']}] 이미 존재 ({len(existing)}개) — skip")
                    continue

            print(f"  [쌍{pair['id']}] {pair['intent_a']} ↔ {pair['intent_b']} 생성 중...")
            prompt = build_boundary_prompt(pair)

            try:
                response = client.generate(llm, prompt)
                items = parse_jsonl_response(response)

                # 허용 라벨만
                valid = {pair["intent_a"], pair["intent_b"]}
                items = [d for d in items if d["label"] in valid]

                save_jsonl(items, out_path)
            except Exception as e:
                print(f"  [쌍{pair['id']}] 실패: {e}")

            time.sleep(1)


def step_adversarial(client: LLMClient, target_llm: str = None):
    """Step 3: 적대적 테스트 생성 (240개 × LLM 3개)"""
    print("\n" + "=" * 60)
    print("  Step 3: 적대적 테스트 생성")
    print("=" * 60)

    llms = [target_llm] if target_llm else client.available_llms()

    for llm in llms:
        out_path = RAW_DIR / f"{llm}_adversarial.jsonl"
        if out_path.exists():
            existing = load_jsonl(out_path)
            if len(existing) >= 200:
                print(f"  [{llm}] 이미 존재 ({len(existing)}개) — skip")
                continue

        print(f"  [{llm.upper()}] 적대적 240개 생성 중...")
        prompt = build_adversarial_prompt()

        try:
            response = client.generate(llm, prompt)
            items = parse_jsonl_response(response)

            # 허용 라벨만
            items = [d for d in items if d["label"] in set(INTENT_LABELS)]

            save_jsonl(items, out_path)
        except Exception as e:
            print(f"  [{llm}] 실패: {e}")

        time.sleep(1)


def step_validate(client: LLMClient):
    """Step 4: 교차 검증 (경계 쌍 + 적대적)"""
    print("\n" + "=" * 60)
    print("  Step 4: 교차 검증")
    print("=" * 60)

    llm_list = client.available_llms()
    if len(llm_list) < 2:
        print("  [SKIP] 검증에는 최소 2개 LLM 필요")
        return

    # 경계 쌍 검증
    for pair in BOUNDARY_PAIRS:
        pair_name = f"{pair['intent_a']}_{pair['intent_b']}"

        for source_llm in llm_list:
            source_path = RAW_DIR / f"{source_llm}_boundary_{pair['id']:02d}_{pair_name}.jsonl"
            if not source_path.exists():
                continue

            data = load_jsonl(source_path)
            validators = [l for l in llm_list if l != source_llm]

            for validator in validators:
                vote_path = RAW_DIR / f"{validator}_vote_boundary_{pair['id']:02d}_{source_llm}.jsonl"
                if vote_path.exists():
                    print(f"  [쌍{pair['id']}] {validator} → {source_llm} 검증 이미 존재 — skip")
                    continue

                print(f"  [쌍{pair['id']}] {validator}가 {source_llm} 데이터 검증 중...")
                prompt = build_validation_prompt(data)

                try:
                    response = client.generate(validator, prompt)
                    votes = parse_jsonl_response(response)
                    save_jsonl(votes, vote_path)
                except Exception as e:
                    print(f"  실패: {e}")

                time.sleep(1)

    # 적대적 검증
    for source_llm in llm_list:
        source_path = RAW_DIR / f"{source_llm}_adversarial.jsonl"
        if not source_path.exists():
            continue

        data = load_jsonl(source_path)
        validators = [l for l in llm_list if l != source_llm]

        for validator in validators:
            vote_path = RAW_DIR / f"{validator}_vote_adversarial_{source_llm}.jsonl"
            if vote_path.exists():
                print(f"  [adv] {validator} → {source_llm} 검증 이미 존재 — skip")
                continue

            print(f"  [adv] {validator}가 {source_llm} 적대적 데이터 검증 중...")

            # 적대적은 양이 많으므로 50개씩 나눠서 검증
            all_votes = []
            for i in range(0, len(data), 50):
                batch = data[i:i+50]
                prompt = build_validation_prompt(batch)
                try:
                    response = client.generate(validator, prompt)
                    votes = parse_jsonl_response(response)
                    all_votes.extend(votes)
                except Exception as e:
                    print(f"    batch {i//50+1} 실패: {e}")
                time.sleep(1)

            save_jsonl(all_votes, vote_path)


def step_qa():
    """Step 5: 품질 검증 (자동 QA)"""
    print("\n" + "=" * 60)
    print("  Step 5: 품질 검증 (QA)")
    print("=" * 60)

    report = []
    issues = []

    # 1. 기본 데이터 합치기
    all_basic = []
    for intent in INTENT_LABELS:
        intent_data = []
        for llm_file in sorted(RAW_DIR.glob(f"*_{intent}.jsonl")):
            if "boundary" in llm_file.name or "adversarial" in llm_file.name or "vote" in llm_file.name:
                continue
            intent_data.extend(load_jsonl(llm_file))

        # 중복 제거 (exact text match)
        seen = set()
        deduped = []
        for d in intent_data:
            if d["text"] not in seen:
                seen.add(d["text"])
                deduped.append(d)

        dup_count = len(intent_data) - len(deduped)
        report.append(f"  {intent}: {len(deduped)}개 (중복 {dup_count}개 제거)")
        if dup_count > 0:
            issues.append(f"  {intent}: 중복 {dup_count}개 발견")

        # intent별 JSONL 저장
        save_jsonl(deduped, DATA_DIR / f"{intent}.jsonl")
        all_basic.extend(deduped)

    # 2. 경계 쌍 합치기
    all_boundary = []
    for pair in BOUNDARY_PAIRS:
        pair_name = f"{pair['intent_a']}_{pair['intent_b']}"
        pair_data = []
        for f in sorted(RAW_DIR.glob(f"*_boundary_{pair['id']:02d}_{pair_name}.jsonl")):
            if "vote" in f.name:
                continue
            pair_data.extend(load_jsonl(f))

        # 중복 제거
        seen = set()
        deduped = []
        for d in pair_data:
            if d["text"] not in seen:
                seen.add(d["text"])
                deduped.append(d)

        all_boundary.extend(deduped)

    save_jsonl(all_boundary, DATA_DIR / "boundary_pairs.jsonl")
    report.append(f"\n  경계 쌍 합계: {len(all_boundary)}개")

    # 3. 적대적 합치기 (교차 검증 결과 반영)
    all_adv = []
    for llm_file in sorted(RAW_DIR.glob("*_adversarial.jsonl")):
        if "vote" in llm_file.name:
            continue
        all_adv.extend(load_jsonl(llm_file))

    # 중복 제거
    seen = set()
    deduped_adv = []
    for d in all_adv:
        if d["text"] not in seen:
            seen.add(d["text"])
            deduped_adv.append(d)

    # 적대적은 JSON으로 저장
    with open(DATA_DIR / "adversarial_v2.json", "w", encoding="utf-8") as f:
        json.dump(deduped_adv, f, ensure_ascii=False, indent=2)
    report.append(f"  적대적 합계: {len(deduped_adv)}개")

    # 4. QA 체크
    all_data = all_basic + all_boundary
    print("\n--- QA 결과 ---")
    print("\n".join(report))

    # 라벨 유효성
    invalid_labels = [d for d in all_data if d["label"] not in set(INTENT_LABELS)]
    print(f"\n  라벨 유효성: {len(invalid_labels)}개 비유효 라벨")
    if invalid_labels:
        issues.append(f"  비유효 라벨 {len(invalid_labels)}개")

    # 클래스 균형
    label_counts = Counter(d["label"] for d in all_basic)
    if label_counts:
        max_c = max(label_counts.values())
        min_c = min(label_counts.values())
        ratio = max_c / min_c if min_c > 0 else float("inf")
        print(f"  클래스 균형: max/min = {ratio:.2f} (< 1.2 권장)")
        print(f"    분포: {dict(label_counts)}")
        if ratio > 1.2:
            issues.append(f"  클래스 불균형: max/min = {ratio:.2f}")

    # 총계
    total = len(all_basic) + len(all_boundary)
    print(f"\n  학습 데이터 총계: {total}개 (기본 {len(all_basic)} + 경계 {len(all_boundary)})")
    print(f"  적대적 테스트: {len(deduped_adv)}개")

    if issues:
        print(f"\n  [WARNING] 발견된 이슈 {len(issues)}건:")
        for issue in issues:
            print(f"    {issue}")
    else:
        print("\n  [OK] QA 통과!")

    # QA 보고서 저장
    ratio_str = f"{ratio:.2f}" if label_counts else "N/A"
    report_str = "\n".join(report)
    issues_str = "\n".join(issues) if issues else "없음"
    qa_report = f"""# 데이터 품질 검증 보고서 (자동 생성)

## 기본 데이터
{report_str}

## QA 결과
- 비유효 라벨: {len(invalid_labels)}개
- 클래스 균형 (max/min): {ratio_str}
- 학습 총계: {total}개
- 적대적 테스트: {len(deduped_adv)}개

## 이슈
{issues_str}
"""
    with open(DATA_DIR / "DATA_QA_REPORT.md", "w", encoding="utf-8") as f:
        f.write(qa_report)
    print(f"\n  -> DATA_QA_REPORT.md 저장됨")


def step_split():
    """Step 6: Stratified Train/Val/Test 분할 (80/10/10)"""
    print("\n" + "=" * 60)
    print("  Step 6: Train/Val/Test 분할")
    print("=" * 60)

    SEED = 42
    random.seed(SEED)

    # 기본 데이터 + 경계 쌍 로드
    all_data = []
    for intent in INTENT_LABELS:
        path = DATA_DIR / f"{intent}.jsonl"
        if path.exists():
            all_data.extend(load_jsonl(path))

    boundary_path = DATA_DIR / "boundary_pairs.jsonl"
    if boundary_path.exists():
        all_data.extend(load_jsonl(boundary_path))

    if not all_data:
        print("  [ERROR] 데이터 없음!")
        return

    # Stratified split
    by_label = {}
    for item in all_data:
        by_label.setdefault(item["label"], []).append(item)

    train, val, test = [], [], []
    for label, items in by_label.items():
        random.shuffle(items)
        n = len(items)
        n_test = max(1, int(n * 0.1))
        n_val = max(1, int(n * 0.1))

        test.extend(items[:n_test])
        val.extend(items[n_test:n_test + n_val])
        train.extend(items[n_test + n_val:])

    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)

    save_jsonl(train, SPLITS_DIR / "train.jsonl")
    save_jsonl(val, SPLITS_DIR / "val.jsonl")
    save_jsonl(test, SPLITS_DIR / "test.jsonl")

    print(f"\n  Train: {len(train)}개")
    print(f"  Val:   {len(val)}개")
    print(f"  Test:  {len(test)}개")
    print(f"  합계:  {len(train) + len(val) + len(test)}개")

    # 분포 확인
    for name, data in [("Train", train), ("Val", val), ("Test", test)]:
        dist = Counter(d["label"] for d in data)
        print(f"\n  {name} 분포: {dict(sorted(dist.items()))}")

    # 테스트 누출 체크
    train_texts = set(d["text"] for d in train)
    test_texts = set(d["text"] for d in test)
    val_texts = set(d["text"] for d in val)

    leak_test = train_texts & test_texts
    leak_val = train_texts & val_texts
    if leak_test:
        print(f"\n  [WARNING] Train-Test 누출: {len(leak_test)}개!")
    if leak_val:
        print(f"\n  [WARNING] Train-Val 누출: {len(leak_val)}개!")
    if not leak_test and not leak_val:
        print(f"\n  [OK] 누출 없음!")


# ── 메인 ──

def main():
    parser = argparse.ArgumentParser(description="Intent v2 데이터 생성 파이프라인")
    parser.add_argument("--step", choices=["basic", "boundary", "adversarial", "validate", "qa", "split", "all"],
                        default="all", help="실행할 단계")
    parser.add_argument("--llm", choices=["gpt", "claude"],
                        default=None, help="특정 LLM만 실행")
    args = parser.parse_args()

    print("=" * 60)
    print("  Intent v2 데이터 생성 파이프라인")
    print("=" * 60)

    client = LLMClient()
    available = client.available_llms()
    print(f"\n사용 가능 LLM: {available}")

    if args.llm and args.llm not in available:
        print(f"\n[ERROR] {args.llm} API 사용 불가. .env 파일을 확인하세요.")
        return

    steps = {
        "basic": lambda: step_basic(client, args.llm),
        "boundary": lambda: step_boundary(client, args.llm),
        "adversarial": lambda: step_adversarial(client, args.llm),
        "validate": lambda: step_validate(client),
        "qa": step_qa,
        "split": step_split,
    }

    if args.step == "all":
        for name, func in steps.items():
            func()
    else:
        steps[args.step]()

    print("\n" + "=" * 60)
    print("  완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
