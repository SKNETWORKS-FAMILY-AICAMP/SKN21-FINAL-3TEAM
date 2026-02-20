"""
회의 관리 API (팀원 C/D 공동 담당)
- CRUD (list / create / get): 팀원 D 구현
- AI 분석 (analyze / generate / download): 팀원 C 연동 예정
"""
from fastapi import APIRouter, Depends, Query, Body
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.meeting import MeetingCreate, MeetingResponse, MeetingDetailResponse, ActionItemResponse
from app.services import meeting_service

router = APIRouter()


@router.get("/", response_model=list[MeetingResponse])
async def list_meetings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회의 목록 조회 (본인만)"""
    meetings = await meeting_service.list_meetings(db, user_id=user.id)
    return [
        MeetingResponse(
            id=m.id,
            title=m.title,
            summary=m.summary,
            risk_level=m.risk_level,
            meeting_date=m.meeting_date,
            created_at=m.created_at,
        )
        for m in meetings
    ]


@router.post("/", response_model=MeetingResponse)
async def create_meeting(
    data: MeetingCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회의 생성 (raw_content 저장, AI 분석은 /{id}/analyze 호출)"""
    meeting = await meeting_service.create_meeting(db, user_id=user.id, data=data)
    return MeetingResponse(
        id=meeting.id,
        title=meeting.title,
        summary=meeting.summary,
        risk_level=meeting.risk_level,
        meeting_date=meeting.meeting_date,
        created_at=meeting.created_at,
    )


@router.get("/{meeting_id}", response_model=MeetingDetailResponse)
async def get_meeting(
    meeting_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회의 상세 조회 (Action Items 포함)"""
    meeting, action_items = await meeting_service.get_meeting(db, meeting_id, user_id=user.id)
    return MeetingDetailResponse(
        id=meeting.id,
        title=meeting.title,
        raw_content=meeting.raw_content,
        summary=meeting.summary,
        decisions=meeting_service.decisions_to_str(meeting.decisions),
        risk_level=meeting.risk_level,
        meeting_date=meeting.meeting_date,
        created_at=meeting.created_at,
        action_items=[
            ActionItemResponse(
                id=item.id,
                content=item.content,
                assignee=item.assignee,
                due_date=item.due_date,
                priority=item.priority,
                status=item.status,
                google_task_id=item.google_task_id,
                email_sent_at=item.email_sent_at,
            )
            for item in action_items
        ],
    )


@router.post("/{meeting_id}/analyze")
async def analyze_meeting(
    meeting_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회의록 AI 분석 (결정사항, Action Item 추출) — 팀원 C 연동 예정"""
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=501, content={"detail": "팀원 C(승언) 문서 Agent 연동 후 구현 예정"})


@router.post("/generate")
async def generate_meeting_minutes(
    title: Optional[str] = Body(None),
    meeting_date: Optional[str] = Body(None),
    attendees: Optional[str] = Body(None, description="참석자 (콤마 구분)"),
    raw_content: str = Body(..., description="회의 내용 텍스트"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회의록 생성 — 팀원 C(승언) 문서 Agent 연동 예정"""
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=501, content={"detail": "팀원 C(승언) 문서 Agent 연동 후 구현 예정"})


@router.get("/{meeting_id}/download")
async def download_meeting_document(
    meeting_id: int,
    format: str = Query("docx", regex="^(docx|pdf)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회의록 다운로드 — 팀원 C(승언) 문서 Agent 연동 예정"""
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=501, content={"detail": "팀원 C(승언) 문서 Agent 연동 후 구현 예정"})
