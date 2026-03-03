"""
일정 관리 API (팀원 D 담당)
- 일정 CRUD (DB 기반 + Google Calendar 선택적 연동)
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate, ScheduleResponse
from app.services import schedule_service

router = APIRouter()


@router.get("/")
async def list_schedules(
    include_team: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """일정 목록 조회 (include_team=true 시 팀원 공유 일정 포함)"""
    schedules = await schedule_service.list_schedules(
        db, user_id=user.id, include_team=include_team, user_team=user.team,
    )

    # 팀 일정 포함 시 user_name 조회
    user_names = {}
    if include_team:
        user_ids = {s.user_id for s in schedules}
        if user_ids:
            result = await db.execute(
                select(User.id, User.name).where(User.id.in_(user_ids))
            )
            user_names = dict(result.all())

    return [
        ScheduleResponse(
            id=s.id,
            title=s.title,
            description=s.description,
            start_time=s.start_time,
            end_time=s.end_time,
            schedule_type=s.schedule_type,
            priority=s.priority,
            google_event_id=s.google_event_id,
            google_meet_link=s.google_meet_link,
            is_team_visible=s.is_team_visible,
            team_name=s.team_name,
            user_id=s.user_id,
            user_name=user_names.get(s.user_id) if include_team else None,
            created_at=s.created_at,
        )
        for s in schedules
    ]


@router.post("/")
async def create_schedule(
    data: ScheduleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """일정 생성 (DB + Google Calendar 선택적 연동)"""
    result = await schedule_service.create_schedule(
        db, user_id=user.id, data=data, user_team=user.team,
    )
    s = result["schedule"]
    return {
        "schedule": ScheduleResponse(
            id=s.id,
            title=s.title,
            description=s.description,
            start_time=s.start_time,
            end_time=s.end_time,
            schedule_type=s.schedule_type,
            priority=s.priority,
            google_event_id=s.google_event_id,
            google_meet_link=s.google_meet_link,
            is_team_visible=s.is_team_visible,
            team_name=s.team_name,
            user_id=s.user_id,
            user_name=user.name,
            created_at=s.created_at,
        ),
        "google_services": result["google_services"],
    }


@router.put("/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """일정 수정 (본인만)"""
    s = await schedule_service.update_schedule(db, schedule_id, user_id=user.id, data=data)
    return ScheduleResponse(
        id=s.id,
        title=s.title,
        description=s.description,
        start_time=s.start_time,
        end_time=s.end_time,
        schedule_type=s.schedule_type,
        priority=s.priority,
        google_event_id=s.google_event_id,
        google_meet_link=s.google_meet_link,
        created_at=s.created_at,
    )


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """일정 삭제 (본인 + 관리자, Google Calendar 이벤트도 삭제)"""
    return await schedule_service.delete_schedule(
        db, schedule_id, user_id=user.id, is_admin=user.is_admin,
    )
