"""
일정 스키마 (팀원 A 정의, 팀원 D 확장)
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ScheduleCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    schedule_type: str = "task"
    priority: str = "medium"
    include_meet: bool = False
    attendee_emails: list[str] = []
    is_team_visible: bool = False
    project_name: Optional[str] = None  # 프로젝트 공유 일정


class ScheduleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    schedule_type: Optional[str] = None
    priority: Optional[str] = None
    is_team_visible: Optional[bool] = None
    project_name: Optional[str] = None


class ScheduleResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    schedule_type: str
    priority: str
    google_event_id: Optional[str] = None
    google_meet_link: Optional[str] = None
    is_team_visible: bool = False
    team_name: Optional[str] = None
    project_name: Optional[str] = None
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    attendees: list[dict] = []
    created_at: datetime
