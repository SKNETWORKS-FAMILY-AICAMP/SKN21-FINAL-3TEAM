"""
LangGraph Agent 오케스트레이터 (팀원 A 담당)

그래프 구조:
  [사용자 입력]
       |
  [Intent 분류 노드]
       | (조건부 엣지)
       +-- judgment          -> [판단 Agent 노드]     (팀원 B)
       +-- doc_search        -> [문서 Agent 노드]     (팀원 C)
       +-- doc_generate      -> [문서 Agent 노드]     (팀원 C)
       +-- meeting_generate  -> [문서 Agent 노드]     (팀원 C)
       +-- schedule_*        -> [일정 Agent 노드]     (팀원 D)
       +-- general           -> [일반 응답 노드]
       +-- confidence < 0.7  -> [재질문 노드]
       |
  [응답 포맷팅 노드]
"""

import logging

from langgraph.graph import StateGraph, END

from ai.agents.state import AgentState
from ai.agents.intent_classifier import get_classifier

logger = logging.getLogger(__name__)

# 컴파일된 그래프 캐시
_compiled_graph = None


# ── 노드 함수 ──


def classify_intent(state: AgentState) -> AgentState:
    """Intent 분류 노드"""
    classifier = get_classifier()
    result = classifier.predict(state["user_input"])
    state["intent"] = result["intent"]
    state["confidence"] = result["confidence"]
    logger.info("Intent: %s (%.4f)", result["intent"], result["confidence"])
    return state


def route_by_intent(state: AgentState) -> str:
    """조건부 라우팅"""
    if state.get("confidence", 0) < 0.7:
        return "clarify"

    intent = state.get("intent", "")
    if intent == "judgment":
        return "judgment_agent"
    elif intent in ("doc_search", "doc_generate", "meeting_generate"):
        return "document_agent"
    elif intent.startswith("schedule_"):
        return "schedule_agent"
    elif intent == "general":
        return "general_response"
    else:
        return "clarify"


def clarify_node(state: AgentState) -> AgentState:
    """재질문 노드"""
    state["agent_response"] = {
        "type": "clarify",
        "message": "질문을 좀 더 구체적으로 말씀해 주시겠어요?",
    }
    return state


def _get_settings():
    """config import — FastAPI 실행 시 / 단독 실행 시 모두 대응"""
    try:
        from app.config import get_settings
        return get_settings()
    except ImportError:
        from backend.app.config import get_settings
        return get_settings()


async def general_response_node(state: AgentState) -> AgentState:
    """일반 응답 노드 — LLM API 호출"""
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
            model=settings.LLM_MODEL_NAME,
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
    try:
        from ai.agents.judgment_agent import judgment_agent

        result = judgment_agent(state)
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
    try:
        from ai.agents.document_agent import document_agent

        result = document_agent(state)
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
    try:
        from ai.agents.schedule_agent import schedule_agent

        result = schedule_agent(state)
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


def format_response(state: AgentState) -> AgentState:
    """응답 포맷팅 노드 — agent_response에 type/message 필드 보장"""
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
    graph.add_node("judgment_agent", safe_judgment_agent)
    graph.add_node("document_agent", safe_document_agent)
    graph.add_node("schedule_agent", safe_schedule_agent)
    graph.add_node("general_response", general_response_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("format_response", format_response)

    # 엔트리 포인트
    graph.set_entry_point("classify_intent")

    # 조건부 엣지: Intent에 따라 분기
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "judgment_agent": "judgment_agent",
            "document_agent": "document_agent",
            "schedule_agent": "schedule_agent",
            "general_response": "general_response",
            "clarify": "clarify",
        },
    )

    # 모든 Agent/노드 → format_response → END
    graph.add_edge("judgment_agent", "format_response")
    graph.add_edge("document_agent", "format_response")
    graph.add_edge("schedule_agent", "format_response")
    graph.add_edge("general_response", "format_response")
    graph.add_edge("clarify", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile()


def get_graph():
    """컴파일된 그래프 인스턴스 반환 (캐시)"""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
