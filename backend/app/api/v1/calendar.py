"""
Google Calendar 연동 API (팀원 D 담당)
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.google_services import EventWithMeetRequest, EventWithMeetResponse
from app.services.calendar_service import GoogleCalendarService

router = APIRouter()
calendar_service = GoogleCalendarService()


@router.get("/events")
async def get_google_events(
    time_min: str = Query(None),
    time_max: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Google Calendar 이벤트 조회 (Pull)"""
    events = await calendar_service.pull_events(db, current_user.id, time_min, time_max)
    return events


@router.post("/sync")
async def sync_to_google(
    event_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """앱 일정 → Google Calendar 동기화 (Push)"""
    result = await calendar_service.push_event(db, current_user.id, event_data)
    return result


@router.post("/event-with-meet", response_model=EventWithMeetResponse)
async def create_event_with_meet(
    request: EventWithMeetRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """이벤트 + Google Meet 링크 자동 생성"""
    event_data = {
        "title": request.title,
        "description": request.description or "",
        "start_time": request.start_time.isoformat(),
        "end_time": request.end_time.isoformat() if request.end_time else request.start_time.isoformat(),
    }
    result = await calendar_service.create_event_with_meet(
        db, current_user.id, event_data, request.attendee_emails or None
    )
    return EventWithMeetResponse(**result)
