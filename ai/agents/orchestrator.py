"""
LangGraph Agent 오케스트레이터 (팀원 A 담당)

그래프 구조:
  [사용자 입력]
       |
  [decompose_query]  ← 복합 질문 감지 (규칙 기반)
       | (route_after_decompose)
    +-- compound       → compound_pending (chat.py에서 스트리밍 처리)
    +-- single         ↓
  [classify_intent]  ← BERT (→ Solar fallback → 임베딩 fallback)
       | (route_by_intent)
    +-- low_confidence  → clarify_with_candidates (top-3 후보 제시)
    +-- judgment        → judgment_agent
    +-- doc_*           → document_agent
    +-- schedule_*      → schedule_agent
    +-- general         → general_response
       |
  [format_response] → END
"""

import logging
import time

from langgraph.graph import StateGraph, END

from ai.agents.state import AgentState
from ai.agents.intent_classifier import get_classifier, detect_compound_query
from ai.agents.config import INTENT_CONFIDENCE_THRESHOLD, ENABLE_COMPLEX_QUERY

logger = logging.getLogger(__name__)

# 컴파일된 그래프 캐시
_compiled_graph = None


# ── 유틸 ──


def _get_settings():
    """config import — FastAPI 실행 시 / 단독 실행 시 모두 대응"""
    from backend.app.config import get_settings
    return get_settings()


# ── Agent 노드 ──


async def general_response_node(state: AgentState) -> AgentState:
    """일반 응답 노드 — LLM API 호출

    stream_mode=True이면 LLM 호출을 건너뛰고 chat.py에서 직접 스트리밍 처리.
    """
    _t = time.time()
    logger.info("[Orchestrator] general_response_node 진입 | stream_mode=%s", state.get('stream_mode'))
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
    logger.info("[Orchestrator] safe_judgment_agent 진입 | stream_mode=%s", state.get('stream_mode'))
    try:
        # 스트리밍 모드: RAG 검색 + 프롬프트 빌드 → chat.py에서 직접 스트리밍
        if state.get("stream_mode"):
            from ai.agents.judgment_agent import (
                _build_context_prompt,
                _build_user_prompt,
                _extract_judgment_history,
            )
            from ai.llm.prompts import JUDGMENT_STREAMING_SYSTEM_PROMPT
            from ai.rag.qdrant_pipeline import get_qdrant_pipeline

            user_input = state["user_input"]
            user_id = state.get("user_id")
            chat_history = state.get("chat_history", [])

            # RAG 검색
            _t_rag = time.time()
            logger.debug("[Orchestrator] judgment 스트리밍: RAG 검색 시작 (top_k=10)...")
            pipeline = get_qdrant_pipeline()
            context = pipeline.retrieve(query=user_input, user_id=user_id, top_k=10, filter={"source": "regulations"})
            logger.debug("[Orchestrator] judgment RAG 완료 (%.2fs) | %d개 문서", time.time()-_t_rag, len(context))

            # 프롬프트 빌드
            judgment_history = _extract_judgment_history(chat_history)
            context_text = _build_context_prompt(context)
            user_prompt = _build_user_prompt(
                user_input, context_text, chat_history, judgment_history
            )

            state["context"] = context
            state["agent_response"] = {
                "type": "judgment",
                "message": "",
                "stream_pending": True,
                "sys_prompt": JUDGMENT_STREAMING_SYSTEM_PROMPT,
                "user_prompt": user_prompt,
                "_rag_context": context,
            }
            logger.debug("[Orchestrator] judgment stream_pending 반환 (%.2fs)", time.time()-_t)
            return state

        from ai.agents.judgment_agent import judgment_agent

        result = await judgment_agent(state)
        logger.info("[Orchestrator] safe_judgment_agent 완료 (%.2fs)", time.time()-_t)
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
    logger.info("[Orchestrator] safe_document_agent 진입")
    try:
        from ai.agents.document_agent import document_agent

        result = await document_agent(state)
        logger.info("[Orchestrator] safe_document_agent 완료 (%.2fs)", time.time()-_t)
        return result
    except NotImplementedError:
        state["agent_response"] = {
            "type": state.get("intent", "doc_retrieve"),
            "message": "문서 Agent는 현재 구현 중입니다. 곧 사용 가능합니다.",
        }
        return state
    except Exception as e:
        logger.error("Document agent error: %s", e)
        state["agent_response"] = {
            "type": state.get("intent", "doc_retrieve"),
            "message": f"문서 처리 중 오류가 발생했습니다: {e}",
        }
        state["error"] = str(e)
        return state


