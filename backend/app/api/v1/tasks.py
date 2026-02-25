"""
Google Tasks API 엔드포인트 (팀원 D 담당)
- Action Item → Google Tasks 동기화
"""
import traceback
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.google_services import (
    TaskCreateRequest,
    TaskSyncRequest,
    TaskSyncAllRequest,
    TaskSyncResponse,
    TaskStatusUpdateRequest,
)
from app.services.tasks_service import GoogleTasksService

logger = logging.getLogger(__name__)
router = APIRouter()
tasks_service = GoogleTasksService()


@router.post("/create")
async def create_task(
    request: TaskCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Task 생성"""
    try:
        result = await tasks_service.create_task(
            db, current_user.id,
            title=request.title,
            assignee=request.assignee,
            due_date=request.due_date,
            priority=request.priority,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tasks create] {type(e).__name__}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Task 생성 오류: {type(e).__name__}: {e}")


@router.delete("/{action_item_id}")
async def delete_task(
    action_item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Task 삭제"""
    try:
        return await tasks_service.delete_task(db, current_user.id, action_item_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tasks delete] {type(e).__name__}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Task 삭제 오류: {type(e).__name__}: {e}")


@router.post("/sync", response_model=TaskSyncResponse)
async def sync_task(
    request: TaskSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """단일 Action Item → Google Task 동기화"""
    try:
        result = await tasks_service.sync_action_item(db, current_user.id, request.action_item_id)
        return TaskSyncResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tasks sync] {type(e).__name__}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Tasks 동기화 오류: {type(e).__name__}: {e}")


@router.post("/sync-all", response_model=TaskSyncResponse)
async def sync_all_tasks(
    request: TaskSyncAllRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """전체 Action Item 동기화"""
    try:
        result = await tasks_service.sync_all(db, current_user.id, request.meeting_id)
        return TaskSyncResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tasks sync-all] {type(e).__name__}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Tasks 전체 동기화 오류: {type(e).__name__}: {e}")


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
    try:
        result = await tasks_service.update_status(db, current_user.id, action_item_id, request.completed)
        return TaskSyncResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tasks status] {type(e).__name__}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Task 상태 변경 오류: {type(e).__name__}: {e}")


@router.post("/pull")
async def pull_task_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Google Tasks → DB 상태 풀"""
    try:
        return await tasks_service.pull_status(db, current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tasks pull] {type(e).__name__}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Tasks Pull 오류: {type(e).__name__}: {e}")
