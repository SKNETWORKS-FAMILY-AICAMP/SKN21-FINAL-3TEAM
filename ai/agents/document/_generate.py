"""문서 생성 파이프라인"""
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from ai.agents.document._common import (
    GENERATED_DOCS_DIR,
    _call_llm,
    _to_readable_str,
    get_last_model_name,
)

# ── 문서 유형 한글명 (여러 곳에서 재사용) ──
DOC_TYPE_NAMES = {
    "meeting_minutes": "회의록",
    "report": "보고서",
    "proposal": "제안서",
}

# ── 정규화 공통 키 ──
_ASSIGNEE_KEYS = ("assignee", "person", "담당자", "owner", "assigned_to")

# 대화형 안내 메시지 (채팅에서 내용 부족 시 안내)
_GENERATE_GUIDE = {
    "meeting_minutes": {
        "title": "회의록",
        "fields": "회의 날짜, 참석자, 회의 내용 (논의사항, 결정사항 등)",
        "example": "3월 23일 팀 회의, 김팀장·이대리 참석, API 설계 논의, REST 채택 결정",
    },
    "report": {
        "title": "업무보고서",
        "fields": "보고 제목, 작성자, 주요 업무 내용, 진행 현황, 향후 계획",
        "example": "3월 주간보고, 프론트엔드 리팩토링 80% 완료, 다음주 테스트 예정",
    },
    "proposal": {
        "title": "제안서",
        "fields": "제안 제목, 목적, 배경, 제안 내용, 기대 효과, 일정, 예산",
        "example": "사내 AI 챗봇 도입 제안, 업무 자동화로 월 40시간 절감 기대",
    },
}


def _first_val(d: dict, keys) -> str:
    """dict에서 keys 순서대로 탐색해 첫 번째 non-empty 값을 반환."""
    for k in keys:
        if k in d and d[k]:
            return str(d[k])
    return ""


# ── 문서생성 필드 수 최적화 (sLLM 학습 분포 매칭) ──
# 학습 데이터: 6~10개 필드(평균 8.1개)
# always = 시스템 템플릿에서 항상 포함할 필드 (학습 데이터 100%/80% 포함)
GENERATION_FIELD_CONFIG = {
    "meeting_minutes": {
        "always": ["title", "date", "attendees", "content", "summary", "decisions", "action_items"],
        "optional": ["meeting_type", "author", "time", "location", "notes"],
        "max_fields": 10,
    },
    "report": {
        "always": ["title", "date", "author", "overview", "main_content", "tasks", "next_plan", "issues"],
        "optional": ["department", "report_type", "report_to", "content", "position"],
        "max_fields": 10,
    },
    "proposal": {
        "always": ["title", "submit_date", "purpose", "content", "expected_effect", "schedule", "budget", "background", "current_situation"],
        "optional": ["company", "manager", "submit_to", "budget_total", "contact"],
        "max_fields": 11,
    },
}


def _select_fields_for_llm(all_fields, template_type, user_input, is_system=True):
    """시스템 템플릿의 필드를 학습 분포(6~10개)에 맞게 선별한다.
    커스텀 템플릿이나 config에 없는 type은 all_fields 그대로 반환."""
    if not is_system:
        return all_fields

    config = GENERATION_FIELD_CONFIG.get(template_type)
    if not config:
        return all_fields

    always_keys = set(config["always"])
    optional_keys = config["optional"]
    max_fields = config["max_fields"]

    all_keys = {f["key"] for f in all_fields}
    selected_keys = always_keys & all_keys  # DB에 있는 always 필드만

    # optional 중 user_input에 관련 키워드가 있는 것 추가
    user_input_lower = (user_input or "").lower()
    for opt_key in optional_keys:
        if len(selected_keys) >= max_fields:
            break
        if opt_key in all_keys and opt_key in user_input_lower:
            selected_keys.add(opt_key)

    selected = [f for f in all_fields if f["key"] in selected_keys]
    print(f"[DocumentAgent] 필드 선별: {len(all_fields)}개 → {len(selected)}개 (is_system={is_system})")
    return selected


