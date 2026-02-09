"""
일정 서비스 (팀원 D 담당)
"""


class ScheduleService:
    """일정 CRUD + 우선순위 자동 설정"""

    async def create_from_action_item(self, action_item_id: int, user_id: int):
        """Action Item → 일정 자동 등록"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def calculate_priority(self, due_date) -> str:
        """마감일 기반 우선순위 자동 설정 (D-day 계산)"""
        # TODO: 팀원 D 구현
        raise NotImplementedError