async def safe_action_agent(state: AgentState) -> AgentState:
    """액션 Agent 안전 래퍼 (파이프라인/결재)"""
    _t = time.time()
    logger.info("[Orchestrator] safe_action_agent 진입 | intent=%s", state.get('intent'))
    try:
        from ai.agents.action_agent import action_agent

        result = await action_agent(state)
        logger.info("[Orchestrator] safe_action_agent 완료 (%.2fs) | response type=%s", time.time()-_t, result.get('agent_response', {}).get('type'))
        return result
    except NotImplementedError:
        state["agent_response"] = {
            "type": state.get("intent", "pipeline_create"),
            "message": "액션 Agent는 현재 구현 중입니다. 곧 사용 가능합니다.",
        }
        return state
    except Exception as e:
        logger.error("Action agent error: %s", e)
        state["agent_response"] = {
            "type": state.get("intent", "pipeline_create"),
            "message": f"액션 처리 중 오류가 발생했습니다: {e}",
        }
        state["error"] = str(e)
        return state


async def safe_schedule_agent(state: AgentState) -> AgentState:
    """일정 Agent 안전 래퍼 (팀원 D)"""
    _t = time.time()
    logger.info("[Orchestrator] safe_schedule_agent 진입")
    try:
        from ai.agents.schedule_agent import schedule_agent

        result = await schedule_agent(state)
        logger.info("[Orchestrator] safe_schedule_agent 완료 (%.2fs) | response type=%s", time.time()-_t, result.get('agent_response', {}).get('type'))
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


# ── 복합 질문 노드 ──

# planner system prompt (v5 학습 데이터와 동일)
_PLANNER_SYSTEM_PROMPT = """당신은 업무 자동화 시스템의 Task Planner입니다.
사용자 요청을 분석하여 실행 가능한 단계별 계획을 JSON으로 출력하세요.

## 사용 가능한 intent (6개)
- judgment: 사규/규정 기반 판단 ("~해도 되나요?", "규정 확인", "규정 알려줘", "기준이 어떻게 돼?")
- doc_retrieve: 문서 검색/조회/요약 ("~문서 찾아줘", "~자료 검색", "회의록 조회")
- doc_generate: 문서 생성 ("보고서 만들어줘", "회의록 작성해줘")
- schedule_add: 일정 등록 ("~에 회의 잡아줘", "휴가 등록")
- schedule_view: 일정 조회 ("다음 주 일정 보여줘")
- general: 일반 질문 (위에 해당하지 않는 경우)

## judgment vs doc_retrieve 구분 기준 (중요!)
- judgment: 사내 규정/규칙/기준/수당/복리후생에 대한 질문. 규정 해석, 가능 여부 판단, 기준 설명 포함.
- doc_retrieve: 특정 문서/파일/보고서/회의록을 찾거나 검색하는 것.

## 출력 형식 (반드시 이 JSON 형식만 출력)
{
  "plan": [
    {
      "step_id": 1,
      "intent": "intent_name",
      "query": "이 단계에서 처리할 구체적 요청",
      "depends_on": []
    }
  ]
}

## 규칙
1. depends_on: 이 단계가 실행되기 전에 완료되어야 하는 step_id 목록
2. depends_on이 비어있으면 즉시 실행 가능 (병렬 처리 가능)
3. 단순 요청은 1단계로 처리
4. 최대 4단계까지만 분해
5. JSON만 출력하고 다른 설명은 하지 마세요"""


async def decompose_query(state: AgentState) -> AgentState:
    """복합 질문 감지 — vLLM planner LoRA (규칙 기반 fallback)"""
    _t = time.time()
    user_input = state["user_input"]

    if not ENABLE_COMPLEX_QUERY:
        state["sub_queries"] = []
        return state

    import os
    use_planner_sllm = os.getenv("PLANNER_MODE", "rule") == "sllm"

    sub_queries = []

    if use_planner_sllm:
        # vLLM planner LoRA 호출
        try:
            sub_queries = await _planner_sllm_decompose(user_input)
            logger.info(
                "[Orchestrator] planner sLLM 분해 (%.2fs) | %d단계: %s",
                time.time() - _t,
                len(sub_queries),
                [sq["hint"] for sq in sub_queries],
            )
        except Exception as e:
            logger.error("[Orchestrator] planner sLLM 실패, 규칙 기반 fallback: %s", e)
            sub_queries = detect_compound_query(user_input)
    else:
        # 규칙 기반 (기존)
        sub_queries = detect_compound_query(user_input)

    state["sub_queries"] = sub_queries

    if sub_queries:
        logger.info(
            "[Orchestrator] 복합 질문 감지 (%.2fs) | %d개 서브쿼리: %s",
            time.time() - _t,
            len(sub_queries),
            [sq["hint"] for sq in sub_queries],
        )
    else:
        logger.debug("[Orchestrator] 단일 질문 (%.2fs)", time.time() - _t)

    return state


