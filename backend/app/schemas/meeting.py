"""
회의 스키마 (팀원 A 정의, 팀원 C/D 확장)
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class MeetingCreate(BaseModel):
    title: str
    raw_content: str
    meeting_date: Optional[datetime] = None


class ActionItemResponse(BaseModel):
    id: int
    content: str
    assignee: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: str
    status: str


class MeetingResponse(BaseModel):
    id: int
    title: str
    summary: Optional[str] = None
    risk_level: Optional[str] = None
    meeting_date: Optional[datetime] = None
    created_at: datetime


class MeetingDetailResponse(MeetingResponse):
    raw_content: str
    decisions: Optional[str] = None
    action_items: List[ActionItemResponse] = []
