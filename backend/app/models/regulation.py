"""
규정 모델 (팀원 D 담당)
"""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Regulation(Base, TimestampMixin):
    __tablename__ = "regulations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(100))  # 정보보안, 인사, 개발 가이드라인 등
    article_number: Mapped[str] = mapped_column(String(50))  # 조항 번호
    content: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
