"""
Approval Request API (팀원 D 담당)
- 결재/승인 요청 CRUD
- 같은 팀 소속끼리 공유
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.approval_request import ApprovalRequest

router = APIRouter()


# ── Schemas ──

class ApprovalCreate(BaseModel):
    type: str  # leave / review / budget / etc
    title: str
    detail: Optional[str] = None


# ── Endpoints ──

@router.get("/")
async def list_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 팀의 pending 요청 목록"""
    query = (
        select(ApprovalRequest)
        .where(ApprovalRequest.status == "pending")
        .order_by(ApprovalRequest.created_at.desc())
    )
    if current_user.team:
        query = query.where(ApprovalRequest.target_team == current_user.team)
    else:
        query = query.where(ApprovalRequest.requester_id == current_user.id)

    result = await db.execute(query)
    items = result.scalars().all()

    # requester 이름/아바타 조회를 위해 user id 수집
    user_ids = list({i.requester_id for i in items})
    users_map = {}
    if user_ids:
        users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in users_result.scalars().all():
            users_map[u.id] = u

    return [
        {
            "id": i.id,
            "type": i.type,
            "title": i.title,
            "detail": i.detail,
            "status": i.status,
            "requester_id": i.requester_id,
            "requester_name": users_map.get(i.requester_id, None) and users_map[i.requester_id].name,
            "requester_avatar": users_map.get(i.requester_id, None) and users_map[i.requester_id].avatar,
            "target_team": i.target_team,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in items
    ]


@router.post("/", status_code=201)
async def create_approval(
    req: ApprovalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """새 결재/승인 요청 생성"""
    approval = ApprovalRequest(
        type=req.type,
        title=req.title,
        detail=req.detail,
        status="pending",
        requester_id=current_user.id,
        target_team=current_user.team,
    )
    db.add(approval)
    await db.flush()
    return {
        "id": approval.id,
        "type": approval.type,
        "title": approval.title,
        "status": approval.status,
    }


@router.put("/{approval_id}/approve")
async def approve_request(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """요청 승인"""
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="이미 처리된 요청입니다")

    approval.status = "approved"
    await db.flush()
    return {"id": approval.id, "status": "approved"}


@router.put("/{approval_id}/reject")
async def reject_request(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """요청 거절"""
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="이미 처리된 요청입니다")

    approval.status = "rejected"
    await db.flush()
    return {"id": approval.id, "status": "rejected"}


@router.post("/seed", status_code=201)
async def seed_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """초기 샘플 데이터 시드 (현재 유저 팀 기준, 기존 pending 없을 때만)"""
    # 현재 유저가 볼 수 있는 pending 확인
    query = select(ApprovalRequest).where(ApprovalRequest.status == "pending")
    if current_user.team:
        query = query.where(ApprovalRequest.target_team == current_user.team)
    else:
        query = query.where(ApprovalRequest.requester_id == current_user.id)
    existing = await db.execute(query.limit(1))
    if existing.scalar_one_or_none():
        return {"seeded": 0, "message": "이미 pending 데이터가 있습니다"}

    samples = [
        {"type": "leave", "title": "연차 신청서", "detail": "3일 (Feb 12 - Feb 14)"},
        {"type": "review", "title": "PR 리뷰 요청", "detail": "feat/auth-module #42"},
        {"type": "budget", "title": "품의서 결재", "detail": "디자인 에셋 구매 (₩150,000)"},
    ]
    for s in samples:
        db.add(ApprovalRequest(
            type=s["type"],
            title=s["title"],
            detail=s["detail"],
            status="pending",
            requester_id=current_user.id,
            target_team=current_user.team,
        ))
    await db.flush()
    return {"seeded": len(samples)}
