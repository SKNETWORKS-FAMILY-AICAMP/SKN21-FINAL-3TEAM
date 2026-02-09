"""
일정 Agent (팀원 D 담당)

기능:
  - Action Item → 일정 자동 등록
  - 일정 조회/수정/삭제
  - 마감일 기반 우선순위 자동 설정
  - 담당자 자동 지정
  - Google Calendar 동기화

입출력:
  Input: AgentState (user_input, intent)
  Output: AgentState (agent_response 채움)
"""
from ai.agents.state import AgentState


def schedule_agent(state: AgentState) -> AgentState:
    """
    일정 Agent 노드 함수 (LangGraph 노드 인터페이스)

    intent에 따라 분기:
      - schedule_add: 일정 추가 + Google Calendar 동기화
      - schedule_view: 일정 조회

    응답 형식 (schedule_add 예시):
    {
        "type": "schedule_add",
        "schedule": {
            "title": "...",
            "start_time": "2025-02-10T09:00:00",
            "end_time": "2025-02-10T10:00:00",
            "priority": "high",
            "google_synced": true
        },
        "message": "일정이 등록되었습니다."
    }
    """
    # TODO: 팀원 D 구현
    raise NotImplementedError("팀원 D: 일정 Agent 구현 필요")
