"""
Google Calendar 서비스 (팀원 D 담당)
"""


class GoogleCalendarService:
    """Google Calendar 양방향 연동"""

    async def connect(self, user_id: int, auth_code: str):
        """Google OAuth 연결"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def disconnect(self, user_id: int):
        """연결 해제"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def push_event(self, schedule_id: int, user_id: int):
        """앱 → Google Calendar 이벤트 생성"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def pull_events(self, user_id: int):
        """Google Calendar → 앱 일정 조회"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def refresh_token_if_needed(self, user_id: int):
        """토큰 자동 갱신"""
        # TODO: 팀원 D 구현
        raise NotImplementedError