def _detect_template_type(user_input: str) -> str:
    """사용자 입력에서 템플릿 타입을 키워드로 감지 (LLM 판단 실패 시 fallback)

    Returns:
        "meeting_minutes" | "jd" | "proposal" | "report" (기본값)
    """
    input_lower = user_input.lower()

    if re.search(r"회의록|미팅.*(기록|노트|정리)", input_lower):
        return "meeting_minutes"
    if re.search(r"jd|채용.*공고|직무.*기술서|job.*description", input_lower):
        return "jd"
    if re.search(r"제안서|proposal", input_lower):
        return "proposal"
    return "report"


async def _query_custom_templates(category: str) -> list:
    """DB에서 해당 카테고리의 커스텀 템플릿 목록 조회"""
    try:
        from sqlalchemy import select
        from app.db.session import async_session
        from app.models.document_template import DocumentTemplate

        async with async_session() as session:
            result = await session.execute(
                select(DocumentTemplate).where(
                    DocumentTemplate.category == category,
                    DocumentTemplate.is_system == False,  # noqa: E712
                ).order_by(DocumentTemplate.created_at.desc())
            )
            templates = result.scalars().all()

        items = []
        for t in templates:
            field_count = 0
            if t.parsed_structure:
                try:
                    ps = json.loads(t.parsed_structure)
                    fields = ps.get("fields", ps) if isinstance(ps, dict) else ps
                    field_count = len(fields) if isinstance(fields, list) else 0
                except Exception:
                    pass
            items.append({
                "template_id": t.id,
                "name": t.name,
                "is_system": False,
                "field_count": field_count,
            })
        return items
    except Exception as e:
        print(f"[DocumentAgent] 커스텀 템플릿 조회 실패: {e}")
        return []


async def _get_system_template_id(category: str) -> int | None:
    """DB에서 해당 카테고리의 시스템 기본 템플릿 ID 조회"""
    try:
        from sqlalchemy import select
        from app.db.session import async_session
        from app.models.document_template import DocumentTemplate

        async with async_session() as session:
            result = await session.execute(
                select(DocumentTemplate.id).where(
                    DocumentTemplate.category == category,
                    DocumentTemplate.is_system == True,  # noqa: E712
                ).limit(1)
            )
            row = result.scalar_one_or_none()

        return row
    except Exception as e:
        print(f"[DocumentAgent] 시스템 템플릿 ID 조회 실패: {e}")
        return None


async def _llm_detect_template_type(user_input: str) -> str:
    """LLM을 사용해 사용자가 어떤 문서를 만들려는지 판단

    단순 키워드 매칭으로는 오탐이 발생하는 경우(예: 제안서 내용에 '회의록' 언급)를
    LLM이 문맥 전체를 보고 올바른 문서 종류를 선택하도록 한다.

    Returns:
        "meeting_minutes" | "report" | "proposal" | "jd"
    """
    sys_prompt = (
        "당신은 문서 생성 요청을 분류하는 전문가입니다.\n"
        "사용자의 요청을 읽고, 사용자가 실제로 만들고자 하는 문서 종류를 판단하세요.\n\n"
        "선택 가능한 문서 종류:\n"
        "- meeting_minutes : 회의록, 미팅 기록, 회의 내용 정리\n"
        "- report          : 업무보고서, 업무 보고, 진행 상황 보고\n"
        "- proposal        : 제안서, 기획서, 사업 제안, 도입 제안\n"
        "- jd              : 채용 공고, JD, 직무 기술서, Job Description\n\n"
        "반드시 아래 JSON 형식으로만 답변하세요:\n"
        "{\"template_type\": \"<선택한 종류>\"}"
    )
    user_prompt = (
        f"사용자 요청:\n{user_input}\n\n"
        "위 요청에서 사용자가 만들려는 문서 종류를 판단해 JSON으로 반환하세요."
    )

    print(f"[DocumentAgent] _llm_detect_template_type LLM 호출...")
    result_str = await _call_llm(sys_prompt, user_prompt, json_mode=True)
    try:
        result = json.loads(result_str)
        template_type = result.get("template_type", "")
        if template_type in ("meeting_minutes", "report", "proposal", "jd"):
            print(f"[DocumentAgent] LLM 판단 template_type={template_type}")
            return template_type
        print(f"[DocumentAgent] LLM 반환값 비정상({template_type}) → regex fallback")
    except Exception as e:
        print(f"[DocumentAgent] LLM 템플릿 판단 실패({e}) → regex fallback")

    return _detect_template_type(user_input)



