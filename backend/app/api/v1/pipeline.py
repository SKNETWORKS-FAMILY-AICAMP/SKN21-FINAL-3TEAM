"""
Pipeline Task API (팀원 D 담당)
- 팀 프로젝트 칸반 보드 CRUD (Google Tasks와 무관)
- 같은 팀 소속끼리만 공유
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from datetime import date

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.pipeline_task import PipelineTask

router = APIRouter()


# ── Schemas ──

class PipelineTaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assignee: Optional[str] = None
    stage: str = "todo"
    priority: str = "medium"
    due_date: Optional[date] = None
    tags: Optional[list[str]] = None

class PipelineTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    stage: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    sort_order: Optional[int] = None
    tags: Optional[list[str]] = None


# ── Endpoints ──

@router.get("/")
async def list_pipeline_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """같은 팀의 Pipeline Task 목록"""
    query = select(PipelineTask).order_by(PipelineTask.sort_order, PipelineTask.created_at)
    if current_user.team:
        query = query.where(PipelineTask.team == current_user.team)
    else:
        query = query.where(PipelineTask.created_by == current_user.id)

    result = await db.execute(query)
    items = result.scalars().all()
    return [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "assignee": t.assignee,
            "stage": t.stage,
            "priority": t.priority,
            "dueDate": t.due_date.strftime("%Y-%m-%d") if t.due_date else None,
            "sort_order": t.sort_order,
            "tags": t.tags.split(",") if t.tags else [],
            "team": t.team,
            "created_by": t.created_by,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in items
    ]


@router.post("/", status_code=201)
async def create_pipeline_task(
    req: PipelineTaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pipeline Task 생성 (자동으로 사용자의 팀 배정)"""
    task = PipelineTask(
        title=req.title,
        description=req.description,
        assignee=req.assignee,
        stage=req.stage,
        priority=req.priority,
        due_date=req.due_date,
        tags=",".join(req.tags) if req.tags else None,
        team=current_user.team,
        created_by=current_user.id,
    )
    db.add(task)
    await db.flush()
    return {
        "id": task.id,
        "title": task.title,
        "stage": task.stage,
        "team": task.team,
    }


@router.put("/{task_id}")
async def update_pipeline_task(
    task_id: int,
    req: PipelineTaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pipeline Task 수정 (같은 팀만)"""
    result = await db.execute(select(PipelineTask).where(PipelineTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task를 찾을 수 없습니다")
    if task.team and task.team != current_user.team:
        raise HTTPException(status_code=403, detail="같은 팀의 태스크만 수정할 수 있습니다")

    data = req.model_dump(exclude_none=True)
    if "tags" in data:
        data["tags"] = ",".join(data["tags"]) if data["tags"] else None
    for field, value in data.items():
        setattr(task, field, value)

    await db.flush()
    return {"id": task.id, "title": task.title, "stage": task.stage}


@router.delete("/{task_id}")
async def delete_pipeline_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pipeline Task 삭제 (같은 팀만)"""
    result = await db.execute(select(PipelineTask).where(PipelineTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task를 찾을 수 없습니다")
    if task.team and task.team != current_user.team:
        raise HTTPException(status_code=403, detail="같은 팀의 태스크만 삭제할 수 있습니다")

    await db.delete(task)
    await db.flush()
    return {"deleted": True, "id": task_id}
