"""
LangGraph Agent 오케스트레이터 (팀원 A 담당)

그래프 구조 (v2 — Smart Hybrid):
  [사용자 입력]
       |
  [classify_intent_v2]  ← BERT 분류 + 복합 감지 + 지시어 감지
       | (route_by_complexity)
       +-- simple          → 기존 단일 Agent (BERT 결과 그대로)
       +-- complex         → decompose_and_classify → execute_sub_queries → merge_responses
       +-- context_dep     → resolve_context → classify_intent_v2 (재분류)
       +-- low_confidence  → clarify_with_candidates (top-3 후보 제시)
       |
  [format_response] → END
"""

import json
import logging
import os
import time

from langgraph.graph import StateGraph, END

from ai.agents.state import AgentState
from ai.agents.intent_classifier import (
    get_classifier,
    detect_complexity,
    is_context_dependent,
    INTENT_LABELS,
)
from ai.agents.config import (
    ENABLE_COMPLEX_QUERY,
    INTENT_CONFIDENCE_THRESHOLD,
    INTENT_FALLBACK_THRESHOLD,
    MAX_SUB_QUERIES,
    CONTEXT_HISTORY_TURNS,
)

logger = logging.getLogger(__name__)

# 컴파일된 그래프 캐시
_compiled_graph = None

# MAX_SUB_QUERIES는 ai.agents.config에서 import


# ── Phase 1: 기존 노드 (유지) ──


def _get_settings():
    """config import — FastAPI 실행 시 / 단독 실행 시 모두 대응"""
    from backend.app.config import get_settings
    return get_settings()


async def general_response_node(state: AgentState) -> AgentState:
    """일반 응답 노드 — LLM API 호출

    stream_mode=True이면 LLM 호출을 건너뛰고 chat.py에서 직접 스트리밍 처리.
    """
    _t = time.time()
    print(f"[Orchestrator] general_response_node 진입 | stream_mode={state.get('stream_mode')}")
    # 스트리밍 모드면 chat.py에서 직접 LLM 스트리밍 처리
    if state.get("stream_mode"):
        state["agent_response"] = {
            "type": "general",
            "message": "",
            "stream_pending": True,
        }
        return state

    # 비스트리밍 모드 (POST /chat/) — 기존대로 전체 응답 생성
    try:
        from openai import AsyncOpenAI

        settings = _get_settings()

        if not settings.OPENAI_API_KEY:
            state["agent_response"] = {
                "type": "general",
                "message": "LLM API 키가 설정되지 않았습니다. .env 파일에 OPENAI_API_KEY를 추가해주세요.",
            }
            return state

        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.LLM_BASE_URL,  # None이면 기본 OpenAI URL 사용
        )

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "당신은 업무 도우미 '듀듀'입니다. 한국어로 친절하게 답변하세요."},
                *state.get("chat_history", []),
                {"role": "user", "content": state["user_input"]},
            ],
            temperature=0.7,
            max_tokens=1024,
        )

        state["agent_response"] = {
            "type": "general",
            "message": response.choices[0].message.content,
        }
    except Exception as e:
        logger.error("General response error: %s", e)
        state["agent_response"] = {
            "type": "general",
            "message": f"응답 생성 중 오류가 발생했습니다: {e}",
        }
        state["error"] = str(e)

    return state


# ── Safe Agent Wrappers (팀원 Agent NotImplementedError 대응) ──


async def safe_judgment_agent(state: AgentState) -> AgentState:
    """판단 Agent 안전 래퍼 (팀원 B)"""
    _t = time.time()
    print(f"[Orchestrator] safe_judgment_agent 진입 | stream_mode={state.get('stream_mode')}")
    try:
        # 스트리밍 모드면 chat.py에서 judgment_agent_stream으로 직접 처리
        if state.get("stream_mode"):
            state["agent_response"] = {
                "type": "judgment",
                "message": "",
                "stream_pending": True,
            }
            return state

        from ai.agents.judgment_agent import judgment_agent

        result = await judgment_agent(state)
        print(f"[Orchestrator] safe_judgment_agent 완료 ({time.time()-_t:.2f}s)")
        return result
    except NotImplementedError:
        state["agent_response"] = {
            "type": "judgment",
            "message": "판단 Agent는 현재 구현 중입니다. 곧 사용 가능합니다.",
        }
        return state
    except Exception as e:
        logger.error("Judgment agent error: %s", e)
        state["agent_response"] = {
            "type": "judgment",
            "message": f"판단 처리 중 오류가 발생했습니다: {e}",
        }
        state["error"] = str(e)
        return state


