"""
Agent 공유 상태 정의 (PM 지용 관리, 전원 참조)

모든 Agent 노드는 이 State를 입력/출력으로 사용합니다.
필드 추가/수정이 필요하면 PM(지용)에게 요청하세요.

- 이 파일을 직접 수정하지 마세요
- 각 Agent는 자기 담당 필드만 읽고/쓰면 됩니다
"""
from typing import TypedDict, Optional


class AgentState(TypedDict):
    """LangGraph 공유 상태"""

    # ── 입력 (백엔드 → AI) ──
    user_input: str                         # 사용자 입력 텍스트
    user_id: int                            # 사용자 ID

    # ── Intent 분류 (지용) ──
    intent: str                             # judgment | doc_search | doc_generate | doc_summary | doc_qa | schedule_add | schedule_view | schedule_followup | general
    confidence: float                       # 분류 신뢰도 (0.0~1.0)
    intent_candidates: Optional[list]       # top-k intent 후보 [{"intent": str, "confidence": float}]

    # ── RAG 검색 결과 (승언) ──
    context: list[dict]                     # [{"content": str, "source": str, "score": float}]

    # ── Agent 응답 (경은/승언 각각 작성) ──
    agent_response: dict                    # Agent가 생성한 최종 응답

    # ── 대화 이력 (경은) ──
    chat_history: list[dict]                # [{"role": "user"|"assistant", "content": "..."}]

    # ── 에러 (경은) ──
    error: Optional[str]                    # 에러 메시지 (없으면 None)

    # ── 템플릿 (PM 지용이 정의, 승언이 사용) ──
    template_id: Optional[int]              # DB 템플릿 ID
    source_page: Optional[str]              # 요청 출처: chatbot | meeting_page | document_page
    template_fields: Optional[list[str]]    # 동적 필드 목록 (예: ["title", "summary", "key_points"])

    # ── 문서 요약/QA (승언) ──
    extracted_text: Optional[str]           # 업로드 파일에서 추출한 텍스트
    document_id: Optional[int]              # 문서 DB ID (프론트에서 선택 시)
    document_content: Optional[str]         # 문서 본문 텍스트 (DB 로딩 or 프론트 전달)

    # ── Google 연동 (혜빈) ──
    google_services_result: Optional[dict]  # schedule_add 시 Google 서비스 결과

    # ── 스트리밍 제어 ──
    stream_mode: Optional[bool]             # True이면 LLM 호출을 chat.py에서 직접 스트리밍 처리
