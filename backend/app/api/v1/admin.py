"""
관리자 API (팀원 D 담당)
"""
import asyncio

from fastapi import APIRouter, Depends, Body, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.models.regulation import Regulation
from app.services import statistics_service


# ── 요청 스키마 ──

class RegulationCreate(BaseModel):
    title: str
    category: str
    article_number: str
    content: str
    version: str = "1.0"


class RegulationUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    article_number: str | None = None
    content: str | None = None
    version: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    is_admin: bool = False

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


# ── 규정 CRUD ──


@router.post("/regulations")
async def create_regulation(
    data: RegulationCreate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """규정 추가 (관리자 전용)"""
    reg = Regulation(
        title=data.title,
        category=data.category,
        article_number=data.article_number,
        content=data.content,
        version=data.version,
    )
    db.add(reg)
    await db.flush()

    # flush 후 값 캡처
    reg_id, reg_title, reg_content, reg_article, reg_category = (
        reg.id, reg.title, reg.content, reg.article_number, reg.category
    )

    def _add():
        from ai.rag.qdrant_pipeline import get_qdrant_pipeline
        pipeline = get_qdrant_pipeline()
        pipeline.add_documents(
            documents=[reg_content],
            metadatas=[{
                "source": "regulations",
                "title": reg_title,
                "article_number": reg_article,
                "category": reg_category,
                "regulation_id": reg_id,
                "scope": "company",
            }],
        )

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _add)
    except Exception as e:
        print(f"[Qdrant] 규정 인덱싱 실패 (DB는 저장됨): {e}")

    return {
        "id": reg.id,
        "title": reg.title,
        "category": reg.category,
        "article_number": reg.article_number,
        "content": reg.content,
        "version": reg.version,
    }


@router.put("/regulations/{regulation_id}")
async def update_regulation(
    regulation_id: int,
    data: RegulationUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """규정 수정 (관리자 전용)"""
    result = await db.execute(select(Regulation).where(Regulation.id == regulation_id))
    reg = result.scalar_one_or_none()
    if reg is None:
        raise HTTPException(status_code=404, detail="규정을 찾을 수 없습니다")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(reg, field, value)

    reg_id, reg_title, reg_content, reg_article, reg_category = (
        reg.id, reg.title, reg.content, reg.article_number, reg.category
    )

    def _update():
        from ai.rag.qdrant_pipeline import get_qdrant_pipeline
        pipeline = get_qdrant_pipeline()
        pipeline.vector_store.delete_by_filter({"regulation_id": reg_id})
        pipeline.add_documents(
            documents=[reg_content],
            metadatas=[{
                "source": "regulations",
                "title": reg_title,
                "article_number": reg_article,
                "category": reg_category,
                "regulation_id": reg_id,
                "scope": "company",
            }],
        )

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _update)
    except Exception as e:
        print(f"[Qdrant] 규정 업데이트 실패 (DB는 수정됨): {e}")

    return {
        "id": reg.id,
        "title": reg.title,
        "category": reg.category,
        "article_number": reg.article_number,
        "content": reg.content,
        "version": reg.version,
    }


@router.delete("/regulations/{regulation_id}")
async def delete_regulation(
    regulation_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """규정 삭제 (관리자 전용)"""
    result = await db.execute(select(Regulation).where(Regulation.id == regulation_id))
    reg = result.scalar_one_or_none()
    if reg is None:
        raise HTTPException(status_code=404, detail="규정을 찾을 수 없습니다")

    reg_id = regulation_id

    def _delete():
        from ai.rag.qdrant_pipeline import get_qdrant_pipeline
        pipeline = get_qdrant_pipeline()
        pipeline.vector_store.delete_by_filter({"regulation_id": reg_id})
        pipeline.searcher.build_bm25_index()

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _delete)
    except Exception as e:
        print(f"[Qdrant] 규정 삭제 실패 (DB는 삭제 진행): {e}")

    await db.delete(reg)
    return {"detail": "규정이 삭제되었습니다"}


# ── 사용자 추가 / 삭제 ──


@router.post("/users")
async def create_user(
    data: UserCreate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자 추가 (관리자 전용)"""
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="이미 존재하는 이메일입니다")
    user = User(
        email=data.email,
        name=data.name,
        hashed_password=hash_password(data.password),
        is_admin=data.is_admin,
    )
    db.add(user)
    await db.flush()
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자 삭제 (관리자 전용)"""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="본인 계정은 삭제할 수 없습니다")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    await db.delete(user)
    return {"detail": "사용자가 삭제되었습니다"}
