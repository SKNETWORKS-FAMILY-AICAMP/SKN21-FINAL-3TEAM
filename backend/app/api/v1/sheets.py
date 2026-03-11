"""
Google Sheets API 엔드포인트 (팀원 D 담당)
- Pipeline 프로젝트 문서화 스프레드시트 생성/동기화
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.google_services import (
    SheetExportProjectRequest,
    SheetCreateResponse,
    SheetSyncRequest,
    SheetSyncResponse,
)
from app.services.sheets_service import GoogleSheetsService

router = APIRouter()
sheets_service = GoogleSheetsService()


@router.post("/export-project", response_model=SheetCreateResponse)
async def export_project(
    request: SheetExportProjectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로젝트 태스크를 Google Sheets로 내보내기"""
    result = await sheets_service.export_project_to_sheet(
        db, current_user.id, request.project_name, request.title
    )
    return SheetCreateResponse(**result)


@router.post("/{spreadsheet_id}/sync", response_model=SheetSyncResponse)
async def sync_sheet(
    spreadsheet_id: str,
    request: SheetSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로젝트 태스크를 기존 시트에 재동기화"""
    result = await sheets_service.sync_project_to_sheet(
        db, current_user.id, spreadsheet_id, request.project_name
    )
    return SheetSyncResponse(**result)


@router.get("/")
async def list_sheets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자의 프로젝트 스프레드시트 목록"""
    return await sheets_service.list_sheets(db, current_user.id)


@router.delete("/{spreadsheet_id}")
async def delete_sheet(
    spreadsheet_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """시트 삭제 (DB 레코드만 삭제)"""
    deleted = await sheets_service.delete_sheet(db, current_user.id, spreadsheet_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="시트를 찾을 수 없습니다")
    return {"message": "삭제되었습니다"}
