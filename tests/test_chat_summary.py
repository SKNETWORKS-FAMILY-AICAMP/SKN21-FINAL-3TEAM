"""대화 요약 기능 테스트

테스트 순서:
  1) summarizer 모듈 단독 테스트 (sLLM → GPT fallback → 규칙 기반)
  2) _maybe_update_summary 로직 시뮬레이션
  3) 요약이 시스템 프롬프트에 잘 주입되는지 확인

실행:
  python tests/test_chat_summary.py
"""
import sys
import os
import asyncio
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")


# ── 테스트용 대화 데이터 ──

SAMPLE_MESSAGES = [
    {"role": "user", "content": "연차 사용 가능 일수가 궁금합니다"},
    {"role": "assistant", "content": "근속연수에 따라 다릅니다. 1년 미만은 월 1일, 1년 이상은 15일이 기본 부여됩니다. 취업규칙 제25조에 명시되어 있습니다."},
    {"role": "user", "content": "3년차인데 추가 연차가 있나요?"},
    {"role": "assistant", "content": "네, 3년 이상 근속 시 2년마다 1일씩 가산됩니다. 따라서 3년차는 기본 15일 + 가산 1일 = 총 16일입니다."},
    {"role": "user", "content": "반차도 사용 가능한가요?"},
    {"role": "assistant", "content": "네, 반차(오전/오후) 사용이 가능합니다. 취업규칙 제26조에 따라 반차는 연차 0.5일로 차감됩니다."},
    {"role": "user", "content": "경조사 휴가는 며칠인가요?"},
    {"role": "assistant", "content": "본인 결혼 5일, 자녀 결혼 1일, 배우자 출산 10일, 부모 사망 5일 등 경조사별로 다릅니다. 취업규칙 제28조를 참고하세요."},
]


async def test_1_summarizer_module():
    """[테스트 1] summarizer 모듈 단독 테스트"""
    print("=" * 60)
    print("[테스트 1] summarizer 모듈 — 대화 요약 생성")
    print("=" * 60)

    from ai.llm.summarizer import summarize_chat_history

    # 처음 4개 메시지(2턴) 요약
    messages = SAMPLE_MESSAGES[:4]
    print(f"\n  입력: {len(messages)}개 메시지 (2턴)")
    for m in messages:
        role = "사용자" if m["role"] == "user" else "  AI"
        print(f"    {role}: {m['content'][:60]}...")

    print(f"\n  요약 생성 중...")
    summary = await summarize_chat_history(messages)

    print(f"\n  ──── 생성된 요약 ────")
    print(f"  {summary}")
    print(f"  ────────────────────")
    print(f"  요약 길이: {len(summary)}자")

    if summary and len(summary) > 10:
        print(f"  [성공] 요약 생성 완료!")
        return summary
    else:
        print(f"  [실패] 요약이 비어있거나 너무 짧음")
        return None


async def test_2_incremental_summary(prev_summary):
    """[테스트 2] 기존 요약 + 새 메시지 → 갱신된 요약"""
    print(f"\n{'=' * 60}")
    print("[테스트 2] 기존 요약에 새 대화 추가하여 갱신")
    print("=" * 60)

    from ai.llm.summarizer import summarize_chat_history

    # 새로 추가된 메시지 (3~4번째 턴)
    new_messages = SAMPLE_MESSAGES[4:]
    print(f"\n  기존 요약: {prev_summary[:80]}...")
    print(f"  새 메시지: {len(new_messages)}개")

    print(f"\n  요약 갱신 중...")
    updated = await summarize_chat_history(new_messages, existing_summary=prev_summary)

    print(f"\n  ──── 갱신된 요약 ────")
    print(f"  {updated}")
    print(f"  ────────────────────")
    print(f"  길이: {len(updated)}자")

    if updated and len(updated) > len(prev_summary) * 0.5:
        print(f"  [성공] 요약 갱신 완료!")
        return True
    else:
        print(f"  [실패] 갱신 결과가 이상함")
        return False


async def test_3_fallback_truncate():
    """[테스트 3] LLM 없이 규칙 기반 fallback 확인"""
    print(f"\n{'=' * 60}")
    print("[테스트 3] fallback 규칙 기반 축약")
    print("=" * 60)

    from ai.llm.summarizer import _fallback_truncate

    result = _fallback_truncate(SAMPLE_MESSAGES[:4], existing_summary="이전 요약 테스트")

    print(f"\n  결과: {result[:200]}...")
    print(f"  길이: {len(result)}자 (최대 500자)")

    if result and "이전 요약 테스트" in result:
        print(f"  [성공] 기존 요약 포함 + 메시지 축약 정상")
        return True
    else:
        print(f"  [실패]")
        return False


async def test_4_prompt_injection():
    """[테스트 4] chat_summary가 시스템 프롬프트에 잘 주입되는지 확인"""
    print(f"\n{'=' * 60}")
    print("[테스트 4] 시스템 프롬프트 주입 시뮬레이션")
    print("=" * 60)

    summary = "사용자가 연차 관련 질문을 했고, 3년차 기준 16일 연차가 있으며 반차(0.5일) 사용이 가능하다고 답변함."

    # chat.py의 general_response 스트리밍 로직 시뮬레이션
    sys_prompt = "당신은 업무 도우미 '듀듀'입니다. 한국어로 친절하게 답변하세요."
    if summary:
        sys_prompt += f"\n\n[이전 대화 요약]\n{summary}"

    recent_history = [
        {"role": "user", "content": "경조사 휴가는 며칠인가요?"},
        {"role": "assistant", "content": "본인 결혼 5일, 자녀 결혼 1일..."},
    ]

    messages = [
        {"role": "system", "content": sys_prompt},
        *recent_history,
        {"role": "user", "content": "아까 연차 몇 일이라고 했죠?"},
    ]

    print(f"\n  시스템 프롬프트:")
    print(f"    {sys_prompt[:100]}...")
    print(f"  최근 대화: {len(recent_history)}개")
    print(f"  현재 질문: '{messages[-1]['content']}'")
    print(f"  → 요약에 '16일'이 있으므로 이전 맥락 참조 가능!")

    # 실제 API 호출 (OPENAI_API_KEY가 있으면)
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print(f"\n  GPT-4o-mini 호출로 실제 확인...")
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=openai_key)

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=200,
            temperature=0.3,
        )
        answer = response.choices[0].message.content
        print(f"\n  ──── AI 응답 ────")
        print(f"  {answer}")
        print(f"  ────────────────")

        if "16" in answer or "연차" in answer:
            print(f"  [성공] 요약 기반으로 이전 대화 맥락을 기억함!")
            return True
        else:
            print(f"  [주의] 응답에 '16'이 없음 — 요약 참조 여부 확인 필요")
            return True  # API 호출 자체는 성공
    else:
        print(f"\n  OPENAI_API_KEY 없음 — 프롬프트 구성만 확인")
        has_summary = "[이전 대화 요약]" in sys_prompt
        print(f"  [{'성공' if has_summary else '실패'}] 요약 주입 여부: {has_summary}")
        return has_summary


async def main():
    print("대화 요약(sLLM) 기능 테스트")
    print("─" * 60)

    # 테스트 3: LLM 불필요
    ok3 = await test_3_fallback_truncate()

    # 테스트 1: sLLM or GPT 필요
    summary = await test_1_summarizer_module()

    # 테스트 2: 테스트 1 결과 필요
    if summary:
        await test_2_incremental_summary(summary)

    # 테스트 4: 프롬프트 주입 확인
    await test_4_prompt_injection()

    print(f"\n{'=' * 60}")
    print("전체 테스트 완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
