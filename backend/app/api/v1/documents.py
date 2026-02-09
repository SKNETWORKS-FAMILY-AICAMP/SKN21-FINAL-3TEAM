"""
문서 관리 API (팀원 C/D 공동 담당)
- 문서 CRUD, 업로드, 검색
- 회사/개인 문서 구분 (scope)
"""
from fastapi import APIRouter, Depends, UploadFile, File, Query
from typing import Optional

from app.api.deps import get_current_user
from app.db.session import get_db

router = APIRouter()


@router.get("/")
async def list_documents(
    scope: Optional[str] = Query(None, regex="^(company|personal)$"),
    keyword: Optional[str] = None,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 목록 조회 (scope 필터 지원)"""
    # TODO: 팀원 D - DB 조회, 팀원 C - 검색 로직
    raise NotImplementedError


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    scope: str = Query("company", regex="^(company|personal)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 업로드 (Docling/PaddleOCR 파싱 → 벡터 DB 저장)"""
    # TODO: 팀원 C - 파싱 파이프라인, 팀원 D - DB 저장
    raise NotImplementedError


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 상세 조회"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 삭제"""
    # TODO: 팀원 D 구현
    raise NotImplementedError
