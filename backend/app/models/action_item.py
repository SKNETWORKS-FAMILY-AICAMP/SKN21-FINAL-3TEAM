"""
Action Item 모델 (팀원 D 담당)
- Google Tasks, Sheets, Gmail 연동 필드 포함
"""
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional

from app.db.base import Base, TimestampMixin


class ActionItem(Base, TimestampMixin):
    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[Optional[int]] = mapped_column(ForeignKey("meetings.id"), nullable=True)
    content: Mapped[str] = mapped_column(String(1000))
    assignee: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 표시용 이름 (외부인 포함)
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)  # 내부 사용자 FK
    due_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # high/medium/low
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/in_progress/done

    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)  # 생성자

    # Google Services 연동
    google_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sheet_row_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
