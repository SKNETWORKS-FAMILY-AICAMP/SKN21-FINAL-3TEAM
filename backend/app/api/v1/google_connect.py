"""
통합 Google OAuth API (팀원 D 담당)
- 단일 OAuth 플로우로 여러 scope 관리
- status/connect/callback/disconnect
"""
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.core.security import decrypt_data, encrypt_data
from app.db.session import get_db
from app.models.oauth_token import OAuthToken
from app.models.user import User
from app.schemas.google_services import (
    GoogleConnectRequest,
    GoogleConnectResponse,
    GoogleDisconnectResponse,
    GoogleStatusResponse,
)
from app.services.google_base_service import GOOGLE_SCOPES

settings = get_settings()
router = APIRouter()


@router.get("/status", response_model=GoogleStatusResponse)
async def google_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Google 연결 상태 + scope 목록"""
    result = await db.execute(
        select(OAuthToken).where(OAuthToken.user_id == current_user.id)
    )
    token = result.scalar_one_or_none()

    if token is None:
        return GoogleStatusResponse(connected=False)

    scopes = token.scopes.split(",") if token.scopes else []
    return GoogleStatusResponse(
        connected=True,
        provider=token.provider,
        scopes=scopes,
        expires_at=token.expires_at,
    )


@router.post("/connect", response_model=GoogleConnectResponse)
async def google_connect(
    request: GoogleConnectRequest,
    current_user: User = Depends(get_current_user),
):
    """OAuth URL 반환 (요청된 scopes로)"""
    # scope 키 → Google scope URL 변환
    scope_urls = []
    for scope_key in request.scopes:
        if scope_key not in GOOGLE_SCOPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"지원하지 않는 scope: {scope_key}. 사용 가능: {list(GOOGLE_SCOPES.keys())}",
            )
        scope_urls.append(GOOGLE_SCOPES[scope_key])

    # state에 user_id + scope_keys 포함 (Fernet 암호화 → CSRF 방지)
    state_data = json.dumps({"user_id": current_user.id, "scopes": request.scopes})
    state = encrypt_data(state_data)

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scope_urls),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    return GoogleConnectResponse(auth_url=auth_url)


@router.get("/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """OAuth 콜백 (code → token 저장)"""
    # state 복호화 → user_id, scopes 추출
    try:
        state_data = json.loads(decrypt_data(state))
        user_id = state_data["user_id"]
        scope_keys = state_data["scopes"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 state 파라미터",
        )

    # authorization code → access_token 교환
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )

    if token_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"토큰 교환 실패: {token_response.text}",
        )

    token_data = token_response.json()

    # expires_in → expires_at 변환
    expires_at = None
    if "expires_in" in token_data:
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            seconds=token_data["expires_in"]
        )

    # 기존 토큰 조회 (scope 병합)
    result = await db.execute(
        select(OAuthToken).where(OAuthToken.user_id == user_id)
    )
    existing_token = result.scalar_one_or_none()

    # scope 병합: 기존 + 신규
    new_scopes = set(scope_keys)
    if existing_token and existing_token.scopes:
        existing_scopes = set(existing_token.scopes.split(","))
        new_scopes = existing_scopes | new_scopes
    scopes_str = ",".join(sorted(new_scopes))

    if existing_token:
        existing_token.access_token = encrypt_data(token_data["access_token"])
        if token_data.get("refresh_token"):
            existing_token.refresh_token = encrypt_data(token_data["refresh_token"])
        existing_token.expires_at = expires_at
        existing_token.scopes = scopes_str
    else:
        oauth_token = OAuthToken(
            user_id=user_id,
            provider="google",
            access_token=encrypt_data(token_data["access_token"]),
            refresh_token=encrypt_data(token_data["refresh_token"]) if token_data.get("refresh_token") else None,
            expires_at=expires_at,
            scopes=scopes_str,
        )
        db.add(oauth_token)

    await db.flush()

    # 프론트엔드로 리다이렉트 (연결 성공)
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/schedules?google=connected")


@router.post("/disconnect", response_model=GoogleDisconnectResponse)
async def google_disconnect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Google 토큰 폐기 + DB 삭제"""
    result = await db.execute(
        select(OAuthToken).where(OAuthToken.user_id == current_user.id)
    )
    token = result.scalar_one_or_none()

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="연결된 Google 계정이 없습니다",
        )

    # Google에 토큰 폐기 요청 (실패해도 로컬 삭제 진행)
    try:
        access_token = decrypt_data(token.access_token)
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": access_token},
            )
    except Exception:
        pass

    await db.delete(token)
    await db.flush()

    return GoogleDisconnectResponse(disconnected=True)
