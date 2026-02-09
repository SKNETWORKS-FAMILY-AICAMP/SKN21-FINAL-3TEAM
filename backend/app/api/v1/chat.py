"""
챗봇 API + SSE 스트리밍 (팀원 A 담당)
"""
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse
from app.api.deps import get_current_user

router = APIRouter()


@router.post("/stream")
async def chat_stream(request: ChatRequest, user=Depends(get_current_user)):
    """SSE 스트리밍 챗봇 응답"""

    async def event_generator():
        # 1. Intent 분류 결과 전송
        # TODO: intent_classifier 연동
        yield f"data: {json.dumps({'type': 'intent', 'value': 'judgment'})}\n\n"

        # 2. Agent 호출 상태 전송
        yield f"data: {json.dumps({'type': 'status', 'value': 'Agent 호출 중...'})}\n\n"

        # 3. LLM 응답 토큰 스트리밍
        # TODO: LangGraph 오케스트레이터 연동
        yield f"data: {json.dumps({'type': 'token', 'value': '응답 준비 중...'})}\n\n"

        # 4. 완료
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, user=Depends(get_current_user)):
    """일반 (비스트리밍) 챗봇 응답"""
    # TODO: 팀원 A - LangGraph 오케스트레이터 연동
    return ChatResponse(
        intent="judgment",
        confidence=0.0,
        response="구현 예정",
    )
