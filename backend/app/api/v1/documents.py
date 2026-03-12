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


def _to_str(v) -> str:
    """LLM이 string 대신 list/dict를 반환하는 경우 문자열로 변환"""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return "\n".join(str(item) for item in v)
    return str(v)


class GenerateDocumentRequest(BaseModel):
    template_type: str
    template_id: int | None = None
    title: str = ""
    date: str = ""
    attendees: list[str] = []
    content: str = ""

router = APIRouter()


# ── 정적 경로 (/{document_id} 보다 먼저 등록) ──


@router.get("/")
async def list_documents(
    scope: str | None = Query(None, regex="^(company|team|personal)$"),
    keyword: str | None = None,
    search_type: str = Query("title", regex="^(title|title_content|date)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 목록 조회 (scope + search_type 필터 지원)"""
    docs = await document_service.list_documents(
        db, user_id=user.id, scope=scope, keyword=keyword,
        search_type=search_type, user_team=user.team,
    )
    return [
        {
            "id": d.id,
            "title": d.title,
            "file_type": d.file_type,
            "scope": d.scope,
            "team_name": d.team_name,
            "status": d.status,
            "uploaded_by": d.uploaded_by,
            "created_at": d.created_at,
            "category": d.category,
            "tags": d.tags,
        }
        for d in docs
    ]


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    scope: str = Query("company", regex="^(company|team|personal)$"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 업로드 (텍스트 추출 → DB 저장)"""
    doc = await document_service.upload_and_parse(
        db, file=file, scope=scope, user_id=user.id,
        team_name=user.team if scope == "team" else None,
    )
    return {
        "id": doc.id,
        "title": doc.title,
        "file_type": doc.file_type,
        "scope": doc.scope,
        "team_name": doc.team_name,
        "status": doc.status,
        "uploaded_by": doc.uploaded_by,
        "created_at": doc.created_at,
        "category": doc.category,
        "tags": doc.tags,
        "summary": doc.summary,
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
        from ai.agents.document_agent import generate_document as ai_generate

        parts = []
        if request.title:
            parts.append(f"제목: {request.title}")
        if request.date:
            parts.append(f"날짜: {request.date}")
        if request.attendees:
            parts.append(f"참석자: {', '.join(request.attendees)}")
        if request.content:
            parts.append(request.content)
        user_input = "\n".join(parts)

        result = await ai_generate(
            category=request.template_type,
            user_input=user_input,
            template_id=request.template_id,
        )

        # 통일된 응답 구조
        data = result.get("data", {})
        response = {
            "document_id": result["document_id"],
            "template_type": result.get("template_type", request.template_type),
            "template_id": result.get("template_id"),
            "template_name": result.get("template_name"),
            "preview": result.get("preview", ""),
            "download_url": f"/api/v1/documents/{result['document_id']}/download",
            "data": data,
        }

        # 회의록: action_items 포함
        if request.template_type == "meeting_minutes":
            response["title"] = data.get("title", request.title)
            response["date"] = data.get("date", request.date)
            response["attendees"] = data.get("attendees", request.attendees)
            response["summary"] = result.get("summary", data.get("summary", ""))
            response["decisions"] = result.get("decisions", data.get("decisions", []))
            response["action_items"] = result.get("action_items", data.get("action_items", []))

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문서 생성 중 오류 발생: {str(e)}")


@router.post("/analyze-all")
async def analyze_all_documents(
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """기존 문서 중 미분석 문서를 일괄 LLM 분석"""
    try:
        result = await document_service.analyze_existing_documents(db)
        await db.commit()
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"일괄 분석 실패: {str(e)}")


@router.post("/reindex-all")
async def reindex_all_documents(
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """기존 문서를 Qdrant에 재인덱싱 (태그/분류/요약 메타데이터 포함)"""
    try:
        result = await document_service.reindex_all_documents(db)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"재인덱싱 실패: {str(e)}")


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
    — DOCX 양식 파일을 업로드하면 규칙 기반으로 필드를 추출하여 저장
    """
    import tempfile
    import os
    from app.models.document_template import DocumentTemplate

    # 파일 타입 검증
    if not file.filename.endswith((".docx", ".DOCX")):
        raise HTTPException(status_code=400, detail="DOCX 파일만 업로드 가능합니다.")

    # 임시 파일에 저장 후 파싱
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from ai.document_parser.template_extractor import extract_template_fields, fields_to_parsed_structure
        fields = extract_template_fields(tmp_path)

        if not fields:
            raise HTTPException(status_code=400, detail="양식에서 필드를 추출하지 못했습니다. DOCX 양식 파일인지 확인해주세요.")

        parsed_structure = fields_to_parsed_structure(fields)

        # 업로드 파일 저장
        upload_dir = Path("uploads/templates")
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = str(upload_dir / f"{user.id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(content)

        # DB 저장
        template = DocumentTemplate(
            name=name,
            description=description,
            file_path=file_path,
            file_type="docx",
            parsed_structure=parsed_structure,
            category=category,
            is_system=False,
            scope=scope,
            uploaded_by=user.id,
            status="ready",
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)

        return {
            "id": template.id,
            "name": template.name,
            "category": template.category,
            "status": "ready",
            "fields": fields,
            "field_count": len(fields),
        }

    finally:
        os.unlink(tmp_path)


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


class UpdateAnalysisRequest(BaseModel):
    category: str | None = None
    tags: list[str] | None = None
    summary: str | None = None


@router.patch("/{document_id}/analysis")
async def update_analysis(
    document_id: int,
    request: UpdateAnalysisRequest,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 분석 결과(카테고리, 태그, 요약) 수정"""
    doc = await document_service.get_document(db, document_id)
    if request.category is not None:
        doc.category = request.category
    if request.tags is not None:
        doc.tags = request.tags
    if request.summary is not None:
        doc.summary = request.summary
    await db.commit()
    return {
        "id": doc.id,
        "category": doc.category,
        "tags": doc.tags,
        "summary": doc.summary,
    }


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
        "category": doc.category,
        "tags": doc.tags,
        "summary": doc.summary,
    }


class UpdateCategoryRequest(BaseModel):
    category: str


@router.patch("/{document_id}/category")
async def update_document_category(
    document_id: int,
    req: UpdateCategoryRequest,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 카테고리(타입) 변경"""
    from sqlalchemy import select
    from app.models.document import Document

    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
    doc.category = req.category
    await db.commit()
    return {"id": doc.id, "category": doc.category}


class UpdateScopeRequest(BaseModel):
    scope: str


@router.patch("/{document_id}/scope")
async def update_document_scope(
    document_id: int,
    req: UpdateScopeRequest,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """문서 공개범위 변경 (company/team/personal)"""
    if req.scope not in ("company", "team", "personal"):
        raise HTTPException(status_code=400, detail="유효하지 않은 scope 값입니다")
    from sqlalchemy import select
    from app.models.document import Document

    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
    doc.scope = req.scope
    if req.scope == "team":
        doc.team_name = user.team
    await db.commit()
    return {"id": doc.id, "scope": doc.scope}


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
