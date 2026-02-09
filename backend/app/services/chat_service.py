"""
챗봇 서비스 (팀원 A 담당)
- Intent 분류 → LangGraph 오케스트레이터 호출 → 응답 반환
"""
from typing import AsyncGenerator


class ChatService:
    """챗봇 비즈니스 로직"""

    async def process_message(self, message: str, user_id: int) -> dict:
        """메시지 처리 (비스트리밍)"""
        # TODO: 팀원 A - intent 분류 → agent 호출 → 응답 반환
        raise NotImplementedError

    async def stream_message(self, message: str, user_id: int) -> AsyncGenerator[str, None]:
        """메시지 처리 (SSE 스트리밍)"""
        # TODO: 팀원 A - intent 분류 → agent 호출 → 토큰 스트리밍
        raise NotImplementedError
