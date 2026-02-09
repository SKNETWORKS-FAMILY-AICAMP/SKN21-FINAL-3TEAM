"""
Google Tasks 서비스 (팀원 D 담당)
- Action Item → Google Tasks 동기화
- 완료/미완료 상태 양방향 동기화
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.google_base_service import GoogleBaseService


class GoogleTasksService(GoogleBaseService):
    """Google Tasks CRUD + 상태 동기화"""

    required_scope = "tasks"

    async def sync_action_item(self, db: AsyncSession, user_id: int, action_item_id: int) -> dict:
        """단일 Action Item → Google Task 동기화"""
        # TODO: 팀원 D 구현
        # - action_item 조회
        # - Google Tasks API로 task 생성/업데이트
        # - action_item.google_task_id 저장
        raise NotImplementedError

    async def sync_all(self, db: AsyncSession, user_id: int, meeting_id: Optional[int] = None) -> dict:
        """전체 Action Item 동기화"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def list_tasks(self, db: AsyncSession, user_id: int) -> list:
        """Google Tasks 목록 조회"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def update_status(self, db: AsyncSession, user_id: int, action_item_id: int, completed: bool) -> dict:
        """Action Item 상태 변경 (완료/미완료) → Google Tasks 동기화"""
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def pull_status(self, db: AsyncSession, user_id: int) -> dict:
        """Google Tasks 상태 → DB 반영"""
        # TODO: 팀원 D 구현
        raise NotImplementedError
