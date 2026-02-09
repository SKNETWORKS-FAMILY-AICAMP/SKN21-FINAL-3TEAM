"""
챗봇 스키마 (팀원 A 정의)
"""
from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    intent: str
    confidence: float
    response: str
    agent_type: Optional[str] = None
