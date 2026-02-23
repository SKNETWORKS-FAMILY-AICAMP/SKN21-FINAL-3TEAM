"""
회의 서비스 (팀원 C/D 공동 담당)
- CRUD: list / create / get (D 담당)
- AI 분석: analyze / generate (C Agent 연동)
"""
import json
import logging
import os
import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting import Meeting
from app.models.action_item import ActionItem
from app.models.document import Document
from app.schemas.meeting import MeetingCreate
from app.config import get_settings

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


# ── 헬퍼 ──


def _derive_risk_level(risks: list[dict]) -> str | None:
    """risks 리스트에서 최고 레벨을 추출한다.

    Agent가 반환하는 level 값: "상"/"높"/"높음"/"high" → "높음"
    """
    if not risks:
        return None

    HIGH = {"상", "높", "높음", "high"}
    MID = {"중", "중간", "medium"}
    # "하"/"낮"/"낮음"/"low" → "낮음"

    has_high = False
    has_mid = False

    for r in risks:
        level = str(r.get("level", "")).strip().lower()
        if level in HIGH:
            has_high = True
        elif level in MID:
            has_mid = True

    if has_high:
        return "높음"
    if has_mid:
        return "중간"
    if risks:
        return "낮음"
    return None


def _parse_due_date(date_str: str | None) -> datetime | None:
    """날짜 문자열을 datetime으로 변환 (실패하면 None)"""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


async def _call_document_agent_for_meeting(raw_content: str, user_id: int) -> dict:
    """회의 내용으로 Document Agent를 호출하여 회의록을 생성한다."""
    state = {
        "user_input": raw_content,
        "user_id": user_id,
        "intent": "doc_generate",
        "template_type": "meeting_minutes",
        "stream_mode": False,
        "context": [],
        "agent_response": {},
        "confidence": 0.0,
    }

    from ai.agents.document_agent import document_agent
    state = await document_agent(state)

    agent_response = state.get("agent_response", {})
    if "error" in agent_response:
        raise HTTPException(status_code=500, detail=agent_response["error"])

    return agent_response


async def _save_action_items(
    db: AsyncSession,
    meeting_id: int,
    action_items_data: list[dict],
) -> list[ActionItem]:
    """Action Items를 DB에 저장한다."""
    items = []
    for ai_data in action_items_data:
        priority_raw = str(ai_data.get("priority", "medium")).strip().lower()
        if priority_raw in ("상", "높", "높음", "high"):
            priority = "high"
        elif priority_raw in ("하", "낮", "낮음", "low"):
            priority = "low"
        else:
            priority = "medium"

        item = ActionItem(
            meeting_id=meeting_id,
            content=ai_data.get("content", ""),
            assignee=ai_data.get("assignee"),
            due_date=_parse_due_date(ai_data.get("due_date")),
            priority=priority,
            status="pending",
        )
        db.add(item)
        items.append(item)

    if items:
        await db.flush()
        for item in items:
            await db.refresh(item)

    return items


# ── 메인 함수 ──


async def generate_meeting(
    db: AsyncSession,
    user_id: int,
    title: str | None,
    meeting_date: datetime | None,
    attendees: str | None,
    raw_content: str,
) -> tuple[Meeting, list[ActionItem], dict]:
    """
    회의록 생성: Agent 호출 → Meeting 생성 → ActionItems 생성 → Document 저장

    Returns:
        (Meeting, list[ActionItem], agent_response)
    """
    settings = get_settings()

    # 1. Agent 호출
    agent_response = await _call_document_agent_for_meeting(raw_content, user_id)
    data = agent_response.get("data", {})

    # 2. Meeting 생성
    resolved_title = title or data.get("title", "회의록")
    meeting = Meeting(
        title=resolved_title,
        raw_content=raw_content,
        summary=data.get("summary") or agent_response.get("summary"),
        decisions=data.get("decisions") or agent_response.get("decisions"),
        risk_level=_derive_risk_level(data.get("risks") or agent_response.get("risks", [])),
        meeting_date=meeting_date or _parse_due_date(data.get("date")),
        created_by=user_id,
    )
    db.add(meeting)
    await db.flush()
    await db.refresh(meeting)

    # 3. Action Items 저장
    action_items_data = data.get("action_items") or agent_response.get("action_items", [])
    action_items = await _save_action_items(db, meeting.id, action_items_data)

    # 4. 회의록 Document 저장 (미리보기용)
    generated_dir = os.path.join(settings.UPLOAD_DIR, "generated")
    os.makedirs(generated_dir, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}.json"
    file_path = os.path.join(generated_dir, file_name)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    doc = Document(
        title=resolved_title,
        file_path=file_path,
        file_type="json",
        content=agent_response.get("preview", ""),
        scope="personal",
        uploaded_by=user_id,
        status="completed",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # agent_response에 실제 ID 반영
    agent_response["meeting_id"] = meeting.id
    agent_response["document_id"] = doc.id
    agent_response["download_url"] = f"/api/v1/meetings/{meeting.id}/download"

    logger.info(f"회의록 생성 완료: meeting_id={meeting.id}, document_id={doc.id}")
    return meeting, action_items, agent_response


async def analyze_meeting(
    db: AsyncSession,
    meeting_id: int,
    user_id: int,
) -> tuple[Meeting, list[ActionItem], dict]:
    """
    기존 회의의 AI 분석: Meeting 조회 → Agent 호출 → Meeting 업데이트 → ActionItems 재생성

    Returns:
        (Meeting, list[ActionItem], agent_response)
    """
    # 1. 기존 Meeting 조회
    result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="회의를 찾을 수 없습니다")
    if meeting.created_by != user_id:
        raise HTTPException(status_code=403, detail="본인의 회의만 분석할 수 있습니다")

    # 2. Agent 호출
    agent_response = await _call_document_agent_for_meeting(meeting.raw_content, user_id)
    data = agent_response.get("data", {})

    # 3. Meeting 업데이트
    meeting.summary = data.get("summary") or agent_response.get("summary")
    meeting.decisions = data.get("decisions") or agent_response.get("decisions")
    meeting.risk_level = _derive_risk_level(data.get("risks") or agent_response.get("risks", []))

    # 4. 기존 ActionItems 삭제 → 새로 생성
    await db.execute(
        delete(ActionItem).where(ActionItem.meeting_id == meeting_id)
    )
    action_items_data = data.get("action_items") or agent_response.get("action_items", [])
    action_items = await _save_action_items(db, meeting_id, action_items_data)

    await db.refresh(meeting)

    agent_response["meeting_id"] = meeting.id
    logger.info(f"회의 분석 완료: meeting_id={meeting.id}, action_items={len(action_items)}")
    return meeting, action_items, agent_response
