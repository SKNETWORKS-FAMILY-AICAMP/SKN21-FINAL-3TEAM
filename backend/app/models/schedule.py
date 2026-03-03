"""
일정 모델 (팀원 D 담당)
"""
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional

from app.db.base import Base, TimestampMixin


class Schedule(Base, TimestampMixin):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    start_time: Mapped[datetime] = mapped_column()
    end_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    schedule_type: Mapped[str] = mapped_column(String(50))  # meeting/task/deadline
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    google_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    google_meet_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    action_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("action_items.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    team_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 유저 소속 팀
    is_team_visible: Mapped[bool] = mapped_column(Boolean, default=False)  # 팀원에게 공유 여부
