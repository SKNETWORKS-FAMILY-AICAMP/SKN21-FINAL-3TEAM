"""
문서 관리 API (팀원 C/D 공동 담당)
- 문서 CRUD, 업로드, 검색
- 템플릿 관리 (업로드/목록/상세/삭제)
- 문서 생성 (템플릿 ID 기반)
- 회사/개인 문서 구분 (scope)
"""
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, Query, Body, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.db.session import get_db
from app.services import document_service, parsing_service, template_service

GENERATED_DOCS_DIR = Path(__file__).resolve().parents[4] / "backend" / "generated_docs"


class GenerateDocumentRequest(BaseModel):
    template_type: str
    title: str = ""
    date: str = ""
    attendees: list[str] = []
    content: str = ""

router = APIRouter()


# ── 정적 경로 (/{document_id} 보다 먼저 등록) ──


@router.get("/")
async def list_documents(
    scope: str | None = Query(None, regex="^(company|personal)$"),
    keyword: str | None = None,
    search_type: str = Query("title", regex="^(title|content|date)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 목록 조회 (scope + search_type 필터 지원)"""
    docs = await document_service.list_documents(
        db, user_id=user.id, scope=scope, keyword=keyword, search_type=search_type
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
    request: GenerateDocumentRequest,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    템플릿 기반 문서 생성 (FR-DOC-008)
    현재 지원: meeting_minutes, report, proposal
    """
    try:
        from ai.agents.document_agent import (
            _generate_meeting_minutes,
            _generate_report,
            _generate_proposal,
        )

        user_input = (
            f"제목: {request.title}\n"
            f"날짜: {request.date}\n"
            f"참석자: {', '.join(request.attendees)}\n"
            f"내용: {request.content}"
        )

        if request.template_type == "meeting_minutes":
            result = _generate_meeting_minutes(user_input)
            return {
                "document_id": result["document_id"],
                "template_type": "meeting_minutes",
                "preview": result["preview"],
                "download_url": f"/api/v1/documents/{result['document_id']}/download",
                "title": result.get("data", {}).get("title", request.title),
                "date": result.get("data", {}).get("date", request.date),
                "attendees": result.get("data", {}).get("attendees", request.attendees),
                "summary": result.get("summary", ""),
                "decisions": result.get("decisions", []),
                "action_items": result.get("action_items", []),
            }

        if request.template_type == "report":
            result = _generate_report(user_input)
            return {
                "document_id": result["document_id"],
                "template_type": "report",
                "preview": result["preview"],
                "download_url": f"/api/v1/documents/{result['document_id']}/download",
                "title": result.get("data", {}).get("title", request.title),
                "overview": result.get("data", {}).get("overview", ""),
                "main_content": result.get("data", {}).get("main_content", ""),
                "tasks": result.get("data", {}).get("tasks", []),
                "next_plan": result.get("data", {}).get("next_plan", ""),
            }

        if request.template_type == "proposal":
            result = _generate_proposal(user_input)
            return {
                "document_id": result["document_id"],
                "template_type": "proposal",
                "preview": result["preview"],
                "download_url": f"/api/v1/documents/{result['document_id']}/download",
                "title": result.get("data", {}).get("title", request.title),
                "background": result.get("data", {}).get("background", ""),
                "content": result.get("data", {}).get("content", ""),
                "expected_effect": result.get("data", {}).get("expected_effect", ""),
                "schedule": result.get("data", {}).get("schedule", []),
                "budget": result.get("data", {}).get("budget", []),
            }

        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 템플릿 타입입니다: {request.template_type}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문서 생성 중 오류 발생: {str(e)}")


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
    raise HTTPException(
        status_code=501,
        detail="키워드 하이라이트 검색은 RAG(Qdrant) 연동 대기 중입니다. 일반 검색은 GET /documents/?keyword= 를 사용하세요.",
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
    raise HTTPException(
        status_code=501,
        detail="커스텀 템플릿 업로드는 문서 구조 추출(from_parsed_structure) 구현 대기 중입니다.",
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
    document_id: str,
    format: str = Query("docx", regex="^(docx|pdf)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    생성된 문서 다운로드 - DOCX (FR-DOC-008)
    document_id: AI 생성 문서의 UUID
    """
    file_path = GENERATED_DOCS_DIR / f"{document_id}.docx"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
    return FileResponse(
        path=str(file_path),
        filename="회의록.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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