async def _planner_sllm_decompose(user_input: str) -> list[dict]:
    """vLLM planner LoRA로 복합질문 분해

    Returns:
        단일이면 [] (classify_intent로 넘김)
        복합이면 [{"query": "...", "hint": "intent_name"}, ...]
    """
    import json
    import re
    from ai.serving.vllm_client import VLLMProvider

    llm = VLLMProvider().with_lora("planner")
    response = await llm.generate(
        prompt=user_input,
        system_prompt=_PLANNER_SYSTEM_PROMPT,
        temperature=0.1,
        max_tokens=512,
    )

    # 응답에서 JSON 블록만 추출 (설명 텍스트 섞여있을 수 있음)
    content = response.content.strip()
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r'\{[^{}]*"plan"\s*:\s*\[.*?\]\s*\}', content, re.DOTALL)
        if not match:
            logger.warning("[Orchestrator] planner 응답에서 JSON 추출 실패: %s", content[:200])
            return []
        result = json.loads(match.group())

    plan = result.get("plan", [])

    # 1단계면 단일 질문 → 빈 리스트 (classify_intent로)
    if len(plan) <= 1:
        return []

    # 복합: sub_queries 형식으로 변환
    sub_queries = []
    for step in plan:
        sub_queries.append({
            "query": step.get("query", user_input),
            "hint": step.get("intent", "general"),
            "step_id": step.get("step_id", 0),
            "depends_on": step.get("depends_on", []),
        })

    return sub_queries


def route_after_decompose(state: AgentState) -> str:
    """decompose 후 라우팅: 복합이면 compound_pending, 단일이면 classify_intent"""
    if state.get("sub_queries"):
        return "compound_pending"
    return "classify_intent"


def compound_pending(state: AgentState) -> AgentState:
    """복합 질문 처리 대기 — chat.py에서 각 sub_query를 순차 스트리밍"""
    sub_queries = state.get("sub_queries", [])
    state["agent_response"] = {
        "type": "compound",
        "message": "",
        "stream_pending": True,
        "sub_queries": sub_queries,
    }
    logger.info("[Orchestrator] compound_pending | %d개 서브쿼리 대기", len(sub_queries))
    return state


# ── 핵심 노드 ──


def classify_intent(state: AgentState) -> AgentState:
    """Intent 분류 — BERT (→ Solar fallback → 임베딩 fallback)"""
    _t = time.time()
    user_input = state["user_input"]
    logger.info("[Orchestrator] classify_intent 시작 | input='%s'", user_input)

    classifier = get_classifier()
    result = classifier.predict(user_input, return_candidates=True)

    state["intent"] = result["intent"]
    state["confidence"] = result["confidence"]
    state["intent_candidates"] = result.get("candidates", [
        {"intent": result["intent"], "confidence": result["confidence"]}
    ])

    logger.info(
        "[Orchestrator] classify_intent 완료 (%.2fs) | intent=%s, confidence=%.4f",
        time.time()-_t, state['intent'], state['confidence']
    )
    return state


