"""
Google Tasks API 엔드포인트 (팀원 D 담당)
- Action Item → Google Tasks 동기화
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.session import get_db

router = APIRouter()


@router.post("/sync")
async def sync_task(user=Depends(get_current_user), db=Depends(get_db)):
    """단일 Action Item → Google Task 동기화"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.post("/sync-all")
async def sync_all_tasks(user=Depends(get_current_user), db=Depends(get_db)):
    """전체 Action Item 동기화"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.get("/")
async def list_tasks(user=Depends(get_current_user), db=Depends(get_db)):
    """Google Tasks 목록 조회"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.put("/{action_item_id}/status")
async def update_task_status(action_item_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    """완료/미완료 상태 변경"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.post("/pull")
async def pull_task_status(user=Depends(get_current_user), db=Depends(get_db)):
    """Google Tasks → DB 상태 풀"""
    # TODO: 팀원 D 구현
    raise NotImplementedError
