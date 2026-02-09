"""
채팅 로그 모델 (팀원 D 담당)
"""
from sqlalchemy import String, Text, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.db.base import Base, TimestampMixin


class ChatLog(Base, TimestampMixin):
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user_message: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(50))
    intent_confidence: Mapped[float] = mapped_column(Float)
    agent_type: Mapped[str] = mapped_column(String(50))  # judgment/document/schedule
    agent_response: Mapped[str] = mapped_column(Text)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