async def safe_document_agent(state: AgentState) -> AgentState:
    """문서 Agent 안전 래퍼 (팀원 C)"""
    _t = time.time()
    print("[Orchestrator] safe_document_agent 진입")
    try:
        from ai.agents.document_agent import document_agent

        result = await document_agent(state)
        print(f"[Orchestrator] safe_document_agent 완료 ({time.time()-_t:.2f}s)")
        return result
    except NotImplementedError:
        state["agent_response"] = {
            "type": state.get("intent", "doc_search"),
            "message": "문서 Agent는 현재 구현 중입니다. 곧 사용 가능합니다.",
        }
        return state
    except Exception as e:
        logger.error("Document agent error: %s", e)
        state["agent_response"] = {
            "type": state.get("intent", "doc_search"),
            "message": f"문서 처리 중 오류가 발생했습니다: {e}",
        }
        state["error"] = str(e)
        return state


async def safe_schedule_agent(state: AgentState) -> AgentState:
    """일정 Agent 안전 래퍼 (팀원 D)"""
    _t = time.time()
    print("[Orchestrator] safe_schedule_agent 진입")
    try:
        from ai.agents.schedule_agent import schedule_agent

        result = await schedule_agent(state)
        print(f"[Orchestrator] safe_schedule_agent 완료 ({time.time()-_t:.2f}s) | response type={result.get('agent_response', {}).get('type')}")
        return result
    except NotImplementedError:
        state["agent_response"] = {
            "type": state.get("intent", "schedule_view"),
            "message": "일정 Agent는 현재 구현 중입니다. 곧 사용 가능합니다.",
        }
        return state
    except Exception as e:
        logger.error("Schedule agent error: %s", e)
        state["agent_response"] = {
            "type": state.get("intent", "schedule_view"),
            "message": f"일정 처리 중 오류가 발생했습니다: {e}",
        }
        state["error"] = str(e)
        return state


# ── Phase 2: 새 노드 (복합 질문 처리) ──


def classify_intent_v2(state: AgentState) -> AgentState:
    """Intent 분류 v2 — BERT + 복합 감지 + 지시어 감지"""
    _t = time.time()
    user_input = state.get("resolved_input") or state["user_input"]
    print(f"[Orchestrator] classify_intent_v2 시작 | input='{user_input}'")

    classifier = get_classifier()
    result = classifier.predict(user_input, return_candidates=True)

    state["intent"] = result["intent"]
    state["confidence"] = result["confidence"]
    state["intent_candidates"] = result.get("candidates", [
        {"intent": result["intent"], "confidence": result["confidence"]}
    ])

    # 지시어 감지 (맥락 의존 쿼리)
    # resolved_input이 이미 있으면 재감지 건너뜀 (무한 루프 방지)
    if not state.get("resolved_input") and is_context_dependent(user_input):
        chat_history = state.get("chat_history", [])
        if chat_history:
            state["needs_context_resolution"] = True
            print(f"[Orchestrator] 지시어 감지됨 → context_resolution 필요")
            return state

    state["needs_context_resolution"] = False

    # 복합 감지 (현재 비활성 — ENABLE_COMPLEX_QUERY=False)
    # candidates = state["intent_candidates"]
    # complexity = detect_complexity(user_input, candidates)
    # state["is_complex"] = complexity["is_complex"]
    state["is_complex"] = False

    print(
        f"[Orchestrator] classify_intent_v2 완료 ({time.time()-_t:.2f}s) | "
        f"intent={state['intent']}, confidence={state['confidence']:.4f}, "
        f"is_complex={state['is_complex']}"
    )
    return state


