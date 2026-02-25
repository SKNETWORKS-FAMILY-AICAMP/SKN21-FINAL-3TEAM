"""
Google Calendar 서비스 (팀원 D 담당)
- GoogleBaseService 상속
- Meet 링크 자동 생성 지원
"""
import uuid
import logging
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.google_base_service import GoogleBaseService

logger = logging.getLogger(__name__)


class GoogleCalendarService(GoogleBaseService):
    """Google Calendar 양방향 연동 + Meet 링크 생성"""

    required_scope = "calendar"

    def _build_service(self, creds):
        return build("calendar", "v3", credentials=creds)

    async def push_event(self, db: AsyncSession, user_id: int, event_data: dict) -> dict:
        """앱 → Google Calendar 이벤트 생성"""
        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)

        event = {
            "summary": event_data["title"],
            "description": event_data.get("description", ""),
            "start": {"dateTime": event_data["start_time"], "timeZone": "Asia/Seoul"},
            "end": {"dateTime": event_data.get("end_time", event_data["start_time"]), "timeZone": "Asia/Seoul"},
            "extendedProperties": {
                "private": {"workflow_type": event_data.get("event_type", "google")}
            },
        }

        calendar_id = event_data.get("calendar_id", "primary")
        result = service.events().insert(calendarId=calendar_id, body=event).execute()
        return {
            "event_id": result["id"],
            "html_link": result.get("htmlLink"),
        }

    async def create_event_with_meet(
        self,
        db: AsyncSession,
        user_id: int,
        event_data: dict,
        attendee_emails: list[str] | None = None,
    ) -> dict:
        """이벤트 생성 + Google Meet 링크 자동 생성"""
        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)

        event = {
            "summary": event_data["title"],
            "description": event_data.get("description", ""),
            "start": {"dateTime": event_data["start_time"], "timeZone": "Asia/Seoul"},
            "end": {"dateTime": event_data.get("end_time", event_data["start_time"]), "timeZone": "Asia/Seoul"},
            "extendedProperties": {
                "private": {"workflow_type": event_data.get("event_type", "google")}
            },
            "conferenceData": {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                },
            },
        }

        if attendee_emails:
            event["attendees"] = [{"email": e} for e in attendee_emails]

        calendar_id = event_data.get("calendar_id", "primary")
        result = (
            service.events()
            .insert(calendarId=calendar_id, body=event, conferenceDataVersion=1)
            .execute()
        )

        meet_link = None
        if result.get("conferenceData") and result["conferenceData"].get("entryPoints"):
            for ep in result["conferenceData"]["entryPoints"]:
                if ep["entryPointType"] == "video":
                    meet_link = ep["uri"]
                    break

        return {
            "event_id": result["id"],
            "html_link": result.get("htmlLink"),
            "meet_link": meet_link,
        }

    async def pull_events(
        self, db: AsyncSession, user_id: int, time_min: str = None, time_max: str = None
    ) -> list:
        """Google Calendar → 앱 일정 조회"""
        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)

        # 기본값: 3개월 전 ~ 3개월 후
        now = datetime.now(timezone.utc)
        if not time_min:
            time_min = (now - timedelta(days=90)).isoformat()
        if not time_max:
            time_max = (now + timedelta(days=90)).isoformat()

        # 모든 캘린더에서 이벤트 수집 (공휴일 캘린더 제외 — 프론트엔드에서 관리)
        events = []
        try:
            calendar_list = service.calendarList().list().execute()
            for cal in calendar_list.get("items", []):
                cal_id = cal["id"]
                # 공휴일 캘린더 제외 (Google 기본 holiday 캘린더)
                if "#holiday@group.v.calendar.google.com" in cal_id:
                    continue
                params = {
                    "calendarId": cal_id,
                    "singleEvents": True,
                    "orderBy": "startTime",
                    "maxResults": 250,
                    "timeMin": time_min,
                    "timeMax": time_max,
                }
                try:
                    result = service.events().list(**params).execute()
                    items = result.get("items", [])
                    for item in items:
                        event_type = (
                            item.get("extendedProperties", {})
                            .get("private", {})
                            .get("workflow_type", "google")
                        )
                        events.append({
                            "event_id": item["id"],
                            "calendar_id": cal_id,
                            "event_type": event_type,
                            "title": item.get("summary", ""),
                            "start": item["start"].get("dateTime", item["start"].get("date")),
                            "end": item["end"].get("dateTime", item["end"].get("date")),
                            "html_link": item.get("htmlLink"),
                            "meet_link": item.get("hangoutLink"),
                            "calendar": cal.get("summary", ""),
                        })
                except Exception:
                    pass
        except Exception:
            raise
        return events

    async def create_calendar(self, db: AsyncSession, user_id: int, name: str, color: str) -> dict:
        """새 Google Calendar 생성 + 색상 설정"""
        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)

        created = service.calendars().insert(body={"summary": name}).execute()
        calendar_id = created["id"]

        # 캘린더 목록에 색상 지정
        service.calendarList().patch(
            calendarId=calendar_id,
            body={"backgroundColor": color, "foregroundColor": "#ffffff"},
        ).execute()

        return {"calendar_id": calendar_id, "name": name}


    async def delete_event(self, db: AsyncSession, user_id: int, event_id: str, calendar_id: str = "primary") -> None:
        """Google Calendar 이벤트 삭제 (지정 캘린더 실패 시 전체 캘린더 탐색)"""
        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)

        # 1차 시도: 전달받은 calendar_id로 삭제
        try:
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            return
        except Exception:
            pass

        # 2차 시도: 전체 캘린더 순회
        try:
            calendar_list = service.calendarList().list().execute()
            for cal in calendar_list.get("items", []):
                cal_id = cal["id"]
                if cal_id == calendar_id:
                    continue  # 이미 시도한 캘린더 건너뜀
                try:
                    service.events().delete(calendarId=cal_id, eventId=event_id).execute()
                    return
                except Exception:
                    continue
        except Exception:
            pass

        raise ValueError(f"이벤트를 찾을 수 없습니다: {event_id}")
