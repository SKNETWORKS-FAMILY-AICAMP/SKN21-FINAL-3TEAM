"""
Action Item 모델 (팀원 D 담당)
"""
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional

from app.db.base import Base, TimestampMixin


class ActionItem(Base, TimestampMixin):
    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"))
    content: Mapped[str] = mapped_column(String(1000))
    assignee: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # high/medium/low
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/in_progress/done
