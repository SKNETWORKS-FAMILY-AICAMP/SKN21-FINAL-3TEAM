"""
Google Tasks 서비스 (팀원 D 담당)
- Action Item → Google Tasks 동기화
- 완료/미완료 상태 양방향 동기화
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_item import ActionItem
from app.services.google_base_service import GoogleBaseService

logger = logging.getLogger(__name__)

TASKLIST_TITLE = "WorkFlow Agent"


class GoogleTasksService(GoogleBaseService):
    """Google Tasks CRUD + 상태 동기화"""

    required_scope = "tasks"

    def _build_service(self, creds):
        return build("tasks", "v1", credentials=creds, cache_discovery=False)

    def _get_or_create_tasklist(self, service) -> str:
        """WorkFlow Agent 전용 태스크 리스트 ID 반환 (없으면 생성)"""
        result = service.tasklists().list(maxResults=100).execute()
        for tl in result.get("items", []):
            if tl["title"] == TASKLIST_TITLE:
                return tl["id"]
        new_list = service.tasklists().insert(body={"title": TASKLIST_TITLE}).execute()
        return new_list["id"]

    async def sync_action_item(self, db: AsyncSession, user_id: int, action_item_id: int) -> dict:
        """단일 Action Item → Google Task 동기화"""
        result = await db.execute(
            select(ActionItem).where(ActionItem.id == action_item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action Item을 찾을 수 없습니다")

        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)
        tasklist_id = self._get_or_create_tasklist(service)

        task_body = {
            "title": item.content,
            "notes": f"담당: {item.assignee or '미지정'} | 우선순위: {item.priority}",
            "status": "completed" if item.status == "done" else "needsAction",
        }
        if item.due_date:
            task_body["due"] = item.due_date.strftime("%Y-%m-%dT00:00:00.000Z")

        if item.google_task_id:
            task_body["id"] = item.google_task_id
            task = service.tasks().update(
                tasklist=tasklist_id, task=item.google_task_id, body=task_body
            ).execute()
        else:
            task = service.tasks().insert(tasklist=tasklist_id, body=task_body).execute()
            item.google_task_id = task["id"]

        return {"task_id": task["id"], "status": task["status"]}

    async def sync_all(self, db: AsyncSession, user_id: int, meeting_id: Optional[int] = None) -> dict:
        """전체 Action Item 동기화"""
        query = select(ActionItem)
        if meeting_id:
            query = query.where(ActionItem.meeting_id == meeting_id)
        result = await db.execute(query)
        items = result.scalars().all()

        synced = 0
        for item in items:
            await self.sync_action_item(db, user_id, item.id)
            synced += 1

        return {"synced_count": synced}

    async def list_tasks(self, db: AsyncSession, user_id: int) -> list:
        """Action Items 목록 (Google Task 연동 정보 포함)"""
        result = await db.execute(select(ActionItem))
        items = result.scalars().all()

        tasks = []
        for item in items:
            tasks.append({
                "action_item_id": item.id,
                "id": item.google_task_id or str(item.id),
                "title": item.content,
                "assignee": item.assignee,
                "deadline": item.due_date.strftime("%Y-%m-%d") if item.due_date else None,
                "priority": item.priority,
                "status": "completed" if item.status == "done" else "needsAction",
                "completed": item.status == "done",
                "synced": item.google_task_id is not None,
            })
        return tasks

    async def update_status(self, db: AsyncSession, user_id: int, action_item_id: int, completed: bool) -> dict:
        """Action Item 상태 변경 → Google Tasks 동기화"""
        result = await db.execute(
            select(ActionItem).where(ActionItem.id == action_item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action Item을 찾을 수 없습니다")

        item.status = "done" if completed else "pending"

        if item.google_task_id:
            creds = await self.get_credentials(db, user_id)
            service = self._build_service(creds)
            tasklist_id = self._get_or_create_tasklist(service)
            service.tasks().update(
                tasklist=tasklist_id,
                task=item.google_task_id,
                body={"id": item.google_task_id, "status": "completed" if completed else "needsAction"},
            ).execute()

        return {"task_id": item.google_task_id, "status": item.status}

    async def pull_status(self, db: AsyncSession, user_id: int) -> dict:
        """Google Tasks 상태 → DB 반영 + 새 Task import"""
        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)
        tasklist_id = self._get_or_create_tasklist(service)

        result = service.tasks().list(
            tasklist=tasklist_id, maxResults=100,
            showCompleted=True, showHidden=True,
        ).execute()
        google_tasks = {t["id"]: t for t in result.get("items", [])}
        logger.info(f"[pull] Google Tasks: {len(google_tasks)}개")

        db_result = await db.execute(
            select(ActionItem).where(ActionItem.google_task_id.isnot(None))
        )
        items = db_result.scalars().all()
        existing_ids = {item.google_task_id for item in items}

        # 1) 기존 아이템 상태 동기화
        updated = 0
        for item in items:
            gt = google_tasks.get(item.google_task_id)
            if gt:
                new_status = "done" if gt["status"] == "completed" else "pending"
                if item.status != new_status:
                    item.status = new_status
                    updated += 1
                    logger.info(f"[pull] 상태변경: {item.content} → {new_status}")

        # 2) Google에서 새로 추가된 Task → DB import
        imported = 0
        for task_id, gt in google_tasks.items():
            if task_id not in existing_ids:
                due_date = None
                if gt.get("due"):
                    try:
                        due_date = datetime.fromisoformat(gt["due"].replace("Z", "+00:00")).replace(tzinfo=None)
                    except (ValueError, AttributeError):
                        pass

                new_item = ActionItem(
                    meeting_id=None,
                    content=gt.get("title", "(제목 없음)"),
                    status="done" if gt.get("status") == "completed" else "pending",
                    priority="medium",
                    google_task_id=task_id,
                    due_date=due_date,
                )
                db.add(new_item)
                imported += 1
                logger.info(f"[pull] 새 Task import: {gt.get('title')}")

        await db.flush()
        return {"updated_count": updated, "imported_count": imported}
