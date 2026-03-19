"""
공개 규정 API
인증 없이 규정 목록 조회 가능 (프론트엔드 RegulationPanel 연동용)
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.regulation import Regulation

router = APIRouter()


@router.get("")
async def list_regulations_public(db: AsyncSession = Depends(get_db)):
    """규정 목록 조회 (공개)"""
    result = await db.execute(
        select(Regulation).order_by(Regulation.category, Regulation.article_number)
    )
    return [
        {
            "id": r.id,
            "title": r.title,
            "category": r.category,
            "article_number": r.article_number,
            "content": r.content,
            "version": r.version,
        }
        for r in result.scalars().all()
    ]


@router.get("/check")
async def check_regulation(q: str = Query(..., description="규정 검증할 질문")):
    """규정 검증 테스트 (공개 — 브라우저에서 바로 확인용)

    사용법: /api/v1/regulations/check?q=재택근무가 가능한가
    """
    from ai.agents.regulation_checker import regulation_check
    result = await regulation_check(q)
    return result
