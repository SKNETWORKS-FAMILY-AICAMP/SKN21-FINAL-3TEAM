"""
회의 스키마 (팀원 A 정의, 팀원 C/D 확장)
"""
from pydantic import BaseModel
from typing import Optional
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
    google_task_id: Optional[str] = None
    email_sent_at: Optional[datetime] = None


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
    action_items: list[ActionItemResponse] = []


# ── 회의록 생성 시 사용되는 하위 모델 ──


class GeneratedActionItem(BaseModel):
    """sLLM이 생성한 Action Item"""
    content: str
    assignee: Optional[str] = None
    due_date: Optional[str] = None


class DetectedRisk(BaseModel):
    """sLLM이 감지한 리스크 항목"""
    description: str
    regulation: Optional[str] = None
    level: str = "medium"                   # low | medium | high


# ── 회의록 생성 (meeting_generate) ──


class MeetingGenerateRequest(BaseModel):
    """회의록 생성 요청 — 회의 내용 텍스트 입력"""
    title: Optional[str] = None
    meeting_date: Optional[datetime] = None # ISO 8601 형식
    attendees: Optional[str] = None         # 참석자 (콤마 구분)
    raw_content: str                        # 회의 내용 텍스트


class MeetingGenerateResponse(BaseModel):
    """회의록 생성 응답 — 요약 + 결정사항 + Action Items + 미리보기 + 다운로드"""
    meeting_id: int
    document_id: int
    summary: str
    decisions: list[str] = []
    action_items: list[GeneratedActionItem] = []
    risk_level: Optional[str] = None
    risks: list[DetectedRisk] = []
    preview: str                            # 마크다운 미리보기
    download_url: str                       # 다운로드 URL
    created_at: datetime
