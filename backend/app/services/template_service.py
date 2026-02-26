"""
문서 템플릿 서비스 (팀원 D 담당 - API, 팀원 C 담당 - 생성 로직)

플로우:
  1. 챗봇 또는 전용 페이지에서 문서 생성 요청
  2. template_id로 DB에서 템플릿 로드 (시스템 or 커스텀)
  3. 시스템 템플릿 → ai/templates/ 클래스 사용
     커스텀 템플릿 → parsed_structure 기반 동적 생성
  4. sLLM으로 user_input 기반 데이터 생성
  5. 템플릿 렌더링 → 미리보기(마크다운) 반환
  6. 다운로드 시 DOCX/PDF 변환

요구사항: FR-DOC-008
"""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_template import DocumentTemplate


# 시스템 기본 제공 템플릿 종류
SYSTEM_TEMPLATE_TYPES = {
    "meeting_minutes": "회의록",
    "report": "보고서",
    "jd": "채용 공고",
    "proposal": "제안서",
}


def _build_system_templates() -> list[dict]:
    """시스템 기본 4종 템플릿을 dict 형태로 반환"""
    now = datetime.utcnow()
    templates = []
    for idx, (category, name) in enumerate(SYSTEM_TEMPLATE_TYPES.items(), start=-4):
        templates.append({
            "id": idx,  # 음수 ID로 시스템 템플릿 구분
            "name": name,
            "description": f"시스템 기본 {name} 템플릿",
            "category": category,
            "is_system": True,
            "scope": "company",
            "file_type": None,
            "status": "ready",
            "created_at": now,
        })
    return templates


async def list_templates(
    db: AsyncSession,
    user_id: int,
    category: str | None = None,
    scope: str | None = None,
) -> list[dict]:
    """
    템플릿 목록 조회: 시스템 기본 4종 + DB 커스텀 템플릿
    """
    # 시스템 템플릿
    system = _build_system_templates()
    if category:
        system = [t for t in system if t["category"] == category]

    # DB 커스텀 템플릿
    stmt = select(DocumentTemplate).where(DocumentTemplate.is_system == False)  # noqa: E712
    if category:
        stmt = stmt.where(DocumentTemplate.category == category)
    if scope:
        stmt = stmt.where(DocumentTemplate.scope == scope)
    stmt = stmt.order_by(DocumentTemplate.created_at.desc())

    result = await db.execute(stmt)
    custom = result.scalars().all()

    custom_dicts = [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "is_system": t.is_system,
            "scope": t.scope,
            "file_type": t.file_type,
            "status": t.status,
            "created_at": t.created_at,
        }
        for t in custom
    ]

    return system + custom_dicts


async def get_template(db: AsyncSession, template_id: int) -> dict:
    """템플릿 상세 조회"""
    # 시스템 템플릿 (음수 ID)
    if template_id < 0:
        system = _build_system_templates()
        for t in system:
            if t["id"] == template_id:
                return {**t, "parsed_structure": None, "file_path": None, "uploaded_by": None}
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")

    result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.id == template_id)
    )
    tmpl = result.scalar_one_or_none()
    if tmpl is None:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")

    return {
        "id": tmpl.id,
        "name": tmpl.name,
        "description": tmpl.description,
        "category": tmpl.category,
        "is_system": tmpl.is_system,
        "scope": tmpl.scope,
        "file_type": tmpl.file_type,
        "status": tmpl.status,
        "created_at": tmpl.created_at,
        "parsed_structure": tmpl.parsed_structure,
        "file_path": tmpl.file_path,
        "uploaded_by": tmpl.uploaded_by,
    }


async def delete_template(
    db: AsyncSession,
    template_id: int,
    user_id: int,
) -> dict:
    """템플릿 삭제 (커스텀만 가능, 시스템 기본 템플릿은 삭제 불가)"""
    if template_id < 0:
        raise HTTPException(status_code=403, detail="시스템 기본 템플릿은 삭제할 수 없습니다")

    result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.id == template_id)
    )
    tmpl = result.scalar_one_or_none()
    if tmpl is None:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")

    if tmpl.is_system:
        raise HTTPException(status_code=403, detail="시스템 기본 템플릿은 삭제할 수 없습니다")

    await db.delete(tmpl)
    return {"message": "템플릿이 삭제되었습니다", "template_id": template_id}


# ── AI 의존 기능 (팀원 C와 협업 필요) ──


async def generate_document(
    db: AsyncSession,
    user_input: str,
    user_id: int,
    template_id: int | None = None,
    template_type: str | None = None,
) -> dict:
    """문서 생성 — AI 로직 필요 (팀원 C 구현 후 연동)"""
    # TODO: 팀원 C (생성 로직) 구현 후 연동
    raise NotImplementedError("문서 생성 기능은 AI Agent 연동 후 사용 가능합니다")


async def download_document(
    db: AsyncSession,
    document_id: int,
    format: str = "docx",
) -> bytes:
    """문서 다운로드 — 템플릿 렌더링 필요 (팀원 C 구현 후 연동)"""
    # TODO: 팀원 C (렌더링) 구현 후 연동
    raise NotImplementedError("문서 다운로드 기능은 AI Agent 연동 후 사용 가능합니다")
