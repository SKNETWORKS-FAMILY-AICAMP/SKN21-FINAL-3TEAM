"""
LangGraph Agent 오케스트레이터 (팀원 A 담당)

그래프 구조:
  [사용자 입력]
       |
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
from ai.agents.intent_classifier import get_classifier
from ai.agents.config import INTENT_CONFIDENCE_THRESHOLD

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
            print("[Orchestrator] judgment 스트리밍: RAG 검색 시작 (top_k=10)...")
            pipeline = get_qdrant_pipeline()
            context = pipeline.retrieve(query=user_input, user_id=user_id, top_k=10)
            print(f"[Orchestrator] judgment RAG 완료 ({time.time()-_t_rag:.2f}s) | {len(context)}개 문서")

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
            print(f"[Orchestrator] judgment stream_pending 반환 ({time.time()-_t:.2f}s)")
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


# ── 핵심 노드 ──


def classify_intent(state: AgentState) -> AgentState:
    """Intent 분류 — BERT (→ Solar fallback → 임베딩 fallback)"""
    _t = time.time()
    user_input = state["user_input"]
    print(f"[Orchestrator] classify_intent 시작 | input='{user_input}'")

    classifier = get_classifier()
    result = classifier.predict(user_input, return_candidates=True)

    state["intent"] = result["intent"]
    state["confidence"] = result["confidence"]
    state["intent_candidates"] = result.get("candidates", [
        {"intent": result["intent"], "confidence": result["confidence"]}
    ])

    print(
        f"[Orchestrator] classify_intent 완료 ({time.time()-_t:.2f}s) | "
        f"intent={state['intent']}, confidence={state['confidence']:.4f}"
    )
    return state


def route_by_intent(state: AgentState) -> str:
    """조건부 라우팅 — intent + confidence 기반 분기"""
    intent = state.get("intent", "")
    confidence = state.get("confidence", 0)

    # 낮은 confidence → top-3 후보 제시
    if confidence < INTENT_CONFIDENCE_THRESHOLD:
        candidates = state.get("intent_candidates", [])
        if len(candidates) >= 2:
            print(f"[Orchestrator] 라우팅: low_confidence → clarify_with_candidates")
            return "clarify_with_candidates"
        print(f"[Orchestrator] 라우팅: low_confidence → general_response")
        return "general_response"

    # intent별 Agent 라우팅
    if intent == "general":
        route = "general_response"
    elif intent == "judgment":
        route = "judgment_agent"
    elif intent in ("doc_search", "doc_generate", "doc_summary", "doc_qa"):
        route = "document_agent"
    elif intent.startswith("schedule_"):
        route = "schedule_agent"
    else:
        route = "general_response"

    print(f"[Orchestrator] 라우팅: {intent} (confidence={confidence:.4f}) → {route}")
    return route


def clarify_with_candidates(state: AgentState) -> AgentState:
    """top-3 후보 제시 노드 (confidence < 0.7)"""
    candidates = state.get("intent_candidates", [])
    print(f"[Orchestrator] clarify_with_candidates 진입 | candidates={candidates}")

    # 후보 목록 구성
    intent_labels_kr = {
        "judgment": "규정 판단",
        "doc_search": "문서 검색",
        "doc_generate": "문서 작성",
        "doc_summary": "문서 요약",
        "doc_qa": "문서 QA",
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


# ── 그래프 빌드 ──


def build_graph():
    """LangGraph StateGraph 빌드 + 컴파일"""
    graph = StateGraph(AgentState)

    # 노드 등록
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("clarify_with_candidates", clarify_with_candidates)
    graph.add_node("judgment_agent", safe_judgment_agent)
    graph.add_node("document_agent", safe_document_agent)
    graph.add_node("schedule_agent", safe_schedule_agent)
    graph.add_node("general_response", general_response_node)
    graph.add_node("format_response", format_response)

    # 엔트리 포인트
    graph.set_entry_point("classify_intent")

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
            logger.error(f"Graph build error: {e}", exc_info=True)
            raise
    return _compiled_graph
