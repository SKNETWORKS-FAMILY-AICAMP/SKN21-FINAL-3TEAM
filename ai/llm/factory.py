"""
LLM 팩토리 + 싱글턴

환경변수 LLM_PROVIDER로 Provider 선택:
  - "openai" (기본값) → OpenAIProvider
  - "anthropic" → AnthropicProvider
  - "vllm" → 4단계에서 구현
"""
import os
import logging
from typing import Optional

from ai.llm.base import BaseLLM, LLMConfig

logger = logging.getLogger(__name__)

_llm_instance: Optional[BaseLLM] = None


def create_llm(
    provider: Optional[str] = None,
    config: Optional[LLMConfig] = None,
) -> BaseLLM:
    """새 LLM 인스턴스 생성 (테스트/커스텀 용도)"""
    provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()

    if provider == "openai":
        from ai.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(config)
    elif provider == "anthropic":
        from ai.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider(config)
    elif provider == "vllm":
        raise NotImplementedError("vLLM Provider는 4단계에서 구현 예정")
    else:
        raise ValueError(f"지원하지 않는 LLM Provider: {provider}")


def get_llm() -> BaseLLM:
    """싱글턴 LLM 인스턴스 반환 (환경변수 기반)"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = create_llm()
        logger.info(f"LLM 싱글턴 생성: {_llm_instance.__class__.__name__}")
    return _llm_instance


def reset_llm() -> None:
    """싱글턴 초기화 (테스트/Provider 전환 시 사용)"""
    global _llm_instance
    _llm_instance = None
    logger.info("LLM 싱글턴 초기화됨")
