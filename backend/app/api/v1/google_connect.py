"""
통합 Google OAuth API (팀원 D 담당)
- 단일 OAuth 플로우로 여러 scope 관리
- status/connect/callback/disconnect
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.session import get_db

router = APIRouter()


@router.get("/status")
async def google_status(user=Depends(get_current_user), db=Depends(get_db)):
    """Google 연결 상태 + scope 목록"""
    # TODO: 팀원 D 구현
    # - oauth_tokens에서 user_id로 토큰 조회
    # - connected, scopes, expires_at 반환
    raise NotImplementedError


@router.post("/connect")
async def google_connect(user=Depends(get_current_user), db=Depends(get_db)):
    """OAuth URL 반환 (요청된 scopes로)"""
    # TODO: 팀원 D 구현
    # - body.scopes → GOOGLE_SCOPES 매핑
    # - google_auth_oauthlib.Flow로 auth_url 생성
    # - state에 user_id + scope_keys 포함
    raise NotImplementedError


@router.get("/callback")
async def google_callback(db=Depends(get_db)):
    """OAuth 콜백 (code → token 저장)"""
    # TODO: 팀원 D 구현
    # - code + state 파라미터 파싱
    # - Flow.fetch_token(code)
    # - oauth_tokens 테이블에 저장/업데이트 (scope 병합)
    raise NotImplementedError


@router.post("/disconnect")
async def google_disconnect(user=Depends(get_current_user), db=Depends(get_db)):
    """Google 토큰 폐기"""
    # TODO: 팀원 D 구현
    raise NotImplementedError
