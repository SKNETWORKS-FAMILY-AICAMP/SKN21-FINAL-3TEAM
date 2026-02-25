"""
Google Calendar 연동 API (팀원 D 담당)
"""
from fastapi import APIRouter, Depends, Query, HTTPException
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


@router.delete("/calendars", status_code=204)
async def delete_calendar(
    calendar_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Google Calendar 삭제"""
    await calendar_service.delete_calendar(db, current_user.id, calendar_id)


@router.post("/calendars", status_code=201)
async def create_calendar(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """새 Google Calendar 생성"""
    name = body.get("name", "새 유형")
    color = body.get("color", "#7C98AB")
    return await calendar_service.create_calendar(db, current_user.id, name, color)



@router.delete("/events/{event_id}", status_code=204)
async def delete_google_event(
    event_id: str,
    calendar_id: str = Query("primary"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Google Calendar 이벤트 삭제"""
    try:
        await calendar_service.delete_event(db, current_user.id, event_id, calendar_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
