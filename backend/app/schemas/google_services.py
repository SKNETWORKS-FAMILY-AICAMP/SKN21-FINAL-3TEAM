"""
Google 서비스 통합 스키마
- Google Tasks, Gmail, Sheets, Meet 요청/응답 스키마
"""
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


# ── Google OAuth ──

class GoogleConnectRequest(BaseModel):
    """OAuth 연결 요청 (scope 선택)"""
    scopes: list[str]  # ["calendar", "tasks", "gmail_send", "sheets"]


class GoogleConnectResponse(BaseModel):
    """OAuth 연결 URL 응답"""
    auth_url: str


class GoogleStatusResponse(BaseModel):
    """Google 연결 상태"""
    connected: bool
    provider: Optional[str] = None
    email: Optional[str] = None
    scopes: list[str] = []
    expires_at: Optional[datetime] = None


class GoogleDisconnectResponse(BaseModel):
    """연결 해제 응답"""
    disconnected: bool


# ── Google Tasks ──

class TaskCreateRequest(BaseModel):
    """Task 생성 요청"""
    title: str
    assignee: Optional[str] = None
    due_date: Optional[date] = None
    priority: str = "medium"  # high/medium/low


class TaskSyncRequest(BaseModel):
    """단일 Task 동기화 요청"""
    action_item_id: int


class TaskSyncAllRequest(BaseModel):
    """전체 동기화 요청"""
    meeting_id: Optional[int] = None


class TaskStatusUpdateRequest(BaseModel):
    """Task 상태 변경"""
    completed: bool


class TaskSyncResponse(BaseModel):
    """동기화 결과"""
    task_id: Optional[str] = None
    status: Optional[str] = None
    synced_count: Optional[int] = None


class TaskListItem(BaseModel):
    """Google Task 항목"""
    id: str
    title: str
    status: str
    due: Optional[str] = None
    notes: Optional[str] = None


# ── Gmail ──

class SendReminderRequest(BaseModel):
    """기한 알림 메일 요청"""
    action_item_id: int
    recipient_email: str


class SendMeetingInviteRequest(BaseModel):
    """회의 초대 메일 요청"""
    recipient_emails: list[str]
    meeting_title: str
    meeting_time: datetime
    meet_link: Optional[str] = None


class SendBulkRemindersRequest(BaseModel):
    """일괄 알림 요청"""
    days_before: int = 3
    recipient_map: dict[str, str] = {}  # {"담당자명": "email@example.com"}


class EmailSendResultItem(BaseModel):
    """개별 메일 발송 결과"""
    recipient: str
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class EmailSendResponse(BaseModel):
    """메일 발송 결과"""
    sent_count: int
    results: list[EmailSendResultItem] = []


# ── Google Sheets ──

class SheetExportProjectRequest(BaseModel):
    """프로젝트 Sheets 내보내기 요청"""
    project_name: str
    title: Optional[str] = None
    generate_wbs: bool = True
    generate_gantt: bool = False
    generate_dashboard: bool = False
    generate_risk: bool = False
    generate_report: bool = False


class SheetSyncRequest(BaseModel):
    """스프레드시트 동기화 요청"""
    project_name: str


class SheetCreateResponse(BaseModel):
    """스프레드시트 생성 결과"""
    spreadsheet_id: str
    spreadsheet_url: str
    title: str
    task_count: int = 0
    wbs_generated: bool = False
    gantt_generated: bool = False
    dashboard_generated: bool = False
    risk_generated: bool = False
    report_generated: bool = False


class SheetSyncResponse(BaseModel):
    """동기화 결과"""
    synced_count: int
    spreadsheet_id: str


class SheetReadResponse(BaseModel):
    """시트 데이터 읽기 결과"""
    values: list[list]  # 셀 값은 str/int/float 혼재 가능
    tabs: list[str]


class CellUpdate(BaseModel):
    """개별 셀 업데이트"""
    cell: str      # "B3"
    value: str


class SheetUpdateRequest(BaseModel):
    """시트 데이터 업데이트 요청"""
    sheet_name: str = "Sheet1"
    updates: list[CellUpdate]


class SheetUpdateResponse(BaseModel):
    """시트 업데이트 결과"""
    updated_count: int


class SheetListItem(BaseModel):
    """스프레드시트 목록 항목"""
    id: int
    spreadsheet_id: str
    spreadsheet_url: str
    sheet_name: str
    project_name: Optional[str] = None
    created_at: datetime


# ── Calendar + Meet ──

class EventWithMeetRequest(BaseModel):
    """이벤트 + Meet 링크 생성 요청"""
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    attendee_emails: list[str] = []


class EventWithMeetResponse(BaseModel):
    """이벤트 + Meet 링크 응답"""
    event_id: str
    html_link: Optional[str] = None
    meet_link: Optional[str] = None


# ── Google 서비스 통합 결과 ──

class GoogleServicesResult(BaseModel):
    """전체 Google 서비스 연동 결과 (schedule_add 응답에 포함)"""
    calendar_synced: bool = False
    meet_link: Optional[str] = None
    task_created: bool = False
    email_sent: bool = False
    sheet_updated: bool = False
    sheet_url: Optional[str] = None
