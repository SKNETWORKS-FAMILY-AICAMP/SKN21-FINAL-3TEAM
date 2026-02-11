"""
Google Tasks API 엔드포인트 (팀원 D 담당)
- Action Item → Google Tasks 동기화
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.google_services import (
    TaskSyncRequest,
    TaskSyncAllRequest,
    TaskSyncResponse,
    TaskStatusUpdateRequest,
)
from app.services.tasks_service import GoogleTasksService

router = APIRouter()
tasks_service = GoogleTasksService()


@router.post("/sync", response_model=TaskSyncResponse)
async def sync_task(
    request: TaskSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """단일 Action Item → Google Task 동기화"""
    result = await tasks_service.sync_action_item(db, current_user.id, request.action_item_id)
    return TaskSyncResponse(**result)


@router.post("/sync-all", response_model=TaskSyncResponse)
async def sync_all_tasks(
    request: TaskSyncAllRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """전체 Action Item 동기화"""
    result = await tasks_service.sync_all(db, current_user.id, request.meeting_id)
    return TaskSyncResponse(**result)


@router.get("/")
async def list_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Google Tasks 목록 조회"""
    return await tasks_service.list_tasks(db, current_user.id)


@router.put("/{action_item_id}/status", response_model=TaskSyncResponse)
async def update_task_status(
    action_item_id: int,
    request: TaskStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """완료/미완료 상태 변경"""
    result = await tasks_service.update_status(db, current_user.id, action_item_id, request.completed)
    return TaskSyncResponse(**result)


@router.post("/pull")
async def pull_task_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Google Tasks → DB 상태 풀"""
    return await tasks_service.pull_status(db, current_user.id)
