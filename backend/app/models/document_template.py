"""
문서 템플릿 모델 (팀원 D 담당)
- 사용자가 업로드한 커스텀 템플릿 및 기본 제공 시스템 템플릿 저장
- category: meeting_minutes | report | jd | proposal | custom
- scope: company (회사 공용) | personal (개인)
"""
from sqlalchemy import String, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.db.base import Base, TimestampMixin


class DocumentTemplate(Base, TimestampMixin):
    __tablename__ = "document_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # docx, pdf
    parsed_structure: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AI가 추출한 양식 구조 (JSON)
    category: Mapped[str] = mapped_column(String(50), default="custom")  # meeting_minutes | report | jd | proposal | custom
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)  # True = 기본 제공 4종
    scope: Mapped[str] = mapped_column(String(10), default="company")  # company | personal
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ready")  # processing | ready | error
