"""
OAuth 토큰 모델 (팀원 D 담당)
- Google Calendar 등 외부 서비스 토큰 저장
"""
from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional

from app.db.base import Base, TimestampMixin


class OAuthToken(Base, TimestampMixin):
    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    provider: Mapped[str] = mapped_column(String(50))  # google
    access_token: Mapped[str] = mapped_column(Text)  # 암호화 저장
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
