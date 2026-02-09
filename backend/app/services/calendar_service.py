"""
Google Calendar 서비스 (팀원 D 담당)
- GoogleBaseService 상속
- Meet 링크 자동 생성 지원
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.google_base_service import GoogleBaseService


class GoogleCalendarService(GoogleBaseService):
    """Google Calendar 양방향 연동 + Meet 링크 생성"""

    required_scope = "calendar"

    async def push_event(self, db: AsyncSession, user_id: int, event_data: dict) -> dict:
        """앱 → Google Calendar 이벤트 생성"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def create_event_with_meet(
        self,
        db: AsyncSession,
        user_id: int,
        event_data: dict,
        attendee_emails: list[str] | None = None,
    ) -> dict:
        """이벤트 생성 + Google Meet 링크 자동 생성 (conferenceData)"""
        # TODO: 팀원 D 구현
        # - Calendar API로 이벤트 생성 (conferenceDataVersion=1)
        # - return {"event_id": ..., "html_link": ..., "meet_link": ...}
        raise NotImplementedError

    async def pull_events(self, db: AsyncSession, user_id: int, time_min: str = None, time_max: str = None) -> list:
        """Google Calendar → 앱 일정 조회"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def disconnect(self, db: AsyncSession, user_id: int):
        """연결 해제 (토큰은 google_connect에서 통합 관리)"""
        # TODO: 팀원 D 구현
        raise NotImplementedError
