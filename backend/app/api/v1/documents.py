"""
문서 관리 API (팀원 C/D 공동 담당)
- 문서 CRUD, 업로드, 검색
- 템플릿 관리 (업로드/목록/상세/삭제)
- 문서 생성 (템플릿 ID 기반)
- 회사/개인 문서 구분 (scope)
"""
from fastapi import APIRouter, Depends, UploadFile, File, Query, Body, HTTPException

from app.api.deps import get_current_user
from app.db.session import get_db
from app.services import document_service, parsing_service, template_service

router = APIRouter()


# ── 정적 경로 (/{document_id} 보다 먼저 등록) ──


@router.get("/")
async def list_documents(
    scope: str | None = Query(None, regex="^(company|personal)$"),
    keyword: str | None = None,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 목록 조회 (scope 필터 지원)"""
    docs = await document_service.list_documents(
        db, user_id=user.id, scope=scope, keyword=keyword
    )
    return [
        {
            "id": d.id,
            "title": d.title,
            "file_type": d.file_type,
            "scope": d.scope,
            "status": d.status,
            "uploaded_by": d.uploaded_by,
            "created_at": d.created_at,
        }
        for d in docs
    ]


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    scope: str = Query("company", regex="^(company|personal)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 업로드 (텍스트 추출 → DB 저장)"""
    doc = await document_service.upload_and_parse(
        db, file=file, scope=scope, user_id=user.id
    )
    return {
        "id": doc.id,
        "title": doc.title,
        "file_type": doc.file_type,
        "scope": doc.scope,
        "status": doc.status,
        "uploaded_by": doc.uploaded_by,
        "created_at": doc.created_at,
    }


@router.post("/generate")
async def generate_document(
    template_id: int | None = Body(None),
    template_type: str | None = Body(None),
    user_input: str = Body(..., description="사용자 입력 (내용/지시사항)"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    템플릿 기반 문서 생성 (FR-DOC-008)
    — AI 로직 필요, 팀원 C 구현 후 연동
    """
    # TODO: 팀원 D (API) + 팀원 C (생성 로직)
    raise HTTPException(
        status_code=501,
        detail="문서 생성 기능은 AI Agent 연동 후 사용 가능합니다",
    )


@router.get("/search/highlight")
async def search_with_highlight(
    keyword: str = Query(...),
    scope: str | None = Query(None, regex="^(company|personal)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    키워드 검색 + 하이라이트 (FR-DOC-006)
    — RAG 연동 필요, 팀원 B 구현 후 연동
    """
    # TODO: 팀원 D (API) + 팀원 B (RAG 검색)
    raise HTTPException(
        status_code=501,
        detail="검색 기능은 RAG 연동 후 사용 가능합니다",
    )


# ── 템플릿 관리 (정적 경로) ──


@router.post("/templates/upload")
async def upload_template(
    file: UploadFile = File(...),
    name: str = Query(..., description="템플릿 이름"),
    description: str | None = Query(None),
    category: str = Query("custom"),
    scope: str = Query("company", regex="^(company|personal)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    커스텀 템플릿 업로드
    — AI 구조 추출 필요, 팀원 C 구현 후 연동
    """
    # TODO: 팀원 D (API) + 팀원 C (구조 추출)
    raise HTTPException(
        status_code=501,
        detail="커스텀 템플릿 업로드 기능은 AI Agent 연동 후 사용 가능합니다",
    )


@router.get("/templates/")
async def list_templates(
    category: str | None = Query(None),
    scope: str | None = Query(None, regex="^(company|personal)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    템플릿 목록 조회
    시스템 기본 템플릿(4종) + 사용자 커스텀 템플릿
    """
    return await template_service.list_templates(
        db, user_id=user.id, category=category, scope=scope
    )


@router.get("/templates/{template_id}")
async def get_template(
    template_id: int,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """템플릿 상세 조회 (parsed_structure 포함)"""
    return await template_service.get_template(db, template_id)


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
    return await template_service.delete_template(db, template_id, user.id)


# ── 동적 경로 (/{document_id}) ──


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 상세 조회"""
    doc = await document_service.get_document(db, document_id)
    return {
        "id": doc.id,
        "title": doc.title,
        "file_type": doc.file_type,
        "scope": doc.scope,
        "status": doc.status,
        "uploaded_by": doc.uploaded_by,
        "created_at": doc.created_at,
        "content": doc.content,
        "file_path": doc.file_path,
        "version": 1,
    }


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 삭제"""
    return await document_service.delete_document(db, document_id, user.id)


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    format: str = Query("docx", regex="^(docx|pdf)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    생성된 문서 다운로드 - DOCX/PDF (FR-DOC-008)
    — 템플릿 렌더링 필요, 팀원 C 구현 후 연동
    """
    # TODO: 팀원 D 구현
    raise HTTPException(
        status_code=501,
        detail="문서 다운로드 기능은 AI Agent 연동 후 사용 가능합니다",
    )


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
    return await parsing_service.get_parsing_status(db, document_id)
