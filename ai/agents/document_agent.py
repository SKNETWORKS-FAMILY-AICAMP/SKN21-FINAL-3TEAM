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
import re
import time
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
      - doc_generate: 문서 생성 (보고서/회의록/JD/제안서)
      - doc_summary: 문서 요약
      - doc_qa: 문서 내용 기반 질의응답
    """
    intent = state.get("intent", "").lower()
    user_input = state.get("user_input", "")
    context = state.get("context", [])
    user_id = state.get("user_id")

    _t_agent = time.time()
    print(f"[DocumentAgent] 진입 | intent={intent}, user_input='{user_input[:50]}...', user_id={user_id}")

    response_data = {}

    stream_mode = state.get("stream_mode", False)
    print(f"[DocumentAgent] stream_mode={stream_mode}, context 길이={len(context)}")

    try:
        if intent == "doc_search":
            print("[DocumentAgent] → _handle_doc_search 호출")
            response_data = _handle_doc_search(user_input, context, user_id, stream_mode=stream_mode)

        elif intent == "doc_generate":
            # template_type 결정: ① state에서 프론트가 보낸 값 ② 키워드 감지
            template_type = state.get("template_type") or _detect_template_type(user_input)
            print(f"[DocumentAgent] → _handle_doc_generate 호출 | template={template_type}")
            response_data = _handle_doc_generate(user_input, template_type)

        elif intent == "doc_summary":
            print("[DocumentAgent] → _handle_doc_summary 호출")
            document_content = state.get("document_content") or state.get("extracted_text")
            response_data = _handle_doc_summary(
                user_input,
                document_content=document_content,
                stream_mode=stream_mode,
            )

        elif intent == "doc_qa":
            print("[DocumentAgent] → _handle_doc_qa 호출")
            response_data = _handle_doc_qa(
                user_input,
                context=context,
                user_id=user_id,
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

    # State 업데이트
    state["agent_response"] = response_data
    return state


# ── 헬퍼 ──

def _detect_template_type(user_input: str) -> str:
    """사용자 입력에서 템플릿 타입을 키워드로 감지

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


# ── Intent 핸들러 ──

def _handle_doc_search(query: str, context: List[str], user_id: int = None, stream_mode: bool = False) -> Dict[str, Any]:
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
            search_results = rag_pipeline.retrieve(query, user_id=user_id, top_k=5)

            # 검색된 문서의 content를 context로 사용
            context = [doc["content"] for doc in search_results]
            print(f"[DocumentAgent] RAG 검색 완료 ({time.time()-_t_rag:.2f}s): {len(context)}개 문서 검색됨")

        except Exception as e:
            print(f"[DocumentAgent] !!! RAG 검색 실패: {e}")
            import traceback
            traceback.print_exc()
            context = []

    # 2. 출처 정보 (답변 + 출처 분리, 중복 제거)
    sources = _build_sources(search_results)
    print(f"[DocumentAgent] 출처 정보: {len(sources)}개")

    # 3. Context가 없으면 검색 실패
    if not context:
        print("[DocumentAgent] context 비어있음 → 검색 실패 응답")
        return {
            "type": "doc_search",
            "answer": "관련 문서를 찾지 못했습니다. 다른 키워드로 검색해보세요.",
            "message": "관련 문서를 찾지 못했습니다. 다른 키워드로 검색해보세요.",
            "sources": sources,
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
    answer = _call_llm(sys_prompt, user_prompt)
    print(f"[DocumentAgent] LLM 응답 길이: {len(answer)}자")

    return {
        "type": "doc_search",
        "answer": answer,
        "message": answer,
        "sources": sources,
        "context": context,
    }

def _handle_doc_generate(user_input: str, template_type: str) -> Dict[str, Any]:
    """문서 생성 처리 (보고서/회의록/JD/제안서)"""
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_generate | template_type={template_type}")

    # 회의록 생성인 경우 전용 프롬프트
    if template_type == "meeting_minutes":
        return _generate_meeting_minutes(user_input)

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
    generated_json_str = _call_llm(sys_prompt, user_prompt, json_mode=True)
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


def _generate_meeting_minutes(user_input: str) -> Dict[str, Any]:
    """회의록 생성 (doc_generate의 meeting_minutes 분기)"""
    _t = time.time()
    print(f"[DocumentAgent] _generate_meeting_minutes | input='{user_input[:80]}...'")

    sys_prompt = "당신은 회의록 작성 전문가입니다. 입력된 회의 내용을 분석하여 JSON 형식으로 출력하세요."
    user_prompt = f"""회의 내용: {user_input}

출력 형식(JSON):
{{
    "title": "회의 제목",
    "date": "YYYY-MM-DD",
    "attendees": ["참석자1", "참석자2"],
    "summary": "전체 요약",
    "decisions": ["결정사항1", ...],
    "action_items": [{{"content": "할일", "assignee": "담당자", "due_date": "기한"}}],
    "risks": [{{"description": "리스크", "level": "상/중/하", "regulation": "관련 규정"}}]
}}"""

    print(f"[DocumentAgent] LLM 호출 (meeting_minutes, json_mode=True)...")
    generated_json_str = _call_llm(sys_prompt, user_prompt, json_mode=True)
    print(f"[DocumentAgent] LLM 응답: {generated_json_str[:200]}...")
    try:
        data = json.loads(generated_json_str)
        print(f"[DocumentAgent] JSON 파싱 성공 | keys={list(data.keys())}")
    except Exception:
        print(f"[DocumentAgent] !!! JSON 파싱 실패")
        data = {"summary": "파싱 실패", "content": generated_json_str}

    # 회의록 미리보기
    preview = f"""# {data.get('title', '회의록')}

## 요약
{data.get('summary', '')}

## 결정사항
{chr(10).join(['- ' + d for d in data.get('decisions', [])])}

## Action Items
{chr(10).join([f"- {ai.get('content')} ({ai.get('assignee')})" for ai in data.get('action_items', [])])}"""

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
        "document_id": 456, # Mock ID
        "download_url": "/api/v1/documents/456/download",
    }


