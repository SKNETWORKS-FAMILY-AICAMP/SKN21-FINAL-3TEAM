"""
Google Sheets 서비스 (팀원 D 담당)
- Pipeline 프로젝트 문서화 스프레드시트 생성/동기화
- 시트 미리보기 (read) / 인라인 편집 (update)
- AI WBS 자동 생성
"""
from datetime import date
from typing import Optional
import json
import logging
import math

from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_task import PipelineTask
from app.models.google_sheet_tracker import GoogleSheetTracker
from app.services.google_base_service import GoogleBaseService

logger = logging.getLogger(__name__)

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
        from datetime import datetime as dt
        d = due_date.date() if isinstance(due_date, dt) else due_date
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
        generate_wbs: bool = True,
    ) -> dict:
        """프로젝트의 태스크를 Google Sheets로 내보내기 (+ WBS 자동 생성)"""
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

        # WBS 자동 생성
        wbs_generated = False
        if generate_wbs and tasks:
            try:
                wbs_generated = await self._generate_wbs_tab(
                    service, spreadsheet_id, tasks
                )
            except Exception as e:
                logger.warning(f"WBS 생성 실패 (flat export는 정상): {e}")

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
            "wbs_generated": wbs_generated,
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

    # ── Phase 1: 시트 미리보기 ──

    async def read_sheet_data(
        self,
        db: AsyncSession,
        user_id: int,
        spreadsheet_id: str,
        sheet_name: str = "Sheet1",
    ) -> dict:
        """Google Sheets에서 셀 데이터 + 탭 목록 읽어오기"""
        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)

        # 탭 이름 목록
        meta = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="sheets.properties.title",
        ).execute()
        tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]

        # 셀 데이터
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=sheet_name,
        ).execute()
        values = result.get("values", [])

        return {"values": values, "tabs": tabs}

    # ── Phase 3: 인라인 편집 ──

    async def update_sheet_data(
        self,
        db: AsyncSession,
        user_id: int,
        spreadsheet_id: str,
        updates: list[dict],
        sheet_name: str = "Sheet1",
    ) -> dict:
        """셀 데이터 일괄 업데이트 (batchUpdate)"""
        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)

        data = []
        for u in updates:
            data.append({
                "range": f"{sheet_name}!{u['cell']}",
                "values": [[u["value"]]],
            })

        body = {
            "valueInputOption": "RAW",
            "data": data,
        }
        result = service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body,
        ).execute()

        return {"updated_count": result.get("totalUpdatedCells", 0)}

    # ── Phase 2: AI WBS 자동 생성 ──

    async def _generate_wbs_tab(
        self,
        service,
        spreadsheet_id: str,
        tasks,
    ) -> bool:
        """LLM으로 WBS 생성 → 스프레드시트에 'WBS' 탭 추가"""
        from ai.llm.factory import get_llm
        from ai.llm.prompts import WBS_GENERATE_SYSTEM_PROMPT

        # 태스크 데이터를 텍스트로 변환
        task_lines = []
        for t in tasks:
            line = f"- {t.title or '(제목 없음)'}"
            if t.assignee:
                line += f" | 담당: {t.assignee}"
            if t.priority:
                line += f" | 우선순위: {PRIORITY_LABEL.get(t.priority, t.priority)}"
            if t.stage:
                line += f" | 상태: {STAGE_LABEL.get(t.stage, t.stage)}"
            if t.due_date:
                line += f" | 마감: {t.due_date.strftime('%Y-%m-%d')}"
            if t.description:
                line += f" | 설명: {t.description[:100]}"
            task_lines.append(line)

        user_prompt = f"프로젝트 태스크 목록:\n" + "\n".join(task_lines)

        # LLM 호출
        llm = get_llm()
        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=WBS_GENERATE_SYSTEM_PROMPT,
            temperature=0.3,
            json_mode=True,
        )

        # JSON 파싱
        wbs_data = json.loads(response)
        wbs_items = wbs_data.get("wbs", [])
        if not wbs_items:
            return False

        # WBS를 평탄화하여 행 데이터 생성
        wbs_rows = [["WBS Code", "Level", "이름", "담당자", "우선순위", "상태", "마감일"]]
        self._flatten_wbs(wbs_items, wbs_rows)

        # "WBS" 탭 추가
        add_sheet_resp = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": "WBS"}}}]},
        ).execute()
        wbs_sheet_id = add_sheet_resp["replies"][0]["addSheet"]["properties"]["sheetId"]

        # WBS 데이터 쓰기
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="WBS!A1",
            valueInputOption="RAW",
            body={"values": wbs_rows},
        ).execute()

        # WBS 포맷팅 (레벨별 색상)
        self._apply_wbs_formatting(service, spreadsheet_id, wbs_sheet_id, wbs_rows)

        return True

    def _flatten_wbs(self, items: list, rows: list):
        """WBS 트리를 평탄화하여 행 데이터로 변환"""
        for item in items:
            rows.append([
                item.get("code", ""),
                str(item.get("level", "")),
                item.get("name", ""),
                item.get("assignee", ""),
                item.get("priority", ""),
                item.get("status", ""),
                item.get("due_date", ""),
            ])
            children = item.get("children", [])
            if children:
                self._flatten_wbs(children, rows)

    def _apply_wbs_formatting(self, service, spreadsheet_id, sheet_id, rows):
        """WBS 탭 포맷팅 — 헤더 + 레벨별 색상"""
        requests = [
            # 헤더 스타일
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.16, "green": 0.24, "blue": 0.55},
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            },
            # 헤더 고정
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            },
        ]

        # 레벨별 색상: Level 1 = 진한 파란, Level 2 = 연한 파란, Level 3 = 흰색
        level_colors = {
            "1": {"red": 0.22, "green": 0.46, "blue": 0.82},   # 진한 파란
            "2": {"red": 0.68, "green": 0.82, "blue": 0.96},   # 연한 파란
        }
        level_text_colors = {
            "1": {"red": 1, "green": 1, "blue": 1},            # 흰 글자
            "2": {"red": 0, "green": 0, "blue": 0},            # 검정 글자
        }

        for row_idx, row in enumerate(rows[1:], start=1):  # 헤더 제외
            level = row[1] if len(row) > 1 else ""
            if level in level_colors:
                requests.append({
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1},
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": level_colors[level],
                                "textFormat": {
                                    "bold": level == "1",
                                    "foregroundColor": level_text_colors[level],
                                },
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat)",
                    }
                })

        # 열 너비
        wbs_col_widths = [80, 50, 250, 100, 80, 100, 100]
        for i, w in enumerate(wbs_col_widths):
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
