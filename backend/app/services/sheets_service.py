"""
Google Sheets 서비스 (팀원 D 담당)
- Action Item 추적 스프레드시트 생성
- 행 추가/동기화
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.google_base_service import GoogleBaseService

HEADER_ROW = ["ID", "내용", "담당자", "마감일", "우선순위", "상태", "Google Task ID"]


class GoogleSheetsService(GoogleBaseService):
    """Google Sheets CRUD + Action Item 추적"""

    required_scope = "sheets"

    async def create_tracking_sheet(
        self,
        db: AsyncSession,
        user_id: int,
        title: str = "Action Items 추적",
        meeting_id: Optional[int] = None,
    ) -> dict:
        """추적 스프레드시트 생성"""
        # TODO: 팀원 D 구현
        # - Sheets API로 스프레드시트 생성
        # - 헤더 행 추가 (HEADER_ROW)
        # - GoogleSheetTracker DB 레코드 저장
        # - return {"spreadsheet_id": ..., "spreadsheet_url": ..., "title": ...}
        raise NotImplementedError

    async def sync_action_items(
        self,
        db: AsyncSession,
        user_id: int,
        spreadsheet_id: str,
        meeting_id: Optional[int] = None,
    ) -> dict:
        """Action Item 데이터를 스프레드시트에 동기화"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def list_sheets(self, db: AsyncSession, user_id: int) -> list:
        """사용자의 추적 스프레드시트 목록"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def get_sheet_url_by_meeting(
        self, db: AsyncSession, user_id: int, meeting_id: int
    ) -> Optional[str]:
        """회의별 스프레드시트 URL 반환"""
        # TODO: 팀원 D 구현
        raise NotImplementedError
