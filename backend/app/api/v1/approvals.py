"""
Approval Request API (팀원 D 담당)
- 결재/승인 요청 CRUD
- 같은 팀 소속끼리 공유
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.approval_request import ApprovalRequest

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "approvals"
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _serialize_approval(i, users_map=None):
    """공통 직렬화 헬퍼"""
    user = (users_map or {}).get(i.requester_id)
    return {
        "id": i.id,
        "type": i.type,
        "title": i.title,
        "detail": i.detail,
        "status": i.status,
        "requester_id": i.requester_id,
        "requester_name": user.name if user else None,
        "requester_avatar": user.avatar if user else None,
        "target_team": i.target_team,
        "file_name": i.file_name,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


async def _get_users_map(db, items):
    user_ids = list({i.requester_id for i in items})
    users_map = {}
    if user_ids:
        users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in users_result.scalars().all():
            users_map[u.id] = u
    return users_map


# ── Endpoints ──

@router.get("/")
async def list_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """모든 pending 요청 목록 (팀 구분 없이 전체 조회)"""
    query = (
        select(ApprovalRequest)
        .where(ApprovalRequest.status == "pending")
        .order_by(ApprovalRequest.created_at.desc())
    )
    result = await db.execute(query)
    items = result.scalars().all()
    users_map = await _get_users_map(db, items)
    return [_serialize_approval(i, users_map) for i in items]


@router.get("/history")
async def list_approval_history(
    status: str = "approved",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """처리 완료된 요청 목록 (approved / rejected)"""
    if status not in ("approved", "rejected"):
        status = "approved"
    query = (
        select(ApprovalRequest)
        .where(ApprovalRequest.status == status)
        .order_by(ApprovalRequest.updated_at.desc())
    )
    result = await db.execute(query)
    items = result.scalars().all()
    users_map = await _get_users_map(db, items)
    return [_serialize_approval(i, users_map) for i in items]


@router.post("/", status_code=201)
async def create_approval(
    type: str = Form(...),
    title: str = Form(...),
    detail: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """새 결재/승인 요청 생성 (파일 첨부 가능)"""
    saved_path = None
    saved_name = None

    if file and file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"허용되지 않는 파일 형식입니다: {ext}")
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}{ext}"
        saved_path = str(UPLOAD_DIR / unique_name)
        content = await file.read()
        with open(saved_path, "wb") as f:
            f.write(content)
        saved_name = file.filename

    approval = ApprovalRequest(
        type=type,
        title=title,
        detail=detail,
        status="pending",
        requester_id=current_user.id,
        target_team=current_user.team,
        file_path=saved_path,
        file_name=saved_name,
    )
    db.add(approval)
    await db.flush()
    return {
        "id": approval.id,
        "type": approval.type,
        "title": approval.title,
        "status": approval.status,
        "file_name": approval.file_name,
    }


@router.get("/{approval_id}/file")
async def download_approval_file(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """첨부파일 다운로드"""
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    if not approval.file_path or not os.path.exists(approval.file_path):
        raise HTTPException(status_code=404, detail="첨부파일이 없습니다")

    return FileResponse(
        path=approval.file_path,
        filename=approval.file_name or "attachment",
        media_type="application/octet-stream",
    )


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


@router.delete("/{approval_id}")
async def delete_approval(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """요청 삭제 (본인이 올린 요청만)"""
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    if approval.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인이 올린 요청만 삭제할 수 있습니다")

    # 첨부파일도 삭제
    if approval.file_path and os.path.exists(approval.file_path):
        os.remove(approval.file_path)

    await db.delete(approval)
    await db.flush()
    return {"deleted": True, "id": approval_id}


@router.post("/seed", status_code=201)
async def seed_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """초기 샘플 데이터 시드 (기존 pending 없을 때만)"""
    existing = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.status == "pending").limit(1)
    )
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
