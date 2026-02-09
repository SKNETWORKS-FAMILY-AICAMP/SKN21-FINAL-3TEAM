"""
Agent 공유 상태 정의 (팀원 A 관리, 전원 참조)

모든 Agent 노드는 이 State를 입력/출력으로 사용합니다.
새 필드를 추가할 때는 팀원 A에게 먼저 확인하세요.
"""
from typing import TypedDict, Optional


class AgentState(TypedDict):
    """LangGraph 공유 상태"""

    # 사용자 입력
    user_input: str
    user_id: int

    # Intent 분류 결과 (팀원 A)
    intent: str  # judgment, doc_search, doc_summary, doc_generate, meeting_analysis, schedule_add, schedule_view
    confidence: float

    # RAG 검색 결과 (팀원 B)
    context: list  # 검색된 문서 chunk 리스트

    # Agent 응답 (팀원 B/C/D 각각 작성)
    agent_response: dict

    # 대화 이력 (팀원 A)
    chat_history: list

    # 에러 (팀원 A)
    error: Optional[str]
