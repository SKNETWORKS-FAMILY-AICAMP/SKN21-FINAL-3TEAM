"""
Google Sheets 추적 모델
- Pipeline 프로젝트 문서화 스프레드시트 정보 저장
"""
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.db.base import Base, TimestampMixin


class GoogleSheetTracker(Base, TimestampMixin):
    __tablename__ = "google_sheet_trackers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    spreadsheet_id: Mapped[str] = mapped_column(String(255))
    spreadsheet_url: Mapped[str] = mapped_column(String(500))
    sheet_name: Mapped[str] = mapped_column(String(255), default="프로젝트 문서")
    project_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    # 하위호환: 기존 meeting_id 컬럼 유지 (nullable)
    meeting_id: Mapped[Optional[int]] = mapped_column(ForeignKey("meetings.id"), nullable=True)
