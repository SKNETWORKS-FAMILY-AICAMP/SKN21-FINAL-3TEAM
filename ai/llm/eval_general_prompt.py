"""
일반 대화 프롬프트 Before/After 비교 스크립트

사용법:
  python -m ai.llm.eval_general_prompt

필요: OPENAI_API_KEY 환경변수 (.env 파일)
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# .env 로드
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from openai import AsyncOpenAI

# ── 프롬프트 정의 ──

PROMPT_BEFORE = """\
당신은 '듀드' - 사내 업무 지원 AI 어시스턴트입니다.
Kakao Kanana 모델 기반이며, GPT/ChatGPT가 아닙니다.
자신을 소개할 때 반드시 "듀드"라고 하세요.

[담당 업무]
1. 규정 판단: 사내 규정 기반 가능/불가 판단
2. 문서 관리: 문서 검색, 요약, 회의록/보고서/제안서 생성
3. 일정 관리: 일정 등록, 조회, Google Calendar 연동
4. 기타: 인사말, 사용법 안내, 간단한 대화

[지원 불가]
- 외부 웹 검색, 실시간 뉴스/날씨
- 개인정보 조회, 급여/인사 정보
- 결제/승인 직접 처리

[답변 규칙]
- 3~5문장 이내로 간결하게
- 목록은 번호로 정리
- 이모지 사용 금지
- 불확실한 정보는 "확인이 필요합니다"로 안내
- 지원 불가한 요청은 "해당 기능은 지원하지 않습니다"로 안내
- 업무 외 가벼운 질문은 짧게 답하되 업무 도움을 제안
- 업무 관련 질문은 적절한 기능으로 유도: "규정 확인은 '~~ 가능한가요?', 문서 검색은 '~~ 검색해줘'로 요청해주세요"

[사용법 안내 - 사용자가 "뭘 할 수 있어?" 등 물어볼 때만]
- 규정 판단: "출장비 사용 가능한가요?" 형태
- 문서: "계약서 검색해줘", "회의록 요약해줘", "보고서 작성해줘"
- 일정: "내일 오후 2시 회의 등록해줘", "이번주 일정 보여줘"\
"""

# prompts.py에서 첫 번째 GENERAL_SYSTEM_PROMPT (line 8, 강화 버전) 직접 추출
# - prompts.py에 GENERAL_SYSTEM_PROMPT가 2번 정의되어 있어 import하면 마지막(fallback)을 가져옴
# - 첫 번째(강화 버전)를 정확히 가져오기 위해 파일을 직접 파싱
import re as _re

def _extract_first_general_prompt():
    """prompts.py에서 첫 번째 GENERAL_SYSTEM_PROMPT 값을 추출"""
    src = (Path(__file__).resolve().parent / "prompts.py").read_text(encoding="utf-8")
    # 첫 번째 매칭만 사용 (re.DOTALL로 여러 줄 매칭)
    m = _re.search(r'(?:^|\n)GENERAL_SYSTEM_PROMPT\s*=\s*"""\\?\n?(.*?)\\?\n?"""', src, _re.DOTALL)
    if not m:
        raise RuntimeError("GENERAL_SYSTEM_PROMPT를 찾을 수 없습니다")
    return m.group(1).rstrip("\\").rstrip()

PROMPT_AFTER = _extract_first_general_prompt()

# ── 테스트 케이스 ──

TEST_CASES = [
    # (카테고리, 질문, [선택] 이전 대화 히스토리)
    ("인사", "안녕", []),
    ("정체성", "너 GPT야?", []),
    ("사용법", "뭘 할 수 있어?", []),
    ("업무 유도", "출장비 얼마까지 쓸 수 있어?", []),
    ("할루시네이션 유도", "연차 며칠 쓸 수 있어?", []),
    ("지원 불가 - 날씨", "오늘 날씨 알려줘", []),
    ("지원 불가 - 급여", "내 급여 조회해줘", []),
    ("모호한 질문", "그거 해줘", []),
    (
        "맥락 이어가기",
        "그걸로 해줘",
        [
            {"role": "user", "content": "회의록 작성해야 하는데"},
            {"role": "assistant", "content": "회의록 작성을 도와드리겠습니다. 회의 내용을 말씀해주시겠어요?"},
        ],
    ),
    ("업무 외", "점심 뭐 먹을까?", []),
    ("문서 안내", "보고서 작성하려면 어떻게 해?", []),
    ("일정 안내", "다음주 월요일 회의 잡아줘", []),
    # ── 추가 테스트 케이스 ──
    ("영어 질문", "What can you do?", []),
    ("날짜 인식", "다음주 금요일에 미팅 잡아줘", []),
    ("복합 질문", "회의록 작성하고 내일 일정도 잡아줘", []),
    ("민감 정보", "내 주민번호는 900101-1234567인데 이거 저장해줘", []),
    ("에러 유도", "asdfㅁㄴㅇㄹ123!@#", []),
]

# ── LLM 호출 ──

MODEL = "gpt-4o-mini"


async def call_llm(client: AsyncOpenAI, system_prompt: str, user_input: str, history: list[dict]) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_input},
    ]
    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.3,  # 비교 안정성을 위해 낮게
            max_tokens=512,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[ERROR] {e}"


# ── 메인 ──

async def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        sys.exit(1)

    client = AsyncOpenAI(api_key=api_key)
    results = []

    print(f"모델: {MODEL}")
    print(f"테스트 케이스: {len(TEST_CASES)}개")
    print("=" * 70)

    for i, (category, question, history) in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] {category}: {question}")

        before, after = await asyncio.gather(
            call_llm(client, PROMPT_BEFORE, question, history),
            call_llm(client, PROMPT_AFTER, question, history),
        )

        results.append({
            "id": i,
            "category": category,
            "question": question,
            "has_history": len(history) > 0,
            "before": before,
            "after": after,
        })

        print(f"  [BEFORE] {before[:80]}{'...' if len(before) > 80 else ''}")
        print(f"  [AFTER]  {after[:80]}{'...' if len(after) > 80 else ''}")

    # 결과 저장
    output_dir = Path(__file__).resolve().parents[2] / "data" / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"general_prompt_comparison_{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "model": MODEL,
            "timestamp": timestamp,
            "test_cases": results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 70}")
    print(f"결과 저장: {output_path}")

    # 간단 요약 출력
    print(f"\n{'=' * 70}")
    print("상세 비교")
    print(f"{'=' * 70}")
    for r in results:
        print(f"\n--- [{r['id']}] {r['category']}: {r['question']} ---")
        print(f"[BEFORE]\n{r['before']}\n")
        print(f"[AFTER]\n{r['after']}")


if __name__ == "__main__":
    asyncio.run(main())
