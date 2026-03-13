"""
챗봇 스키마 (팀원 A 정의)

SSE 스트리밍 흐름:
  1. 프론트가 ChatRequest를 POST로 전송
  2. 백엔드가 SSE(Server-Sent Events)로 응답 스트리밍
  3. 프론트가 이벤트를 하나씩 받아서 실시간 렌더링

SSE 이벤트 순서:
  → [intent]   어떤 Agent가 처리하는지 알려줌
  → [token]    응답 텍스트가 한 글자씩 옴 (실시간 타이핑 효과)
  → [token]    ...
  → [result]   최종 구조화된 응답 (카드 UI용 데이터)
  → [done]     스트리밍 종료
  → [error]    에러 발생 시
"""
from pydantic import BaseModel
from typing import Optional, Any


# ── 요청 ──

class ChatRequest(BaseModel):
    """챗봇 메시지 요청"""
    message: str                            # 사용자 입력 텍스트
    session_id: Optional[str] = None        # 대화 세션 ID (없으면 새 세션)
    source_page: Optional[str] = None       # 어느 페이지에서 보냈는지 (chatbot | meeting_page | document_page)
    template_id: Optional[int] = None       # 문서/회의록 페이지에서 템플릿 지정 시
    template_type: Optional[str] = None     # 시스템 템플릿 타입 직접 지정 시
    document_id: Optional[int] = None       # 문서 요약/QA 시 대상 문서 ID


# ── Agent별 Result 데이터 모델 ──

class JudgmentResultData(BaseModel):
    """judgment intent 응답 데이터"""
    result: str                             # yes | no | conditional
    reasoning: str
    regulations: list[dict] = []            # [{"name": "...", "article": "...", "content": "..."}]


class DocGenerateResultData(BaseModel):
    """doc_generate intent 응답 데이터"""
    document_id: int
    preview: str
    template_type: str
    download_url: str


class DocSummaryResultData(BaseModel):
    """doc_summary intent 응답 데이터"""
    title: Optional[str] = None
    core_summary: str
    key_points: list[str] = []
    keywords: list[str] = []


class DocQAResultData(BaseModel):
    """doc_qa intent 응답 데이터"""
    answer: str
    citations: list[dict] = []              # [{"source": "...", "content": "...", "relevance": "높음|중간|낮음"}]
    confidence: float = 0.0


class DocSearchResultData(BaseModel):
    """doc_search intent 응답 데이터"""
    answer: str
    sources: list[dict] = []                # [{"id": 1, "title": "...", "snippet": "...", "score": 0.95}]


class ScheduleAddResultData(BaseModel):
    """schedule_add intent 응답 데이터"""
    schedule_id: int
    google_services: Optional[dict] = None  # GoogleServicesResult 구조


# ── SSE 이벤트 ──

class SSEIntentEvent(BaseModel):
    """[intent] 이벤트 — Intent 분류 결과 알려줌"""
    event: str = "intent"
    intent: str                             # judgment, doc_search, doc_generate, doc_summary, schedule_add, schedule_view, general
    confidence: float
    agent_type: str                         # judgment_agent, document_agent, schedule_agent, general


class SSETokenEvent(BaseModel):
    """[token] 이벤트 — 응답 텍스트가 한 토큰씩 옴"""
    event: str = "token"
    token: str                              # 토큰 하나 (글자 1~2개)


class SSEResultEvent(BaseModel):
    """[result] 이벤트 — 최종 구조화된 응답 (카드 UI에서 사용)

    intent별 data 구조:
      judgment         → JudgmentResultData
      doc_generate     → DocGenerateResultData
      doc_search       → DocSearchResultData
      doc_summary      → DocSummaryResultData
      schedule_add     → ScheduleAddResultData
      schedule_view    → list[ScheduleResponse]
      general          → {"answer": "..."}
    """
    event: str = "result"
    intent: str
    data: Any                               # intent별 구조 — 위 docstring 참고


class SSEDoneEvent(BaseModel):
    """[done] 이벤트 — 스트리밍 종료"""
    event: str = "done"
    chat_log_id: Optional[int] = None       # 저장된 대화 로그 ID


class SSEErrorEvent(BaseModel):
    """[error] 이벤트 — 에러 발생"""
    event: str = "error"
    message: str
    code: Optional[str] = None              # 에러 코드


# ── 일반 응답 (SSE 안 쓸 때) ──

class ChatResponse(BaseModel):
    """비스트리밍 응답 (테스트/폴백용)"""
    intent: str
    confidence: float
    response: str
    agent_type: Optional[str] = None
    data: Optional[Any] = None              # 구조화된 응답 데이터