async def _extract_decisions_actions(content: str, summary: str = "") -> Dict[str, Any]:
    """
    후처리 fallback — 1차 생성에서 decisions/action_items가 비어있을 때
    이미 생성된 content/summary를 넣고 sLLM에 추출만 요청한다.
    """
    source_text = content
    if summary:
        source_text = f"{summary}\n\n{content}"

    sys_prompt = (
        "당신은 회의록 분석 전문가입니다. "
        "주어진 회의 내용에서 결정사항(decisions)과 실행항목(action_items)을 추출하세요.\n\n"
        "반드시 아래 JSON 형식으로만 응답하세요:\n"
        '{"decisions": ["결정사항1", "결정사항2"], '
        '"action_items": [{"content": "할일", "assignee": "담당자", "due_date": "기한"}]}\n\n'
        "규칙:\n"
        "- decisions는 회의에서 확정된 사항을 문자열 배열로 작성하세요.\n"
        "- action_items는 후속 조치가 필요한 항목을 객체 배열로 작성하세요.\n"
        "- 각각 최소 2개 이상 추출하세요.\n"
        "- 내용에 없는 것을 만들어내지 마세요.\n"
        "- JSON 외의 텍스트를 포함하지 마세요."
    )
    user_prompt = f"다음 회의 내용에서 decisions와 action_items를 추출하세요.\n\n[회의 내용]\n{source_text}"

    try:
        result_str = await _call_llm(sys_prompt, user_prompt, json_mode=True, task="generate")
        result = json.loads(result_str)
        return result
    except Exception as e:
        print(f"[DocumentAgent] fallback 추출 실패: {e}")
        return {}



def _build_narrative_input(category: str, fields_data: Dict[str, Any], content: str = "") -> str:
    """폼 필드(짧은 값) → 서술형 텍스트로 변환하여 학습 데이터 형식(700~1500자)에 가깝게 만든다."""
    parts = []

    if category == "meeting_minutes":
        title = fields_data.get("title", "")
        date = fields_data.get("date", "")
        attendees = fields_data.get("attendees", [])
        if isinstance(attendees, list):
            attendees_str = ", ".join(attendees)
        else:
            attendees_str = str(attendees)
        if date and title:
            parts.append(f"{date}에 진행된 '{title}' 회의")
        elif title:
            parts.append(f"'{title}' 회의")
        if attendees_str:
            parts.append(f"참석자: {attendees_str}")
    elif category == "report":
        title = fields_data.get("title", "")
        author = fields_data.get("author", "")
        department = fields_data.get("department", "")
        date = fields_data.get("date", "")
        if title:
            parts.append(f"보고서 제목: {title}")
        if author:
            parts.append(f"작성자: {author}")
        if department:
            parts.append(f"부서: {department}")
        if date:
            parts.append(f"날짜: {date}")
    elif category == "proposal":
        title = fields_data.get("title", "")
        company = fields_data.get("company", "")
        manager = fields_data.get("manager", "")
        date = fields_data.get("submit_date", "")
        if title:
            parts.append(f"제안명: {title}")
        if company:
            parts.append(f"제안사: {company}")
        if manager:
            parts.append(f"담당자: {manager}")
        if date:
            parts.append(f"제출일: {date}")
    else:
        # 기타 카테고리: 모든 필드를 나열
        for k, v in fields_data.items():
            if v and k != "content":
                parts.append(f"{k}: {v}")

    # content (본문 텍스트) 추가
    if content:
        parts.append(f"\n{content}")

    return "\n".join(parts)


