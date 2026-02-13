"""
문서 Agent (팀원 C 담당)

기능:
  - 문서 검색 결과 반환 (doc_search)
  - 사용자 템플릿(업로드 or 선택) 기반 문서 요약 및 생성 (doc_generate)
  - 회의 내용 요약 + 회의록 양식 채워서 생성 (meeting_generate)
  - 규정 리스크 자동 감지 (RAG 기반 규정 대조)

입출력:
  Input: AgentState (user_input, intent, context, template_id)
  Output: AgentState (agent_response 채움)
"""
import json
import logging
from typing import Any, Dict, List

from ai.agents.state import AgentState
from ai.templates import get_system_template

# 로거 설정
logger = logging.getLogger(__name__)

async def document_agent(state: AgentState) -> AgentState:
    """
    문서 Agent 노드 함수 (LangGraph 노드 인터페이스)

    intent에 따라 분기:
      - doc_search: 문서 검색 결과 반환
      - doc_generate: 사용자 템플릿(업로드 or 선택) 기반 문서 요약 및 생성
      - meeting_generate: 회의 내용 요약 + 회의록 양식 채워서 생성
    """
    intent = state.get("intent", "").lower()
    user_input = state.get("user_input", "")
    context = state.get("context", [])
    user_id = state.get("user_id")

    logger.info(f"Document Agent executing. Intent: {intent}")

    response_data = {}

    stream_mode = state.get("stream_mode", False)

    try:
        if intent == "doc_search":
            response_data = _handle_doc_search(user_input, context, user_id, stream_mode=stream_mode)
        
        elif intent == "doc_generate":
            # 템플릿 ID나 종류를 state에서 가져옴 (없으면 기본값)
            # template_id = state.get("template_id")
            # TODO: template_id로 템플릿 로드 (시스템 또는 커스텀)
            # 여기서는 시스템 템플릿 'report'를 기본으로 가정
            template_type = "report" 
            response_data = _handle_doc_generate(user_input, template_type)

        elif intent == "meeting_generate":
            response_data = _handle_meeting_generate(user_input)

        elif intent == "risk_detect":
             # 리스크 감지만 별도로 요청하는 경우 (옵션)
             response_data = _handle_risk_detect(user_input)
             
        else:
            # 기본 처리 (general 등) 또는 에러
            response_data = {"error": f"지원하지 않는 intent입니다: {intent}"}

    except Exception as e:
        logger.error(f"Error in document_agent: {e}", exc_info=True)
        response_data = {"error": str(e)}

    # State 업데이트
    state["agent_response"] = response_data
    return state


def _detect_search_intent(query: str) -> str:
    """사용자 질문에서 검색 의도 감지

    Args:
        query: 사용자 질문

    Returns:
        "summarize" | "find" | "explain"
    """
    import re

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

[중요 지시사항]
- 관련 문서들을 목록으로 나열하세요
- 각 문서의 핵심 내용을 한 줄로 요약하세요
- "다음 문서들을 찾았습니다:" 형식으로 시작하세요

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


def _handle_doc_search(query: str, context: List[str], user_id: int = None, stream_mode: bool = False) -> Dict[str, Any]:
    """문서 검색 결과 처리

    Args:
        query: 사용자 질의
        context: 이미 검색된 컨텍스트 (있으면 사용, 없으면 RAG 검색)
        user_id: 사용자 ID (scope 필터용)
        stream_mode: True이면 LLM 호출 건너뛰고 프롬프트만 반환
    """
    search_results = []

    # 1. Context가 비어있으면 RAG 검색 수행
    if not context:
        try:
            from ai.rag.qdrant_pipeline import get_qdrant_pipeline

            logger.info(f"RAG 검색 수행: '{query}'")
            rag_pipeline = get_qdrant_pipeline()
            search_results = rag_pipeline.retrieve(query, user_id=user_id, top_k=5)

            # 검색된 문서의 content를 context로 사용
            context = [doc["content"] for doc in search_results]
            logger.info(f"RAG 검색 완료: {len(context)}개 문서 검색됨")

        except Exception as e:
            logger.error(f"RAG 검색 실패: {e}", exc_info=True)
            context = []

    # 2. 출처 정보 (답변 + 출처 분리, 중복 제거)
    sources = []
    seen_sources = set()
    if search_results:
        for doc in search_results:
            content_key = doc.get("content", "")[:100]
            if content_key in seen_sources:
                continue
            seen_sources.add(content_key)

            sources.append({
                "title": doc.get("title", "제목 없음"),
                "source": doc.get("source", ""),
                "score": doc.get("score", 0.0),
                "content": doc.get("content", "")[:200] + "...",
            })

    # 3. Context가 없으면 검색 실패
    if not context:
        return {
            "type": "doc_search",
            "answer": "관련 문서를 찾지 못했습니다. 다른 키워드로 검색해보세요.",
            "message": "관련 문서를 찾지 못했습니다. 다른 키워드로 검색해보세요.",
            "sources": sources,
            "context": context,
        }

    # 4. 프롬프트 생성
    sys_prompt, user_prompt = _build_search_prompt(query, context)

    # 5. 스트리밍 모드면 LLM 호출 건너뛰기 (chat.py에서 직접 스트리밍)
    if stream_mode:
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
    answer = _call_llm(sys_prompt, user_prompt)

    return {
        "type": "doc_search",
        "answer": answer,
        "message": answer,
        "sources": sources,
        "context": context,
    }

