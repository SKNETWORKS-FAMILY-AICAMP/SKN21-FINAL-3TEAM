"""
회의 관리 API (팀원 C/D 공동 담당)
"""
from fastapi import APIRouter, Depends, Query, Body
from typing import Optional

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


# ── 회의록 생성 (meeting_generate) ──


@router.post("/generate")
async def generate_meeting_minutes(
    title: Optional[str] = Body(None),
    meeting_date: Optional[str] = Body(None),
    attendees: Optional[str] = Body(None, description="참석자 (콤마 구분)"),
    raw_content: str = Body(..., description="회의 내용 텍스트"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    회의록 요약 및 생성

    플로우:
    1. 사용자가 회의 내용 텍스트 입력 + (선택) 제목/날짜/참석자
    2. 문서 Agent (meeting_generate)로 전달
    3. sLLM으로 요약 (결정사항, Action Item 추출)
    4. MeetingMinutesTemplate 양식에 데이터 채움
    5. 규정 리스크 자동 스캔 (RAG)
    6. meetings 테이블 + documents 테이블 + action_items 테이블 저장

    응답: 요약 + 결정사항 + Action Items + 미리보기(MD) + 다운로드 URL + 리스크
    """
    # TODO: 팀원 D (API) + 팀원 C (생성 로직)
    raise NotImplementedError


@router.get("/{meeting_id}/download")
async def download_meeting_document(
    meeting_id: int,
    format: str = Query("docx", regex="^(docx|pdf)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    생성된 회의록 문서 다운로드 (DOCX/PDF)

    MeetingPreview에서 "다운로드" 버튼 클릭 시 호출
    """
    # TODO: 팀원 D 구현
    raise NotImplementedError