async def generate_document(
    category: str,
    fields_data: Dict[str, Any] | None = None,
    content: str = "",
    template_id: int | None = None,
    user_input: str | None = None,
) -> Dict[str, Any]:
    """
    문서 생성 공통 진입점 — 문서생성 페이지와 챗봇 모두 이 함수를 호출.

    Args:
        category: 'meeting_minutes' | 'report' | 'proposal'
        fields_data: 폼 필드 딕셔너리 (문서생성 페이지에서 전달)
        content: 본문 텍스트
        template_id: 커스텀 템플릿 ID (None이면 시스템 기본)
        user_input: 자연어 텍스트 (챗봇 fallback용, fields_data가 없을 때 사용)
    """
    # 입력 검증: fields_data도 user_input도 없으면 에러
    if not fields_data and not content and not user_input:
        raise ValueError("문서 생성을 위한 입력이 없습니다. 폼 데이터 또는 텍스트를 전달해주세요.")

    # 제안서: 프론트에서 date로 오면 submit_date로 통일 (LoRA 학습 키)
    if fields_data and category == "proposal":
        if "date" in fields_data and "submit_date" not in fields_data:
            fields_data["submit_date"] = fields_data.pop("date")

    # fields_data가 있으면 서술형으로 변환, 없으면 user_input 그대로 사용 (챗봇)
    if fields_data:
        narrative = _build_narrative_input(category, fields_data, content)
    else:
        narrative = user_input or content or ""

    if template_id:
        result = await _generate_with_custom_template(narrative, template_id, category, fields_data)
    elif (system_tpl_id := await _get_system_template_id(category)):
        result = await _generate_with_custom_template(narrative, system_tpl_id, category, fields_data)
    else:
        raise ValueError(f"시스템 템플릿이 DB에 없습니다. 카테고리: {category}. DB 시딩을 확인하세요.")

    # 사용된 모델명 추가 (프론트에서 LoRA/Base 표시용)
    result["model_name"] = get_last_model_name()
    return result


async def _handle_doc_generate(user_input: str, template_type: str, document_content: str = None, template_id: int = None, stream_mode: bool = False) -> Dict[str, Any]:
    """문서 생성 처리 (보고서/회의록/JD/제안서 + 커스텀 양식)

    stream_mode=True: chat.py에서 단계별 상태 표시용 generate_config 반환
    stream_mode=False: 블로킹으로 바로 생성 (문서생성 페이지 등)
    """
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_generate | template_type={template_type}, template_id={template_id}, stream_mode={stream_mode}")

    if document_content:
        user_input = f"{user_input}\n\n[첨부 문서 내용]\n{document_content}"

    # 내용 부족 시 대화형 안내 (template_id 있으면 스킵 — template_pick 선택 후 재전송)
    if len(user_input.strip()) < 20 and not template_id:
        guide = _GENERATE_GUIDE.get(template_type, _GENERATE_GUIDE["report"])
        return {
            "type": "clarify",
            "message": (
                f"{guide['title']}을 작성할게요. 아래 내용을 알려주세요:\n\n"
                f"- {guide['fields']}\n\n"
                f"예시: \"{guide['example']}\""
            ),
        }

    # 커스텀 양식 (DB에 등록된 template_id)이 있으면 동적 필드로 생성
    if template_id:
        if stream_mode:
            return {
                "type": "doc_generate",
                "stream_pending": True,
                "generate_config": {
                    "user_input": user_input,
                    "template_type": template_type,
                    "template_id": template_id,
                },
            }
        return await _generate_with_custom_template(user_input, template_id, template_type)

    # 챗봇 요청: 해당 카테고리에 커스텀 템플릿이 있으면 선택지 제공
    if template_type in ("meeting_minutes", "report", "proposal"):
        custom_templates = await _query_custom_templates(template_type)
        type_label = DOC_TYPE_NAMES.get(template_type, template_type)

        # 시스템 기본 템플릿 DB ID 조회
        system_tpl_id = await _get_system_template_id(template_type)
        system_field_counts = {"meeting_minutes": 4, "report": 5, "proposal": 5}
        all_templates = [{"template_id": system_tpl_id, "name": f"기본 {type_label}", "is_system": True, "field_count": system_field_counts.get(template_type, 4)}]
        all_templates.extend(custom_templates)

        if len(all_templates) >= 2:
            # 2개 이상이면 선택지 제공
            lines = [f"{type_label} 양식을 선택해주세요:"]
            for i, tpl in enumerate(all_templates, 1):
                suffix = " (시스템)" if tpl.get("is_system") else f" ({tpl.get('field_count', '?')}개 필드)"
                lines.append(f"{i}. {tpl['name']}{suffix}")
            return {
                "type": "template_pick",
                "message": "\n".join(lines),
                "templates": all_templates,
                "template_type": template_type,
            }

        # 1개(기본만)면 바로 생성 — system_tpl_id 전달
        if stream_mode:
            return {
                "type": "doc_generate",
                "stream_pending": True,
                "generate_config": {
                    "user_input": user_input,
                    "template_type": template_type,
                    "template_id": system_tpl_id,
                },
            }
        return await generate_document(category=template_type, user_input=user_input, template_id=system_tpl_id)

    # 지원되지 않는 카테고리 fallback
    if stream_mode:
        return {
            "type": "doc_generate",
            "stream_pending": True,
            "generate_config": {
                "user_input": user_input,
                "template_type": template_type or "report",
                "template_id": None,
            },
        }
    return await generate_document(category=template_type or "report", user_input=user_input)


