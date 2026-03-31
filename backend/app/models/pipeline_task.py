"""
Pipeline Task 모델 (팀원 D 담당)
- 팀 프로젝트 칸반 보드용 (Google Tasks와 무관)
"""
from sqlalchemy import String, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional

from app.db.base import Base, TimestampMixin


class PipelineTask(Base, TimestampMixin):
    __tablename__ = "pipeline_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assignee: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    stage: Mapped[str] = mapped_column(String(30), default="todo")  # todo / in_progress / review / done
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # high / medium / low
    due_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    team: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 팀별 분리
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 쉼표 구분 태그
    project: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)  # 출처 회의/프로젝트명
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
