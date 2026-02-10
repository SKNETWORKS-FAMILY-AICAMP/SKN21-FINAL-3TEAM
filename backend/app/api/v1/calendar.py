"""
Google Calendar 연동 API (팀원 D 담당)
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.session import get_db

router = APIRouter()


@router.post("/connect")
async def connect_google_calendar(user=Depends(get_current_user), db=Depends(get_db)):
    """Google Calendar 연결 (→ /api/v1/google/connect 사용 권장)"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.post("/disconnect")
async def disconnect_google_calendar(user=Depends(get_current_user), db=Depends(get_db)):
    """Google Calendar 연결 해제 (→ /api/v1/google/disconnect 사용 권장)"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.get("/events")
async def get_google_events(user=Depends(get_current_user), db=Depends(get_db)):
    """Google Calendar 이벤트 조회 (Pull)"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.post("/sync")
async def sync_to_google(user=Depends(get_current_user), db=Depends(get_db)):
    """앱 일정 → Google Calendar 동기화 (Push)"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.post("/event-with-meet")
async def create_event_with_meet(user=Depends(get_current_user), db=Depends(get_db)):
    """이벤트 + Google Meet 링크 자동 생성"""
    # TODO: 팀원 D 구현
    # - event_data + attendee_emails 파싱
    # - calendar_service.create_event_with_meet() 호출
    # - return {event_id, html_link, meet_link}
    raise NotImplementedError