async def _generate_with_custom_template(user_input: str, template_id: int, template_type: str, fields_data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """커스텀 양식(DB 등록)으로 문서 생성 — 동적 필드 명세"""
    _t = time.time()
    print(f"[DocumentAgent] _generate_with_custom_template | template_id={template_id}")

    # DB에서 parsed_structure 조회
    try:
        from sqlalchemy import select
        from app.db.session import async_session
        from app.models.document_template import DocumentTemplate

        async with async_session() as session:
            result = await session.execute(
                select(DocumentTemplate).where(DocumentTemplate.id == template_id)
            )
            template = result.scalar_one_or_none()

        if not template or not template.parsed_structure:
            raise ValueError(f"template_id={template_id} 없거나 parsed_structure 없음. DB 시딩을 확인하세요.")

        raw_ps = json.loads(template.parsed_structure)
        fields = raw_ps.get("fields", raw_ps) if isinstance(raw_ps, dict) else raw_ps
        if not isinstance(fields, list):
            fields = []
        template_name = template.name
        print(f"[DocumentAgent] 커스텀 양식 '{template_name}' 로드 | {len(fields)}개 필드")

    except Exception as e:
        print(f"[DocumentAgent] DB 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        raise ValueError(f"템플릿 DB 조회 실패: {e}")

    # 문서 유형명 (미리보기/DOCX 빌더에서 사용)
    _PROMPT_TYPE_NAMES = {**DOC_TYPE_NAMES, "report": "업무보고서"}
    doc_type_name = _PROMPT_TYPE_NAMES.get(template_type, template_name)

    # ── 경로 분기: fill-fields 데이터 있으면 DOCX 빌드만, 없으면 sLLM 호출 ──
    if fields_data:
        # 경로 1: fill-fields에서 이미 sLLM으로 채운 데이터 → 그대로 사용
        filled_count = sum(1 for v in fields_data.values() if v not in (None, "", []))
        print(f"[DocumentAgent] fill-fields 데이터 사용 (sLLM 생략) | {filled_count}/{len(fields)}개 채워짐")
        data = dict(fields_data)
        for f in fields:
            if f["key"] not in data:
                desc = f.get("description", "")
                data[f["key"]] = [] if ("배열" in desc or "목록" in desc) else ""
    else:
        # 경로 2: fill-fields를 거치지 않은 경우 (챗봇 등) → sLLM 호출
        is_system = getattr(template, "is_system", False) if template else False
        fields_for_llm = _select_fields_for_llm(fields, template_type, user_input, is_system)

        from ai.document_parser.template_extractor import fields_to_prompt
        field_spec = fields_to_prompt(fields_for_llm)

        input_label = {
            "meeting_minutes": "회의 내용",
            "report": "업무 내용",
            "proposal": "제안 내용",
        }.get(template_type, "내용")

        from ai.llm.prompts import DOC_GENERATE_SLLM_PROMPT
        user_prompt = (
            f"다음 내용을 바탕으로 문서를 JSON 형식으로 작성해주세요.\n\n"
            f"[문서 유형] {doc_type_name}\n\n"
            f"[필드 명세]\n{field_spec}\n\n"
            f"[{input_label}]\n{user_input}"
        )

        print(f"[DocumentAgent] sLLM 호출 | {len(fields_for_llm)}개 필드, 문서유형={doc_type_name}")
        generated_json_str = await _call_llm(DOC_GENERATE_SLLM_PROMPT, user_prompt, json_mode=True, task="generate")

        try:
            data = json.loads(generated_json_str)
        except Exception:
            data = {"content": user_input}

        content_val = data.get("content", "")
        if isinstance(content_val, dict):
            data["content"] = user_input
        elif isinstance(content_val, str) and content_val.strip().startswith("{"):
            data["content"] = user_input

        if not data.get("current_situation") and data.get("background"):
            data["current_situation"] = data["background"]

        for f in fields:
            if f["key"] not in data:
                desc = f.get("description", "")
                data[f["key"]] = [] if ("배열" in desc or "목록" in desc) else ""

    # 회의록: action_items 정규화 + 문자열 필드 변환
    if template_type == "meeting_minutes":
        for str_field in ("title", "summary"):
            data[str_field] = _to_readable_str(data.get(str_field, ""))

        _TASK_KEYS = ("task", "content", "item", "action", "할일", "내용", "업무", "name")
        _DUE_KEYS  = ("due_date", "deadline", "기한", "due", "end_date", "완료일")
        raw_ai = data.get("action_items", [])
        if isinstance(raw_ai, dict):
            raw_ai = list(raw_ai.values())
        normalized_ai = []
        for item in (raw_ai if isinstance(raw_ai, list) else []):
            if isinstance(item, str):
                normalized_ai.append({"task": item, "assignee": "", "due_date": ""})
            elif isinstance(item, dict):
                normalized_ai.append({
                    "task":     _first_val(item, _TASK_KEYS),
                    "assignee": _first_val(item, _ASSIGNEE_KEYS),
                    "due_date": _first_val(item, _DUE_KEYS),
                })
        data["action_items"] = normalized_ai
        print(f"[DocumentAgent] 커스텀 회의록 action_items 정규화: {len(normalized_ai)}개")

        # ── 후처리 fallback: decisions/action_items가 비어있으면 2차 추출 ──
        has_decisions = bool(data.get("decisions"))
        has_actions = bool(normalized_ai)
        if (not has_decisions or not has_actions) and data.get("content"):
            print(f"[DocumentAgent] 후처리 fallback 시작 | decisions={has_decisions}, action_items={has_actions}")
            extract_result = await _extract_decisions_actions(data["content"], data.get("summary", ""))
            if not has_decisions and extract_result.get("decisions"):
                data["decisions"] = extract_result["decisions"]
                print(f"[DocumentAgent] fallback decisions 추출: {len(data['decisions'])}개")
            if not has_actions and extract_result.get("action_items"):
                raw_fb = extract_result["action_items"]
                fb_normalized = []
                for item in (raw_fb if isinstance(raw_fb, list) else []):
                    if isinstance(item, str):
                        fb_normalized.append({"task": item, "assignee": "", "due_date": ""})
                    elif isinstance(item, dict):
                        fb_normalized.append({
                            "task":     _first_val(item, _TASK_KEYS),
                            "assignee": _first_val(item, _ASSIGNEE_KEYS),
                            "due_date": _first_val(item, _DUE_KEYS),
                        })
                data["action_items"] = fb_normalized
                print(f"[DocumentAgent] fallback action_items 추출: {len(fb_normalized)}개")

    # 보고서: tasks 정규화
    elif template_type == "report":
        for str_field in ("title", "overview", "main_content", "issues", "next_plan"):
            data[str_field] = _to_readable_str(data.get(str_field, ""))

        _ITEM_KEYS     = ("item", "task", "업무항목", "업무", "내용", "task_name", "name")
        _PROGRESS_KEYS = ("progress", "진행률", "rate", "completion", "status")
        _START_KEYS    = ("start_date", "start", "시작일", "started_at")
        _END_KEYS      = ("end_date", "end", "완료예정일", "due_date", "deadline", "due")

        raw_tasks = data.get("tasks", [])
        if isinstance(raw_tasks, dict):
            raw_tasks = list(raw_tasks.values())
        normalized_tasks = []
        for t in (raw_tasks if isinstance(raw_tasks, list) else []):
            if isinstance(t, str):
                normalized_tasks.append({"item": t, "assignee": "", "progress": "", "start_date": "", "end_date": ""})
            elif isinstance(t, dict):
                normalized_tasks.append({
                    "item":       _first_val(t, _ITEM_KEYS),
                    "assignee":   _first_val(t, _ASSIGNEE_KEYS),
                    "progress":   _first_val(t, _PROGRESS_KEYS),
                    "start_date": _first_val(t, _START_KEYS),
                    "end_date":   _first_val(t, _END_KEYS),
                })
        data["tasks"] = normalized_tasks
        print(f"[DocumentAgent] 커스텀 보고서 tasks 정규화: {len(normalized_tasks)}개")

    # 제안서: schedule + budget 정규화
    elif template_type == "proposal":
        for str_field in ("title", "background", "purpose", "analysis", "content", "expected_effect"):
            data[str_field] = _to_readable_str(data.get(str_field, ""))

        _SCH_ITEM_KEYS = ("item", "task", "추진항목", "업무", "name", "내용")
        _PHASE1_KEYS   = ("phase1", "1단계", "phase_1", "step1", "1차")
        _PHASE2_KEYS   = ("phase2", "2단계", "phase_2", "step2", "2차")
        _PHASE3_KEYS   = ("phase3", "3단계", "phase_3", "step3", "3차")
        _PHASE4_KEYS   = ("phase4", "4단계", "phase_4", "step4", "4차")

        raw_sch = data.get("schedule", [])
        if isinstance(raw_sch, dict):
            raw_sch = list(raw_sch.values())
        data["schedule"] = [
            {"item": _first_val(s, _SCH_ITEM_KEYS), "phase1": _first_val(s, _PHASE1_KEYS),
             "phase2": _first_val(s, _PHASE2_KEYS), "phase3": _first_val(s, _PHASE3_KEYS),
             "phase4": _first_val(s, _PHASE4_KEYS)}
            if isinstance(s, dict) else {"item": str(s), "phase1": "", "phase2": "", "phase3": "", "phase4": ""}
            for s in (raw_sch if isinstance(raw_sch, list) else [])
        ]
        print(f"[DocumentAgent] 커스텀 제안서 schedule 정규화: {len(data['schedule'])}개")

        _BUD_ITEM_KEYS = ("item", "항목", "name", "내용", "task")
        _QTY_KEYS      = ("quantity", "수량", "qty", "count")
        _UPRICE_KEYS   = ("unit_price", "단가", "price", "unit_cost", "단위가격")
        _AMOUNT_KEYS   = ("amount", "금액", "total", "합계", "비용", "cost")

        raw_bud = data.get("budget", [])
        if isinstance(raw_bud, dict):
            raw_bud = list(raw_bud.values())
        data["budget"] = [
            {"item": _first_val(b, _BUD_ITEM_KEYS), "quantity": _first_val(b, _QTY_KEYS),
             "unit_price": _first_val(b, _UPRICE_KEYS), "amount": _first_val(b, _AMOUNT_KEYS)}
            if isinstance(b, dict) else {"item": str(b), "quantity": "", "unit_price": "", "amount": ""}
            for b in (raw_bud if isinstance(raw_bud, list) else [])
        ]
        print(f"[DocumentAgent] 커스텀 제안서 budget 정규화: {len(data['budget'])}개")

    # 미리보기 생성
    preview_parts = [f"# {data.get('title', doc_type_name)}"]
    for f in fields:
        key = f["key"]
        val = data.get(key, "")
        if val and key != "title":
            label = f.get("label", key)
            if isinstance(val, list):
                val_str = "\n".join([f"- {item}" if isinstance(item, str) else f"- {json.dumps(item, ensure_ascii=False)}" for item in val])
                preview_parts.append(f"\n## {label}\n{val_str}")
            else:
                preview_parts.append(f"\n## {label}\n{val}")
    preview = "\n".join(preview_parts)

    doc_uuid = str(uuid.uuid4())
    GENERATED_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(GENERATED_DOCS_DIR / f"{doc_uuid}.docx")

    # fields_data가 있으면 사용자 수정값 반영 (fill-fields 결과를 이미 data로 쓴 경우 중복이지만 안전)
    if fields_data:
        for key, val in fields_data.items():
            if val not in (None, "", []):
                data[key] = val

    # DOCX 생성: 시스템 빌더 → 범용 레이아웃 순으로 분기
    # 커스텀 템플릿은 범용 레이아웃 사용 (원본 양식 레이아웃 보존이 불완전하므로)
    try:
        from ai.skills.create_from_template import create_generic_document

        is_system = getattr(template, "is_system", False) if template else False
        if is_system and template_type == "meeting_minutes":
            from ai.skills.create_meeting_minutes import create_meeting_minutes
            docx_data = {
                "title": data.get("title", "회의록"),
                "date": data.get("date", ""),
                "time": data.get("time", ""),
                "location": data.get("location", ""),
                "meeting_type": data.get("meeting_type", "정기"),
                "attendees": data.get("attendees", []),
                "author": data.get("author", ""),
                "content": data.get("content", data.get("summary", "")),
                "decisions": data.get("decisions", []),
                "action_items": data.get("action_items", []),
                "notes": data.get("notes", ""),
            }
            print(f"[DocumentAgent] 시스템 회의록 빌더로 DOCX 생성")
            create_meeting_minutes(output_path, docx_data)
        elif is_system and template_type == "report":
            from ai.skills.create_report import create_report
            print(f"[DocumentAgent] 시스템 보고서 빌더로 DOCX 생성")
            create_report(output_path, data)
        elif is_system and template_type == "proposal":
            from ai.skills.create_proposal import create_proposal
            print(f"[DocumentAgent] 시스템 제안서 빌더로 DOCX 생성")
            create_proposal(output_path, data)
        else:
            # 커스텀 템플릿 → 범용 레이아웃 (깔끔한 새 DOCX)
            print(f"[DocumentAgent] 범용 레이아웃으로 DOCX 생성")
            create_generic_document(output_path, data, fields, DOC_TYPE_NAMES.get(template_type, template_name))
        print(f"[DocumentAgent] 커스텀 DOCX 생성 완료: {output_path}")
    except Exception as e:
        print(f"[DocumentAgent] !!! 커스텀 DOCX 생성 실패: {e}")
        import traceback
        traceback.print_exc()

    return {
        "type": "doc_generate",
        "template_type": template_type,
        "template_id": template_id,
        "template_name": template_name,
        "preview": preview,
        "data": data,
        "document_id": doc_uuid,
        "docx_path": output_path,
        "download_url": f"/api/v1/documents/{doc_uuid}/download",
    }
