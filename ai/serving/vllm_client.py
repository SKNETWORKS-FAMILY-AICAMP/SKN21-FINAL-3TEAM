"""
vLLM Provider — BaseLLM 호환 인터페이스

vLLM은 OpenAI 호환 API를 제공하므로, OpenAI SDK로 호출한다.
LoRA 어댑터를 모델 파라미터로 지정하여 판단용/문서용을 구분한다.

사용법:
  1. vLLM 서버 실행 (RunPod 또는 로컬):
     python -m vllm.entrypoints.openai.api_server \
       --model kaist-ai/Kanana-1.5-8B \
       --enable-lora --lora-modules v1_judgment=./lora_v1 v2_document=./lora_v2

  2. 환경변수 설정:
     LLM_PROVIDER=vllm
     VLLM_BASE_URL=http://localhost:8000/v1
     VLLM_MODEL=kaist-ai/Kanana-1.5-8B  (또는 LoRA 어댑터명)

  3. 기존 코드 변경 없이 get_llm()으로 사용:
     from ai.llm import get_llm
     llm = get_llm()  # → VLLMProvider 인스턴스
     response = await llm.generate(prompt="...", system_prompt="...")
"""
import logging
import os
from typing import AsyncGenerator, Optional

from ai.llm.base import BaseLLM, LLMConfig, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class VLLMProvider(BaseLLM):
    """vLLM OpenAI 호환 API Provider

    vLLM 서버가 OpenAI 호환 /v1/chat/completions 엔드포인트를 제공하므로
    openai SDK를 그대로 사용한다. LoRA 어댑터는 model 파라미터로 지정.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        config = config or LLMConfig()

        # vLLM 전용 환경변수 (RunPod Serverless 또는 로컬 vLLM 서버)
        self.base_url = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        self.model = config.model or os.getenv("VLLM_MODEL", "kakaocorp/kanana-1.5-8b-instruct-2505")
        self.api_key = os.getenv("VLLM_API_KEY", "EMPTY")

        if not config.model:
            config.model = self.model

        super().__init__(config)
        self._client = None

        logger.info(f"VLLMProvider 초기화: base_url={self.base_url}, model={self.model}")

    def _get_client(self):
        """AsyncOpenAI 클라이언트 (지연 초기화)"""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """단일 프롬프트로 응답 생성"""
        client = self._get_client()

        messages = []
        sys_content = system_prompt or self.config.system_prompt
        if json_mode and sys_content:
            sys_content += "\n\n반드시 유효한 JSON만 출력하세요. 설명이나 마크다운 없이 JSON 객체만 반환합니다."
        if sys_content:
            messages.append({"role": "system", "content": sys_content})
        messages.append({"role": "user", "content": prompt})

        extra_kwargs = {}
        if json_mode:
            extra_kwargs["extra_body"] = {"guided_json": True}

        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature if temperature is not None else self.config.temperature,
            top_p=self.config.top_p,
            **extra_kwargs,
        )

        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason or "",
        )

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """단일 프롬프트로 스트리밍 응답 생성"""
        client = self._get_client()

        messages = []
        if system_prompt or self.config.system_prompt:
            messages.append({"role": "system", "content": system_prompt or self.config.system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature if temperature is not None else self.config.temperature,
            top_p=self.config.top_p,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """멀티턴 채팅 응답 생성"""
        client = self._get_client()

        api_messages = []
        if system_prompt or self.config.system_prompt:
            api_messages.append({"role": "system", "content": system_prompt or self.config.system_prompt})
        api_messages.extend({"role": m.role, "content": m.content} for m in messages)

        response = await client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature if temperature is not None else self.config.temperature,
            top_p=self.config.top_p,
        )

        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason or "",
        )

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """멀티턴 채팅 스트리밍 응답 생성"""
        client = self._get_client()

        api_messages = []
        if system_prompt or self.config.system_prompt:
            api_messages.append({"role": "system", "content": system_prompt or self.config.system_prompt})
        api_messages.extend({"role": m.role, "content": m.content} for m in messages)

        stream = await client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature if temperature is not None else self.config.temperature,
            top_p=self.config.top_p,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def with_lora(self, adapter_name: str) -> "VLLMProvider":
        """LoRA 어댑터를 지정한 새 인스턴스 반환

        vLLM에서 LoRA는 model 파라미터로 어댑터명을 지정하여 사용한다.

        사용법:
            llm = get_llm()
            judgment_llm = llm.with_lora("v1_judgment")
            document_llm = llm.with_lora("v2_document")
        """
        new_config = LLMConfig(
            model=adapter_name,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            system_prompt=self.config.system_prompt,
        )
        new_provider = VLLMProvider(new_config)
        new_provider.base_url = self.base_url
        new_provider.api_key = self.api_key
        new_provider.model = adapter_name
        return new_provider
