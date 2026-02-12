"""
Anthropic Claude Provider

AsyncAnthropic을 사용한 Claude 모델 연동.
Anthropic API 차이점 처리:
  - system은 top-level 파라미터
  - token 필드명 다름 (input_tokens / output_tokens)
"""
import os
import logging
from typing import AsyncGenerator, Optional

from anthropic import AsyncAnthropic

from ai.llm.base import BaseLLM, LLMConfig, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLM):
    """Anthropic Claude Provider"""

    def __init__(self, config: Optional[LLMConfig] = None):
        if config is None:
            config = LLMConfig(
                model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            )
        super().__init__(config)

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")

        self.client = AsyncAnthropic(api_key=api_key)

    def _build_params(
        self,
        messages: list[dict],
        system_prompt: Optional[str],
        max_tokens: Optional[int],
        temperature: Optional[float],
    ) -> dict:
        """Anthropic API 호출 파라미터 구성"""
        params = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": max_tokens or self.config.max_tokens,
        }

        # temperature 0이면 top_p 사용 불가 — Anthropic 제약
        temp = temperature if temperature is not None else self.config.temperature
        if temp > 0:
            params["temperature"] = temp
            params["top_p"] = self.config.top_p

        # Anthropic: system은 top-level 파라미터
        sys_prompt = system_prompt or self.config.system_prompt
        if sys_prompt:
            params["system"] = sys_prompt

        return params

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        messages = [{"role": "user", "content": prompt}]
        params = self._build_params(messages, system_prompt, max_tokens, temperature)

        response = await self.client.messages.create(**params)

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason or "",
        )

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        messages = [{"role": "user", "content": prompt}]
        params = self._build_params(messages, system_prompt, max_tokens, temperature)

        async with self.client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                yield text

    async def chat(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        # Anthropic: system 메시지는 별도 처리, 나머지만 messages로
        api_messages = []
        effective_system = system_prompt or self.config.system_prompt

        for msg in messages:
            if msg.role == "system":
                # system 메시지는 top-level param으로 병합
                if effective_system:
                    effective_system += "\n\n" + msg.content
                else:
                    effective_system = msg.content
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        params = self._build_params(api_messages, effective_system, max_tokens, temperature)

        response = await self.client.messages.create(**params)

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason or "",
        )

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        api_messages = []
        effective_system = system_prompt or self.config.system_prompt

        for msg in messages:
            if msg.role == "system":
                if effective_system:
                    effective_system += "\n\n" + msg.content
                else:
                    effective_system = msg.content
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        params = self._build_params(api_messages, effective_system, max_tokens, temperature)

        async with self.client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                yield text
