"""
Slack 알림 서비스 (팀원 D 담당)
- 매일 오전 9시 마감 임박 Task 알림
- Webhook 기반 Slack 메시지 전송
"""
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.action_item import ActionItem

logger = logging.getLogger(__name__)


async def send_slack_webhook(webhook_url: str, text: str) -> bool:
    """Slack Incoming Webhook으로 메시지 전송"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json={"text": text})
            if resp.status_code == 200:
                logger.info("[Slack] 메시지 전송 성공")
                return True
            logger.warning(f"[Slack] 전송 실패: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"[Slack] 전송 오류: {e}")
        return False


async def check_and_notify_deadlines(db: AsyncSession):
    """
    마감 임박 Task 확인 → slack_enabled 사용자에게 Webhook 알림
    매일 오전 9시에 실행됨
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        logger.warning("[Slack] SLACK_WEBHOOK_URL 미설정, 알림 스킵")
        return

    # 내일 날짜 계산
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date()

    # slack_enabled인 사용자 조회
    result = await db.execute(
        select(User).where(User.slack_enabled == True, User.is_active == True)
    )
    slack_users = result.scalars().all()

    if not slack_users:
        logger.info("[Slack] slack_enabled 사용자 없음, 스킵")
        return

    # 마감일이 내일인 Action Item 조회
    result = await db.execute(
        select(ActionItem).where(
            ActionItem.due_date.isnot(None),
            ActionItem.status != "done",
        )
    )
    items = result.scalars().all()

    # 내일 마감인 항목 필터
    deadline_items = [
        item for item in items
        if item.due_date and item.due_date.date() == tomorrow
    ]

    if not deadline_items:
        logger.info("[Slack] 내일 마감 항목 없음")
        return

    # 알림 메시지 구성
    lines = [f":warning: *[마감 임박 알림]* 내일({tomorrow.strftime('%m/%d')}) 마감 항목:"]
    for item in deadline_items:
        assignee = item.assignee or "미지정"
        lines.append(f"  - *{item.content}* (담당: {assignee})")

    message = "\n".join(lines)
    sent = await send_slack_webhook(webhook_url, message)
    logger.info(f"[Slack] 마감 알림 전송: {len(deadline_items)}건, 성공={sent}")