def _is_schedule_followup(user_input: str, chat_history: list[dict]) -> bool:
    """이전 대화가 schedule 관련이고, 현재 입력이 후속 응답이면 followup"""
    import re
    text = user_input.lower()
    has_email = bool(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', user_input))
    has_meet_keyword = any(kw in text for kw in (
        "meet", "미트", "미팅", "링크", "화상",
        "네", "응", "좋아", "생성", "만들어", "yes", "ok",
        "초대", "메일", "보내", "참석",
    ))
    # 시간 관련 입력 (schedule_clarify 후속 응답)
    has_time_input = bool(re.search(r'\d{1,2}\s*시|\d{1,2}:\d{2}|오전|오후|저녁|아침|점심', text))

    # 이전 assistant 응답에서 schedule 관련 타입 확인
    last_schedule_type = None
    for msg in reversed(chat_history):
        agent_response = msg.get("agentResponse") or msg.get("agent_response")
        if agent_response and isinstance(agent_response, dict):
            if agent_response.get("type") in ("schedule_add", "schedule_followup", "schedule_clarify"):
                last_schedule_type = agent_response.get("type")
                break
        content = msg.get("content", "")
        if "일정이 Google Calendar에 등록" in content or "Meet 링크" in content or "초대 메일" in content:
            last_schedule_type = "schedule_add"
            break
        if "몇 시에 잡을까요" in content:
            last_schedule_type = "schedule_clarify"
            break

    if not last_schedule_type:
        return False

    # schedule_clarify 후속 → 시간 입력이면 followup
    if last_schedule_type == "schedule_clarify" and has_time_input:
        return True

    # schedule_add/followup 후속 → 이메일/meet 키워드면 followup
    if has_email or has_meet_keyword:
        return True

    return False


def route_by_intent(state: AgentState) -> str:
    """조건부 라우팅 — intent + confidence 기반 분기"""
    intent = state.get("intent", "")
    confidence = state.get("confidence", 0)

    # schedule followup 감지 (confidence 체크보다 우선 — 이전 대화 맥락 기반)
    user_input = state.get("user_input", "")
    chat_history = state.get("chat_history", [])
    logger.debug("[Orchestrator] followup 체크: chat_history=%d개, input='%s'", len(chat_history), user_input[:50])
    is_followup = _is_schedule_followup(user_input, chat_history)
    logger.debug("[Orchestrator] _is_schedule_followup 결과: %s", is_followup)
    if is_followup:
        state["intent"] = "schedule_followup"
        logger.info("[Orchestrator] 라우팅: schedule_followup 감지 → schedule_agent")
        return "schedule_agent"

    # 낮은 confidence → top-3 후보 제시
    if confidence < INTENT_CONFIDENCE_THRESHOLD:
        candidates = state.get("intent_candidates", [])
        if len(candidates) >= 2:
            logger.info("[Orchestrator] 라우팅: low_confidence → clarify_with_candidates")
            return "clarify_with_candidates"
        logger.info("[Orchestrator] 라우팅: low_confidence → general_response")
        return "general_response"

    # intent별 Agent 라우팅
    if intent == "general":
        route = "general_response"
    elif intent == "judgment":
        route = "judgment_agent"
    elif intent in ("doc_retrieve", "doc_generate"):
        route = "document_agent"
    elif intent.startswith("schedule_") or intent in ("pipeline_create", "approval_create"):
        route = "schedule_agent"
    else:
        route = "general_response"

    logger.info("[Orchestrator] 라우팅: %s (confidence=%.4f) → %s", intent, confidence, route)
    return route


def clarify_with_candidates(state: AgentState) -> AgentState:
    """top-3 후보 제시 노드 (confidence < 0.7)"""
    candidates = state.get("intent_candidates", [])
    logger.debug("[Orchestrator] clarify_with_candidates 진입 | candidates=%s", candidates)

    # 후보 목록 구성
    intent_labels_kr = {
        "judgment": "규정 판단",
        "doc_retrieve": "문서 검색/조회/요약",
        "doc_generate": "문서 작성",
        "schedule_add": "일정 추가",
        "schedule_view": "일정 조회",
        "pipeline_create": "태스크 생성",
        "approval_create": "결재 요청",
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


def format_response(state: AgentState) -> AgentState:
    """응답 포맷팅 노드 — agent_response에 type/message 필드 보장"""
    logger.debug("[Orchestrator] format_response 진입 | agent_response type=%s", state.get('agent_response', {}).get('type', 'none'))
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


# ── 그래프 빌드 ──


def build_graph():
    """LangGraph StateGraph 빌드 + 컴파일"""
    graph = StateGraph(AgentState)

    # 노드 등록
    graph.add_node("decompose_query", decompose_query)
    graph.add_node("compound_pending", compound_pending)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("clarify_with_candidates", clarify_with_candidates)
    graph.add_node("judgment_agent", safe_judgment_agent)
    graph.add_node("document_agent", safe_document_agent)
    graph.add_node("schedule_agent", safe_schedule_agent)
    graph.add_node("general_response", general_response_node)
    graph.add_node("format_response", format_response)

    # 엔트리 포인트 — 복합 질문 감지부터 시작
    graph.set_entry_point("decompose_query")

    # decompose_query → 복합/단일 분기
    graph.add_conditional_edges(
        "decompose_query",
        route_after_decompose,
        {
            "compound_pending": "compound_pending",
            "classify_intent": "classify_intent",
        },
    )

    # classify_intent → intent + confidence 기반 분기
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "clarify_with_candidates": "clarify_with_candidates",
            "judgment_agent": "judgment_agent",
            "document_agent": "document_agent",
            "schedule_agent": "schedule_agent",
            "general_response": "general_response",
        },
    )

    # 모든 Agent/노드 → format_response → END
    graph.add_edge("compound_pending", "format_response")
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
            logger.info("Orchestrator graph compiled successfully")
        except Exception as e:
            logger.error("Graph build error: %s", e, exc_info=True)
            raise
    return _compiled_graph
