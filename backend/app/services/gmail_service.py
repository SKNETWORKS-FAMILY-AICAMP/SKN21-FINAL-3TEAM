"""
Gmail 서비스 (팀원 D 담당)
- 담당자 기한 알림 메일 발송
- 회의 초대 메일 (Meet 링크 포함) 발송
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.google_base_service import GoogleBaseService


class GmailService(GoogleBaseService):
    """Gmail 발송 서비스"""

    required_scope = "gmail_send"

    async def send_reminder(
        self, db: AsyncSession, user_id: int, action_item_id: int, recipient_email: str
    ) -> dict:
        """기한 알림 메일 발송"""
        # TODO: 팀원 D 구현
        # - action_item 조회
        # - HTML 메일 빌드 (내용, 담당자, 마감일, 우선순위)
        # - Gmail API로 발송
        # - action_item.email_sent_at 업데이트
        raise NotImplementedError

    async def send_meeting_invite(
        self,
        db: AsyncSession,
        user_id: int,
        recipient_emails: list[str],
        meeting_title: str,
        meeting_time: str,
        meet_link: Optional[str] = None,
    ) -> dict:
        """회의 초대 메일 발송 (Meet 링크 포함)"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def send_bulk_reminders(
        self,
        db: AsyncSession,
        user_id: int,
        days_before: int = 3,
        recipient_map: Optional[dict[str, str]] = None,
    ) -> dict:
        """마감 임박 Action Item 일괄 알림 발송"""
        # TODO: 팀원 D 구현
        raise NotImplementedError
