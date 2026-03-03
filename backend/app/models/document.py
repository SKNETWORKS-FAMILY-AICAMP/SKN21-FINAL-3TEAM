"""
문서 모델 (팀원 D 담당)
- scope: 'company' (회사 공용) / 'team' (팀 공유) / 'personal' (개인)
"""
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str] = mapped_column(String(1000))
    file_type: Mapped[str] = mapped_column(String(20))  # pdf, docx, txt
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str] = mapped_column(String(20), default="company")  # company / team / personal
    team_name: Mapped[str | None] = mapped_column(String(50), nullable=True)  # scope='team' 시 소속 팀
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="processing")  # processing / ready / error
