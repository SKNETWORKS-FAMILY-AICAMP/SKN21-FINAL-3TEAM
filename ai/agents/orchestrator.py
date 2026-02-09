"""
LangGraph Agent 오케스트레이터 (팀원 A 담당)

그래프 구조:
  [사용자 입력]
       ↓
  [Intent 분류 노드]
       ↓ (조건부 엣지)
       ├── judgment     → [판단 Agent 노드]     (팀원 B)
       ├── doc_*        → [문서 Agent 노드]     (팀원 C)
       ├── schedule_*   → [일정 Agent 노드]     (팀원 D)
       └── confidence < 0.7 → [재질문 노드]
       ↓
  [응답 포맷팅 노드]
"""
from ai.agents.state import AgentState

# from langgraph.graph import StateGraph, END


def classify_intent(state: AgentState) -> AgentState:
    """Intent 분류 노드 (팀원 A 구현)"""
    # TODO: klue/bert-base 모델로 intent 분류
    # state["intent"] = 분류결과
    # state["confidence"] = 신뢰도
    return state


def route_by_intent(state: AgentState) -> str:
    """조건부 라우팅 (팀원 A 구현)"""
    if state.get("confidence", 0) < 0.7:
        return "clarify"

    intent = state.get("intent", "")
    if intent == "judgment":
        return "judgment_agent"
    elif intent.startswith("doc_") or intent == "meeting_analysis":
        return "document_agent"
    elif intent.startswith("schedule_"):
        return "schedule_agent"
    else:
        return "clarify"


def clarify_node(state: AgentState) -> AgentState:
    """재질문 노드 (팀원 A 구현)"""
    state["agent_response"] = {
        "type": "clarify",
        "message": "질문을 좀 더 구체적으로 말씀해 주시겠어요?",
    }
    return state


def format_response(state: AgentState) -> AgentState:
    """응답 포맷팅 노드 (팀원 A 구현)"""
    # TODO: agent_response를 사용자 친화적 형태로 변환
    return state


def build_graph():
    """LangGraph StateGraph 빌드 (팀원 A 구현)"""
    # TODO: 팀원 A
    # graph = StateGraph(AgentState)
    # graph.add_node("classify_intent", classify_intent)
    # graph.add_node("judgment_agent", judgment_agent)    # 팀원 B
    # graph.add_node("document_agent", document_agent)    # 팀원 C
    # graph.add_node("schedule_agent", schedule_agent)    # 팀원 D
    # graph.add_node("clarify", clarify_node)
    # graph.add_node("format_response", format_response)
    # graph.set_entry_point("classify_intent")
    # graph.add_conditional_edges("classify_intent", route_by_intent, {...})
    # return graph.compile()
    raise NotImplementedError("팀원 A: LangGraph 그래프 빌드 구현 필요")
