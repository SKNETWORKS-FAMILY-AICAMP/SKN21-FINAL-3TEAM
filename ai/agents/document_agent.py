"""
문서 Agent (팀원 C 담당)

기능:
  - 회의록 파싱 → 결정사항, Action Item, 참석자, 기한 추출 (JSON)
  - 문서 요약 (sLLM 활용)
  - 템플릿 기반 문서 생성 (JD, 보고서, 제안서)
  - 규정 리스크 자동 감지 (RAG 기반 규정 대조)

입출력:
  Input: AgentState (user_input, intent, context)
  Output: AgentState (agent_response 채움)
"""
from ai.agents.state import AgentState


def document_agent(state: AgentState) -> AgentState:
    """
    문서 Agent 노드 함수 (LangGraph 노드 인터페이스)

    intent에 따라 분기:
      - doc_search: 문서 검색 결과 반환
      - doc_summary: 문서 요약
      - doc_generate: 템플릿 기반 문서 생성
      - meeting_analysis: 회의록 분석

    응답 형식 (meeting_analysis 예시):
    {
        "type": "meeting_analysis",
        "summary": "회의 요약...",
        "decisions": ["결정사항1", "결정사항2"],
        "action_items": [
            {"content": "...", "assignee": "홍길동", "due_date": "2025-02-15"}
        ],
        "risk_level": "중간",
        "risks": [
            {"description": "...", "regulation": "정보보안 규정 3.2조", "level": "높음"}
        ]
    }
    """
    # TODO: 팀원 C 구현
    raise NotImplementedError("팀원 C: 문서 Agent 구현 필요")
