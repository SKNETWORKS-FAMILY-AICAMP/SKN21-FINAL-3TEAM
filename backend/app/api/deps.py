"""
공통 의존성 (팀원 A/D 공동)
- DB 세션, 인증 의존성 등
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.db.session import get_db

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db),
):
    """JWT 토큰에서 현재 사용자 추출 (팀원 D 구현)"""
    # TODO: 팀원 D - JWT 토큰 검증 및 사용자 조회 로직
    raise NotImplementedError("팀원 D: JWT 인증 로직 구현 필요")


async def get_admin_user(current_user=Depends(get_current_user)):
    """관리자 권한 확인 (팀원 D 구현)"""
    # TODO: 팀원 D - 관리자 권한 확인
    raise NotImplementedError("팀원 D: 관리자 권한 확인 구현 필요")
