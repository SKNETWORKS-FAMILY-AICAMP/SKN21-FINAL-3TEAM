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
import re

from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_task import PipelineTask
from app.models.google_sheet_tracker import GoogleSheetTracker
from app.services.google_base_service import GoogleBaseService

logger = logging.getLogger(__name__)

# 이모지 제거 정규식 (Unicode Emoji 범위)
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001F9FF"   # Misc Symbols, Emoticons, etc.
    "\U00002702-\U000027B0"    # Dingbats
    "\U0000FE00-\U0000FE0F"    # Variation Selectors
    "\U0000200D"               # ZWJ
    "\U000025A0-\U000025FF"    # Geometric Shapes (■, □ 등은 유지 — Gantt 바)
    "]+",
    flags=re.UNICODE,
)

# Gantt 바용 ■는 유지하고 나머지 이모지만 제거
_EMOJI_STRIP_RE = re.compile(
    "[\U0001F300-\U0001F9FF"
    "\U00002702-\U000027B0"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    """문자열에서 이모지를 제거하고 앞뒤 공백 정리"""
    if not isinstance(text, str):
        return text
    return _EMOJI_STRIP_RE.sub("", text).strip()


def _clean_rows(rows: list[list]) -> list[list]:
    """2D 행 데이터의 모든 셀에서 이모지 제거"""
    return [[_strip_emoji(cell) if isinstance(cell, str) else cell for cell in row] for row in rows]

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
        generate_gantt: bool = False,
        generate_dashboard: bool = False,
        generate_risk: bool = False,
        generate_report: bool = False,
    ) -> dict:
        """프로젝트의 태스크를 Google Sheets로 내보내기 (+ WBS 자동 생성)"""
        # 프로젝트 태스크 조회
        query = select(PipelineTask).where(PipelineTask.project == project_name)
        result = await db.execute(query)
        tasks = result.scalars().all()

        # 확장 탭용: 사용자의 일정 + 결재 조회
        schedules = []
        approvals = []
        if generate_gantt or generate_dashboard or generate_risk or generate_report:
            from app.models.schedule import Schedule
            from app.models.approval_request import ApprovalRequest

            sched_result = await db.execute(
                select(Schedule).where(Schedule.user_id == user_id)
            )
            schedules = sched_result.scalars().all()

            appr_result = await db.execute(
                select(ApprovalRequest).where(ApprovalRequest.requester_id == user_id)
            )
            approvals = appr_result.scalars().all()

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

        # 탭 이름을 'project'로 변경
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": sheet_id,
                                "title": "project"
                            },
                            "fields": "title"
                        }
                    }
                ]
            }
        ).execute()

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

        # 데이터 쓰기 (이모지 제거)
        rows = _clean_rows(rows)
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

        # Gantt 차트 탭
        gantt_generated = False
        if generate_gantt and (tasks or schedules):
            try:
                gantt_generated = await self._generate_gantt_tab(service, spreadsheet_id, tasks, schedules)
            except Exception as e:
                logger.warning(f"Gantt 차트 생성 실패: {e}")

        # Dashboard 탭
        dashboard_generated = False
        if generate_dashboard and (tasks or schedules or approvals):
            try:
                dashboard_generated = await self._generate_dashboard_tab(service, spreadsheet_id, tasks, schedules, approvals)
            except Exception as e:
                logger.warning(f"Dashboard 생성 실패: {e}")

        # Risk Analysis 탭
        risk_generated = False
        if generate_risk and (tasks or schedules or approvals):
            try:
                risk_generated = await self._generate_risk_tab(service, spreadsheet_id, tasks, schedules, approvals)
            except Exception as e:
                logger.warning(f"Risk 분석 생성 실패: {e}")

        # Weekly Report 탭
        report_generated = False
        if generate_report and (tasks or schedules or approvals):
            try:
                report_generated = await self._generate_weekly_report_tab(service, spreadsheet_id, tasks, schedules, approvals)
            except Exception as e:
                logger.warning(f"주간 보고서 생성 실패: {e}")

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
            "gantt_generated": gantt_generated,
            "dashboard_generated": dashboard_generated,
            "risk_generated": risk_generated,
            "report_generated": report_generated,
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
        from googleapiclient.errors import HttpError

        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)

        try:
            # 탭 이름 목록
            meta = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields="sheets.properties.title",
            ).execute()
            tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]
        except HttpError as e:
            logger.error(f"시트 메타데이터 조회 실패 (spreadsheet_id={spreadsheet_id}): {e}")
            from fastapi import HTTPException
            status_code = e.resp.status if hasattr(e, 'resp') else 500
            reason = str(e)
            raise HTTPException(status_code=status_code, detail=f"Google Sheets 접근 실패: {reason}")

        # 요청된 탭이 없으면 첫 번째 탭 사용 (한국어 로케일: "시트1" vs "Sheet1")
        actual_tab = sheet_name
        if tabs and sheet_name not in tabs:
            actual_tab = tabs[0]
            logger.info(f"탭 '{sheet_name}' 없음 → '{actual_tab}'로 대체 (spreadsheet_id={spreadsheet_id})")

        try:
            # 셀 데이터
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=actual_tab,
            ).execute()
            raw_values = result.get("values", [])
            # 모든 셀 값을 문자열로 변환 (Google API가 숫자를 int/float으로 반환할 수 있음)
            values = [[str(cell) if cell is not None else "" for cell in row] for row in raw_values]
        except HttpError as e:
            logger.error(f"시트 데이터 조회 실패 (spreadsheet_id={spreadsheet_id}, tab={actual_tab}): {e}")
            from fastapi import HTTPException
            status_code = e.resp.status if hasattr(e, 'resp') else 500
            raise HTTPException(status_code=status_code, detail=f"시트 데이터 조회 실패: {str(e)}")

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
        wbs_data = json.loads(response.content)
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
        wbs_rows = _clean_rows(wbs_rows)
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

    # ── 확장: Gantt 차트 탭 ──

    async def _generate_gantt_tab(self, service, spreadsheet_id, tasks, schedules=None) -> bool:
        """태스크의 마감일 기반 간트 차트 표현 (Pipeline 태스크만 — 개인일정 제외)"""
        from datetime import datetime as dt, timedelta

        # 간트 항목 수집: (title, assignee, status_label, bar_start, bar_end, color_key)
        gantt_items = []

        # PipelineTask: 마감일 있는 것만
        for t in tasks:
            if not t.due_date:
                continue
            d = t.due_date.date() if isinstance(t.due_date, dt) else t.due_date
            bar_end = d
            bar_start = d - timedelta(days=5)
            gantt_items.append((
                t.title or "", t.assignee or "",
                STAGE_LABEL.get(t.stage, t.stage or ""),
                bar_start, bar_end, t.stage or "todo",
            ))

        # 개인 캘린더 일정은 포함하지 않음 (프로젝트 Gantt는 Pipeline 태스크만)

        if not gantt_items:
            return False

        # 날짜 범위 계산
        all_dates = [item[3] for item in gantt_items] + [item[4] for item in gantt_items]
        min_date = min(all_dates)
        max_date = max(all_dates)
        chart_start = min_date - timedelta(days=3)
        chart_end = max_date + timedelta(days=3)
        total_days = (chart_end - chart_start).days + 1
        if total_days > 60:
            total_days = 60
            chart_end = chart_start + timedelta(days=59)

        # 헤더
        header = ["항목", "담당자", "상태"]
        date_cols = []
        for i in range(total_days):
            d = chart_start + timedelta(days=i)
            date_cols.append(d)
            header.append(d.strftime("%m/%d"))

        rows = [header]
        task_bars = []

        for title, assignee, status_label, bar_start, bar_end, color_key in gantt_items:
            if bar_start < chart_start:
                bar_start = chart_start
            if bar_end > chart_end:
                bar_end = chart_end

            row = [title, assignee, status_label]
            for col_d in date_cols:
                if bar_start <= col_d <= bar_end:
                    row.append("■")
                else:
                    row.append("")
            rows.append(row)

            start_col = 3 + max(0, (bar_start - chart_start).days)
            end_col = 3 + min(total_days - 1, (bar_end - chart_start).days)
            task_bars.append((len(rows) - 1, start_col, end_col, color_key))

        # "Gantt" 탭 생성
        resp = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": "Gantt"}}}]},
        ).execute()
        gantt_sheet_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]

        # 데이터 쓰기 (이모지 제거, ■ Gantt 바는 유지)
        rows = _clean_rows(rows)
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Gantt!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        # 포맷팅
        stage_colors = {
            "done":        {"red": 0.30, "green": 0.75, "blue": 0.40},  # 녹색
            "in_progress": {"red": 0.29, "green": 0.53, "blue": 0.91},  # 파란색
            "review":      {"red": 0.98, "green": 0.74, "blue": 0.18},  # 주황색
            "todo":        {"red": 0.75, "green": 0.75, "blue": 0.75},  # 회색
            "schedule_meeting":  {"red": 0.56, "green": 0.36, "blue": 0.80},  # 보라색
            "schedule_task":     {"red": 0.40, "green": 0.73, "blue": 0.65},  # 청록색
            "schedule_deadline": {"red": 0.90, "green": 0.35, "blue": 0.35},  # 빨간색
            "schedule_review":   {"red": 0.95, "green": 0.65, "blue": 0.30},  # 주황색
            "schedule_milestone":{"red": 0.65, "green": 0.45, "blue": 0.85},  # 연보라색
        }
        requests = [
            # 헤더 스타일
            {
                "repeatCell": {
                    "range": {"sheetId": gantt_sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.20, "green": 0.30, "blue": 0.55},
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}, "fontSize": 9},
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            },
            {"updateSheetProperties": {
                "properties": {"sheetId": gantt_sheet_id, "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 3}},
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }},
        ]

        # 열 너비: 태스크명=200, 담당자=80, 상태=80, 날짜=30
        for i, w in enumerate([200, 80, 80]):
            requests.append({
                "updateDimensionProperties": {
                    "range": {"sheetId": gantt_sheet_id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                    "properties": {"pixelSize": w},
                    "fields": "pixelSize",
                }
            })
        if total_days > 0:
            requests.append({
                "updateDimensionProperties": {
                    "range": {"sheetId": gantt_sheet_id, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 3 + total_days},
                    "properties": {"pixelSize": 32},
                    "fields": "pixelSize",
                }
            })

        # 간트 바 색상
        for row_idx, start_col, end_col, stage in task_bars:
            color = stage_colors.get(stage, stage_colors["todo"])
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": gantt_sheet_id,
                        "startRowIndex": row_idx,
                        "endRowIndex": row_idx + 1,
                        "startColumnIndex": start_col,
                        "endColumnIndex": end_col + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": color,
                            "textFormat": {"foregroundColor": color, "fontSize": 8},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            })

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

        return True

    # ── 확장: 진행 현황 대시보드 탭 ──

    async def _generate_dashboard_tab(self, service, spreadsheet_id, tasks, schedules=None, approvals=None) -> bool:
        """태스크 + 일정 + 결재 통계를 집계하여 대시보드 탭 생성 (LLM 불필요)"""
        from datetime import datetime as dt

        if not tasks and not schedules and not approvals:
            return False

        # ── 태스크 통계 ──
        stage_counts = {}
        assignee_counts = {}
        priority_counts = {}
        overdue_tasks = []

        for t in tasks:
            stage = STAGE_LABEL.get(t.stage, t.stage or "미정")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

            assignee = t.assignee or "미할당"
            assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1

            priority = PRIORITY_LABEL.get(t.priority, t.priority or "미정")
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

            if t.due_date:
                d = t.due_date.date() if isinstance(t.due_date, dt) else t.due_date
                if d < date.today() and t.stage != "done":
                    overdue_tasks.append(t)

        total = len(tasks)
        done_count = stage_counts.get("Done", 0)
        progress_pct = round(done_count / total * 100, 1) if total > 0 else 0

        # ── 일정 통계 ──
        schedule_type_counts = {}
        upcoming_schedules = []
        for s in (schedules or []):
            stype = {"meeting": "회의", "task": "태스크", "deadline": "마감"}.get(s.schedule_type, s.schedule_type or "기타")
            schedule_type_counts[stype] = schedule_type_counts.get(stype, 0) + 1
            if s.start_time:
                from datetime import timedelta as td
                s_date = s.start_time.date() if isinstance(s.start_time, dt) else s.start_time
                if date.today() <= s_date <= date.today() + td(days=7):
                    upcoming_schedules.append(s)

        # ── 결재 통계 ──
        approval_status_counts = {}
        for a in (approvals or []):
            status = {"pending": "대기중", "approved": "승인", "rejected": "반려"}.get(a.status, a.status or "기타")
            approval_status_counts[status] = approval_status_counts.get(status, 0) + 1

        # ── 행 데이터 구성 ──
        rows = [
            ["프로젝트 통합 대시보드", "", "", ""],
            [],
        ]

        if tasks:
            rows.extend([
                ["── 파이프라인 태스크 ──", "", "", ""],
                ["전체 진행률", f"{progress_pct}%", f"({done_count}/{total} 완료)", ""],
                [],
                ["상태", "건수", "비율", "바"],
            ])
            for stage, cnt in sorted(stage_counts.items(), key=lambda x: -x[1]):
                pct = round(cnt / total * 100, 1)
                bar = "█" * int(pct / 5)
                rows.append([stage, str(cnt), f"{pct}%", bar])

            rows.extend([[], ["담당자", "건수", "비율", ""]])
            for assignee, cnt in sorted(assignee_counts.items(), key=lambda x: -x[1]):
                pct = round(cnt / total * 100, 1)
                rows.append([assignee, str(cnt), f"{pct}%", ""])

            rows.extend([[], ["우선순위", "건수", "비율", ""]])
            for pri, cnt in sorted(priority_counts.items(), key=lambda x: -x[1]):
                pct = round(cnt / total * 100, 1)
                rows.append([pri, str(cnt), f"{pct}%", ""])

        if overdue_tasks:
            rows.extend([
                [],
                ["── 마감 초과 태스크 ──", "", "", ""],
                ["태스크명", "담당자", "마감일", "초과일수"],
            ])
            for t in overdue_tasks:
                d = t.due_date.date() if isinstance(t.due_date, dt) else t.due_date
                over = (date.today() - d).days
                rows.append([t.title or "", t.assignee or "", d.strftime("%Y-%m-%d"), f"{over}일"])

        if schedules:
            rows.extend([
                [],
                ["── 일정 현황 ──", "", "", ""],
                ["유형", "건수", "", ""],
            ])
            for stype, cnt in sorted(schedule_type_counts.items(), key=lambda x: -x[1]):
                rows.append([stype, str(cnt), "", ""])

            if upcoming_schedules:
                rows.extend([[], ["향후 7일 일정", "", "", ""]])
                for s in upcoming_schedules[:10]:
                    s_date = s.start_time.strftime("%m/%d %H:%M") if s.start_time else ""
                    rows.append([s.title or "", s_date, s.schedule_type or "", ""])

        if approvals:
            rows.extend([
                [],
                ["── 결재 현황 ──", "", "", ""],
                ["상태", "건수", "", ""],
            ])
            for status, cnt in sorted(approval_status_counts.items(), key=lambda x: -x[1]):
                rows.append([status, str(cnt), "", ""])

        # "Dashboard" 탭 생성
        resp = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": "Dashboard"}}}]},
        ).execute()
        dash_sheet_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]

        rows = _clean_rows(rows)
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Dashboard!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        # 포맷팅
        requests = [
            # 제목 행
            {
                "repeatCell": {
                    "range": {"sheetId": dash_sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "fontSize": 14},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat)",
                }
            },
            # 진행률 행
            {
                "repeatCell": {
                    "range": {"sheetId": dash_sheet_id, "startRowIndex": 2, "endRowIndex": 3},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "fontSize": 12},
                            "backgroundColor": {"red": 0.85, "green": 0.92, "blue": 0.83},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            },
        ]

        # 섹션 헤더 스타일 (── 으로 시작하는 행)
        for idx, row in enumerate(rows):
            if row and isinstance(row[0], str) and row[0].startswith("──"):
                requests.append({
                    "repeatCell": {
                        "range": {"sheetId": dash_sheet_id, "startRowIndex": idx, "endRowIndex": idx + 1},
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True, "fontSize": 10},
                                "backgroundColor": {"red": 0.93, "green": 0.93, "blue": 0.93},
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor)",
                    }
                })

        # 열 너비
        for i, w in enumerate([200, 80, 80, 150]):
            requests.append({
                "updateDimensionProperties": {
                    "range": {"sheetId": dash_sheet_id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                    "properties": {"pixelSize": w},
                    "fields": "pixelSize",
                }
            })

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

        return True

    # ── 확장: AI 리스크 분석 탭 ──

    async def _generate_risk_tab(self, service, spreadsheet_id, tasks, schedules=None, approvals=None) -> bool:
        """LLM으로 프로젝트 리스크 분석 → 'Risk Analysis' 탭 생성"""
        from ai.llm.factory import get_llm
        from ai.llm.prompts import PROJECT_RISK_ANALYSIS_SYSTEM_PROMPT

        task_lines = []
        for t in tasks:
            line = f"- [태스크] {t.title or '(제목 없음)'}"
            if t.assignee:
                line += f" | 담당: {t.assignee}"
            if t.priority:
                line += f" | 우선순위: {PRIORITY_LABEL.get(t.priority, t.priority)}"
            if t.stage:
                line += f" | 상태: {STAGE_LABEL.get(t.stage, t.stage)}"
            if t.due_date:
                line += f" | 마감: {t.due_date.strftime('%Y-%m-%d')}"
            task_lines.append(line)

        for s in (schedules or []):
            line = f"- [일정/{s.schedule_type or '기타'}] {s.title or '(제목 없음)'}"
            if s.start_time:
                line += f" | 시작: {s.start_time.strftime('%Y-%m-%d %H:%M')}"
            if s.end_time:
                line += f" | 종료: {s.end_time.strftime('%Y-%m-%d %H:%M')}"
            if s.priority:
                line += f" | 우선순위: {s.priority}"
            task_lines.append(line)

        for a in (approvals or []):
            line = f"- [결재/{a.type}] {a.title or '(제목 없음)'} | 상태: {a.status}"
            if a.created_at:
                line += f" | 요청일: {a.created_at.strftime('%Y-%m-%d')}"
            task_lines.append(line)

        user_prompt = f"오늘 날짜: {date.today().isoformat()}\n\n프로젝트 데이터 (태스크+일정+결재):\n" + "\n".join(task_lines)

        llm = get_llm()
        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=PROJECT_RISK_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.3,
            json_mode=True,
        )

        data = json.loads(response.content)
        risks = data.get("risks", [])
        summary = data.get("summary", "")

        # 행 데이터
        rows = [
            ["프로젝트 리스크 분석", "", "", "", ""],
            ["요약:", summary, "", "", ""],
            [],
            ["위험도", "카테고리", "설명", "관련 태스크", "권장 조치"],
        ]

        for r in risks:
            affected = ", ".join(r.get("affected_tasks", []))
            rows.append([
                f"{r.get('level', '')}",
                r.get("category", ""),
                r.get("description", ""),
                affected,
                r.get("recommendation", ""),
            ])

        if not risks:
            rows.append(["", "", "식별된 리스크가 없습니다.", "", ""])

        # "Risk Analysis" 탭 생성
        resp = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": "Risk Analysis"}}}]},
        ).execute()
        risk_sheet_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]

        rows = _clean_rows(rows)
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="'Risk Analysis'!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        # 포맷팅
        requests = [
            # 제목
            {
                "repeatCell": {
                    "range": {"sheetId": risk_sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 14}}},
                    "fields": "userEnteredFormat(textFormat)",
                }
            },
            # 테이블 헤더
            {
                "repeatCell": {
                    "range": {"sheetId": risk_sheet_id, "startRowIndex": 3, "endRowIndex": 4},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.85, "green": 0.20, "blue": 0.20},
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            },
        ]

        for i, w in enumerate([100, 100, 300, 200, 300]):
            requests.append({
                "updateDimensionProperties": {
                    "range": {"sheetId": risk_sheet_id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                    "properties": {"pixelSize": w},
                    "fields": "pixelSize",
                }
            })

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

        return True

    # ── 확장: AI 주간 보고서 탭 ──

    async def _generate_weekly_report_tab(self, service, spreadsheet_id, tasks, schedules=None, approvals=None) -> bool:
        """LLM으로 주간 보고서 생성 → 'Weekly Report' 탭 생성"""
        from ai.llm.factory import get_llm
        from ai.llm.prompts import WEEKLY_REPORT_SYSTEM_PROMPT

        task_lines = []
        for t in tasks:
            line = f"- [태스크] {t.title or '(제목 없음)'}"
            if t.assignee:
                line += f" | 담당: {t.assignee}"
            if t.priority:
                line += f" | 우선순위: {PRIORITY_LABEL.get(t.priority, t.priority)}"
            if t.stage:
                line += f" | 상태: {STAGE_LABEL.get(t.stage, t.stage)}"
            if t.due_date:
                line += f" | 마감: {t.due_date.strftime('%Y-%m-%d')}"
            task_lines.append(line)

        for s in (schedules or []):
            line = f"- [일정/{s.schedule_type or '기타'}] {s.title or '(제목 없음)'}"
            if s.start_time:
                line += f" | 시작: {s.start_time.strftime('%Y-%m-%d %H:%M')}"
            task_lines.append(line)

        for a in (approvals or []):
            line = f"- [결재/{a.type}] {a.title or '(제목 없음)'} | 상태: {a.status}"
            if a.created_at:
                line += f" | 요청일: {a.created_at.strftime('%Y-%m-%d')}"
            task_lines.append(line)

        user_prompt = f"오늘 날짜: {date.today().isoformat()}\n\n프로젝트 데이터 (태스크+일정+결재):\n" + "\n".join(task_lines)

        llm = get_llm()
        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=WEEKLY_REPORT_SYSTEM_PROMPT,
            temperature=0.3,
            json_mode=True,
        )

        data = json.loads(response.content)
        period = data.get("period", "")
        completed = data.get("completed", [])
        in_progress = data.get("in_progress", [])
        planned = data.get("planned", [])
        meetings = data.get("meetings", [])
        approval_items = data.get("approvals", [])
        blockers = data.get("blockers", [])
        summary = data.get("summary", "")

        rows = [
            ["주간 보고서", "", ""],
            ["기간:", period, ""],
            ["요약:", summary, ""],
            [],
            ["── 완료 ──", "", ""],
            ["태스크", "담당자", ""],
        ]
        for item in completed:
            rows.append([item.get("task", ""), item.get("assignee", ""), ""])
        if not completed:
            rows.append(["(없음)", "", ""])

        rows.extend([
            [],
            ["── 진행 중 ──", "", ""],
            ["태스크", "담당자", "진행 상황"],
        ])
        for item in in_progress:
            rows.append([item.get("task", ""), item.get("assignee", ""), item.get("progress", "")])
        if not in_progress:
            rows.append(["(없음)", "", ""])

        rows.extend([
            [],
            ["── 다음 주 예정 ──", "", ""],
            ["태스크", "담당자", "마감일"],
        ])
        for item in planned:
            rows.append([item.get("task", ""), item.get("assignee", ""), item.get("due", "")])
        if not planned:
            rows.append(["(없음)", "", ""])

        if meetings:
            rows.extend([
                [],
                ["── 회의 일정 ──", "", ""],
                ["회의명", "날짜", "비고"],
            ])
            for m in meetings:
                rows.append([m.get("title", ""), m.get("date", ""), m.get("note", "")])

        if approval_items:
            rows.extend([
                [],
                ["── 결재 현황 ──", "", ""],
                ["결재명", "유형", "상태"],
            ])
            for a in approval_items:
                rows.append([a.get("title", ""), a.get("type", ""), a.get("status", "")])

        if blockers:
            rows.extend([
                [],
                ["── 블로커/이슈 ──", "", ""],
            ])
            for b in blockers:
                rows.append([b, "", ""])

        # "Weekly Report" 탭 생성
        resp = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": "Weekly Report"}}}]},
        ).execute()
        report_sheet_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]

        rows = _clean_rows(rows)
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="'Weekly Report'!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        # 포맷팅
        requests = [
            {
                "repeatCell": {
                    "range": {"sheetId": report_sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 14}}},
                    "fields": "userEnteredFormat(textFormat)",
                }
            },
        ]

        # 섹션 헤더 색상
        section_colors = {
            "완료": {"red": 0.85, "green": 0.93, "blue": 0.83},  # 녹색
            "진행 중": {"red": 0.80, "green": 0.88, "blue": 0.97},  # 파란색
            "예정": {"red": 0.98, "green": 0.93, "blue": 0.80},  # 노란색
            "회의": {"red": 0.90, "green": 0.90, "blue": 0.97},  # 연보라
            "결재": {"red": 0.90, "green": 0.93, "blue": 0.93},  # 연청록
            "블로커": {"red": 0.97, "green": 0.83, "blue": 0.83},  # 빨간색
        }
        for idx, row in enumerate(rows):
            if row and isinstance(row[0], str) and row[0].startswith("──"):
                color = {"red": 0.93, "green": 0.93, "blue": 0.93}
                for keyword, c in section_colors.items():
                    if keyword in row[0]:
                        color = c
                        break
                requests.append({
                    "repeatCell": {
                        "range": {"sheetId": report_sheet_id, "startRowIndex": idx, "endRowIndex": idx + 1},
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True, "fontSize": 10},
                                "backgroundColor": color,
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor)",
                    }
                })

        for i, w in enumerate([250, 100, 200]):
            requests.append({
                "updateDimensionProperties": {
                    "range": {"sheetId": report_sheet_id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                    "properties": {"pixelSize": w},
                    "fields": "pixelSize",
                }
            })

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

        return True

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
