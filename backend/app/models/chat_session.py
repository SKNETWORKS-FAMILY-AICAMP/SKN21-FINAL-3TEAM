"""
채팅 세션 모델 (팀원 D 담당)
- 세션 메타데이터 (이름, 유저 ID) 관리
- chat_logs 테이블이 실제 메시지 저장
- summary: sLLM 기반 대화 요약 (오래된 메시지 압축)
"""
from typing import Optional

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # UUID
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100), default="새 대화")
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)  # sLLM 대화 요약
    summary_turn_count: Mapped[int] = mapped_column(default=0)  # 요약에 포함된 턴 수
