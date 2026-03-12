"""
일정 서비스 (팀원 D 담당)
- 일정 CRUD + 우선순위 자동 설정
- 4개 Google 서비스 오케스트레이션 통합
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import Schedule
from app.models.action_item import ActionItem
from app.models.oauth_token import OAuthToken
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from app.services.calendar_service import GoogleCalendarService
from app.services.tasks_service import GoogleTasksService
from app.services.gmail_service import GmailService
from app.services.sheets_service import GoogleSheetsService

logger = logging.getLogger(__name__)


def calculate_priority(due_date: Optional[datetime]) -> str:
    """마감일 기반 우선순위 자동 설정 (D-day 계산)"""
    if due_date is None:
        return "low"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    delta = (due_date - now).days
    if delta <= 1:
        return "high"
    elif delta <= 3:
        return "medium"
    return "low"


async def list_schedules(
    db: AsyncSession,
    user_id: int,
    include_team: bool = False,
    user_team: str | None = None,
    schedule_type: str | None = None,
) -> list[Schedule]:
    """일정 목록 조회 (include_team=True 시 같은 팀의 공유 일정 포함, schedule_type 필터 선택)"""
    from sqlalchemy import or_, and_

    if include_team and user_team:
        base_condition = or_(
            Schedule.user_id == user_id,
            and_(Schedule.team_name == user_team, Schedule.is_team_visible == True),
        )
    else:
        base_condition = Schedule.user_id == user_id

    query = select(Schedule).where(base_condition)

    if schedule_type:
        query = query.where(Schedule.schedule_type == schedule_type)

    result = await db.execute(query.order_by(Schedule.start_time.desc()))
    return list(result.scalars().all())


async def get_schedule(
    db: AsyncSession, schedule_id: int, user_id: int, is_admin: bool = False,
) -> Schedule:
    """단일 조회 + 본인 소유 확인 (관리자는 소유권 체크 스킵)"""
    result = await db.execute(
        select(Schedule).where(Schedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다")
    if not is_admin and schedule.user_id != user_id:
        raise HTTPException(status_code=403, detail="본인의 일정만 조회할 수 있습니다")
    return schedule


def _strip_tz(dt: Optional[datetime]) -> Optional[datetime]:
    """timezone-aware datetime → naive datetime 변환 (TIMESTAMP WITHOUT TIME ZONE 호환)"""
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


async def create_schedule(
    db: AsyncSession,
    user_id: int,
    data: ScheduleCreate,
    user_team: str | None = None,
) -> dict:
    """
    일정 생성 — DB 저장 + Google Calendar 연동 (선택적, best-effort)
    """
    # 1. DB 저장 (timezone-aware → naive 변환: TIMESTAMP WITHOUT TIME ZONE 호환)
    start_naive = _strip_tz(data.start_time)
    end_naive = _strip_tz(data.end_time)

    schedule = Schedule(
        title=data.title,
        description=data.description,
        start_time=start_naive,
        end_time=end_naive,
        schedule_type=data.schedule_type,
        priority=data.priority or calculate_priority(end_naive),
        user_id=user_id,
        team_name=user_team,
        is_team_visible=data.is_team_visible,
    )
    db.add(schedule)
    await db.flush()

    # 2. Google Calendar 연동 (best-effort)
    google_result = {"calendar_synced": False, "meet_link": None, "email_sent": False}

    token = await _get_oauth_token(db, user_id)
    if token and _has_scope(token, "calendar"):
        try:
            calendar_service = GoogleCalendarService()
            event_data = {
                "title": data.title,
                "description": data.description or "",
                "start_time": data.start_time.isoformat(),
                "end_time": (data.end_time or data.start_time).isoformat(),
            }

            if data.include_meet:
                result = await calendar_service.create_event_with_meet(
                    db, user_id, event_data, data.attendee_emails or None,
                )
                schedule.google_event_id = result["event_id"]
                schedule.google_meet_link = result.get("meet_link")
                google_result["meet_link"] = result.get("meet_link")
            else:
                result = await calendar_service.push_event(db, user_id, event_data)
                schedule.google_event_id = result["event_id"]

            google_result["calendar_synced"] = True
        except Exception as e:
            logger.warning(f"Google Calendar 연동 실패 (best-effort): {e}")

    # 3. Gmail 초대 메일 (best-effort)
    if data.attendee_emails and token and _has_scope(token, "gmail_send"):
        try:
            gmail_service = GmailService()
            await gmail_service.send_meeting_invite(
                db,
                user_id,
                recipient_emails=data.attendee_emails,
                meeting_title=data.title,
                meeting_time=data.start_time.strftime("%Y-%m-%d %H:%M"),
                meet_link=schedule.google_meet_link,
            )
            google_result["email_sent"] = True
        except Exception as e:
            logger.warning(f"Gmail 초대 발송 실패 (best-effort): {e}")

    # 4. Slack 알림 (best-effort, slack_enabled인 경우)
    try:
        from app.models.user import User
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if user and user.slack_enabled:
            from app.services.slack_service import send_slack_webhook
            import os
            webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
            if webhook_url:
                time_str = data.start_time.strftime("%m/%d %H:%M")
                msg = f":calendar: *[일정 등록]* {data.title}\n  - 시간: {time_str}\n  - 등록자: {user.name}"
                if schedule.google_meet_link:
                    msg += f"\n  - Meet: {schedule.google_meet_link}"
                await send_slack_webhook(webhook_url, msg)
    except Exception as e:
        logger.warning(f"Slack 알림 실패 (best-effort): {e}")

    return {"schedule": schedule, "google_services": google_result}


async def update_schedule(
    db: AsyncSession,
    schedule_id: int,
    user_id: int,
    data: ScheduleUpdate,
) -> Schedule:
    """전달된 필드만 업데이트 + 우선순위 재계산"""
    schedule = await get_schedule(db, schedule_id, user_id)

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(schedule, field, value)

    # end_time이 변경되었고 priority를 직접 지정하지 않은 경우 재계산
    if "end_time" in update_fields and "priority" not in update_fields:
        schedule.priority = calculate_priority(schedule.end_time)

    return schedule


async def delete_schedule(
    db: AsyncSession, schedule_id: int, user_id: int, is_admin: bool = False,
) -> dict:
    """DB 삭제 + Google Calendar 이벤트 삭제 (best-effort, 관리자는 타인 일정도 삭제 가능)"""
    schedule = await get_schedule(db, schedule_id, user_id, is_admin=is_admin)

    # Google Calendar 이벤트 삭제 (best-effort)
    if schedule.google_event_id:
        token = await _get_oauth_token(db, user_id)
        if token and _has_scope(token, "calendar"):
            try:
                calendar_service = GoogleCalendarService()
                creds = await calendar_service.get_credentials(db, user_id)
                from googleapiclient.discovery import build
                service = build("calendar", "v3", credentials=creds)
                service.events().delete(
                    calendarId="primary", eventId=schedule.google_event_id
                ).execute()
            except Exception as e:
                logger.warning(f"Google Calendar 이벤트 삭제 실패 (best-effort): {e}")

    await db.delete(schedule)
    return {"message": "일정이 삭제되었습니다", "schedule_id": schedule_id}


async def create_from_action_item(
    db: AsyncSession, action_item_id: int, user_id: int,
) -> dict:
    """Action Item → 일정 자동 등록"""
    result = await db.execute(
        select(ActionItem).where(ActionItem.id == action_item_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Action Item을 찾을 수 없습니다")

    data = ScheduleCreate(
        title=f"[Action Item] {item.content[:100]}",
        description=f"담당: {item.assignee or '미지정'}\n우선순위: {item.priority}",
        start_time=item.due_date or datetime.now(timezone.utc).replace(tzinfo=None),
        end_time=item.due_date,
        schedule_type="task",
        priority=item.priority,
    )
    return await create_schedule(db, user_id, data)


async def create_with_google_services(
    db: AsyncSession,
    user_id: int,
    schedule_data: dict,
    include_meet: bool = False,
    attendee_emails: list[str] | None = None,
    action_item_id: Optional[int] = None,
    meeting_id: Optional[int] = None,
) -> dict:
    """
    일정 생성 + 4개 Google 서비스 자동 연동 오케스트레이션

    Returns:
        {
            "schedule": Schedule,
            "google_services": {
                "calendar_synced": bool,
                "meet_link": str | None,
                "task_created": bool,
                "email_sent": bool,
                "sheet_updated": bool,
                "sheet_url": str | None,
            }
        }
    """
    data = ScheduleCreate(
        title=schedule_data["title"],
        description=schedule_data.get("description"),
        start_time=schedule_data["start_time"],
        end_time=schedule_data.get("end_time"),
        schedule_type=schedule_data.get("schedule_type", "google"),
        priority=schedule_data.get("priority", "medium"),
        include_meet=include_meet,
        attendee_emails=attendee_emails or [],
    )

    result = await create_schedule(db, user_id, data)
    google_services = result["google_services"]
    google_services["task_created"] = False
    google_services["sheet_updated"] = False
    google_services["sheet_url"] = None

    token = await _get_oauth_token(db, user_id)
    if not token:
        return result

    # Google Tasks 연동
    if action_item_id and _has_scope(token, "tasks"):
        try:
            tasks_service = GoogleTasksService()
            await tasks_service.sync_action_item(db, user_id, action_item_id)
            google_services["task_created"] = True
        except Exception as e:
            logger.warning(f"Google Tasks 연동 실패 (best-effort): {e}")

    # Google Sheets 연동
    if meeting_id and _has_scope(token, "sheets"):
        try:
            sheets_service = GoogleSheetsService()
            sheet_url = await sheets_service.get_sheet_url_by_meeting(db, user_id, meeting_id)
            if sheet_url:
                from app.models.google_sheet_tracker import GoogleSheetTracker
                tracker_result = await db.execute(
                    select(GoogleSheetTracker).where(
                        GoogleSheetTracker.user_id == user_id,
                        GoogleSheetTracker.meeting_id == meeting_id,
                    )
                )
                tracker = tracker_result.scalar_one_or_none()
                if tracker:
                    await sheets_service.sync_action_items(
                        db, user_id, tracker.spreadsheet_id, meeting_id
                    )
                    google_services["sheet_updated"] = True
                    google_services["sheet_url"] = sheet_url
        except Exception as e:
            logger.warning(f"Google Sheets 연동 실패 (best-effort): {e}")

    return result


# ── 내부 헬퍼 ──

async def _get_oauth_token(db: AsyncSession, user_id: int) -> OAuthToken | None:
    """사용자의 OAuth 토큰 조회"""
    result = await db.execute(
        select(OAuthToken).where(OAuthToken.user_id == user_id)
    )
    return result.scalar_one_or_none()


def _has_scope(token: OAuthToken, scope: str) -> bool:
    """특정 scope 보유 여부"""
    if not token or not token.scopes:
        return False
    return scope in token.scopes.split(",")
