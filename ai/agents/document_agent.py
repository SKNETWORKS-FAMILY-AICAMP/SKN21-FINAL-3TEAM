"""
문서 Agent (팀원 C 담당)

기능:
  - 문서 검색 결과 반환 (doc_search)
  - 문서 생성 — 보고서/회의록/JD/제안서 (doc_generate)
  - 문서 요약 (doc_summary)
  - 문서 내용 기반 질의응답 (doc_qa)
  - 규정 리스크 자동 감지 (RAG 기반 규정 대조)

입출력:
  Input: AgentState (user_input, intent, context, template_id, document_id, document_content)
  Output: AgentState (agent_response 채움)
"""
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

GENERATED_DOCS_DIR = Path(__file__).resolve().parents[2] / "backend" / "generated_docs"

from ai.agents.state import AgentState
from ai.templates import get_system_template

# 로거 설정
logger = logging.getLogger(__name__)

async def document_agent(state: AgentState) -> AgentState:
    """
    문서 Agent 노드 함수 (LangGraph 노드 인터페이스)

    intent에 따라 분기:
      - doc_search: 문서 검색 결과 반환
      - doc_generate: 문서 생성 (보고서/회의록/JD/제안서)
      - doc_summary: 문서 요약
      - doc_qa: 문서 내용 기반 질의응답
    """
    intent = state.get("intent", "").lower()
    user_input = state.get("user_input", "")
    context = state.get("context", [])
    user_id = state.get("user_id")
    user_team = state.get("user_team")

    _t_agent = time.time()
    print(f"[DocumentAgent] 진입 | intent={intent}, user_input='{user_input[:50]}...', user_id={user_id}, user_team={user_team}")

    response_data = {}

    stream_mode = state.get("stream_mode", False)
    print(f"[DocumentAgent] stream_mode={stream_mode}, context 길이={len(context)}")

    try:
        if intent == "doc_search":
            print("[DocumentAgent] → _handle_doc_search 호출")
            response_data = await _handle_doc_search(user_input, context, user_id, user_team=user_team, stream_mode=stream_mode)

        elif intent == "doc_generate":
            # template_type 결정: ① state에서 프론트가 보낸 값 ② LLM 판단 ③ 키워드 fallback
            document_content = state.get("document_content") or state.get("extracted_text")
            template_type = state.get("template_type") or await _llm_detect_template_type(user_input)
            template_id = state.get("template_id")  # 커스텀 양식 ID (DB)
            print(f"[DocumentAgent] → _handle_doc_generate 호출 | template={template_type}, template_id={template_id}")
            response_data = await _handle_doc_generate(user_input, template_type, document_content, template_id=template_id)

        elif intent == "doc_summary":
            print("[DocumentAgent] → _handle_doc_summary 호출")
            document_content = state.get("document_content") or state.get("extracted_text")
            response_data = await _handle_doc_summary(
                user_input,
                document_content=document_content,
                user_id=user_id,
                user_team=user_team,
                stream_mode=stream_mode,
            )

        elif intent == "doc_qa":
            print("[DocumentAgent] → _handle_doc_qa 호출")
            response_data = await _handle_doc_qa(
                user_input,
                context=context,
                user_id=user_id,
                user_team=user_team,
                stream_mode=stream_mode,
            )

        elif intent == "risk_detect":
             print("[DocumentAgent] → _handle_risk_detect 호출")
             response_data = _handle_risk_detect(user_input)

        else:
            print(f"[DocumentAgent] !!! 지원하지 않는 intent: {intent}")
            response_data = {"error": f"지원하지 않는 intent입니다: {intent}"}

    except Exception as e:
        print(f"[DocumentAgent] !!! 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        response_data = {"error": str(e)}

    print(f"[DocumentAgent] 완료 ({time.time()-_t_agent:.2f}s) | response type={response_data.get('type')}, keys={list(response_data.keys())}")

    # 모델명 추가 (프론트에서 표시용)
    response_data["model_name"] = _last_model_name

    # State 업데이트
    state["agent_response"] = response_data
    return state


# ── 헬퍼 ──

def _to_readable_str(val) -> str:
    """LLM이 반환한 값을 사람이 읽을 수 있는 문자열로 변환.

    - str  → 그대로 반환
    - dict → "- key: value" 형태로 줄 구성
    - list → 각 항목을 "-" 로 시작하는 줄로 구성
             항목이 dict이면 values만 추출하여 " / " 로 연결
    """
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return "\n".join(f"- {k}: {v}" for k, v in val.items() if v)
    if isinstance(val, list):
        lines = []
        for item in val:
            if isinstance(item, dict):
                # dict 값들만 추출 (빈 값 제외) → "값1 / 값2" 형태
                parts = [str(v) for v in item.values() if v]
                lines.append("- " + " / ".join(parts) if parts else "")
            else:
                lines.append(f"- {item}")
        return "\n".join(l for l in lines if l)
    return str(val) if val else ""


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
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            return []

        engine = create_async_engine(db_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            from app.models.document_template import DocumentTemplate
            result = await session.execute(
                select(DocumentTemplate).where(
                    DocumentTemplate.category == category,
                    DocumentTemplate.is_system == False,  # noqa: E712
                ).order_by(DocumentTemplate.created_at.desc())
            )
            templates = result.scalars().all()

        await engine.dispose()

        items = []
        for t in templates:
            field_count = 0
            if t.parsed_structure:
                try:
                    field_count = len(json.loads(t.parsed_structure))
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


def _detect_search_intent(query: str) -> str:
    """사용자 질문에서 검색 의도 감지

    Args:
        query: 사용자 질문

    Returns:
        "summarize" | "find" | "explain"
    """
    query_lower = query.lower()

    # 요약 키워드 (최우선)
    if re.search(r"요약|정리|간단히|핵심|짧게", query_lower):
        return "summarize"

    # 찾기 키워드
    if re.search(r"찾아|검색|문서|어디|목록", query_lower):
        return "find"

    # 기본값: 설명
    return "explain"


def _build_search_prompt(query: str, context: list) -> tuple:
    """검색 의도에 맞는 시스템/유저 프롬프트 생성

    Returns:
        (sys_prompt, user_prompt)
    """
    intent_type = _detect_search_intent(query)

    if intent_type == "summarize":
        sys_prompt = """당신은 문서 요약 전문가입니다.

    [중요 지시사항]
    - 반드시 핵심 내용만 2-3문장으로 간결하게 요약하세요
    - 불필요한 세부사항은 절대 포함하지 마세요
    - 가장 중요한 정보만 선택하세요

    답변 시 Context에 포함된 정보만 사용하고, 추측하지 마세요."""

    elif intent_type == "find":
        sys_prompt = """당신은 문서 검색 전문가입니다.

    [관련성 판단 기준]
    - 사용자의 검색 키워드(사람 이름, 주제, 문서 유형 등)가 문서 내용에 포함되어 있으면 관련 문서입니다
    - 검색 키워드와 전혀 상관없는 문서는 나열하지 마세요

    [출력 규칙]
    - 각 문서의 제목은 반드시 [문서 제목: ...] 에 표시된 실제 제목을 사용하세요. 내용에서 추측하지 마세요.
    - 관련 문서가 있으면 "다음 문서들을 찾았습니다:" 형식으로 시작하고, 각 문서의 제목과 핵심 내용을 한 줄로 요약하세요
    - 관련 문서가 하나도 없으면 "관련 문서를 찾지 못했습니다. 다른 키워드로 검색해보세요."라고만 답하세요
    - 관련 있는 문서는 빠뜨리지 마세요

    답변 시 Context에 포함된 정보만 사용하고, 추측하지 마세요."""

    else:  # explain
        sys_prompt = """당신은 문서 설명 전문가입니다.

    [중요 지시사항]
    - 관련 내용을 상세히 설명하세요 (5문장 이상)
    - 조건, 절차, 예외사항 등을 포함하세요
    - 이해하기 쉽게 구조화하여 설명하세요

    답변 시 Context에 포함된 정보만 사용하고, 추측하지 마세요."""

    user_prompt = f"Context:\n{json.dumps(context, ensure_ascii=False)}\n\nQuestion: {query}"

    return sys_prompt, user_prompt

# ── Intent 핸들러 ──

async def _handle_doc_search(query: str, context: List[str], user_id: int = None, user_team: str = None, stream_mode: bool = False) -> Dict[str, Any]:
    """문서 검색 결과 처리"""
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_search | query='{query[:50]}', context 길이={len(context)}, stream_mode={stream_mode}")
    search_results = []

    # 1. Context가 비어있으면 RAG 검색 수행
    if not context:
        try:
            from ai.rag.qdrant_pipeline import get_qdrant_pipeline

            _t_rag = time.time()
            print(f"[DocumentAgent] RAG 검색 수행: '{query[:50]}'")
            rag_pipeline = get_qdrant_pipeline()
            search_results = rag_pipeline.retrieve(query, user_id=user_id, user_team=user_team, top_k=5, filter={"source": "documents"})

            # 검색된 문서의 content를 context로 사용
            context = [f"[문서 제목: {doc.get('title', '')}]\n{doc['content']}" for doc in search_results]
            print(f"[DocumentAgent] RAG 검색 완료 ({time.time()-_t_rag:.2f}s): {len(context)}개 문서 검색됨")

        except Exception as e:
            print(f"[DocumentAgent] !!! RAG 검색 실패: {e}")
            import traceback
            traceback.print_exc()
            context = []

    # 2. 출처 정보 (답변 + 출처 분리, 중복 제거)
    sources = _build_sources(search_results)
    print(f"[DocumentAgent] 출처 정보: {len(sources)}개")

    # 3. Context가 없으면 검색 실패 (절대 점수 필터링으로 모두 제거된 경우 포함)
    if not context:
        print("[DocumentAgent] context 비어있음 → 관련 문서 없음 응답")
        return {
            "type": "doc_search",
            "answer": "관련 문서를 찾지 못했습니다. 다른 키워드로 검색해보세요.",
            "message": "관련 문서를 찾지 못했습니다. 다른 키워드로 검색해보세요.",
            "sources": [],
            "context": context,
        }

    # 4. 프롬프트 생성
    sys_prompt, user_prompt = _build_search_prompt(query, context)
    print(f"[DocumentAgent] 프롬프트 생성 완료 | search_intent={_detect_search_intent(query)}")

    # 5. 스트리밍 모드면 LLM 호출 건너뛰기 (chat.py에서 직접 스트리밍)
    if stream_mode:
        print(f"[DocumentAgent] stream_mode=True → stream_pending 반환 ({time.time()-_t:.2f}s)")
        return {
            "type": "doc_search",
            "stream_pending": True,
            "sys_prompt": sys_prompt,
            "user_prompt": user_prompt,
            "answer": "",
            "message": "",
            "sources": sources,
            "context": context,
        }

    # 6. 비스트리밍: LLM 호출
    print("[DocumentAgent] stream_mode=False → LLM 직접 호출")
    answer = await _call_llm(sys_prompt, user_prompt)
    print(f"[DocumentAgent] LLM 응답 길이: {len(answer)}자")

    return {
        "type": "doc_search",
        "answer": answer,
        "message": answer,
        "sources": sources,
        "context": context,
    }

async def _handle_doc_generate(user_input: str, template_type: str, document_content: str = None, template_id: int = None) -> Dict[str, Any]:
    """문서 생성 처리 (보고서/회의록/JD/제안서 + 커스텀 양식)"""
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_generate | template_type={template_type}, template_id={template_id}")

    if document_content:
        user_input = f"{user_input}\n\n[첨부 문서 내용]\n{document_content}"

    if len(user_input.strip()) < 20:
        return {
            "type": "clarify",
            "message": "문서 생성을 위한 내용이 부족합니다.\n화면의 **[📎 첨부 버튼]**을 눌러 기준 문서를 업로드하시거나, 작성할 내용을 좀 더 자세히 입력해주세요."
        }

    # 커스텀 양식 (DB에 등록된 template_id)이 있으면 동적 필드로 생성
    if template_id:
        return await _generate_with_custom_template(user_input, template_id, template_type)

    # 챗봇 요청: 해당 카테고리에 커스텀 템플릿이 있으면 선택지 제공
    if template_type in ("meeting_minutes", "report", "proposal"):
        custom_templates = await _query_custom_templates(template_type)
        doc_type_names = {
            "meeting_minutes": "회의록",
            "report": "보고서",
            "proposal": "제안서",
        }
        type_label = doc_type_names.get(template_type, template_type)

        # 시스템 기본 + 커스텀 목록 구성
        all_templates = [{"template_id": None, "name": f"기본 {type_label}", "is_system": True}]
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

        # 1개(기본만)면 바로 생성
        if template_type == "meeting_minutes":
            return await _generate_meeting_minutes(user_input)
        if template_type == "report":
            return await _generate_report(user_input)
        if template_type == "proposal":
            return await _generate_proposal(user_input)

    # 1. 템플릿 가져오기
    try:
        template = get_system_template(template_type)
        print(f"[DocumentAgent] 템플릿 로드 성공: {template_type}")
    except ValueError:
        print(f"[DocumentAgent] 템플릿 '{template_type}' 없음 → report fallback")
        try:
            template = get_system_template("report") # Fallback
        except Exception:
            template = None

    # 2. LLM이 템플릿 필드 채우기
    required_fields = template.REQUIRED_FIELDS if template and hasattr(template, 'REQUIRED_FIELDS') else 'all'

    sys_prompt = f"당신은 문서 작성 도우미입니다. 사용자의 요청을 바탕으로 '{template_type}' JSON 데이터를 생성하세요."
    user_prompt = f"요청: {user_input}\n\n필수 필드: {required_fields}"

    print(f"[DocumentAgent] LLM 호출 (doc_generate, json_mode=True)...")
    generated_json_str = await _call_llm(sys_prompt, user_prompt, json_mode=True)
    print(f"[DocumentAgent] LLM 응답: {generated_json_str[:200]}...")
    try:
        data = json.loads(generated_json_str)
        print(f"[DocumentAgent] JSON 파싱 성공 | keys={list(data.keys())}")
    except json.JSONDecodeError:
        print(f"[DocumentAgent] !!! JSON 파싱 실패 → fallback")
        data = {"content": generated_json_str} # Fallback

    # 3. 템플릿 렌더링 (Markdown)
    preview = f"# {data.get('title', '문서')}\n\n{data.get('content', '내용 없음')}"

    return {
        "type": "doc_generate",
        "template_type": template_type,
        "template_id": None,
        "template_name": template.template_name if template else template_type,
        "preview": preview,
        "data": data,
        "document_id": 123, # Mock ID
        "download_url": "/api/v1/documents/123/download"
    }


async def _generate_meeting_minutes(user_input: str) -> Dict[str, Any]:
    """회의록 생성 (doc_generate의 meeting_minutes 분기)"""
    _t = time.time()
    print(f"[DocumentAgent] _generate_meeting_minutes | input='{user_input[:80]}...'")

    from ai.llm.prompts import DOC_GENERATE_SLLM_PROMPT
    sys_prompt = DOC_GENERATE_SLLM_PROMPT
    user_prompt = (
        f"다음 내용을 바탕으로 문서를 JSON 형식으로 작성해주세요.\n\n"
        f"[문서 유형] 회의록\n\n"
        f"[필드 명세]\n"
        f"- title: 회의 주제를 반영한 구체적인 제목\n"
        f"- date: 회의 날짜 (YYYY-MM-DD 형식, 없으면 오늘 날짜)\n"
        f"- attendees: 참석자 이름 배열 (없으면 빈 배열)\n"
        f"- summary: 회의에서 논의된 주요 내용을 3~5문장으로 요약\n"
        f"- decisions: 결정된 사항 목록 (배열, 없으면 빈 배열)\n"
        f'- action_items: 후속 조치 목록 배열. 각 항목은 {{"content": "내용", "assignee": "담당자", "due_date": "기한"}} 형태\n'
        f'- risks: 리스크 목록 배열. 각 항목은 {{"description": "설명", "level": "상/중/하", "mitigation": "대응방안"}} 형태\n\n'
        f"[회의 내용]\n{user_input}"
    )

    print(f"[DocumentAgent] LLM 호출 (meeting_minutes, json_mode=True)...")
    generated_json_str = await _call_llm(sys_prompt, user_prompt, json_mode=True, task="generate")
    print(f"[DocumentAgent] LLM 응답: {generated_json_str[:200]}...")
    try:
        data = json.loads(generated_json_str)
        print(f"[DocumentAgent] JSON 파싱 성공 | keys={list(data.keys())}")
    except Exception:
        print(f"[DocumentAgent] !!! JSON 파싱 실패")
        data = {"summary": "파싱 실패", "content": generated_json_str}

    # LLM이 문자열 필드를 dict/list로 반환하는 경우 사람이 읽을 수 있게 변환
    for str_field in ("title", "summary"):
        data[str_field] = _to_readable_str(data.get(str_field, ""))

    # action_items 정규화: create_meeting_minutes.py 기대 키 → content, assignee, due_date
    _CONTENT_KEYS  = ("content", "task", "item", "action", "할일", "내용", "업무", "name")
    _ASSIGNEE_KEYS = ("assignee", "person", "담당자", "owner", "assigned_to")
    _DUE_KEYS      = ("due_date", "deadline", "기한", "due", "end_date", "완료일")

    def _first_val(d: dict, keys):
        for k in keys:
            if k in d and d[k]:
                return str(d[k])
        return ""

    raw_ai = data.get("action_items", [])
    if isinstance(raw_ai, dict):
        raw_ai = list(raw_ai.values())
    normalized_ai = []
    for item in (raw_ai if isinstance(raw_ai, list) else []):
        if isinstance(item, str):
            normalized_ai.append({"content": item, "assignee": "", "due_date": ""})
        elif isinstance(item, dict):
            normalized_ai.append({
                "content":  _first_val(item, _CONTENT_KEYS),
                "assignee": _first_val(item, _ASSIGNEE_KEYS),
                "due_date": _first_val(item, _DUE_KEYS),
            })
    data["action_items"] = normalized_ai
    print(f"[DocumentAgent] action_items 정규화 완료: {len(normalized_ai)}개")

    # 회의록 미리보기
    preview = f"""# {data.get('title', '회의록')}

    ## 요약
    {data.get('summary', '')}

    ## 결정사항
    {chr(10).join(['- ' + d for d in data.get('decisions', [])])}

    ## Action Items
    {chr(10).join([f"- {ai.get('content')} ({ai.get('assignee')})" for ai in data.get('action_items', [])])}"""

    # DOCX 파일 생성
    doc_uuid = str(uuid.uuid4())
    GENERATED_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(GENERATED_DOCS_DIR / f"{doc_uuid}.docx")

    attendees = data.get("attendees", [])
    docx_data = {
        "title": data.get("title", "회의록"),
        "date": data.get("date", ""),
        "time": data.get("time", ""),
        "location": data.get("location", ""),
        "meeting_type": data.get("meeting_type", "정기"),
        "attendees": attendees,
        "author": data.get("author", attendees[0] if attendees else ""),
        "content": data.get("summary", ""),
        "decisions": data.get("decisions", []),
        "action_items": data.get("action_items", []),
        "notes": data.get("notes", ""),
    }

    try:
        from ai.skills.create_meeting_minutes import create_meeting_minutes
        create_meeting_minutes(output_path, docx_data)
        print(f"[DocumentAgent] DOCX 생성 완료: {output_path}")
    except Exception as e:
        print(f"[DocumentAgent] !!! DOCX 생성 실패: {e}")
        import traceback
        traceback.print_exc()

    return {
        "type": "doc_generate",
        "template_type": "meeting_minutes",
        "template_id": None,
        "template_name": "회의록",
        "summary": data.get("summary"),
        "decisions": data.get("decisions", []),
        "action_items": data.get("action_items", []),
        "risks": data.get("risks", []),
        "preview": preview,
        "data": data,
        "document_id": doc_uuid,
        "docx_path": output_path,
        "download_url": f"/api/v1/documents/{doc_uuid}/download",
    }


async def _generate_report(user_input: str) -> Dict[str, Any]:
    """업무보고서 생성"""
    _t = time.time()
    print(f"[DocumentAgent] _generate_report | input='{user_input[:80]}...'")

    from ai.llm.prompts import DOC_GENERATE_SLLM_PROMPT
    sys_prompt = DOC_GENERATE_SLLM_PROMPT
    user_prompt = (
        f"다음 내용을 바탕으로 문서를 JSON 형식으로 작성해주세요.\n\n"
        f"[문서 유형] 업무보고서\n\n"
        f"[필드 명세]\n"
        f"- title: 업무 내용을 반영한 구체적인 보고서 제목\n"
        f"- author: 작성자 이름 (없으면 빈 문자열)\n"
        f"- date: 작성 날짜 (YYYY-MM-DD 형식)\n"
        f"- department: 부서명 (없으면 빈 문자열)\n"
        f"- position: 직급 (없으면 빈 문자열)\n"
        f"- report_to: 보고 대상 (없으면 빈 문자열)\n"
        f"- report_type: '일일', '주간', '월간', '수시' 중 하나\n"
        f"- overview: 업무 내용을 요약한 보고 개요 (3~5문장)\n"
        f"- main_content: 업무 세부 내용을 항목별로 구체적으로 작성\n"
        f'- tasks: 진행 업무 목록 배열. 각 항목은 {{"item": "업무명", "assignee": "담당자", "progress": "진행률", "start_date": "시작일", "end_date": "종료일"}} 형태\n'
        f"- issues: 이슈 및 건의사항 (없으면 빈 문자열)\n"
        f"- next_plan: 향후 계획 (구체적으로 작성)\n\n"
        f"[업무 내용]\n{user_input}"
    )

    generated_json_str = await _call_llm(sys_prompt, user_prompt, json_mode=True, task="generate")
    try:
        data = json.loads(generated_json_str)
        print(f"[DocumentAgent] JSON 파싱 성공 | keys={list(data.keys())}")
    except Exception:
        print(f"[DocumentAgent] !!! JSON 파싱 실패")
        data = {"overview": "파싱 실패", "main_content": generated_json_str}

    # LLM이 문자열 필드를 dict/list로 반환하는 경우 사람이 읽을 수 있게 변환
    for str_field in ("title", "overview", "main_content", "issues", "next_plan"):
        data[str_field] = _to_readable_str(data.get(str_field, ""))

    # tasks 정규화: 다양한 키 이름을 표준 키(item/assignee/progress/start_date/end_date)로 통일
    _ITEM_KEYS     = ("item", "task", "업무항목", "업무", "내용", "task_name", "name")
    _ASSIGNEE_KEYS = ("assignee", "person", "담당자", "owner", "assigned_to")
    _PROGRESS_KEYS = ("progress", "진행률", "rate", "completion", "status")
    _START_KEYS    = ("start_date", "start", "시작일", "started_at")
    _END_KEYS      = ("end_date", "end", "완료예정일", "due_date", "deadline", "due")

    def _first(d: dict, keys):
        for k in keys:
            if k in d and d[k]:
                return str(d[k])
        return ""

    raw_tasks = data.get("tasks", [])
    if isinstance(raw_tasks, dict):
        raw_tasks = list(raw_tasks.values())
    normalized_tasks = []
    for t in (raw_tasks if isinstance(raw_tasks, list) else []):
        if isinstance(t, str):
            normalized_tasks.append({"item": t, "assignee": "", "progress": "", "start_date": "", "end_date": ""})
        elif isinstance(t, dict):
            normalized_tasks.append({
                "item":       _first(t, _ITEM_KEYS),
                "assignee":   _first(t, _ASSIGNEE_KEYS),
                "progress":   _first(t, _PROGRESS_KEYS),
                "start_date": _first(t, _START_KEYS),
                "end_date":   _first(t, _END_KEYS),
            })
    data["tasks"] = normalized_tasks
    print(f"[DocumentAgent] tasks 정규화 완료: {len(normalized_tasks)}개")

    overview = data.get('overview', '')
    main_content = data.get('main_content', '')
    next_plan = data.get('next_plan', '')

    preview = f"""# {data.get('title', '업무보고서')}

## 보고 개요
{overview}

## 주요 내용
{main_content}

## 향후 계획
{next_plan}"""

    doc_uuid = str(uuid.uuid4())
    GENERATED_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(GENERATED_DOCS_DIR / f"{doc_uuid}.docx")

    try:
        from ai.skills.create_report import create_report
        create_report(output_path, data)
        print(f"[DocumentAgent] 업무보고서 DOCX 생성 완료: {output_path}")
    except Exception as e:
        print(f"[DocumentAgent] !!! 업무보고서 DOCX 생성 실패: {e}")
        import traceback
        traceback.print_exc()

    return {
        "type": "doc_generate",
        "template_type": "report",
        "template_name": "업무보고서",
        "preview": preview,
        "data": data,
        "document_id": doc_uuid,
        "docx_path": output_path,
        "download_url": f"/api/v1/documents/{doc_uuid}/download",
    }


async def _generate_proposal(user_input: str) -> Dict[str, Any]:
    """제안서 생성"""
    _t = time.time()
    print(f"[DocumentAgent] _generate_proposal | input='{user_input[:80]}...'")

    from ai.llm.prompts import DOC_GENERATE_SLLM_PROMPT
    sys_prompt = DOC_GENERATE_SLLM_PROMPT
    user_prompt = (
        f"다음 내용을 바탕으로 문서를 JSON 형식으로 작성해주세요.\n\n"
        f"[문서 유형] 제안서\n\n"
        f"[필드 명세]\n"
        f"- title: 제안 내용을 반영한 구체적인 제안서 제목\n"
        f"- submit_date: 제출 날짜 (YYYY-MM-DD, 없으면 오늘 날짜)\n"
        f"- submit_to: 제출처 (없으면 빈 문자열)\n"
        f"- company: 제안사 이름 (없으면 빈 문자열)\n"
        f"- manager: 담당자 이름 (없으면 빈 문자열)\n"
        f"- contact: 연락처 (없으면 빈 문자열)\n"
        f"- purpose: 제안 목적 및 필요성 (3~5문장)\n"
        f"- background: 제안 배경 (2~3문장)\n"
        f"- content: 제안 내용을 항목별로 구체적으로 작성\n"
        f'- schedule: 추진 일정 배열. 각 항목은 {{"phase": "단계", "task": "업무", "period": "기간"}} 형태\n'
        f'- budget: 예산 배열. 각 항목은 {{"item": "항목", "amount": "금액"}} 형태\n'
        f"- budget_total: 합계 금액 (없으면 빈 문자열)\n"
        f"- expected_effect: 기대 효과 (3~5문장)\n\n"
        f"[제안 내용]\n{user_input}"
    )

    generated_json_str = await _call_llm(sys_prompt, user_prompt, json_mode=True, task="generate")
    try:
        data = json.loads(generated_json_str)
        print(f"[DocumentAgent] JSON 파싱 성공 | keys={list(data.keys())}")
    except Exception:
        print(f"[DocumentAgent] !!! JSON 파싱 실패")
        data = {"purpose": "파싱 실패", "content": generated_json_str}

    # LLM이 문자열 필드를 dict/list로 반환하는 경우 사람이 읽을 수 있게 변환
    for str_field in ("title", "background", "purpose", "analysis", "content", "expected_effect"):
        data[str_field] = _to_readable_str(data.get(str_field, ""))

    # schedule 정규화: create_proposal.py 기대 키 → item, phase1, phase2, phase3, phase4
    _SCH_ITEM_KEYS   = ("item", "task", "추진항목", "업무", "name", "내용")
    _PHASE1_KEYS     = ("phase1", "1단계", "phase_1", "step1", "1차")
    _PHASE2_KEYS     = ("phase2", "2단계", "phase_2", "step2", "2차")
    _PHASE3_KEYS     = ("phase3", "3단계", "phase_3", "step3", "3차")
    _PHASE4_KEYS     = ("phase4", "4단계", "phase_4", "step4", "4차")

    def _fv(d, keys):
        for k in keys:
            if k in d and d[k]:
                return str(d[k])
        return ""

    raw_sch = data.get("schedule", [])
    if isinstance(raw_sch, dict):
        raw_sch = list(raw_sch.values())
    data["schedule"] = [
        {"item": _fv(s, _SCH_ITEM_KEYS), "phase1": _fv(s, _PHASE1_KEYS),
         "phase2": _fv(s, _PHASE2_KEYS), "phase3": _fv(s, _PHASE3_KEYS),
         "phase4": _fv(s, _PHASE4_KEYS)}
        if isinstance(s, dict) else {"item": str(s), "phase1": "", "phase2": "", "phase3": "", "phase4": ""}
        for s in (raw_sch if isinstance(raw_sch, list) else [])
    ]
    print(f"[DocumentAgent] schedule 정규화 완료: {len(data['schedule'])}개")

    # budget 정규화: create_proposal.py 기대 키 → item, quantity, unit_price, amount
    _BUD_ITEM_KEYS  = ("item", "항목", "name", "내용", "task")
    _QTY_KEYS       = ("quantity", "수량", "qty", "count")
    _UPRICE_KEYS    = ("unit_price", "단가", "price", "unit_cost", "단위가격")
    _AMOUNT_KEYS    = ("amount", "금액", "total", "합계", "비용", "cost")

    raw_bud = data.get("budget", [])
    if isinstance(raw_bud, dict):
        raw_bud = list(raw_bud.values())
    data["budget"] = [
        {"item": _fv(b, _BUD_ITEM_KEYS), "quantity": _fv(b, _QTY_KEYS),
         "unit_price": _fv(b, _UPRICE_KEYS), "amount": _fv(b, _AMOUNT_KEYS)}
        if isinstance(b, dict) else {"item": str(b), "quantity": "", "unit_price": "", "amount": ""}
        for b in (raw_bud if isinstance(raw_bud, list) else [])
    ]
    print(f"[DocumentAgent] budget 정규화 완료: {len(data['budget'])}개")

    preview = f"""# {data.get('title', '제안서')}

## 제안 배경
{data.get('background', '')}

## 제안 내용
{data.get('content', '')}

## 기대 효과
{data.get('expected_effect', '')}"""

    doc_uuid = str(uuid.uuid4())
    GENERATED_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(GENERATED_DOCS_DIR / f"{doc_uuid}.docx")

    try:
        from ai.skills.create_proposal import create_proposal
        create_proposal(output_path, data)
        print(f"[DocumentAgent] 제안서 DOCX 생성 완료: {output_path}")
    except Exception as e:
        print(f"[DocumentAgent] !!! 제안서 DOCX 생성 실패: {e}")
        import traceback
        traceback.print_exc()

    return {
        "type": "doc_generate",
        "template_type": "proposal",
        "template_name": "제안서",
        "preview": preview,
        "data": data,
        "document_id": doc_uuid,
        "docx_path": output_path,
        "download_url": f"/api/v1/documents/{doc_uuid}/download",
    }


async def _generate_with_custom_template(user_input: str, template_id: int, template_type: str) -> Dict[str, Any]:
    """커스텀 양식(DB 등록)으로 문서 생성 — 동적 필드 명세"""
    _t = time.time()
    print(f"[DocumentAgent] _generate_with_custom_template | template_id={template_id}")

    # DB에서 parsed_structure 조회
    try:
        import asyncio
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        import os

        db_url = os.getenv("DATABASE_URL", "")
        engine = create_async_engine(db_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            from app.models.document_template import DocumentTemplate
            result = await session.execute(
                select(DocumentTemplate).where(DocumentTemplate.id == template_id)
            )
            template = result.scalar_one_or_none()

        await engine.dispose()

        if not template or not template.parsed_structure:
            print(f"[DocumentAgent] template_id={template_id} 없거나 parsed_structure 없음 → 기본 생성")
            if template_type == "meeting_minutes":
                return await _generate_meeting_minutes(user_input)
            elif template_type == "report":
                return await _generate_report(user_input)
            elif template_type == "proposal":
                return await _generate_proposal(user_input)

        fields = json.loads(template.parsed_structure)
        template_name = template.name
        print(f"[DocumentAgent] 커스텀 양식 '{template_name}' 로드 | {len(fields)}개 필드")

    except Exception as e:
        print(f"[DocumentAgent] DB 조회 실패: {e} → 기본 생성 fallback")
        import traceback
        traceback.print_exc()
        if template_type == "meeting_minutes":
            return await _generate_meeting_minutes(user_input)
        elif template_type == "report":
            return await _generate_report(user_input)
        return await _generate_proposal(user_input)

    # 동적 필드 명세 생성
    from ai.document_parser.template_extractor import fields_to_prompt
    field_spec = fields_to_prompt(fields)

    # 문서 유형명 결정
    doc_type_names = {
        "meeting_minutes": "회의록",
        "report": "업무보고서",
        "proposal": "제안서",
    }
    doc_type_name = doc_type_names.get(template_type, template_name)
    input_label = {
        "meeting_minutes": "회의 내용",
        "report": "업무 내용",
        "proposal": "제안 내용",
    }.get(template_type, "내용")

    # sLLM용 프롬프트 (학습 데이터와 동일한 형식)
    from ai.llm.prompts import DOC_GENERATE_SLLM_PROMPT
    sys_prompt = DOC_GENERATE_SLLM_PROMPT
    user_prompt = (
        f"다음 내용을 바탕으로 문서를 JSON 형식으로 작성해주세요.\n\n"
        f"[문서 유형] {doc_type_name}\n\n"
        f"[필드 명세]\n{field_spec}\n\n"
        f"[{input_label}]\n{user_input}"
    )

    print(f"[DocumentAgent] 동적 프롬프트 생성 | 필드 {len(fields)}개, 문서유형={doc_type_name}")
    generated_json_str = await _call_llm(sys_prompt, user_prompt, json_mode=True, task="generate")

    try:
        data = json.loads(generated_json_str)
        print(f"[DocumentAgent] JSON 파싱 성공 | keys={list(data.keys())}")
    except Exception:
        print(f"[DocumentAgent] !!! JSON 파싱 실패")
        data = {"content": generated_json_str}

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

    # category에 맞는 기존 DOCX 빌더 재활용
    try:
        if template_type == "meeting_minutes":
            from ai.skills.create_meeting_minutes import create_meeting_minutes
            attendees = data.get("attendees", [])
            docx_data = {
                "title": data.get("title", "회의록"),
                "date": data.get("date", ""),
                "time": data.get("time", ""),
                "location": data.get("location", ""),
                "meeting_type": data.get("meeting_type", "정기"),
                "attendees": attendees,
                "author": data.get("author", attendees[0] if attendees else ""),
                "content": data.get("summary", data.get("content", "")),
                "decisions": data.get("decisions", []),
                "action_items": data.get("action_items", []),
                "notes": data.get("notes", ""),
            }
            create_meeting_minutes(output_path, docx_data)
        elif template_type == "report":
            from ai.skills.create_report import create_report
            docx_data = {
                "title": data.get("title", "업무보고서"),
                "author": data.get("author", ""),
                "date": data.get("date", ""),
                "department": data.get("department", ""),
                "position": data.get("position", ""),
                "report_to": data.get("report_to", ""),
                "report_type": data.get("report_type", "수시"),
                "overview": data.get("overview", ""),
                "main_content": data.get("main_content", ""),
                "tasks": data.get("tasks", []),
                "issues": data.get("issues", ""),
                "next_plan": data.get("next_plan", ""),
            }
            create_report(output_path, docx_data)
        elif template_type == "proposal":
            from ai.skills.create_proposal import create_proposal
            docx_data = {
                "title": data.get("title", "제안서"),
                "submit_date": data.get("submit_date", data.get("date", "")),
                "submit_to": data.get("submit_to", ""),
                "company": data.get("company", ""),
                "manager": data.get("manager", ""),
                "contact": data.get("contact", ""),
                "purpose": data.get("purpose", ""),
                "background": data.get("background", ""),
                "content": data.get("content", ""),
                "schedule": data.get("schedule", []),
                "budget": data.get("budget", []),
                "expected_effect": data.get("expected_effect", ""),
            }
            create_proposal(output_path, docx_data)
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


async def _handle_doc_summary(user_input: str, document_content: str = None, user_id: int = None, user_team: str = None, stream_mode: bool = False) -> Dict[str, Any]:
    """문서 요약 처리"""
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_summary | content_len={len(document_content) if document_content else 0}, stream_mode={stream_mode}")
    # DEBUG: document_content 앞부분 미리보기
    if document_content:
        print(f"[DocumentAgent] document_content 미리보기 (앞 300자):\n{document_content[:300]}")
    else:
        print(f"[DocumentAgent] document_content 없음 → Qdrant 문서 목록 조회")

    # 문서 내용이 없으면 Qdrant에서 문서 목록 조회 후 doc_pick 반환
    if not document_content:
        print("[DocumentAgent] document_content 없음 → Qdrant 문서 목록 조회")
        try:
            from ai.rag.qdrant_pipeline import get_qdrant_pipeline
            pipeline = get_qdrant_pipeline()
            doc_list = pipeline.list_documents(source="documents", user_id=user_id)
            print(f"[DocumentAgent] Qdrant 문서 목록 {len(doc_list)}개 조회됨")
        except Exception as e:
            print(f"[DocumentAgent] Qdrant 문서 목록 조회 실패: {e}")
            doc_list = []
        return {
            "type": "doc_pick",
            "message": "요약할 문서를 선택해주세요:",
            "documents": doc_list,
        }

    from ai.llm.prompts import DOC_SUMMARY_SYSTEM_PROMPT

    sys_prompt = DOC_SUMMARY_SYSTEM_PROMPT
    # 문서 내용이 너무 길면 앞부분만 사용 (토큰 제한)
    truncated = document_content[:8000] if len(document_content) > 8000 else document_content
    user_prompt = f"다음 문서를 요약해주세요.\n\n사용자 요청: {user_input}\n\n문서 내용:\n{truncated}"

    # 스트리밍 모드: stream_pending 패턴 (doc_search와 동일)
    if stream_mode:
        print(f"[DocumentAgent] stream_mode=True → stream_pending 반환 ({time.time()-_t:.2f}s)")
        return {
            "type": "doc_summary",
            "stream_pending": True,
            "sys_prompt": sys_prompt,
            "user_prompt": user_prompt,
            "answer": "",
            "message": "",
        }

    # 비스트리밍: LLM 직접 호출
    print("[DocumentAgent] stream_mode=False → LLM 직접 호출 (doc_summary)")
    answer = await _call_llm(sys_prompt, user_prompt, task="summary")
    print(f"[DocumentAgent] LLM 응답 길이: {len(answer)}자")

    return {
        "type": "doc_summary",
        "answer": answer,
        "message": answer,
    }


async def _handle_doc_qa(query: str, context: list = None, user_id: int = None, user_team: str = None, stream_mode: bool = False) -> Dict[str, Any]:
    """문서 내용 기반 질의응답"""
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_qa | query='{query[:50]}', context_len={len(context) if context else 0}, stream_mode={stream_mode}")
    search_results = []

    # Context가 비어있으면 RAG 검색
    if not context:
        try:
            from ai.rag.qdrant_pipeline import get_qdrant_pipeline

            _t_rag = time.time()
            print(f"[DocumentAgent] RAG 검색 수행 (doc_qa): '{query[:50]}'")
            rag_pipeline = get_qdrant_pipeline()
            search_results = rag_pipeline.retrieve(query, user_id=user_id, user_team=user_team, top_k=5, filter={"source": "documents"})
            context = [f"[문서 제목: {doc.get('title', '')}]\n{doc['content']}" for doc in search_results]
            print(f"[DocumentAgent] RAG 검색 완료 ({time.time()-_t_rag:.2f}s): {len(context)}개 문서")

        except Exception as e:
            print(f"[DocumentAgent] !!! RAG 검색 실패: {e}")
            import traceback
            traceback.print_exc()
            context = []

    # 출처 정보 구성
    sources = _build_sources(search_results)

    # Context가 없으면 실패 (절대 점수 필터링으로 모두 제거된 경우 포함)
    if not context:
        print("[DocumentAgent] context 비어있음 → 관련 문서 없음 응답")
        return {
            "type": "doc_qa",
            "answer": "관련 문서를 찾지 못했습니다. 다른 질문을 시도해보세요.",
            "message": "관련 문서를 찾지 못했습니다. 다른 질문을 시도해보세요.",
            "sources": [],
            "citations": [],
            "confidence": 0.0,
        }

    from ai.llm.prompts import DOC_QA_SYSTEM_PROMPT

    # 스트리밍 모드: answer 텍스트만 토큰으로 전송, sources는 result 이벤트로
    if stream_mode:
        # 스트리밍용 프롬프트 (자연어 답변 → sources는 별도 전달)
        sys_prompt = """당신은 기업 문서 기반 질의응답 전문가입니다.
    주어진 문서 내용을 근거로 사용자의 질문에 정확하게 답변하세요.

    규칙:
    - 반드시 제공된 문서 내용만을 근거로 답변하세요.
    - 답변 근거가 되는 문서를 언급하세요.
    - 문서에서 답을 찾을 수 없으면 솔직히 답하세요.
    - 한국어로 답변하세요."""

        user_prompt = f"Context:\n{json.dumps(context, ensure_ascii=False)}\n\nQuestion: {query}"

        print(f"[DocumentAgent] stream_mode=True → stream_pending 반환 ({time.time()-_t:.2f}s)")
        return {
            "type": "doc_qa",
            "stream_pending": True,
            "sys_prompt": sys_prompt,
            "user_prompt": user_prompt,
            "answer": "",
            "message": "",
            "sources": sources,
        }

    # 비스트리밍: JSON mode로 구조화된 응답
    user_prompt = f"Context:\n{json.dumps(context, ensure_ascii=False)}\n\nQuestion: {query}"
    print("[DocumentAgent] stream_mode=False → LLM 직접 호출 (doc_qa, json_mode)")
    answer_json_str = await _call_llm(DOC_QA_SYSTEM_PROMPT, user_prompt, json_mode=True, task="qa")

    try:
        qa_result = json.loads(answer_json_str)
    except json.JSONDecodeError:
        qa_result = {"answer": answer_json_str, "citations": [], "confidence": 0.5}

    return {
        "type": "doc_qa",
        "answer": qa_result.get("answer", ""),
        "message": qa_result.get("answer", ""),
        "citations": qa_result.get("citations", []),
        "confidence": qa_result.get("confidence", 0.5),
        "sources": sources,
    }


def _handle_risk_detect(user_input: str) -> Dict[str, Any]:
    """리스크 감지"""
    # 구현 필요
    return {"type": "risk_detect", "risks": []}


# ── 공통 유틸 ──

def _build_sources(search_results: list) -> list:
    """검색 결과에서 출처 정보 구성 (중복 제거)"""
    sources = []
    seen_sources = set()
    if search_results:
        for doc in search_results:
            content_key = doc.get("content", "")[:100]
            if content_key in seen_sources:
                continue
            seen_sources.add(content_key)

            sources.append({
                "title": doc.get("title") or doc.get("chapter") or doc.get("source", "제목 없음"),
                "source": doc.get("source", ""),
                "score": doc.get("score", 0.0),
                "content": doc.get("content", ""),
                "document_id": doc.get("document_id"),
            })
    return sources


_last_model_name = "unknown"

async def _call_llm(sys_prompt: str, user_prompt: str, json_mode: bool = False, task: str = None) -> str:
    """
    LLM 호출 — 모드에 따라 LLM API 또는 sLLM(vLLM + LoRA) 사용

    Args:
        task: 파인튜닝 태스크명 ("generate", "qa", "summary").
              DOC_AGENT_MODE=sllm일 때 해당 LoRA 어댑터로 라우팅.
              None이면 항상 LLM API 사용 (template_type 감지 등).
    """
    global _last_model_name
    _t_llm = time.time()
    mode = os.getenv("DOC_AGENT_MODE", "api")
    sllm_tasks = os.getenv("DOC_SLLM_TASKS", "generate").split(",")  # sLLM 적용 태스크 (쉼표 구분)
    print(f"[DocumentAgent] _call_llm 호출 | mode={mode}, task={task}, sllm_tasks={sllm_tasks}, json_mode={json_mode}")
    try:
        if mode == "sllm" and task in sllm_tasks:
            # sLLM 모드: vLLM + LoRA 어댑터
            try:
                from ai.serving.vllm_client import VLLMProvider
                use_lora = os.getenv("VLLM_USE_LORA", "false").lower() == "true"
                if use_lora:
                    llm = VLLMProvider().with_lora(f"v2_{task}")
                    _last_model_name = os.getenv("VLLM_MODEL", "Kanana-1.5-8B") + f" (LoRA v2_{task})"
                    print(f"[DocumentAgent] _call_llm | sLLM: v2_{task} LoRA 어댑터")
                else:
                    llm = VLLMProvider()
                    _last_model_name = os.getenv("VLLM_MODEL", "Kanana-1.5-8B")
                    print(f"[DocumentAgent] _call_llm | sLLM: base model (LoRA 없음)")
                response = await llm.generate(
                    prompt=user_prompt,
                    system_prompt=sys_prompt,
                    temperature=0.7,
                    json_mode=json_mode,
                )
                result = response.content
                print(f"[DocumentAgent] _call_llm | sLLM 응답 ({time.time()-_t_llm:.2f}s) 길이: {len(result)}자")
                return result
            except Exception as e:
                print(f"[DocumentAgent] _call_llm | sLLM 실패, API fallback: {e}")
                _last_model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini") + " (fallback)"
                from ai.llm import get_llm
                llm = get_llm()
        else:
            # API 모드: 기존 LLM Factory (GPT/Claude)
            from ai.llm import get_llm
            llm = get_llm()
            _last_model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            print(f"[DocumentAgent] _call_llm | API: {llm.__class__.__name__}")

        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=sys_prompt,
            temperature=0.7,
            json_mode=json_mode,
        )

        result = response.content
        print(f"[DocumentAgent] _call_llm | 응답 ({time.time()-_t_llm:.2f}s) 길이: {len(result)}자")
        return result

    except Exception as e:
        print(f"[DocumentAgent] _call_llm | !!! 에러: {e}")
        import traceback
        traceback.print_exc()
        return _get_mock_response(user_prompt, json_mode)

def _get_mock_response(user_prompt: str, json_mode: bool) -> str:
    """API 키 없을 때 나가는 Mock 응답"""
    prompt_lower = user_prompt.lower()
    if json_mode:
        # doc_qa mock — "Question:" 패턴 우선 검사
        if "question" in prompt_lower or "answer" in prompt_lower:
            return json.dumps({
                "answer": "문서에 따르면 해당 내용은 다음과 같습니다. (Mock 응답)",
                "citations": [
                    {"source": "내부 규정 문서", "content": "관련 조항 내용 발췌 (Mock)", "relevance": "높음"}
                ],
                "confidence": 0.85,
            }, ensure_ascii=False)
        # meeting mock
        if "회의" in user_prompt or "summary" in prompt_lower:
             return json.dumps({
                "title": "주간 개발 회의 (Mock)",
                "date": "2026-02-12",
                "attendees": ["김철수", "이영희", "박민수"],
                "summary": "금주 개발 진행 상황 공유 및 이슈 논의. API 스키마 확정됨.",
                "decisions": ["API 스키마 확정", "DB 설계를 이번 주 내로 완료하기로 함"],
                "action_items": [
                    {"content": "API 명세서 작성", "assignee": "김철수", "due_date": "2026-02-15"},
                    {"content": "DB 마이그레이션", "assignee": "이영희", "due_date": "2026-02-16"}
                ],
                "risks": [
                    {"description": "일정 지연 가능성 존재", "regulation": "프로젝트 관리 규정", "level": "중간"}
                ]
            }, ensure_ascii=False)
        # 기본 문서 mock
        return json.dumps({
            "title": "자동 생성 문서 (Mock)",
            "content": "LLM에 의해 생성된 문서 내용입니다.\\n사용자 요청을 반영하여 작성되었습니다."
        }, ensure_ascii=False)

    # 요약 mock
    if "요약" in user_prompt or "문서 내용" in user_prompt:
        return "## 핵심 요약\n\n이 문서는 주요 업무 프로세스를 설명합니다. (Mock 요약 응답)\n\n### 주요 포인트\n- 포인트 1\n- 포인트 2\n- 포인트 3"

    return "LLM이 생성한 답변입니다. (문서 검색 결과 등) - Mock Response"
