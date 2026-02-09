"""
일정 관리 API (팀원 D 담당)
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.session import get_db

router = APIRouter()


@router.get("/")
async def list_schedules(user=Depends(get_current_user), db=Depends(get_db)):
    """일정 목록 조회"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.post("/")
async def create_schedule(user=Depends(get_current_user), db=Depends(get_db)):
    """일정 생성 (Action Item → 일정 자동 등록)"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.put("/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """일정 수정"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """일정 삭제"""
    # TODO: 팀원 D 구현
    raise NotImplementedError
