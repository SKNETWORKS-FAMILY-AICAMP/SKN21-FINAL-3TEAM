"""
Google Sheets 서비스 (팀원 D 담당)
- Action Item 추적 스프레드시트 생성
- 행 추가/동기화
"""
from typing import Optional

from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_item import ActionItem
from app.models.google_sheet_tracker import GoogleSheetTracker
from app.services.google_base_service import GoogleBaseService

HEADER_ROW = ["ID", "내용", "담당자", "마감일", "우선순위", "상태", "Google Task ID"]


class GoogleSheetsService(GoogleBaseService):
    """Google Sheets CRUD + Action Item 추적"""

    required_scope = "sheets"

    def _build_service(self, creds):
        return build("sheets", "v4", credentials=creds)

    async def create_tracking_sheet(
        self,
        db: AsyncSession,
        user_id: int,
        title: str = "Action Items 추적",
        meeting_id: Optional[int] = None,
    ) -> dict:
        """추적 스프레드시트 생성"""
        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)

        spreadsheet = service.spreadsheets().create(
            body={"properties": {"title": title}}
        ).execute()

        spreadsheet_id = spreadsheet["spreadsheetId"]
        spreadsheet_url = spreadsheet["spreadsheetUrl"]

        # 헤더 행 추가
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="A1",
            valueInputOption="RAW",
            body={"values": [HEADER_ROW]},
        ).execute()

        # DB 트래커 저장
        tracker = GoogleSheetTracker(
            user_id=user_id,
            spreadsheet_id=spreadsheet_id,
            spreadsheet_url=spreadsheet_url,
            sheet_name=title,
            meeting_id=meeting_id,
        )
        db.add(tracker)
        await db.flush()

        return {
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_url": spreadsheet_url,
            "title": title,
        }

    async def sync_action_items(
        self,
        db: AsyncSession,
        user_id: int,
        spreadsheet_id: str,
        meeting_id: Optional[int] = None,
    ) -> dict:
        """Action Item 데이터를 스프레드시트에 동기화"""
        query = select(ActionItem)
        if meeting_id:
            query = query.where(ActionItem.meeting_id == meeting_id)
        result = await db.execute(query)
        items = result.scalars().all()

        rows = []
        for item in items:
            rows.append([
                str(item.id),
                item.content,
                item.assignee or "",
                item.due_date.strftime("%Y-%m-%d") if item.due_date else "",
                item.priority,
                item.status,
                item.google_task_id or "",
            ])

        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)

        # 기존 데이터 클리어 (헤더 제외) 후 다시 쓰기
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range="A2:G",
        ).execute()

        if rows:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="A2",
                valueInputOption="RAW",
                body={"values": rows},
            ).execute()

        return {"synced_count": len(rows), "spreadsheet_id": spreadsheet_id}

    async def list_sheets(self, db: AsyncSession, user_id: int) -> list:
        """사용자의 추적 스프레드시트 목록"""
        result = await db.execute(
            select(GoogleSheetTracker).where(GoogleSheetTracker.user_id == user_id)
        )
        trackers = result.scalars().all()
        return [
            {
                "id": t.id,
                "spreadsheet_id": t.spreadsheet_id,
                "spreadsheet_url": t.spreadsheet_url,
                "sheet_name": t.sheet_name,
                "meeting_id": t.meeting_id,
                "created_at": t.created_at,
            }
            for t in trackers
        ]

    async def get_sheet_url_by_meeting(
        self, db: AsyncSession, user_id: int, meeting_id: int
    ) -> Optional[str]:
        """회의별 스프레드시트 URL 반환"""
        result = await db.execute(
            select(GoogleSheetTracker).where(
                GoogleSheetTracker.user_id == user_id,
                GoogleSheetTracker.meeting_id == meeting_id,
            )
        )
        tracker = result.scalar_one_or_none()
        return tracker.spreadsheet_url if tracker else None
