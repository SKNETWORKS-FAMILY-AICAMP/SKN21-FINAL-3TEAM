"""
문서 Agent (팀원 C 담당)

기능:
  - 문서 검색 결과 반환 (doc_search)
  - 사용자 템플릿(업로드 or 선택) 기반 문서 요약 및 생성 (doc_generate)
  - 회의 내용 요약 + 회의록 양식 채워서 생성 (meeting_generate)
  - 규정 리스크 자동 감지 (RAG 기반 규정 대조)

입출력:
  Input: AgentState (user_input, intent, context, template_id)
  Output: AgentState (agent_response 채움)
"""
from ai.agents.state import AgentState


def document_agent(state: AgentState) -> AgentState:
    """
    문서 Agent 노드 함수 (LangGraph 노드 인터페이스)

    intent에 따라 분기:
      - doc_search: 문서 검색 결과 반환
      - doc_generate: 사용자 템플릿(업로드 or 선택) 기반 문서 요약 및 생성
      - meeting_generate: 회의 내용 요약 + 회의록 양식 채워서 생성

    응답 형식 (meeting_generate 예시):
    {
        "type": "meeting_generate",
        "summary": "회의 요약...",
        "decisions": ["결정사항1", "결정사항2"],
        "action_items": [
            {"content": "...", "assignee": "홍길동", "due_date": "2025-02-15"}
        ],
        "risk_level": "중간",
        "risks": [
            {"description": "...", "regulation": "정보보안 규정 3.2조", "level": "높음"}
        ],
        "preview": "# 마크다운 미리보기...",
        "document_id": 123,
        "download_url": "/api/v1/meetings/123/download",
        "auto_scan": true
    }
    """
    # TODO: 팀원 C 구현
    #
    # doc_generate 응답 형식:
    # {
    #     "type": "doc_generate",
    #     "template_id": 42,
    #     "template_name": "보고서",
    #     "preview": "# 2026 Q1 보고서\n## 개요\n...",
    #     "document_id": 123,
    #     "download_url": "/api/v1/documents/123/download"
    # }
    #
    # meeting_generate 응답 형식:
    # {
    #     "type": "meeting_generate",
    #     "summary": "회의 요약...",
    #     "decisions": ["결정사항1", "결정사항2"],
    #     "action_items": [
    #         {"content": "...", "assignee": "홍길동", "due_date": "2025-02-15"}
    #     ],
    #     "risk_level": "중간",
    #     "risks": [
    #         {"description": "...", "regulation": "정보보안 규정 3.2조", "level": "높음"}
    #     ],
    #     "preview": "# 회의록 마크다운...",
    #     "document_id": 456,
    #     "download_url": "/api/v1/meetings/456/download",
    #     "auto_scan": True
    # }
    raise NotImplementedError("팀원 C: 문서 Agent 구현 필요")
