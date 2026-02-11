"""
Google Sheets API 엔드포인트 (팀원 D 담당)
- Action Item 추적 스프레드시트 생성/동기화
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.google_services import (
    SheetCreateRequest,
    SheetCreateResponse,
    SheetSyncRequest,
    SheetSyncResponse,
)
from app.services.sheets_service import GoogleSheetsService

router = APIRouter()
sheets_service = GoogleSheetsService()


@router.post("/create", response_model=SheetCreateResponse)
async def create_sheet(
    request: SheetCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """추적 스프레드시트 생성"""
    result = await sheets_service.create_tracking_sheet(
        db, current_user.id, request.title, request.meeting_id
    )
    return SheetCreateResponse(**result)


@router.post("/{spreadsheet_id}/sync", response_model=SheetSyncResponse)
async def sync_sheet(
    spreadsheet_id: str,
    request: SheetSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """스프레드시트에 Action Item 동기화"""
    result = await sheets_service.sync_action_items(
        db, current_user.id, spreadsheet_id, request.meeting_id
    )
    return SheetSyncResponse(**result)


@router.get("/")
async def list_sheets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자의 추적 스프레드시트 목록"""
    return await sheets_service.list_sheets(db, current_user.id)


@router.get("/{meeting_id}/url")
async def get_sheet_url(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회의별 스프레드시트 URL"""
    url = await sheets_service.get_sheet_url_by_meeting(db, current_user.id, meeting_id)
    return {"spreadsheet_url": url}
