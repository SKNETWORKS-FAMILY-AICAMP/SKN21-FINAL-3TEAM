"""
관리자 API (팀원 D 담당)
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_admin_user
from app.db.session import get_db

router = APIRouter()


@router.get("/users")
async def list_users(admin=Depends(get_admin_user), db=Depends(get_db)):
    """사용자 목록 조회"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.get("/stats")
async def system_stats(admin=Depends(get_admin_user), db=Depends(get_db)):
    """시스템 통계"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.get("/logs")
async def query_logs(admin=Depends(get_admin_user), db=Depends(get_db)):
    """질의 로그 조회"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.get("/regulations")
async def list_regulations(admin=Depends(get_admin_user), db=Depends(get_db)):
    """규정 관리"""
    # TODO: 팀원 D 구현
    raise NotImplementedError
