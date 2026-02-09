"""
회의 관리 API (팀원 C/D 공동 담당)
"""
from fastapi import APIRouter, Depends, UploadFile, File

from app.api.deps import get_current_user
from app.db.session import get_db

router = APIRouter()


@router.get("/")
async def list_meetings(user=Depends(get_current_user), db=Depends(get_db)):
    """회의 목록 조회"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.post("/")
async def create_meeting(user=Depends(get_current_user), db=Depends(get_db)):
    """회의 생성"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.get("/{meeting_id}")
async def get_meeting(
    meeting_id: int,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """회의 상세 조회 (AI 분석 결과 포함)"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.post("/{meeting_id}/analyze")
async def analyze_meeting(
    meeting_id: int,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """회의록 AI 분석 (결정사항, Action Item 추출)"""
    # TODO: 팀원 C - 문서 Agent 연동
    raise NotImplementedError
