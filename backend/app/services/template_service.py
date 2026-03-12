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
                # form: true (UI 폼에 표시)
                {"key": "title", "label": "회의 제목", "type": "text", "required": True, "form": True,
                 "description": "회의 주제를 반영한 구체적인 제목"},
                {"key": "date", "label": "회의 날짜", "type": "date", "required": True, "form": True,
                 "description": "회의 날짜 (YYYY-MM-DD 형식, 없으면 오늘 날짜)"},
                {"key": "attendees", "label": "참석자", "type": "list", "required": False, "form": True,
                 "description": "참석자 이름 배열 (없으면 빈 배열)"},
                {"key": "content", "label": "회의 내용", "type": "textarea", "required": True, "form": True,
                 "description": "회의에서 논의된 내용을 상세히 입력"},
                # form: false (LLM이 생성, UI에 안 보임)
                {"key": "time", "form": False, "description": "회의 시간 (없으면 빈 문자열)"},
                {"key": "location", "form": False, "description": "회의 장소 (없으면 빈 문자열)"},
                {"key": "meeting_type", "form": False, "description": "'정기', '긴급', '수시' 중 하나"},
                {"key": "author", "form": False, "description": "작성자 이름 (없으면 빈 문자열)"},
                {"key": "summary", "form": False, "description": "회의에서 논의된 주요 내용을 3~5문장으로 요약"},
                {"key": "decisions", "form": False, "description": "결정된 사항 목록 (JSON 배열)"},
                {"key": "action_items", "form": False,
                 "description": '후속 조치 목록 배열. 각 항목은 {"task": "할 일", "assignee": "담당자", "due_date": "기한"} 형태'},
                {"key": "risks", "form": False,
                 "description": '리스크 목록 배열. 각 항목은 {"description": "설명", "level": "상/중/하", "mitigation": "대응방안"} 형태'},
                {"key": "notes", "form": False, "description": "기타 메모 (없으면 빈 문자열)"},
            ]
        }, ensure_ascii=False),
    },
    {
        "name": "기본 보고서",
        "description": "시스템 기본 업무보고서 템플릿",
        "category": "report",
        "parsed_structure": json.dumps({
            "fields": [
                # form: true (UI 폼에 표시)
                {"key": "title", "label": "보고서 제목", "type": "text", "required": True, "form": True,
                 "description": "업무 내용을 반영한 구체적인 보고서 제목"},
                {"key": "date", "label": "작성일", "type": "date", "required": True, "form": True,
                 "description": "작성 날짜 (YYYY-MM-DD 형식)"},
                {"key": "author", "label": "작성자", "type": "text", "required": False, "form": True,
                 "description": "작성자 이름 (없으면 빈 문자열)"},
                {"key": "department", "label": "부서", "type": "text", "required": False, "form": True,
                 "description": "부서명 (없으면 빈 문자열)"},
                {"key": "content", "label": "업무 내용", "type": "textarea", "required": True, "form": True,
                 "description": "업무 내용을 상세히 입력"},
                # form: false (LLM이 생성, UI에 안 보임)
                {"key": "position", "form": False, "description": "직급 (없으면 빈 문자열)"},
                {"key": "report_to", "form": False, "description": "보고 대상 (없으면 빈 문자열)"},
                {"key": "report_type", "form": False,
                 "description": "'일일', '주간', '월간', '수시' 중 하나"},
                {"key": "overview", "form": False,
                 "description": "업무 내용을 요약한 보고 개요 (3~5문장)"},
                {"key": "main_content", "form": False,
                 "description": "업무 세부 내용을 항목별로 구체적으로 작성"},
                {"key": "tasks", "form": False,
                 "description": '진행 업무 목록 배열. 각 항목은 {"item": "업무명", "assignee": "담당자", "progress": "진행률", "start_date": "시작일", "end_date": "종료일"} 형태'},
                {"key": "issues", "form": False, "description": "이슈 및 건의사항 (없으면 빈 문자열)"},
                {"key": "next_plan", "form": False, "description": "향후 계획 (구체적으로 작성)"},
            ]
        }, ensure_ascii=False),
    },
    {
        "name": "기본 제안서",
        "description": "시스템 기본 제안서 템플릿",
        "category": "proposal",
        "parsed_structure": json.dumps({
            "fields": [
                # form: true (UI 폼에 표시)
                {"key": "title", "label": "제안서 제목", "type": "text", "required": True, "form": True,
                 "description": "제안 내용을 반영한 구체적인 제안서 제목"},
                {"key": "date", "label": "제출일", "type": "date", "required": True, "form": True,
                 "description": "제출 날짜 (YYYY-MM-DD, 없으면 오늘 날짜)"},
                {"key": "company", "label": "제안사", "type": "text", "required": False, "form": True,
                 "description": "제안사 이름 (없으면 빈 문자열)"},
                {"key": "manager", "label": "담당자", "type": "text", "required": False, "form": True,
                 "description": "담당자 이름 (없으면 빈 문자열)"},
                {"key": "content", "label": "제안 내용", "type": "textarea", "required": True, "form": True,
                 "description": "제안 내용을 항목별로 구체적으로 입력"},
                # form: false (LLM이 생성, UI에 안 보임)
                {"key": "submit_to", "form": False, "description": "제출처 (없으면 빈 문자열)"},
                {"key": "contact", "form": False, "description": "연락처 (없으면 빈 문자열)"},
                {"key": "purpose", "form": False, "description": "제안 목적 및 필요성 (3~5문장)"},
                {"key": "background", "form": False, "description": "제안 배경 (2~3문장)"},
                {"key": "schedule", "form": False,
                 "description": '추진 일정 배열. 각 항목은 {"phase": "단계", "task": "업무", "period": "기간"} 형태'},
                {"key": "budget", "form": False,
                 "description": '예산 배열. 각 항목은 {"item": "항목", "amount": "금액"} 형태'},
                {"key": "budget_total", "form": False, "description": "합계 금액 (없으면 빈 문자열)"},
                {"key": "expected_effect", "form": False, "description": "기대 효과 (3~5문장)"},
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
