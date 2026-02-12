"""
LLM API 연동 공통 모듈

사용법:
    from ai.llm import get_llm
    from ai.llm.prompts import JUDGMENT_SYSTEM_PROMPT

    llm = get_llm()
    response = await llm.generate(prompt="...", system_prompt=JUDGMENT_SYSTEM_PROMPT)
"""
from ai.llm.base import BaseLLM, LLMConfig, LLMMessage, LLMResponse
from ai.llm.factory import get_llm, create_llm, reset_llm

__all__ = [
    "BaseLLM",
    "LLMConfig",
    "LLMMessage",
    "LLMResponse",
    "get_llm",
    "create_llm",
    "reset_llm",
]
