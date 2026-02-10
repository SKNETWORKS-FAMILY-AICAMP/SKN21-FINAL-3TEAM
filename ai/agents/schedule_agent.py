"""
일정 Agent (팀원 D 담당)

기능:
  - Action Item → 일정 자동 등록
  - 일정 조회/수정/삭제
  - 마감일 기반 우선순위 자동 설정
  - 담당자 자동 지정
  - Google Calendar + Meet + Tasks + Gmail + Sheets 통합 연동

입출력:
  Input: AgentState (user_input, intent)
  Output: AgentState (agent_response + google_services_result 채움)

schedule_add 응답 형식:
  {
      "type": "schedule_add",
      "schedule": {
          "title": "...",
          "start_time": "2025-02-10T09:00:00",
          "end_time": "2025-02-10T10:00:00",
          "priority": "high"
      },
      "google_services": {
          "calendar_synced": true,
          "meet_link": "https://meet.google.com/abc-defg-hij",
          "task_created": true,
          "email_sent": true,
          "sheet_updated": true,
          "sheet_url": "https://docs.google.com/spreadsheets/d/..."
      },
      "message": "일정이 등록되었습니다."
  }

schedule_view 응답 형식:
  {
      "type": "schedule_view",
      "schedules": [...],
      "message": "일정 목록입니다."
  }
"""
from ai.agents.state import AgentState


def schedule_agent(state: AgentState) -> AgentState:
    """
    일정 Agent 노드 함수 (LangGraph 노드 인터페이스)

    intent에 따라 분기:
      - schedule_add: 일정 추가 + Google 서비스 통합 연동
      - schedule_view: 일정 조회
    """
    # TODO: 팀원 D 구현
    # - intent == "schedule_add": LLM으로 user_input 파싱 → ScheduleService.create_with_google_services() 호출
    # - intent == "schedule_view": 조회 조건 파싱 → DB 조회
    # - agent_response + google_services_result 설정
    raise NotImplementedError("팀원 D: 일정 Agent 구현 필요")
