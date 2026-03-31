"""
공개 규정 API
인증 없이 규정 목록 조회 가능 (프론트엔드 RegulationPanel 연동용)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
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


@router.get("/by-article")
async def get_regulation_by_article(
    article: str = Query(..., description="조항 번호 (예: 제9조, 윤리강령 제1조)"),
    title: str = Query(None, description="규정 제목 힌트 (예: 윤리강령 제1조 (목적))"),
    db: AsyncSession = Depends(get_db),
):
    """조항 번호로 규정 전문 조회 — 규정명 포함 시 정확 매칭"""
    reg = None

    # 1) title 힌트가 있으면 title로 먼저 검색
    if title:
        result = await db.execute(
            select(Regulation).where(Regulation.title.contains(title))
        )
        reg = result.scalars().first()

    # 2) 정확 매칭 (기존 "제9조" 또는 "윤리강령 제1조")
    if not reg:
        result = await db.execute(
            select(Regulation).where(Regulation.article_number == article)
        )
        reg = result.scalar_one_or_none()

    # 3) 부분 매칭 — article이 "제1조"일 때 "윤리강령 제1조" 등을 찾음
    if not reg:
        result = await db.execute(
            select(Regulation).where(Regulation.article_number.contains(article))
        )
        reg = result.scalars().first()

    if not reg:
        raise HTTPException(status_code=404, detail="해당 조항을 찾을 수 없습니다")
    return {
        "id": reg.id,
        "title": reg.title,
        "category": reg.category,
        "article_number": reg.article_number,
        "content": reg.content,
        "version": reg.version,
    }


@router.get("/check")
async def check_regulation(q: str = Query(..., description="규정 검증할 질문")):
    """규정 검증 테스트 (공개 — 브라우저에서 바로 확인용)

    사용법: /api/v1/regulations/check?q=재택근무가 가능한가
    """
    from ai.agents.regulation_checker import regulation_check
    result = await regulation_check(q)
    return result
