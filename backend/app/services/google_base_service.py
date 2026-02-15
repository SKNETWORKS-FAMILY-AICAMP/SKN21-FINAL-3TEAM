"""
Google API 공통 베이스 서비스 (팀원 D 담당)
- OAuth 토큰 관리 (조회, 갱신, scope 검증)
- 모든 Google 서비스(Calendar, Tasks, Gmail, Sheets)가 상속
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from app.models.oauth_token import OAuthToken
from app.core.security import encrypt_data, decrypt_data
from app.config import get_settings

settings = get_settings()

# Google OAuth scope 매핑
GOOGLE_SCOPES = {
    "calendar": "https://www.googleapis.com/auth/calendar",
    "tasks": "https://www.googleapis.com/auth/tasks",
    "gmail_send": "https://www.googleapis.com/auth/gmail.send",
    "sheets": "https://www.googleapis.com/auth/spreadsheets",
}


class GoogleBaseService:
    """Google API 공통 베이스 클래스 — 5개 서비스가 상속"""

    required_scope: str = ""  # 서브클래스에서 지정

    async def get_token(self, db: AsyncSession, user_id: int) -> OAuthToken | None:
        """사용자의 OAuth 토큰 조회"""
        result = await db.execute(
            select(OAuthToken).where(OAuthToken.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_credentials(self, db: AsyncSession, user_id: int) -> Credentials:
        """Google API 인증 정보 반환 (토큰 자동 갱신 포함)"""
        token = await self.get_token(db, user_id)
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google 계정이 연결되지 않았습니다",
            )

        self._check_scope(token)

        creds = Credentials(
            token=decrypt_data(token.access_token),
            refresh_token=decrypt_data(token.refresh_token) if token.refresh_token else None,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )

        # 토큰 만료 시 갱신
        if token.expires_at and token.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            if creds.refresh_token:
                await self._refresh_token(db, token, creds)
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="토큰이 만료되었습니다. 다시 연결해주세요",
                )

        return creds

    def _check_scope(self, token: OAuthToken) -> None:
        """필요한 scope이 토큰에 포함되어 있는지 확인"""
        if not self.required_scope:
            return
        if not self.has_scope(token, self.required_scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"'{self.required_scope}' 권한이 필요합니다. Google 연결에서 추가해주세요",
            )

    async def _refresh_token(self, db: AsyncSession, token: OAuthToken, creds: Credentials) -> None:
        """만료된 토큰 갱신"""
        creds.refresh(Request())
        token.access_token = encrypt_data(creds.token)
        if creds.expiry:
            token.expires_at = creds.expiry.replace(tzinfo=None)

    def has_scope(self, token: OAuthToken, scope: str) -> bool:
        """특정 scope 보유 여부"""
        if not token.scopes:
            return False
        return scope in token.scopes.split(",")
