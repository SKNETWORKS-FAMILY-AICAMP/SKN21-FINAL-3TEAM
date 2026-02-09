"""
vLLM API 클라이언트 (팀원 B 담당)

vLLM은 OpenAI 호환 API를 제공합니다.
LoRA 어댑터를 요청에 따라 판단용/문서용으로 교체합니다.
"""
from typing import AsyncGenerator


class VLLMClient:
    """vLLM 서버 API 클라이언트"""

    def __init__(self, base_url: str = "http://localhost:8080/v1"):
        self.base_url = base_url

    async def generate(
        self,
        prompt: str,
        lora_adapter: str = None,  # "v1_judgment" or "v2_document"
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> str:
        """일반 생성 (비스트리밍)"""
        # TODO: 팀원 B 구현
        raise NotImplementedError

    async def stream_generate(
        self,
        prompt: str,
        lora_adapter: str = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str, None]:
        """스트리밍 생성 (토큰 단위)"""
        # TODO: 팀원 B 구현
        raise NotImplementedError