def _handle_doc_summary(user_input: str, document_content: str = None, stream_mode: bool = False) -> Dict[str, Any]:
    """문서 요약 처리"""
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_summary | content_len={len(document_content) if document_content else 0}, stream_mode={stream_mode}")

    # 문서 내용이 없으면 안내 메시지
    if not document_content:
        print("[DocumentAgent] document_content 없음 → 안내 메시지")
        return {
            "type": "doc_summary",
            "message": "요약할 문서를 선택해주세요. 문서관리 페이지에서 문서를 선택하거나, 챗봇에 파일을 업로드해주세요.",
            "answer": "요약할 문서를 선택해주세요. 문서관리 페이지에서 문서를 선택하거나, 챗봇에 파일을 업로드해주세요.",
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
    answer = _call_llm(sys_prompt, user_prompt)
    print(f"[DocumentAgent] LLM 응답 길이: {len(answer)}자")

    return {
        "type": "doc_summary",
        "answer": answer,
        "message": answer,
    }


def _handle_doc_qa(query: str, context: list = None, user_id: int = None, stream_mode: bool = False) -> Dict[str, Any]:
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
            search_results = rag_pipeline.retrieve(query, user_id=user_id, top_k=5)
            context = [doc["content"] for doc in search_results]
            print(f"[DocumentAgent] RAG 검색 완료 ({time.time()-_t_rag:.2f}s): {len(context)}개 문서")

        except Exception as e:
            print(f"[DocumentAgent] !!! RAG 검색 실패: {e}")
            import traceback
            traceback.print_exc()
            context = []

    # 출처 정보 구성
    sources = _build_sources(search_results)

    # Context가 없으면 실패
    if not context:
        print("[DocumentAgent] context 비어있음 → 검색 실패 응답")
        return {
            "type": "doc_qa",
            "answer": "관련 문서를 찾지 못했습니다. 다른 질문을 시도해보세요.",
            "message": "관련 문서를 찾지 못했습니다. 다른 질문을 시도해보세요.",
            "sources": sources,
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
    answer_json_str = _call_llm(DOC_QA_SYSTEM_PROMPT, user_prompt, json_mode=True)

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
                "content": doc.get("content", "")[:200] + "...",
            })
    return sources


def _call_llm(sys_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
    """
    LLM 호출 (Solar API 사용)
    """
    _t_llm = time.time()
    print(f"[DocumentAgent] _call_llm 호출 | json_mode={json_mode}")
    try:
        from openai import OpenAI
        import os

        api_key = os.getenv("SOLAR_API_KEY")
        print(f"[DocumentAgent] _call_llm | SOLAR_API_KEY 존재: {bool(api_key)}")
        if not api_key:
            print("[DocumentAgent] _call_llm | API 키 없음 → mock 응답")
            return _get_mock_response(user_prompt, json_mode)

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.upstage.ai/v1/solar"
        )

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]

        print(f"[DocumentAgent] _call_llm | Solar API 호출 중...")
        response = client.chat.completions.create(
            model="solar-1-mini-chat",
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"} if json_mode else {"type": "text"}
        )

        result = response.choices[0].message.content
        print(f"[DocumentAgent] _call_llm | Solar API 응답 ({time.time()-_t_llm:.2f}s) 길이: {len(result)}자")
        return result

    except ImportError:
        print("[DocumentAgent] _call_llm | !!! openai 패키지 없음")
        return _get_mock_response(user_prompt, json_mode)
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
