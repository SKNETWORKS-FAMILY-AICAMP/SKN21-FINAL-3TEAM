"""
Google Sheets API 엔드포인트 (팀원 D 담당)
- Action Item 추적 스프레드시트 생성/동기화
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.session import get_db

router = APIRouter()


@router.post("/create")
async def create_sheet(user=Depends(get_current_user), db=Depends(get_db)):
    """추적 스프레드시트 생성"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.post("/{spreadsheet_id}/sync")
async def sync_sheet(spreadsheet_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    """스프레드시트에 Action Item 동기화"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.get("/")
async def list_sheets(user=Depends(get_current_user), db=Depends(get_db)):
    """사용자의 추적 스프레드시트 목록"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.get("/{meeting_id}/url")
async def get_sheet_url(meeting_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    """회의별 스프레드시트 URL"""
    # TODO: 팀원 D 구현
    raise NotImplementedError
