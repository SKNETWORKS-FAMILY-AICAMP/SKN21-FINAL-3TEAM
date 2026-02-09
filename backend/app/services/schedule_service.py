"""
일정 서비스 (팀원 D 담당)
- 일정 CRUD + 우선순위 자동 설정
- 4개 Google 서비스 오케스트레이션 통합
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.calendar_service import GoogleCalendarService
from app.services.tasks_service import GoogleTasksService
from app.services.gmail_service import GmailService
from app.services.sheets_service import GoogleSheetsService


class ScheduleService:
    """일정 CRUD + 우선순위 자동 설정 + Google 서비스 오케스트레이션"""

    def __init__(self):
        self.calendar_service = GoogleCalendarService()
        self.tasks_service = GoogleTasksService()
        self.gmail_service = GmailService()
        self.sheets_service = GoogleSheetsService()

    async def create_from_action_item(self, db: AsyncSession, action_item_id: int, user_id: int):
        """Action Item → 일정 자동 등록"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def calculate_priority(self, due_date: Optional[datetime]) -> str:
        """마감일 기반 우선순위 자동 설정 (D-day 계산)"""
        # TODO: 팀원 D 구현
        # - D-1 이하: high / D-3 이하: medium / 그 외: low
        raise NotImplementedError

    async def create_with_google_services(
        self,
        db: AsyncSession,
        user_id: int,
        schedule_data: dict,
        include_meet: bool = False,
        attendee_emails: list[str] | None = None,
        action_item_id: Optional[int] = None,
        meeting_id: Optional[int] = None,
    ) -> dict:
        """
        일정 생성 + 4개 Google 서비스 자동 연동

        Returns:
            {
                "schedule": Schedule,
                "google_services": {
                    "calendar_synced": bool,
                    "meet_link": str | None,
                    "task_created": bool,
                    "email_sent": bool,
                    "sheet_updated": bool,
                    "sheet_url": str | None,
                }
            }
        """
        # TODO: 팀원 D 구현
        # 1. Schedule 생성
        # 2. oauth_token 조회 → scope 확인
        # 3. calendar scope → push_event / create_event_with_meet
        # 4. tasks scope + action_item_id → sync_action_item
        # 5. gmail_send scope + attendee_emails → send_meeting_invite
        # 6. sheets scope + meeting_id → sync_action_items
        raise NotImplementedError
