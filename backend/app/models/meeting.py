"""
회의 모델 (팀원 D 담당)
"""
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional

from app.db.base import Base, TimestampMixin


class Meeting(Base, TimestampMixin):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    raw_content: Mapped[str] = mapped_column(Text)  # 원본 회의록
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AI 요약
    decisions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # 결정사항 JSON 배열
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 높음/중간/낮음
    meeting_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
