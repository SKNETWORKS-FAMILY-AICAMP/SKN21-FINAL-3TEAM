"""
관리자 API (팀원 D 담당)
"""
from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user
from app.db.session import get_db
from app.models.user import User
from app.models.regulation import Regulation
from app.services import statistics_service

router = APIRouter()


@router.get("/users")
async def list_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자 목록 조회 (관리자 전용)"""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "is_admin": u.is_admin,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.get("/stats")
async def system_stats(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """시스템 전체 통계 (관리자 전용)"""
    return await statistics_service.get_dashboard_stats(db, user_id=None)


@router.get("/logs")
async def query_logs(
    page: int = 1,
    per_page: int = 20,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """질의 로그 조회"""
    return await statistics_service.get_query_logs(db, page=page, per_page=per_page)


@router.get("/regulations")
async def list_regulations(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """규정 목록 조회 (관리자 전용)"""
    result = await db.execute(
        select(Regulation).order_by(Regulation.category, Regulation.article_number)
    )
    regs = result.scalars().all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "category": r.category,
            "article_number": r.article_number,
            "version": r.version,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in regs
    ]


# ── UI_UX.pdf 추가 엔드포인트 ──


@router.get("/query-logs")
async def get_query_logs(
    page: int = 1,
    per_page: int = 20,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    질의 로그 조회 (NF-ST-002)
    사용자 / 질문 내용 / 호출된 Agent / 응답 시간 포함
    """
    return await statistics_service.get_query_logs(db, page=page, per_page=per_page)


@router.get("/top-queries")
async def get_top_queries(
    period: str = "daily",
    limit: int = 10,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Top 질의 응답 통계 (월/주/일)
    period: daily | weekly | monthly
    """
    return await statistics_service.get_top_queries(db, period=period, limit=limit)


@router.put("/users/{user_id}/permissions")
async def update_user_permissions(
    user_id: int,
    is_admin: bool = Body(..., embed=True),
    is_active: bool = Body(..., embed=True),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자 권한 변경 (관리자/활성화 여부)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    user.is_admin = is_admin
    user.is_active = is_active
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
    }
