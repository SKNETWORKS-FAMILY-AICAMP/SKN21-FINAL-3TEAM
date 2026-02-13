"""
챗봇 API + SSE 스트리밍 (팀원 A 담당)
"""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_initial_state(request: ChatRequest, user, stream_mode: bool = False) -> dict:
    """AgentState 필드 초기화"""
    return {
        "user_input": request.message,
        "user_id": user.id,
        "intent": "",
        "confidence": 0.0,
        "context": [],
        "agent_response": {},
        "chat_history": [],
        "error": None,
        "template_id": request.template_id,
        "source_page": request.source_page,
        "template_fields": None,
        "extracted_text": None,
        "google_services_result": None,
        "stream_mode": stream_mode,
    }


def _get_agent_type(intent: str) -> str:
    """intent에 대응하는 agent_type 반환"""
    if intent == "judgment":
        return "judgment_agent"
    elif intent in ("doc_search", "doc_generate", "meeting_generate"):
        return "document_agent"
    elif intent.startswith("schedule_"):
        return "schedule_agent"
    return "general"


@router.post("/stream")
async def chat_stream(request: ChatRequest, user=Depends(get_current_user)):
    """SSE 스트리밍 챗봇 응답"""

    async def event_generator():
        try:
            logger.info(f"[Chat] Starting stream for user {user.id}: '{request.message}'")

            # lazy import (AI 의존성 없을 때 서버 기동 안 깨지게)
            from ai.agents.orchestrator import get_graph

            graph = get_graph()
            initial_state = _build_initial_state(request, user, stream_mode=True)

            logger.info(f"[Chat] Initial state: intent={initial_state.get('intent')}, user_input={initial_state.get('user_input')}")

            # astream으로 노드별 실시간 이벤트 전송
            final_state = {}

            async for event in graph.astream(initial_state):
                # event = {"node_name": {updated_state_fields}}
                for node_name, node_output in event.items():
                    final_state.update(node_output)

                    if node_name == "classify_intent":
                        # 1. Intent 분류 결과 즉시 전송
                        intent = node_output.get("intent", "general")
                        confidence = node_output.get("confidence", 0.0)
                        yield f"data: {json.dumps({'type': 'intent', 'intent': intent, 'confidence': confidence, 'agent_type': _get_agent_type(intent)}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'status', 'value': f'{_get_agent_type(intent)} 처리 중...'}, ensure_ascii=False)}\n\n"

                    elif node_name == "general_response":
                        # 2-1. 일반 응답 스트리밍 (Solar API)
                        import os as _os
                        from openai import AsyncOpenAI

                        solar_key = _os.getenv("SOLAR_API_KEY")

                        if not solar_key:
                            yield f"data: {json.dumps({'type': 'error', 'message': 'SOLAR_API_KEY가 설정되지 않았습니다.'}, ensure_ascii=False)}\n\n"
                            continue

                        client = AsyncOpenAI(
                            api_key=solar_key,
                            base_url="https://api.upstage.ai/v1/solar",
                        )

                        user_input = final_state.get("user_input", "")
                        chat_history = final_state.get("chat_history", [])

                        stream = await client.chat.completions.create(
                            model="solar-1-mini-chat",
                            messages=[
                                {"role": "system", "content": "당신은 업무 도우미 '듀듀'입니다. 한국어로 친절하게 답변하세요."},
                                *chat_history,
                                {"role": "user", "content": user_input},
                            ],
                            temperature=0.7,
                            max_tokens=1024,
                            stream=True,
                        )

                        full_response = ""
                        async for chunk in stream:
                            if chunk.choices[0].delta.content:
                                token = chunk.choices[0].delta.content
                                full_response += token
                                yield f"data: {json.dumps({'type': 'token', 'value': token}, ensure_ascii=False)}\n\n"

                        # 최종 응답 저장
                        final_state["agent_response"] = {
                            "type": "general",
                            "message": full_response,
                        }

                    elif node_name == "document_agent":
                        # 2-2. 문서 Agent 스트리밍
                        agent_response = node_output.get("agent_response", {})

                        if agent_response.get("stream_pending"):
                            # RAG 검색은 완료, LLM 답변만 스트리밍
                            import os as _os2
                            from openai import AsyncOpenAI as _AsyncOpenAI2

                            solar_key = _os2.getenv("SOLAR_API_KEY")
                            if not solar_key:
                                yield f"data: {json.dumps({'type': 'error', 'message': 'SOLAR_API_KEY가 설정되지 않았습니다.'}, ensure_ascii=False)}\n\n"
                                continue

                            doc_client = _AsyncOpenAI2(
                                api_key=solar_key,
                                base_url="https://api.upstage.ai/v1/solar",
                            )

                            doc_stream = await doc_client.chat.completions.create(
                                model="solar-1-mini-chat",
                                messages=[
                                    {"role": "system", "content": agent_response["sys_prompt"]},
                                    {"role": "user", "content": agent_response["user_prompt"]},
                                ],
                                temperature=0.7,
                                max_tokens=1024,
                                stream=True,
                            )

                            full_doc_response = ""
                            async for chunk in doc_stream:
                                if chunk.choices[0].delta.content:
                                    token = chunk.choices[0].delta.content
                                    full_doc_response += token
                                    yield f"data: {json.dumps({'type': 'token', 'value': token}, ensure_ascii=False)}\n\n"

                            # 최종 응답 업데이트
                            agent_response["message"] = full_doc_response
                            agent_response["answer"] = full_doc_response
                            agent_response.pop("stream_pending", None)
                            agent_response.pop("sys_prompt", None)
                            agent_response.pop("user_prompt", None)
                            final_state["agent_response"] = agent_response
                        else:
                            yield f"data: {json.dumps({'type': 'status', 'value': 'document_agent 처리 완료'}, ensure_ascii=False)}\n\n"

                    elif node_name == "format_response":
                        # 3. 최종 응답 전송
                        agent_response = node_output.get("agent_response", final_state.get("agent_response", {}))
                        intent = final_state.get("intent", "general")
                        message = agent_response.get("message", "")

                        # 이미 스트리밍한 경우 token 전송 건너뛰기
                        if not agent_response.get("stream_pending") and intent not in ("general", "doc_search"):
                            yield f"data: {json.dumps({'type': 'token', 'value': message}, ensure_ascii=False)}\n\n"

                        yield f"data: {json.dumps({'type': 'result', 'intent': intent, 'data': agent_response}, ensure_ascii=False)}\n\n"

                    else:
                        # 2. Agent 노드 완료 시 상태 업데이트
                        yield f"data: {json.dumps({'type': 'status', 'value': f'{node_name} 처리 완료'}, ensure_ascii=False)}\n\n"

            # 4. 완료
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"[Chat] Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, user=Depends(get_current_user)):
    """일반 (비스트리밍) 챗봇 응답"""
    try:
        from ai.agents.orchestrator import get_graph

        graph = get_graph()
        initial_state = _build_initial_state(request, user)

        result = await graph.ainvoke(initial_state)

        intent = result.get("intent", "general")
        confidence = result.get("confidence", 0.0)
        agent_response = result.get("agent_response", {})

        return ChatResponse(
            intent=intent,
            confidence=confidence,
            response=agent_response.get("message", ""),
            agent_type=_get_agent_type(intent),
            data=agent_response,
        )
    except Exception as e:
        logger.error("Chat error: %s", e)
        return ChatResponse(
            intent="general",
            confidence=0.0,
            response=f"오류가 발생했습니다: {e}",
        )
