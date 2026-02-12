"""
Gmail API 엔드포인트 (팀원 D 담당)
- 기한 알림 메일 + 회의 초대 메일 발송
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.google_services import (
    SendReminderRequest,
    SendMeetingInviteRequest,
    SendBulkRemindersRequest,
    EmailSendResponse,
)
from app.services.gmail_service import GmailService

router = APIRouter()
gmail_service = GmailService()


@router.post("/send-reminder")
async def send_reminder(
    request: SendReminderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """기한 알림 메일 발송"""
    return await gmail_service.send_reminder(
        db, current_user.id, request.action_item_id, request.recipient_email
    )


@router.post("/send-meeting-invite", response_model=EmailSendResponse)
async def send_meeting_invite(
    request: SendMeetingInviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회의 초대 메일 (Meet 링크 포함)"""
    result = await gmail_service.send_meeting_invite(
        db,
        current_user.id,
        request.recipient_emails,
        request.meeting_title,
        request.meeting_time.isoformat(),
        request.meet_link,
    )
    return EmailSendResponse(**result)


@router.post("/send-bulk-reminders", response_model=EmailSendResponse)
async def send_bulk_reminders(
    request: SendBulkRemindersRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """마감 임박 전체 알림 발송"""
    result = await gmail_service.send_bulk_reminders(
        db, current_user.id, request.days_before, request.recipient_map or None
    )
    return EmailSendResponse(**result)
