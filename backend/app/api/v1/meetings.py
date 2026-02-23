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
from app.schemas.meeting import (
    MeetingCreate, MeetingResponse, MeetingDetailResponse,
    ActionItemResponse, MeetingGenerateResponse, GeneratedActionItem, DetectedRisk,
)
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
    """
    기존 회의 AI 분석 — Document Agent를 호출하여 요약/결정사항/Action Items 추출
    """
    meeting, action_items, agent_response = await meeting_service.analyze_meeting(
        db, meeting_id=meeting_id, user_id=user.id
    )
    data = agent_response.get("data", {})
    risks = data.get("risks") or agent_response.get("risks", [])

    return {
        "meeting_id": meeting.id,
        "summary": meeting.summary,
        "decisions": meeting.decisions or [],
        "action_items": [
            GeneratedActionItem(
                content=item.content,
                assignee=item.assignee,
                due_date=item.due_date.strftime("%Y-%m-%d") if item.due_date else None,
            )
            for item in action_items
        ],
        "risk_level": meeting.risk_level,
        "risks": [
            DetectedRisk(
                description=r.get("description", ""),
                regulation=r.get("regulation"),
                level=r.get("level", "medium"),
            )
            for r in risks
        ],
    }


@router.post("/generate", response_model=MeetingGenerateResponse)
async def generate_meeting_minutes(
    title: Optional[str] = Body(None),
    meeting_date: Optional[str] = Body(None),
    attendees: Optional[str] = Body(None, description="참석자 (콤마 구분)"),
    raw_content: str = Body(..., description="회의 내용 텍스트"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    회의록 생성 — Document Agent를 호출하여 회의록 + Action Items 생성
    """
    from datetime import datetime as dt

    # meeting_date 문자열 → datetime 변환
    parsed_date = None
    if meeting_date:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):
            try:
                parsed_date = dt.strptime(meeting_date.strip(), fmt)
                break
            except ValueError:
                continue

    meeting, action_items, agent_response = await meeting_service.generate_meeting(
        db,
        user_id=user.id,
        title=title,
        meeting_date=parsed_date,
        attendees=attendees,
        raw_content=raw_content,
    )
    data = agent_response.get("data", {})
    risks = data.get("risks") or agent_response.get("risks", [])

    return MeetingGenerateResponse(
        meeting_id=meeting.id,
        document_id=agent_response.get("document_id", 0),
        summary=meeting.summary or "",
        decisions=meeting.decisions if isinstance(meeting.decisions, list) else [],
        action_items=[
            GeneratedActionItem(
                content=item.content,
                assignee=item.assignee,
                due_date=item.due_date.strftime("%Y-%m-%d") if item.due_date else None,
            )
            for item in action_items
        ],
        risk_level=meeting.risk_level,
        risks=[
            DetectedRisk(
                description=r.get("description", ""),
                regulation=r.get("regulation"),
                level=r.get("level", "medium"),
            )
            for r in risks
        ],
        preview=agent_response.get("preview", ""),
        download_url=agent_response.get("download_url", ""),
        created_at=meeting.created_at,
    )


@router.get("/{meeting_id}/download")
async def download_meeting_document(
    meeting_id: int,
    format: str = Query("docx", regex="^(docx|pdf)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회의록 다운로드 (DOCX/PDF) — to_docx 구현 대기 중"""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=501,
        content={
            "detail": "회의록 다운로드(DOCX/PDF 변환)는 to_docx 구현 대기 중입니다. 미리보기는 GET /meetings/{id} 에서 확인 가능합니다."
        },
    )