def route_by_complexity(state: AgentState) -> str:
    """조건부 라우팅 — 복합도에 따라 분기"""
    intent = state.get("intent", "")
    confidence = state.get("confidence", 0)
    is_complex = state.get("is_complex", False)
    needs_context = state.get("needs_context_resolution", False)

    # 1. 맥락 해석 필요
    if needs_context:
        print(f"[Orchestrator] 라우팅: context_dependent → resolve_context")
        return "resolve_context"

    # 2. 복합 질문 (현재 비활성)
    # if ENABLE_COMPLEX_QUERY and is_complex and confidence >= INTENT_FALLBACK_THRESHOLD:
    #     print(f"[Orchestrator] 라우팅: complex → decompose_and_classify")
    #     return "decompose_and_classify"

    # 3. 낮은 confidence → top-3 후보 제시
    if confidence < INTENT_CONFIDENCE_THRESHOLD:
        candidates = state.get("intent_candidates", [])
        if len(candidates) >= 2:
            print(f"[Orchestrator] 라우팅: low_confidence → clarify_with_candidates")
            return "clarify_with_candidates"
        print(f"[Orchestrator] 라우팅: low_confidence → general_response")
        return "general_response"

    # 4. 단순 질문 — 기존과 동일 (BERT fast path)
    if intent == "general":
        route = "general_response"
    elif intent == "judgment":
        route = "judgment_agent"
    elif intent in ("doc_search", "doc_generate", "meeting_generate"):
        route = "document_agent"
    elif intent.startswith("schedule_"):
        route = "schedule_agent"
    else:
        route = "general_response"

    print(f"[Orchestrator] 라우팅: simple ({intent}, confidence={confidence:.4f}) → {route}")
    return route


async def resolve_context(state: AgentState) -> AgentState:
    """맥락 해석 노드 — 지시어를 chat_history 참조하여 명확한 문장으로 변환"""
    _t = time.time()
    user_input = state["user_input"]
    chat_history = state.get("chat_history", [])
    print(f"[Orchestrator] resolve_context 진입 | input='{user_input}'")

    # chat_history가 없으면 해석 불가 → 그대로 진행
    if not chat_history:
        state["resolved_input"] = user_input
        state["needs_context_resolution"] = False
        return state

    try:
        from openai import AsyncOpenAI

        settings = _get_settings()
        if not settings.OPENAI_API_KEY:
            state["resolved_input"] = user_input
            state["needs_context_resolution"] = False
            return state

        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

        # 최근 5턴만 사용
        recent_history = chat_history[-(CONTEXT_HISTORY_TURNS * 2):]
        history_text = "\n".join(
            f"{'사용자' if m['role'] == 'user' else '듀듀'}: {m['content']}"
            for m in recent_history
        )

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": """사용자가 이전 대화를 참조하는 질문을 했습니다.

이전 대화를 참고하여, 사용자의 현재 질문을 명확한 독립 문장으로 재작성하세요.
예: "그거 정리해줘" → "아까 논의한 스프린트 리뷰 내용을 회의록으로 정리해줘"

재작성된 질문만 출력하세요. 다른 설명은 불필요합니다."""},
                {"role": "user", "content": f"대화 이력:\n{history_text}\n\n현재 질문: {user_input}"},
            ],
            temperature=0.3,
            max_tokens=256,
        )

        resolved = response.choices[0].message.content.strip()
        state["resolved_input"] = resolved
        state["needs_context_resolution"] = False

        print(f"[Orchestrator] resolve_context 완료 ({time.time()-_t:.2f}s) | '{user_input}' → '{resolved}'")

    except Exception as e:
        logger.error("Context resolution error: %s", e)
        state["resolved_input"] = user_input
        state["needs_context_resolution"] = False

    return state


def _validate_decomposition(result: dict) -> bool:
    """LLM 분해 결과 검증"""
    sub_queries = result.get("sub_queries", [])

    # 검증 1: 비어있으면 실패
    if not sub_queries or len(sub_queries) == 0:
        return False

    # 검증 2: 각 서브쿼리에 필수 필드 있는지
    for sq in sub_queries:
        if "query" not in sq or "intent" not in sq:
            return False
        # 검증 3: intent가 유효한 카테고리인지
        if sq["intent"] not in INTENT_LABELS:
            return False

    # 검증 4: depends_on 순환 참조 없는지
    for i, sq in enumerate(sub_queries):
        dep = sq.get("depends_on")
        if dep is not None:
            if not isinstance(dep, int) or dep < 0 or dep >= i:
                return False

    return True


async def decompose_and_classify(state: AgentState) -> AgentState:
    """복합 질문 분해 노드 — LLM이 분류+분해+순서 결정을 한번에 처리"""
    _t = time.time()
    user_input = state.get("resolved_input") or state["user_input"]
    candidates = state.get("intent_candidates", [])
    print(f"[Orchestrator] decompose_and_classify 진입 | input='{user_input}'")

    try:
        from openai import AsyncOpenAI

        settings = _get_settings()
        if not settings.OPENAI_API_KEY:
            logger.warning("No API key for decomposition, falling back to single intent")
            state["is_complex"] = False
            return state

        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

        # BERT top-3 정보를 힌트로 제공
        candidates_hint = ", ".join(
            f"{c['intent']}({c['confidence']:.2f})" for c in candidates[:3]
        ) if candidates else "없음"

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": f"""당신은 사용자의 복합 질문을 분석하는 도우미입니다.

