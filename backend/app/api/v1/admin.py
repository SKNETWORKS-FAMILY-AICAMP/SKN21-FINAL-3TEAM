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


# ── UI_UX.pdf 추가 엔드포인트 ──


@router.get("/query-logs")
async def get_query_logs(
    page: int = 1,
    per_page: int = 20,
    admin=Depends(get_admin_user),
    db=Depends(get_db),
):
    """
    질의 로그 조회 (NF-ST-002)

    UI_UX.pdf: "[추가] 질의 로그 탭 (사용자, 질문 내용, 호출된 Agent, 응답 시간)"
    """
    # TODO: 팀원 D 구현
    # statistics_service.get_query_logs() 호출
    raise NotImplementedError


@router.get("/top-queries")
async def get_top_queries(
    period: str = "daily",
    limit: int = 10,
    admin=Depends(get_admin_user),
    db=Depends(get_db),
):
    """
    Top 질의 응답 통계

    UI_UX.pdf: "Top 질의 응답 (월/주/일 탭으로 인기 질문 랭킹)"
    """
    # TODO: 팀원 D 구현
    # statistics_service.get_top_queries() 호출
    raise NotImplementedError


@router.put("/users/{user_id}/permissions")
async def update_user_permissions(
    user_id: int,
    admin=Depends(get_admin_user),
    db=Depends(get_db),
):
    """
    권한별 페이지 접근 제한 설정

    UI_UX.pdf: "[추가] 권한별 접근 제한 설정 (페이지별 접근 권한 체크박스)"
    """
    # TODO: 팀원 D 구현
    raise NotImplementedError
