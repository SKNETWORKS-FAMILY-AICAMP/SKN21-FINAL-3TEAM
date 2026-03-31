"""
Slack 연동 API (팀원 D 담당)
- 알림 활성화/비활성화
- 상태 조회
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User

router = APIRouter()


@router.get("/status")
async def slack_status(user: User = Depends(get_current_user)):
    """Slack 연결 상태 조회"""
    return {"connected": user.slack_enabled}


@router.post("/connect")
async def slack_connect(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Slack 알림 활성화"""
    user.slack_enabled = True
    await db.flush()
    return {"connected": True}


@router.delete("/disconnect")
async def slack_disconnect(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Slack 알림 비활성화"""
    user.slack_enabled = False
    await db.flush()
    return {"connected": False}
