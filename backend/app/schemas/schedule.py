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


class ScheduleResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    schedule_type: str
    priority: str
    google_event_id: Optional[str] = None
    created_at: datetime
