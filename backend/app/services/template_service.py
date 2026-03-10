"""
문서 템플릿 서비스

플로우:
  1. 앱 시작 시 ensure_system_templates()로 시스템 템플릿 DB 시딩
  2. template_id로 DB에서 템플릿 로드 (시스템 / 커스텀 동일 취급)
  3. parsed_structure 기반 동적 프롬프트 조립 → sLLM 호출
  4. 카테고리별 DOCX 빌더로 문서 생성
"""
import json
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_template import DocumentTemplate

logger = logging.getLogger(__name__)

# ── 시스템 템플릿 정의 (parsed_structure 포함) ──

SYSTEM_TEMPLATES = [
    {
        "name": "기본 회의록",
        "description": "시스템 기본 회의록 템플릿",
        "category": "meeting_minutes",
        "parsed_structure": json.dumps({
            "fields": [
                {"key": "title", "label": "회의 제목", "type": "text", "required": True},
                {"key": "date", "label": "회의 날짜", "type": "date", "required": True},
                {"key": "attendees", "label": "참석자", "type": "list", "required": False},
                {"key": "content", "label": "회의 내용", "type": "textarea", "required": True},
            ]
        }, ensure_ascii=False),
    },
    {
        "name": "기본 보고서",
        "description": "시스템 기본 업무보고서 템플릿",
        "category": "report",
        "parsed_structure": json.dumps({
            "fields": [
                {"key": "title", "label": "보고서 제목", "type": "text", "required": True},
                {"key": "date", "label": "작성일", "type": "date", "required": True},
                {"key": "author", "label": "작성자", "type": "text", "required": False},
                {"key": "department", "label": "부서", "type": "text", "required": False},
                {"key": "content", "label": "업무 내용", "type": "textarea", "required": True},
            ]
        }, ensure_ascii=False),
    },
    {
        "name": "기본 제안서",
        "description": "시스템 기본 제안서 템플릿",
        "category": "proposal",
        "parsed_structure": json.dumps({
            "fields": [
                {"key": "title", "label": "제안서 제목", "type": "text", "required": True},
                {"key": "date", "label": "제출일", "type": "date", "required": True},
                {"key": "company", "label": "제안사", "type": "text", "required": False},
                {"key": "manager", "label": "담당자", "type": "text", "required": False},
                {"key": "content", "label": "제안 내용", "type": "textarea", "required": True},
            ]
        }, ensure_ascii=False),
    },
]


async def ensure_system_templates(db: AsyncSession) -> None:
    """앱 시작 시 시스템 템플릿이 DB에 없으면 시딩"""
    result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.is_system == True)  # noqa: E712
    )
    existing = result.scalars().all()
    existing_categories = {t.category for t in existing}

    for tpl_def in SYSTEM_TEMPLATES:
        if tpl_def["category"] in existing_categories:
            # 이미 있으면 parsed_structure만 업데이트
            for t in existing:
                if t.category == tpl_def["category"]:
                    t.parsed_structure = tpl_def["parsed_structure"]
                    break
            continue

        tpl = DocumentTemplate(
            name=tpl_def["name"],
            description=tpl_def["description"],
            category=tpl_def["category"],
            is_system=True,
            scope="company",
            status="ready",
            parsed_structure=tpl_def["parsed_structure"],
        )
        db.add(tpl)
        logger.info(f"[TemplateService] 시스템 템플릿 시딩: {tpl_def['name']}")

    await db.commit()


def _template_to_dict(t: DocumentTemplate) -> dict:
    """ORM 모델 → dict 변환"""
    field_count = 0
    if t.parsed_structure:
        try:
            ps = json.loads(t.parsed_structure)
            fields = ps.get("fields", ps) if isinstance(ps, dict) else ps
            field_count = len(fields) if isinstance(fields, list) else 0
        except Exception:
            pass

    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "is_system": t.is_system,
        "scope": t.scope,
        "file_type": t.file_type,
        "status": t.status,
        "created_at": t.created_at,
        "field_count": field_count,
    }


async def list_templates(
    db: AsyncSession,
    user_id: int,
    category: str | None = None,
    scope: str | None = None,
) -> list[dict]:
    """템플릿 목록 조회 (시스템 + 커스텀, 모두 DB에서)"""
    stmt = select(DocumentTemplate)
    if category:
        stmt = stmt.where(DocumentTemplate.category == category)
    if scope:
        stmt = stmt.where(DocumentTemplate.scope == scope)
    stmt = stmt.order_by(DocumentTemplate.is_system.desc(), DocumentTemplate.created_at.desc())

    result = await db.execute(stmt)
    templates = result.scalars().all()
    return [_template_to_dict(t) for t in templates]


async def get_template(db: AsyncSession, template_id: int) -> dict:
    """템플릿 상세 조회 (parsed_structure 포함)"""
    result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.id == template_id)
    )
    tmpl = result.scalar_one_or_none()
    if tmpl is None:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")

    d = _template_to_dict(tmpl)
    d["parsed_structure"] = tmpl.parsed_structure
    d["file_path"] = tmpl.file_path
    d["uploaded_by"] = tmpl.uploaded_by
    return d


async def delete_template(
    db: AsyncSession,
    template_id: int,
    user_id: int,
) -> dict:
    """템플릿 삭제 (커스텀만 가능)"""
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
