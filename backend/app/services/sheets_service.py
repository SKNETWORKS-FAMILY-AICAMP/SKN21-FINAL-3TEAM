"""
Google Sheets 서비스 (팀원 D 담당)
- Pipeline 프로젝트 문서화 스프레드시트 생성/동기화
"""
from datetime import date
from typing import Optional
import math

from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_task import PipelineTask
from app.models.google_sheet_tracker import GoogleSheetTracker
from app.services.google_base_service import GoogleBaseService

HEADER_ROW = ["No", "태스크명", "담당자", "우선순위", "상태", "마감일", "D-day", "태그", "설명"]

STAGE_LABEL = {
    "todo": "To Do",
    "in_progress": "In Progress",
    "review": "Review",
    "done": "Done",
}

PRIORITY_LABEL = {
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
}


class GoogleSheetsService(GoogleBaseService):
    """Google Sheets — Pipeline 프로젝트 문서화"""

    required_scope = "sheets"

    def _build_service(self, creds):
        return build("sheets", "v4", credentials=creds)

    def _calc_dday(self, due_date) -> str:
        if not due_date:
            return ""
        d = due_date if isinstance(due_date, date) else due_date.date()
        diff = (d - date.today()).days
        if diff < 0:
            return f"{abs(diff)}일 초과"
        if diff == 0:
            return "D-Day"
        return f"D-{diff}"

    async def export_project_to_sheet(
        self,
        db: AsyncSession,
        user_id: int,
        project_name: str,
        title: Optional[str] = None,
    ) -> dict:
        """프로젝트의 태스크를 Google Sheets로 내보내기"""
        # 프로젝트 태스크 조회
        query = select(PipelineTask).where(PipelineTask.project == project_name)
        result = await db.execute(query)
        tasks = result.scalars().all()

        sheet_title = title or f"{project_name} — 프로젝트 문서"

        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)

        # 스프레드시트 생성
        spreadsheet = service.spreadsheets().create(
            body={"properties": {"title": sheet_title}}
        ).execute()

        spreadsheet_id = spreadsheet["spreadsheetId"]
        spreadsheet_url = spreadsheet["spreadsheetUrl"]
        sheet_id = spreadsheet["sheets"][0]["properties"]["sheetId"]

        # 데이터 준비
        rows = [HEADER_ROW]
        for idx, task in enumerate(tasks, 1):
            rows.append([
                str(idx),
                task.title or "",
                task.assignee or "",
                PRIORITY_LABEL.get(task.priority, task.priority or ""),
                STAGE_LABEL.get(task.stage, task.stage or ""),
                task.due_date.strftime("%Y-%m-%d") if task.due_date else "",
                self._calc_dday(task.due_date),
                task.tags or "",
                task.description or "",
            ])

        # 데이터 쓰기
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        # 서식 적용
        self._apply_formatting(service, spreadsheet_id, sheet_id, len(rows))

        # DB 트래커 저장
        tracker = GoogleSheetTracker(
            user_id=user_id,
            spreadsheet_id=spreadsheet_id,
            spreadsheet_url=spreadsheet_url,
            sheet_name=sheet_title,
            project_name=project_name,
        )
        db.add(tracker)
        await db.flush()

        return {
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_url": spreadsheet_url,
            "title": sheet_title,
            "task_count": len(tasks),
        }

    def _apply_formatting(self, service, spreadsheet_id, sheet_id, row_count):
        """헤더 스타일 + 열 너비 설정"""
        requests = [
            # 헤더 행 스타일
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.29, "green": 0.36, "blue": 0.86},
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            },
            # 헤더 행 고정
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            },
        ]

        # 열 너비 설정
        col_widths = [40, 250, 100, 80, 100, 100, 80, 150, 300]
        for i, w in enumerate(col_widths):
            requests.append({
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                    "properties": {"pixelSize": w},
                    "fields": "pixelSize",
                }
            })

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

    async def sync_project_to_sheet(
        self,
        db: AsyncSession,
        user_id: int,
        spreadsheet_id: str,
        project_name: str,
    ) -> dict:
        """기존 시트에 프로젝트 태스크 재동기화"""
        query = select(PipelineTask).where(PipelineTask.project == project_name)
        result = await db.execute(query)
        tasks = result.scalars().all()

        rows = []
        for idx, task in enumerate(tasks, 1):
            rows.append([
                str(idx),
                task.title or "",
                task.assignee or "",
                PRIORITY_LABEL.get(task.priority, task.priority or ""),
                STAGE_LABEL.get(task.stage, task.stage or ""),
                task.due_date.strftime("%Y-%m-%d") if task.due_date else "",
                self._calc_dday(task.due_date),
                task.tags or "",
                task.description or "",
            ])

        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)

        # 기존 데이터 클리어 (헤더 제외) 후 다시 쓰기
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range="A2:I",
        ).execute()

        if rows:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="A2",
                valueInputOption="RAW",
                body={"values": rows},
            ).execute()

        return {"synced_count": len(rows), "spreadsheet_id": spreadsheet_id}

    async def list_sheets(self, db: AsyncSession, user_id: int) -> list:
        """사용자의 프로젝트 스프레드시트 목록"""
        result = await db.execute(
            select(GoogleSheetTracker).where(GoogleSheetTracker.user_id == user_id)
        )
        trackers = result.scalars().all()
        return [
            {
                "id": t.id,
                "spreadsheet_id": t.spreadsheet_id,
                "spreadsheet_url": t.spreadsheet_url,
                "sheet_name": t.sheet_name,
                "project_name": t.project_name,
                "created_at": t.created_at,
            }
            for t in trackers
        ]

    async def delete_sheet(
        self,
        db: AsyncSession,
        user_id: int,
        spreadsheet_id: str,
    ) -> bool:
        """DB에서 추적 시트 레코드 삭제"""
        result = await db.execute(
            select(GoogleSheetTracker).where(
                GoogleSheetTracker.user_id == user_id,
                GoogleSheetTracker.spreadsheet_id == spreadsheet_id,
            )
        )
        tracker = result.scalar_one_or_none()
        if not tracker:
            return False
        await db.delete(tracker)
        await db.flush()
        return True
