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


# ── UI_UX.pdf 추가 엔드포인트 ──


@router.post("/generate")
async def generate_document(
    template_type: str = Query(..., regex="^(meeting_minutes|report|jd|proposal)$"),
    user_input: str = Query(..., description="사용자 입력 (회의 요약 등)"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    템플릿 기반 문서 생성 (FR-DOC-008)

    챗봇에서 "회의록 만들어줘" → 요약 입력 → 템플릿 생성 → 미리보기 반환
    """
    # TODO: 팀원 D (API) + 팀원 C (생성 로직)
    # 1. template_service.generate_document() 호출
    # 2. 미리보기(마크다운) + document_id 반환
    raise NotImplementedError


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    format: str = Query("docx", regex="^(docx|pdf)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    생성된 문서 다운로드 - DOCX/PDF (FR-DOC-008)

    GenerateCard에서 "다운로드" 버튼 클릭 시 호출
    """
    # TODO: 팀원 D 구현
    # 1. template_service.download_document() 호출
    # 2. StreamingResponse로 파일 반환
    raise NotImplementedError


@router.get("/{document_id}/parsing-status")
async def get_parsing_status(
    document_id: int,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    문서 파싱 상태 조회 (NF-PRF-002)

    프론트에서 폴링: "파싱 중..." → "파싱 완료 ✓"
    """
    # TODO: 팀원 D 구현
    # parsing_service.get_parsing_status() 호출
    raise NotImplementedError


@router.get("/search/highlight")
async def search_with_highlight(
    keyword: str = Query(...),
    scope: Optional[str] = Query(None, regex="^(company|personal)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    키워드 검색 + 하이라이트 (FR-DOC-006)

    검색 결과에 매칭 키워드 위치 정보 포함
    """
    # TODO: 팀원 D (API) + 팀원 B (RAG 검색)
    # 1. RAG 검색 수행
    # 2. 검색 결과에 keyword 위치(offset) 정보 추가
    # 3. 관련도 순 정렬
    raise NotImplementedError
