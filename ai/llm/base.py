"""
LLM 추상 인터페이스 (공통 모듈)

모든 LLM Provider(OpenAI, Anthropic, vLLM)가 구현해야 하는
공통 인터페이스를 정의합니다.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional


@dataclass
class LLMConfig:
    """LLM 설정"""
    model: str = ""
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 1.0
    system_prompt: str = ""


@dataclass
class LLMMessage:
    """채팅 메시지"""
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    """LLM 응답"""
    content: str
    model: str = ""
    usage: dict = field(default_factory=dict)
    finish_reason: str = ""


class BaseLLM(ABC):
    """LLM Provider 추상 베이스 클래스"""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """단일 프롬프트로 응답 생성"""
        ...

    @abstractmethod
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """단일 프롬프트로 스트리밍 응답 생성"""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """멀티턴 채팅 응답 생성"""
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """멀티턴 채팅 스트리밍 응답 생성"""
        ...
