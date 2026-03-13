"""
Pipeline Task API (팀원 D 담당)
- 팀 프로젝트 칸반 보드 CRUD (Google Tasks와 무관)
- 같은 팀 소속끼리만 공유
- 회의록 액션아이템 → Pipeline Todo 일괄 추가
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from datetime import date

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.pipeline_task import PipelineTask
from app.models.project import Project

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
    project: Optional[str] = None


class ActionItemToPipeline(BaseModel):
    task: str
    assignee: Optional[str] = None
    deadline: Optional[str] = None  # YYYY-MM-DD
    priority: str = "medium"


class BulkActionItemsRequest(BaseModel):
    items: list[ActionItemToPipeline]
    source: Optional[str] = None  # 회의 제목 / 프로젝트명

class PipelineTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    stage: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    sort_order: Optional[int] = None
    tags: Optional[list[str]] = None
    project: Optional[str] = None


# ── Endpoints ──

@router.get("/")
async def list_pipeline_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """본인이 생성했거나 참여 중인 프로젝트의 Pipeline Task 목록"""
    # 본인이 참여 중인 프로젝트명 수집
    assigned_q = select(PipelineTask.project).where(
        or_(
            PipelineTask.assignee == current_user.name,
            PipelineTask.assignee_id == current_user.id,
        ),
        PipelineTask.project.isnot(None),
    ).distinct()
    assigned_result = await db.execute(assigned_q)
    participated_projects = [r[0] for r in assigned_result.all()]

    # 본인이 생성했거나 members에 포함된 프로젝트명 수집
    created_q = select(Project.name).where(
        or_(
            Project.created_by == current_user.id,
            Project.members.contains(current_user.name),
        )
    )
    created_result = await db.execute(created_q)
    created_projects = [r[0] for r in created_result.all()]

    # 참여 + 생성 + 멤버 프로젝트 합집합
    visible_projects = list(set(participated_projects + created_projects))

    query = select(PipelineTask).order_by(PipelineTask.sort_order, PipelineTask.created_at)
    if visible_projects:
        query = query.where(
            or_(
                PipelineTask.created_by == current_user.id,
                PipelineTask.assignee == current_user.name,
                PipelineTask.assignee_id == current_user.id,
                PipelineTask.project.in_(visible_projects),
            )
        )
    else:
        query = query.where(
            or_(
                PipelineTask.created_by == current_user.id,
                PipelineTask.assignee == current_user.name,
                PipelineTask.assignee_id == current_user.id,
            )
        )

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
            "project": t.project,
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
        project=req.project,
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
    """Pipeline Task 수정 (같은 팀 또는 같은 프로젝트 참여자)"""
    result = await db.execute(select(PipelineTask).where(PipelineTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task를 찾을 수 없습니다")

    # 권한 확인: 같은 팀, 프로젝트 멤버, 프로젝트 참여자(assignee), 또는 본인 생성
    has_access = False
    if not task.team or task.team == current_user.team:
        has_access = True
    elif task.created_by == current_user.id:
        has_access = True
    elif task.project:
        proj_result = await db.execute(
            select(Project).where(Project.name == task.project)
        )
        proj = proj_result.scalar_one_or_none()
        if proj:
            if proj.members and current_user.name in proj.members.split(","):
                has_access = True
            elif proj.created_by == current_user.id:
                has_access = True
        # 해당 프로젝트의 태스크에 assignee로 참여 중이면 접근 허용
        if not has_access:
            assigned_q = await db.execute(
                select(PipelineTask.id).where(
                    PipelineTask.project == task.project,
                    or_(
                        PipelineTask.assignee == current_user.name,
                        PipelineTask.assignee_id == current_user.id,
                    ),
                ).limit(1)
            )
            if assigned_q.first():
                has_access = True
    if not has_access:
        raise HTTPException(status_code=403, detail="이 태스크를 수정할 권한이 없습니다")

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


@router.post("/from-action-items", status_code=201)
async def create_from_action_items(
    req: BulkActionItemsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회의록 액션아이템을 Pipeline Todo로 일괄 추가"""
    created = []
    for item in req.items:
        due = None
        if item.deadline:
            try:
                due = date.fromisoformat(item.deadline)
            except ValueError:
                pass

        task = PipelineTask(
            title=item.task,
            assignee=item.assignee,
            stage="todo",
            priority=item.priority,
            due_date=due,
            tags="회의록",
            project=req.source or None,
            team=current_user.team,
            created_by=current_user.id,
        )
        db.add(task)
        await db.flush()
        created.append({"id": task.id, "title": task.title})

    # 프로젝트 레코드도 자동 생성 (중복 방지)
    if req.source:
        existing = await db.execute(
            select(Project).where(Project.name == req.source, Project.team == current_user.team)
        )
        if not existing.scalar_one_or_none():
            db.add(Project(name=req.source, team=current_user.team, created_by=current_user.id))
            await db.flush()

    return {"created_count": len(created), "items": created}


# ── Project Endpoints ──

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    members: Optional[list[str]] = None  # 멤버 이름 목록


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    members: Optional[list[str]] = None


@router.get("/projects")
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """본인이 생성했거나 태스크에 참여 중인 프로젝트만 표시"""
    # 본인이 assignee인 태스크의 프로젝트명 수집 (참여자 판별)
    assigned_q = select(PipelineTask.project).where(
        or_(
            PipelineTask.assignee == current_user.name,
            PipelineTask.assignee_id == current_user.id,
        ),
        PipelineTask.project.isnot(None),
    ).distinct()
    assigned_result = await db.execute(assigned_q)
    assigned_project_names = [r[0] for r in assigned_result.all()]

    # 본인이 생성, 태스크 참여, 또는 members에 포함된 프로젝트 반환
    query = select(Project).order_by(Project.created_at)
    conditions = [Project.created_by == current_user.id]
    if assigned_project_names:
        conditions.append(Project.name.in_(assigned_project_names))
    # members 컬럼에 이름이 포함된 프로젝트도 표시
    conditions.append(Project.members.contains(current_user.name))
    query = query.where(or_(*conditions))

    result = await db.execute(query)
    items = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "team": p.team,
            "members": p.members.split(",") if p.members else [],
            "created_by": p.created_by,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in items
    ]


@router.post("/projects", status_code=201)
async def create_project(
    req: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로젝트 생성 (중복 이름 방지)"""
    existing = await db.execute(
        select(Project).where(Project.name == req.name, Project.team == current_user.team)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="같은 이름의 프로젝트가 이미 있습니다")

    project = Project(
        name=req.name,
        description=req.description,
        team=current_user.team,
        members=",".join(req.members) if req.members else None,
        created_by=current_user.id,
    )
    db.add(project)
    await db.flush()
    return {"id": project.id, "name": project.name, "members": req.members or []}


@router.put("/projects/{project_id}")
async def update_project(
    project_id: int,
    req: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로젝트 수정"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    if project.team and project.team != current_user.team:
        raise HTTPException(status_code=403, detail="같은 팀의 프로젝트만 수정할 수 있습니다")

    if req.name is not None:
        project.name = req.name
    if req.description is not None:
        project.description = req.description
    if req.members is not None:
        project.members = ",".join(req.members) if req.members else None

    await db.flush()
    return {
        "id": project.id,
        "name": project.name,
        "members": project.members.split(",") if project.members else [],
    }


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로젝트 삭제"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    if project.team and project.team != current_user.team:
        raise HTTPException(status_code=403, detail="같은 팀의 프로젝트만 삭제할 수 있습니다")

    await db.delete(project)
    await db.flush()
    return {"deleted": True, "id": project_id}
