"""
통계 서비스 (팀원 D 담당)

UI_UX.pdf: "Top 질의 응답 (월/주/일)", "시스템 현황 (통계, AI 정확도 리포트)"
요구사항: NF-ST-002
"""
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_log import ChatLog
from app.models.meeting import Meeting
from app.models.action_item import ActionItem
from app.models.user import User


def _period_start(period: str) -> datetime:
    """period 문자열 → 시작 datetime"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if period == "weekly":
        return now - timedelta(days=7)
    if period == "monthly":
        return now - timedelta(days=30)
    return now - timedelta(days=1)  # daily (default)


async def get_top_queries(
    db: AsyncSession,
    period: str = "daily",
    limit: int = 10,
    team: str | None = None,
) -> list[dict]:
    """
    인기 질의 Top N 조회 (chat_logs 기간별 집계)

    Returns:
        [{"question": "...", "count": 15, "intent": "judgment", "last_asked": "..."}]
    """
    since = _period_start(period)
    stmt = (
        select(
            ChatLog.user_message,
            ChatLog.intent,
            func.count(ChatLog.id).label("count"),
            func.max(ChatLog.created_at).label("last_asked"),
        )
        .where(ChatLog.created_at >= since)
    )
    if team:
        stmt = stmt.join(User, ChatLog.user_id == User.id).where(User.team == team)
    stmt = (
        stmt.group_by(ChatLog.user_message, ChatLog.intent)
        .order_by(func.count(ChatLog.id).desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "question": row.user_message,
            "intent": row.intent,
            "count": row.count,
            "last_asked": (row.last_asked.isoformat() + "Z") if row.last_asked else None,
        }
        for row in result.all()
    ]


async def get_dashboard_stats(db: AsyncSession, user_id: int | None = None, team: str | None = None) -> dict:
    """
    대시보드 통계 카드 데이터

    Returns:
        {"today_queries": 24, "processed_meetings": 5,
         "completed_action_items": 12, "risk_alerts": 3}
    """
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )

    q_queries = select(func.count(ChatLog.id)).where(ChatLog.created_at >= today_start)
    if user_id:
        q_queries = q_queries.where(ChatLog.user_id == user_id)
    if team:
        q_queries = q_queries.join(User, ChatLog.user_id == User.id).where(User.team == team)
    today_queries = (await db.execute(q_queries)).scalar() or 0

    q_meetings = select(func.count(Meeting.id))
    if user_id:
        q_meetings = q_meetings.where(Meeting.created_by == user_id)
    if team:
        q_meetings = q_meetings.join(User, Meeting.created_by == User.id).where(User.team == team)
    processed_meetings = (await db.execute(q_meetings)).scalar() or 0

    completed_action_items = (
        await db.execute(
            select(func.count(ActionItem.id)).where(ActionItem.status == "done")
        )
    ).scalar() or 0

    risk_alerts = (
        await db.execute(
            select(func.count(Meeting.id)).where(Meeting.risk_level == "높음")
        )
    ).scalar() or 0

    return {
        "today_queries": today_queries,
        "processed_meetings": processed_meetings,
        "completed_action_items": completed_action_items,
        "risk_alerts": risk_alerts,
    }


async def get_query_logs(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """
    질의 로그 조회 — 페이지네이션 (관리자 전용)

    Returns:
        {"items": [...], "total": 150, "page": 1, "per_page": 20}
    """
    offset = (page - 1) * per_page
    total = (await db.execute(select(func.count(ChatLog.id)))).scalar() or 0
    result = await db.execute(
        select(ChatLog).order_by(ChatLog.created_at.desc()).offset(offset).limit(per_page)
    )
    logs = result.scalars().all()
    return {
        "items": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "session_id": log.session_id,
                "question": log.user_message,
                "intent": log.intent,
                "intent_confidence": log.intent_confidence,
                "agent": log.agent_type,
                "response_time_ms": log.response_time_ms,
                "timestamp": (log.created_at.isoformat() + "Z") if log.created_at else None,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
