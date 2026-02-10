"""
Google API 공통 베이스 서비스 (팀원 D 담당)
- OAuth 토큰 관리 (조회, 갱신, scope 검증)
- 모든 Google 서비스(Calendar, Tasks, Gmail, Sheets)가 상속
"""
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def get_token(self, db: AsyncSession, user_id: int):
        """사용자의 OAuth 토큰 조회"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def get_credentials(self, db: AsyncSession, user_id: int):
        """Google API 인증 정보 반환 (토큰 자동 갱신 포함)"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    def _check_scope(self, token) -> None:
        """필요한 scope이 토큰에 포함되어 있는지 확인"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def _refresh_token(self, db: AsyncSession, token, creds):
        """만료된 토큰 갱신"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    def has_scope(self, token, scope: str) -> bool:
        """특정 scope 보유 여부"""
        # TODO: 팀원 D 구현
        raise NotImplementedError
