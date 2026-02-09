"""
Gmail API 엔드포인트 (팀원 D 담당)
- 기한 알림 메일 + 회의 초대 메일 발송
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.session import get_db

router = APIRouter()


@router.post("/send-reminder")
async def send_reminder(user=Depends(get_current_user), db=Depends(get_db)):
    """기한 알림 메일 발송"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.post("/send-meeting-invite")
async def send_meeting_invite(user=Depends(get_current_user), db=Depends(get_db)):
    """회의 초대 메일 (Meet 링크 포함)"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.post("/send-bulk-reminders")
async def send_bulk_reminders(user=Depends(get_current_user), db=Depends(get_db)):
    """마감 임박 전체 알림 발송"""
    # TODO: 팀원 D 구현
    raise NotImplementedError
