"""
챗봇 API + SSE 스트리밍 (팀원 A 담당)
"""

import json
import logging
import time

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
            _t_total = time.time()
            print(f"\n{'='*60}")
            print(f"[Chat] 요청 수신 | user_id={user.id} | message='{request.message}'")
            print(f"{'='*60}")

            # lazy import (AI 의존성 없을 때 서버 기동 안 깨지게)
            from ai.agents.orchestrator import get_graph

            print("[Chat] 그래프 로딩 중...")
            graph = get_graph()
            initial_state = _build_initial_state(request, user, stream_mode=True)
            print("[Chat] 그래프 로딩 완료. astream 시작...")

            # astream으로 노드별 실시간 이벤트 전송
            final_state = {}

            async for event in graph.astream(initial_state):
                # event = {"node_name": {updated_state_fields}}
                for node_name, node_output in event.items():
                    _t_node = time.time() - _t_total
                    print(f"\n[Chat] >>> 노드 이벤트 수신: {node_name} (+{_t_node:.2f}s)")
                    print(f"[Chat]     output keys: {list(node_output.keys())}")
                    final_state.update(node_output)

                    if node_name == "classify_intent":
                        # 1. Intent 분류 결과 즉시 전송
                        intent = node_output.get("intent", "general")
                        confidence = node_output.get("confidence", 0.0)
                        agent_type = _get_agent_type(intent)
                        print(f"[Chat] Intent 분류 결과: intent={intent}, confidence={confidence:.4f}, agent_type={agent_type}")
                        yield f"data: {json.dumps({'type': 'intent', 'intent': intent, 'confidence': confidence, 'agent_type': agent_type}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'status', 'value': f'{agent_type} 처리 중...'}, ensure_ascii=False)}\n\n"

                    elif node_name == "general_response":
                        # 2-1. 일반 응답 스트리밍 (Solar API)
                        print("[Chat] general_response 노드 진입 → Solar API 스트리밍 시작")
                        import os as _os
                        from openai import AsyncOpenAI

                        solar_key = _os.getenv("SOLAR_API_KEY")
                        print(f"[Chat] SOLAR_API_KEY 존재: {bool(solar_key)}")

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
                        print(f"[Chat] general_response 스트리밍 완료. 응답 길이: {len(full_response)}자")
                        final_state["agent_response"] = {
                            "type": "general",
                            "message": full_response,
                        }

                    elif node_name == "document_agent":
                        # 2-2. 문서 Agent 스트리밍
                        agent_response = node_output.get("agent_response", {})
                        print(f"[Chat] document_agent 노드 진입. stream_pending={agent_response.get('stream_pending')}")

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

                    elif node_name == "schedule_agent":
                        # 2-3. 일정 Agent (스트리밍 불필요 — JSON 파싱 + API 호출 결과)
                        agent_response = node_output.get("agent_response", {})
                        print(f"[Chat] schedule_agent 노드 완료. response: {agent_response}")
                        yield f"data: {json.dumps({'type': 'status', 'value': 'schedule_agent 처리 완료'}, ensure_ascii=False)}\n\n"

                    elif node_name == "format_response":
                        # 3. 최종 응답 전송
                        agent_response = node_output.get("agent_response", final_state.get("agent_response", {}))
                        intent = final_state.get("intent", "general")
                        message = agent_response.get("message", "")

                        # message가 비어있으면 preview/summary에서 가져오기
                        if not message:
                            message = agent_response.get("preview", "") or agent_response.get("summary", "")
                            if message:
                                agent_response["message"] = message

                        print(f"[Chat] format_response 노드. intent={intent}, message 길이={len(message)}자")

                        # 이미 스트리밍한 경우 token 전송 건너뛰기
                        if not agent_response.get("stream_pending") and intent not in ("general", "doc_search"):
                            yield f"data: {json.dumps({'type': 'token', 'value': message}, ensure_ascii=False)}\n\n"

                        yield f"data: {json.dumps({'type': 'result', 'intent': intent, 'data': agent_response}, ensure_ascii=False)}\n\n"

                    else:
                        # 2. Agent 노드 완료 시 상태 업데이트
                        yield f"data: {json.dumps({'type': 'status', 'value': f'{node_name} 처리 완료'}, ensure_ascii=False)}\n\n"

            # 4. 완료
            _t_done = time.time() - _t_total
            print(f"[Chat] 스트림 완료 ✓ (총 {_t_done:.2f}s)")
            print(f"{'='*60}\n")
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            print(f"[Chat] !!! 스트림 에러: {e}")
            import traceback
            traceback.print_exc()
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
