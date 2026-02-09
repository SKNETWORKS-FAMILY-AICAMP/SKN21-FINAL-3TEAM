"""
문서 관리 API (팀원 C/D 공동 담당)
- 문서 CRUD, 업로드, 검색
- 템플릿 관리 (업로드/목록/상세/삭제)
- 문서 생성 (템플릿 ID 기반)
- 회사/개인 문서 구분 (scope)
"""
from fastapi import APIRouter, Depends, UploadFile, File, Query, Body
from typing import Optional

from app.api.deps import get_current_user
from app.db.session import get_db

router = APIRouter()


# ── 문서 CRUD ──


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


# ── 문서 생성 ──


@router.post("/generate")
async def generate_document(
    template_id: Optional[int] = Body(None),
    template_type: Optional[str] = Body(None),
    user_input: str = Body(..., description="사용자 입력 (내용/지시사항)"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    템플릿 기반 문서 생성 (FR-DOC-008)

    - template_id: DB 저장된 템플릿 ID (커스텀/시스템)
    - template_type: 시스템 템플릿 직접 지정 (template_id 없을 때)
    - user_input: 사용자가 입력한 내용/지시사항

    챗봇 또는 문서 생성 전용 페이지에서 호출
    """
    # TODO: 팀원 D (API) + 팀원 C (생성 로직)
    # 1. template_id OR template_type으로 템플릿 로드
    # 2. template_service.generate_document() 호출
    # 3. 미리보기(마크다운) + document_id 반환
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

    GenerateCard / DocumentPreview에서 "다운로드" 버튼 클릭 시 호출
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

    프론트에서 폴링: "파싱 중..." → "파싱 완료"
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
    raise NotImplementedError


# ── 템플릿 관리 ──


@router.post("/templates/upload")
async def upload_template(
    file: UploadFile = File(...),
    name: str = Query(..., description="템플릿 이름"),
    description: Optional[str] = Query(None),
    category: str = Query("custom"),
    scope: str = Query("company", regex="^(company|personal)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    커스텀 템플릿 업로드

    1. 파일 저장 (docx/pdf)
    2. AI가 양식 구조(parsed_structure) 추출
    3. document_templates 테이블에 저장
    """
    # TODO: 팀원 D (API) + 팀원 C (구조 추출)
    # 1. 파일 저장
    # 2. template_service.upload_template() 호출
    # 3. 구조 추출 (비동기) → status: processing → ready
    raise NotImplementedError


@router.get("/templates/")
async def list_templates(
    category: Optional[str] = Query(None),
    scope: Optional[str] = Query(None, regex="^(company|personal)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    템플릿 목록 조회

    시스템 기본 템플릿(4종) + 사용자 커스텀 템플릿
    """
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.get("/templates/{template_id}")
async def get_template(
    template_id: int,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """템플릿 상세 조회 (parsed_structure 포함)"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    템플릿 삭제 (커스텀 템플릿만 삭제 가능)

    시스템 기본 템플릿(is_system=True)은 삭제 불가
    """
    # TODO: 팀원 D 구현
    raise NotImplementedError
