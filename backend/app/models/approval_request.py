"""
Approval Request 모델 (팀원 D 담당)
- 결재/승인 요청 (연차, PR 리뷰, 품의서 등)
"""
from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.db.base import Base, TimestampMixin


class ApprovalRequest(Base, TimestampMixin):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(30))  # leave / review / budget / etc
    title: Mapped[str] = mapped_column(String(500))
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / approved / rejected
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    target_team: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
