"""
Project 모델 — Pipeline 프로젝트 그룹
"""
from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.db.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    team: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