def _handle_doc_generate(user_input: str, template_type: str) -> Dict[str, Any]:
    """문서 생성 처리"""
    # 1. 템플릿 가져오기
    try:
        template = get_system_template(template_type)
    except ValueError:
        try:
            template = get_system_template("report") # Fallback
        except Exception:
            template = None

    # 2. LLM이 템플릿 필드 채우기
    required_fields = template.REQUIRED_FIELDS if template and hasattr(template, 'REQUIRED_FIELDS') else 'all'
    
    sys_prompt = f"당신은 문서 작성 도우미입니다. 사용자의 요청을 바탕으로 '{template_type}' JSON 데이터를 생성하세요."
    user_prompt = f"요청: {user_input}\n\n필수 필드: {required_fields}"
    
    generated_json_str = _call_llm(sys_prompt, user_prompt, json_mode=True)
    try:
        data = json.loads(generated_json_str)
    except json.JSONDecodeError:
        data = {"content": generated_json_str} # Fallback

    # 3. 템플릿 렌더링 (Markdown)
    # BaseTemplate.render()가 구현되어 있다면:
    # preview = template.render(data)
    # 현재는 미구현이므로 임시 처리
    preview = f"# {data.get('title', '문서')}\n\n{data.get('content', '내용 없음')}"

    return {
        "type": "doc_generate",
        "template_id": None, # 추후 DB ID
        "template_name": template.template_name if template else template_type,
        "preview": preview,
        "data": data,
        "document_id": 123, # Mock ID
        "download_url": "/api/v1/documents/123/download" # Mock URL
    }

def _handle_meeting_generate(user_input: str) -> Dict[str, Any]:
    """회의록 생성 처리"""
    # 1. LLM으로 회의 내용 분석 및 구조화
    sys_prompt = "당신은 회의록 작성 전문가입니다. 입력된 회의 내용을 분석하여 JSON 형식으로 출력하세요."
    user_prompt = f"""
    회의 내용: {user_input}
    
    출력 형식(JSON):
    {{
        "title": "회의 제목",
        "date": "YYYY-MM-DD",
        "attendees": ["참석자1", "참석자2"],
        "summary": "전체 요약",
        "decisions": ["결정사항1", ...],
        "action_items": [{{"content": "할일", "assignee": "담당자", "due_date": "기한"}}],
        "risks": [{{"description": "리스크", "level": "상/중/하", "regulation": "관련 규정"}}]
    }}
    """
    
    generated_json_str = _call_llm(sys_prompt, user_prompt, json_mode=True)
    try:
        data = json.loads(generated_json_str)
    except Exception:
        data = {"summary": "파싱 실패", "content": generated_json_str}

    # 2. 회의록 템플릿 렌더링
    # meeting_template = get_system_template("meeting_minutes")
    # preview = meeting_template.render(data)
    
    # 임시 렌더링
    preview = f"""# {data.get('title', '회의록')}
    
## 요약
{data.get('summary', '')}

## 결정사항
{chr(10).join(['- ' + d for d in data.get('decisions', [])])}

## Action Items
{chr(10).join([f"- {ai.get('content')} ({ai.get('assignee')})" for ai in data.get('action_items', [])])}
"""

    return {
        "type": "meeting_generate",
        "summary": data.get("summary"),
        "decisions": data.get("decisions", []),
        "action_items": data.get("action_items", []),
        "risk_level": "중간", # 로직 필요
        "risks": data.get("risks", []),
        "preview": preview,
        "document_id": 456, # Mock ID
        "download_url": "/api/v1/meetings/456/download",
        "auto_scan": True
    }

def _handle_risk_detect(user_input: str) -> Dict[str, Any]:
    """리스크 감지"""
    # 구현 필요
    return {"type": "risk_detect", "risks": []}

def _call_llm(sys_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
    """
    LLM 호출 (Solar API 사용)
    """
    try:
        from openai import OpenAI
        import os
        
        # 환경변수에서 API 키 로드 (없으면 에러)
        api_key = os.getenv("SOLAR_API_KEY")
        if not api_key:
            # 키가 없으면 개발용 Mock 리턴 (테스트 편의성 위해)
            logger.warning("SOLAR_API_KEY not found. Returning mock response.")
            return _get_mock_response(user_prompt, json_mode)

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.upstage.ai/v1/solar"
        )
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = client.chat.completions.create(
            model="solar-1-mini-chat",
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"} if json_mode else {"type": "text"}
        )
        
        return response.choices[0].message.content

    except ImportError:
        logger.error("openai package not installed.")
        return _get_mock_response(user_prompt, json_mode)
    except Exception as e:
        logger.error(f"LLM Call Error: {e}")
        return _get_mock_response(user_prompt, json_mode)

def _get_mock_response(user_prompt: str, json_mode: bool) -> str:
    """API 키 없을 때 나가는 Mock 응답"""
    if json_mode:
        if "회의" in user_prompt or "summary" in user_prompt:
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
        else:
            return json.dumps({
                "title": "자동 생성 문서 (Mock)",
                "content": "LLM에 의해 생성된 문서 내용입니다.\\n사용자 요청을 반영하여 작성되었습니다."
            }, ensure_ascii=False)
    
    return "LLM이 생성한 답변입니다. (문서 검색 결과 등) - Mock Response"
