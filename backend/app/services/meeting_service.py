"""
회의 서비스 (팀원 C/D 공동 담당)
- CRUD: list / create / get (D 담당)
- AI 분석: analyze (C 담당, 추후 연동)
"""
import json
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting import Meeting
from app.models.action_item import ActionItem
from app.schemas.meeting import MeetingCreate

logger = logging.getLogger(__name__)


async def list_meetings(db: AsyncSession, user_id: int) -> list[Meeting]:
    """본인이 생성한 회의 목록 조회"""
    result = await db.execute(
        select(Meeting)
        .where(Meeting.created_by == user_id)
        .order_by(Meeting.created_at.desc())
    )
    return list(result.scalars().all())


async def create_meeting(db: AsyncSession, user_id: int, data: MeetingCreate) -> Meeting:
    """회의 생성 (raw_content 저장, AI 분석은 별도 엔드포인트)"""
    meeting = Meeting(
        title=data.title,
        raw_content=data.raw_content,
        meeting_date=data.meeting_date,
        created_by=user_id,
    )
    db.add(meeting)
    await db.flush()
    return meeting


async def get_meeting(db: AsyncSession, meeting_id: int, user_id: int) -> tuple[Meeting, list[ActionItem]]:
    """회의 상세 + Action Items 조회"""
    result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="회의를 찾을 수 없습니다")
    if meeting.created_by != user_id:
        raise HTTPException(status_code=403, detail="본인의 회의만 조회할 수 있습니다")

    items_result = await db.execute(
        select(ActionItem)
        .where(ActionItem.meeting_id == meeting_id)
        .order_by(ActionItem.created_at.asc())
    )
    action_items = list(items_result.scalars().all())
    return meeting, action_items


def decisions_to_str(decisions) -> str | None:
    """JSONB dict/list → 문자열 변환 (스키마 호환)"""
    if decisions is None:
        return None
    if isinstance(decisions, str):
        return decisions
    return json.dumps(decisions, ensure_ascii=False)