사용자의 질문을 분석하여 개별 작업으로 분해하세요.
각 작업의 의도(intent)와 실행 순서를 결정하세요.

가능한 intent 카테고리:
- judgment: 규정 기반 판단
- doc_search: 문서/규정 검색
- doc_generate: 문서 생성
- meeting_generate: 회의록 작성
- schedule_add: 일정 추가
- schedule_view: 일정 조회
- general: 일반 질문

BERT 분류기의 힌트: {candidates_hint}

반드시 아래 JSON 형식으로만 응답하세요:
{{"sub_queries": [{{"query": "분해된 질문", "intent": "카테고리", "depends_on": null}}], "execution_type": "sequential"}}

규칙:
- sub_queries는 최대 {MAX_SUB_QUERIES}개까지만
- depends_on: 이전 단계 결과가 필요하면 해당 인덱스(0부터), 아니면 null
- execution_type: "sequential" 또는 "parallel"
- 분해가 불필요하면 단일 sub_query만 반환"""},
                {"role": "user", "content": user_input},
            ],
            temperature=0.2,
            max_tokens=512,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        print(f"[Orchestrator] LLM 분해 응답: {raw}")
        result = json.loads(raw)

        # 서브쿼리 3개 초과 시 거부
        if len(result.get("sub_queries", [])) > MAX_SUB_QUERIES:
            state["agent_response"] = {
                "type": "clarify",
                "message": f"질문이 너무 복잡합니다. {MAX_SUB_QUERIES}개 이하로 나눠서 질문해주시겠어요?",
            }
            state["is_complex"] = False
            print(f"[Orchestrator] 서브쿼리 {len(result['sub_queries'])}개 → 너무 많아 거부")
            return state

        # 검증
        if _validate_decomposition(result):
            state["sub_queries"] = result["sub_queries"]
            state["is_complex"] = True
            print(f"[Orchestrator] 분해 성공: {len(result['sub_queries'])}개 서브쿼리")
        else:
            logger.warning("LLM decomposition validation failed, falling back to single intent")
            state["is_complex"] = False

    except Exception as e:
        logger.error(f"LLM decomposition error: {e}")
        state["is_complex"] = False

    print(f"[Orchestrator] decompose_and_classify 완료 ({time.time()-_t:.2f}s) | is_complex={state.get('is_complex')}")
    return state


def _route_intent_to_agent(intent: str) -> str:
    """intent → agent 함수명 매핑"""
    if intent == "judgment":
        return "judgment_agent"
    elif intent in ("doc_search", "doc_generate", "meeting_generate"):
        return "document_agent"
    elif intent.startswith("schedule_"):
        return "schedule_agent"
    return "general_response"


async def _execute_single_agent(sub_query: dict, parent_state: AgentState, prev_context: list = None) -> dict:
    """단일 서브쿼리 Agent 실행"""
    # 서브 state 복제
    sub_state = dict(parent_state)
    sub_state["user_input"] = sub_query["query"]
    sub_state["intent"] = sub_query["intent"]
    sub_state["confidence"] = sub_query.get("confidence", 0.9)
    sub_state["agent_response"] = {}
    sub_state["stream_mode"] = False  # 서브쿼리는 직접 응답 생성 (스트리밍 X)

    # 의존 단계 결과를 context에 포함
    if prev_context:
        sub_state["context"] = prev_context

    # Agent 실행
    agent_name = _route_intent_to_agent(sub_query["intent"])
    agent_fn_map = {
        "judgment_agent": safe_judgment_agent,
        "document_agent": safe_document_agent,
        "schedule_agent": safe_schedule_agent,
        "general_response": general_response_node,
    }

    agent_fn = agent_fn_map.get(agent_name, general_response_node)
    result_state = await agent_fn(sub_state)

    return {
        "intent": sub_query["intent"],
        "query": sub_query["query"],
        "agent_response": result_state.get("agent_response", {}),
        "context": result_state.get("context", []),
    }


async def execute_sub_queries(state: AgentState) -> AgentState:
    """서브쿼리 순차 실행 노드"""
    _t = time.time()
    sub_queries = state.get("sub_queries", [])
    print(f"[Orchestrator] execute_sub_queries 진입 | {len(sub_queries)}개 서브쿼리")

    if not sub_queries:
        state["is_complex"] = False
        return state

    sub_responses = []

    for i, sq in enumerate(sub_queries):
        print(f"[Orchestrator] 서브쿼리 {i+1}/{len(sub_queries)} 실행: intent={sq['intent']}, query='{sq['query']}'")
        try:
            # depends_on 확인: 의존하는 이전 단계가 실패했으면 건너뛰기
            dep = sq.get("depends_on")
            if dep is not None and dep < len(sub_responses):
                if sub_responses[dep].get("status") == "failed":
                    sub_responses.append({
                        "status": "skipped",
                        "intent": sq["intent"],
                        "query": sq["query"],
                        "reason": f"{dep+1}단계 실패로 건너뜀",
                    })
                    print(f"[Orchestrator] 서브쿼리 {i+1} 건너뜀 (의존 단계 실패)")
                    continue

            # 이전 단계 결과를 context로 전달
            prev_context = None
            if dep is not None and dep < len(sub_responses):
                prev_resp = sub_responses[dep]
                if prev_resp.get("status") == "success":
                    prev_context = prev_resp.get("context", [])

            result = await _execute_single_agent(sq, state, prev_context)
            result["status"] = "success"
            sub_responses.append(result)
            print(f"[Orchestrator] 서브쿼리 {i+1} 완료")

        except Exception as e:
            logger.error(f"Sub-query {i+1} error: {e}")
            sub_responses.append({
                "status": "failed",
                "intent": sq["intent"],
                "query": sq["query"],
                "error": str(e),
            })

    state["sub_responses"] = sub_responses
    print(f"[Orchestrator] execute_sub_queries 완료 ({time.time()-_t:.2f}s)")
    return state


def merge_responses(state: AgentState) -> AgentState:
    """서브쿼리 결과 통합 노드"""
    _t = time.time()
    sub_responses = state.get("sub_responses", [])
    print(f"[Orchestrator] merge_responses 진입 | {len(sub_responses)}개 응답 병합")

    if not sub_responses:
        state["agent_response"] = {
            "type": "multi_intent",
            "message": "처리 결과가 없습니다.",
        }
        return state

    # 섹션 구성
    sections = []
    for i, resp in enumerate(sub_responses):
        status = resp.get("status", "unknown")
        agent_resp = resp.get("agent_response", {})

        if status == "success":
            section = {
                "step": i + 1,
                "intent": resp.get("intent", ""),
                "query": resp.get("query", ""),
                "status": "success",
                "result": agent_resp,
            }
        elif status == "skipped":
            section = {
                "step": i + 1,
                "intent": resp.get("intent", ""),
                "query": resp.get("query", ""),
                "status": "skipped",
                "result": {"message": resp.get("reason", "건너뜀")},
            }
        else:
            section = {
                "step": i + 1,
                "intent": resp.get("intent", ""),
                "query": resp.get("query", ""),
                "status": "failed",
                "result": {"message": f"처리 실패: {resp.get('error', '알 수 없는 오류')}"},
            }
        sections.append(section)

    # 텍스트 포맷 생성
    message = _format_sections_as_text(sections)

    # 마지막 성공 결과의 메시지를 요약으로
    summary = "처리가 완료되었습니다."
    for s in reversed(sections):
        if s["status"] == "success":
            summary = s["result"].get("message", summary)
            break

    state["agent_response"] = {
        "type": "multi_intent",
        "sections": sections,
        "summary": summary,
        "message": message,
    }

    print(f"[Orchestrator] merge_responses 완료 ({time.time()-_t:.2f}s)")
    return state


def _format_sections_as_text(sections: list) -> str:
    """섹션별 텍스트 포맷"""
    lines = []
    for s in sections:
        status_icon = {"success": "", "skipped": "⚠️", "failed": "❌"}.get(s["status"], "")
        step_label = f"{status_icon} {s['step']}단계: {s['query']}".strip()
        lines.append(step_label)

        result_msg = s["result"].get("message", "")
        if result_msg:
            lines.append(f"  {result_msg}")
        lines.append("")

    return "\n".join(lines).strip()


def clarify_with_candidates(state: AgentState) -> AgentState:
    """top-3 후보 제시 노드 (confidence < 0.7)"""
    candidates = state.get("intent_candidates", [])
    print(f"[Orchestrator] clarify_with_candidates 진입 | candidates={candidates}")

    # 후보 목록 구성
    intent_labels_kr = {
        "judgment": "규정 판단",
        "doc_search": "문서 검색",
        "doc_generate": "문서 작성",
        "meeting_generate": "회의록 작성",
        "schedule_add": "일정 추가",
        "schedule_view": "일정 조회",
        "general": "일반 질문",
    }

    candidate_list = []
    for c in candidates[:3]:
        label = intent_labels_kr.get(c["intent"], c["intent"])
        pct = int(c["confidence"] * 100)
        candidate_list.append({
            "intent": c["intent"],
            "label": label,
            "confidence": c["confidence"],
            "display": f"{label} ({pct}%)",
        })

    state["agent_response"] = {
        "type": "clarify_candidates",
        "message": "다음 중 어느 것에 가까운가요?\n" + "\n".join(
            f"  {i+1}. {c['display']}" for i, c in enumerate(candidate_list)
        ),
        "candidates": candidate_list,
    }

    return state


async def post_execution_check(state: AgentState) -> tuple:
    """Agent 실행 후 결과 빈약 시 재분류 시도 (해결5-방어1)

    TODO: 다른 팀원 Agent 완성 후 실제 판정 로직 구현
    - judgment Agent: RAG 결과 0건이면 규정 못 찾은 것
    - doc_search Agent: 검색 결과 없음
    - schedule Agent: 파싱 실패

    Returns:
        (state, should_retry): should_retry=True이면 다른 intent로 재실행 필요
    """
    response = state.get("agent_response", {})
    intent = state.get("intent", "")

    # TODO: Agent 완성 후 빈약 결과 판정 조건 구현
    is_poor_result = False

    # 판단 Agent: context(RAG 결과)가 비어있으면 규정을 못 찾은 것
    # if intent == "judgment" and not state.get("context"):
    #     is_poor_result = True

    # 문서 검색: 검색 결과 없음
    # if intent == "doc_search" and response.get("sources", []) == []:
    #     is_poor_result = True

    # 일정: 파싱 실패
    # if intent.startswith("schedule_") and response.get("error"):
    #     is_poor_result = True

    if is_poor_result:
        logger.info(f"Poor result detected for intent={intent}, attempting reclassification")
        # TODO: LLM 재분류 호출
        # reclassified = await llm_reclassify(state["user_input"], state["chat_history"])
        # if reclassified["intent"] != intent:
        #     state["intent"] = reclassified["intent"]
        #     state["agent_response"] = {}
        #     return state, True
        pass

    return state, False


def format_response(state: AgentState) -> AgentState:
    """응답 포맷팅 노드 — agent_response에 type/message 필드 보장"""
    print(f"[Orchestrator] format_response 진입 | agent_response type={state.get('agent_response', {}).get('type', 'none')}")
    resp = state.get("agent_response", {})
    if not resp:
        state["agent_response"] = {
            "type": state.get("intent", "general"),
            "message": "응답을 생성하지 못했습니다.",
        }
    else:
        if "type" not in resp:
            resp["type"] = state.get("intent", "general")
        if "message" not in resp:
            resp["message"] = ""
    return state


# ── 그래프 빌드 (v2) ──


def _route_after_decompose(state: AgentState) -> str:
    """decompose 후 라우팅: 복합이면 실행, 아니면 단순 경로"""
    is_complex = state.get("is_complex", False)

    # clarify 응답이 이미 설정됨 (서브쿼리 초과 등)
    if state.get("agent_response", {}).get("type") == "clarify":
        return "format_response"

    if is_complex and state.get("sub_queries"):
        return "execute_sub_queries"

    # fallback: 단순 의도로 재라우팅
    return _simple_route(state)


def _route_after_context(state: AgentState) -> str:
    """context resolution 후 → classify_intent_v2 재실행"""
    return "classify_intent_v2"


def _simple_route(state: AgentState) -> str:
    """단순 의도 라우팅 (기존 route_by_intent 역할)"""
    intent = state.get("intent", "")
    if intent == "judgment":
        return "judgment_agent"
    elif intent in ("doc_search", "doc_generate", "meeting_generate"):
        return "document_agent"
    elif intent.startswith("schedule_"):
        return "schedule_agent"
    return "general_response"


def build_graph():
    """LangGraph StateGraph 빌드 + 컴파일 (v2 — Smart Hybrid)"""
    graph = StateGraph(AgentState)

    # 노드 등록
    graph.add_node("classify_intent_v2", classify_intent_v2)
    graph.add_node("resolve_context", resolve_context)
    # 복합 질문 노드 (현재 비활성)
    # graph.add_node("decompose_and_classify", decompose_and_classify)
    # graph.add_node("execute_sub_queries", execute_sub_queries)
    # graph.add_node("merge_responses", merge_responses)
    graph.add_node("clarify_with_candidates", clarify_with_candidates)
    graph.add_node("judgment_agent", safe_judgment_agent)
    graph.add_node("document_agent", safe_document_agent)
    graph.add_node("schedule_agent", safe_schedule_agent)
    graph.add_node("general_response", general_response_node)
    graph.add_node("format_response", format_response)

    # 엔트리 포인트
    graph.set_entry_point("classify_intent_v2")

    # classify_intent_v2 → 복합도에 따라 분기
    graph.add_conditional_edges(
        "classify_intent_v2",
        route_by_complexity,
        {
            "resolve_context": "resolve_context",
            # "decompose_and_classify": "decompose_and_classify",  # 복합 질문 비활성
            "clarify_with_candidates": "clarify_with_candidates",
            "judgment_agent": "judgment_agent",
            "document_agent": "document_agent",
            "schedule_agent": "schedule_agent",
            "general_response": "general_response",
        },
    )

    # resolve_context → classify_intent_v2 재실행
    graph.add_conditional_edges(
        "resolve_context",
        _route_after_context,
        {
            "classify_intent_v2": "classify_intent_v2",
        },
    )

    # 복합 질문 엣지 (현재 비활성)
    # graph.add_conditional_edges(
    #     "decompose_and_classify",
    #     _route_after_decompose,
    #     {
    #         "execute_sub_queries": "execute_sub_queries",
    #         "judgment_agent": "judgment_agent",
    #         "document_agent": "document_agent",
    #         "schedule_agent": "schedule_agent",
    #         "general_response": "general_response",
    #         "format_response": "format_response",
    #     },
    # )
    # graph.add_edge("execute_sub_queries", "merge_responses")
    # graph.add_edge("merge_responses", "format_response")

    # 모든 Agent/노드 → format_response → END
    graph.add_edge("judgment_agent", "format_response")
    graph.add_edge("document_agent", "format_response")
    graph.add_edge("schedule_agent", "format_response")
    graph.add_edge("general_response", "format_response")
    graph.add_edge("clarify_with_candidates", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile()


def get_graph():
    """컴파일된 그래프 인스턴스 반환 (캐시)"""
    global _compiled_graph
    if _compiled_graph is None:
        try:
            _compiled_graph = build_graph()
            logger.info("Orchestrator graph compiled successfully (v2 — Smart Hybrid)")
        except Exception as e:
            logger.error(f"Graph build error: {e}", exc_info=True)
            raise
    return _compiled_graph
