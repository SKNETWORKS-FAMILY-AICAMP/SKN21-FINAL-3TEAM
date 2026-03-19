"""
대화 요약 모듈 — sLLM 기반 대화 기억 압축

긴 대화에서 오래된 메시지를 sLLM(vLLM)으로 요약하여
토큰을 절약하면서 맥락을 유지합니다.

흐름:
  1. chat.py에서 ChatLog 저장 후 호출
  2. 현재 세션의 전체 메시지를 로드
  3. 최근 3턴(6개)을 제외한 나머지 + 기존 요약을 합쳐서 새 요약 생성
  4. ChatSession.summary에 저장

sLLM 실패 시 GPT-4o-mini로 fallback.
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# 요약 트리거 기준: 이 턴 수를 초과하면 요약 생성
SUMMARY_TRIGGER_TURNS = 3  # 3턴(6메시지) 초과 시

CHAT_SUMMARY_SYSTEM_PROMPT = """\
당신은 대화 요약 전문가입니다.
이전 대화 내용을 간결하게 요약하여 대화의 핵심 맥락을 보존합니다.

규칙:
- 사용자가 어떤 주제로 질문했는지, AI가 어떤 답변을 했는지 핵심만 정리하세요.
- 판단 결과(가능/불가/조건부), 문서 생성 결과, 일정 등록 결과 등 중요 결과를 반드시 포함하세요.
- 규정 조항번호, 날짜, 금액 등 구체적인 수치/정보는 유지하세요.
- 3~5문장 이내로 요약하세요.
- 한국어로 작성하세요.\
"""


async def summarize_chat_history(
    messages: list[dict],
    existing_summary: Optional[str] = None,
) -> str:
    """대화 메시지 목록을 요약 텍스트로 압축

    Args:
        messages: 요약할 메시지 목록 [{"role": "user"|"assistant", "content": "..."}]
        existing_summary: 기존 요약 (있으면 합쳐서 갱신)

    Returns:
        요약 텍스트
    """
    # 요약할 대화 텍스트 구성
    lines = []
    if existing_summary:
        lines.append(f"[이전 대화 요약]\n{existing_summary}\n")

    lines.append("[새로운 대화]")
    for msg in messages:
        role = "사용자" if msg["role"] == "user" else "AI"
        content = msg.get("content", "")
        if content:
            # 너무 긴 응답은 앞부분만 (토큰 절약)
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"{role}: {content}")

    prompt = "\n".join(lines)

    # sLLM(vLLM) 우선 시도
    use_vllm = os.getenv("LLM_PROVIDER", "").lower() == "vllm" or os.getenv("VLLM_BASE_URL")

    if use_vllm:
        try:
            summary = await _summarize_with_vllm(prompt)
            if summary:
                logger.info("[Summarizer] sLLM 요약 성공 (%d자)", len(summary))
                return summary
        except Exception as e:
            logger.warning("[Summarizer] sLLM 요약 실패, fallback: %s", e)

    # Fallback: GPT-4o-mini
    try:
        summary = await _summarize_with_openai(prompt)
        logger.info("[Summarizer] GPT fallback 요약 성공 (%d자)", len(summary))
        return summary
    except Exception as e:
        logger.error("[Summarizer] 요약 완전 실패: %s", e)
        # 최후 수단: 단순 텍스트 축약
        return _fallback_truncate(messages, existing_summary)


async def _summarize_with_vllm(prompt: str) -> str:
    """vLLM(sLLM)으로 요약 생성"""
    from ai.serving.vllm_client import VLLMProvider
    provider = VLLMProvider()
    response = await provider.generate(
        prompt=prompt,
        system_prompt=CHAT_SUMMARY_SYSTEM_PROMPT,
        max_tokens=300,
        temperature=0.3,
    )
    return response.content.strip()


async def _summarize_with_openai(prompt: str) -> str:
    """GPT-4o-mini로 요약 생성 (fallback)"""
    from openai import AsyncOpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 미설정")

    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": CHAT_SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=300,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def _fallback_truncate(
    messages: list[dict],
    existing_summary: Optional[str] = None,
) -> str:
    """LLM 전부 실패 시 단순 규칙 기반 축약"""
    parts = []
    if existing_summary:
        parts.append(existing_summary)

    for msg in messages:
        role = "사용자" if msg["role"] == "user" else "AI"
        content = msg.get("content", "")
        if content:
            parts.append(f"{role}: {content[:100]}")

    result = " | ".join(parts)
    # 최대 500자로 제한
    return result[:500]
