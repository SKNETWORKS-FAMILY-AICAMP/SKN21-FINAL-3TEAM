"""
SQLAlchemy Base (팀원 D 담당)
모든 모델이 상속하는 Base 클래스
"""
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import func
from datetime import datetime


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """생성일/수정일 자동 관리 믹스인"""
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
