"""
판단 이력 모델 (팀원 D 담당)
- 과거 판단 기록 저장 (판단 Agent 이력 참조용)
"""
from sqlalchemy import String, Float, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.db.base import Base, TimestampMixin


class Judgment(Base, TimestampMixin):
    __tablename__ = "judgments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(30))  # yes/no/conditional/no_regulation
    confidence: Mapped[float] = mapped_column(Float)
    reasoning: Mapped[str] = mapped_column(Text)  # 근거
    conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 조건부일 때 조건
    alternatives: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 대안
    regulations_cited: Mapped[str] = mapped_column(Text)  # 참조 규정 JSON
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
