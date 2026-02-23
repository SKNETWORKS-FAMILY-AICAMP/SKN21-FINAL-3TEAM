"""
챗봇 API + SSE 스트리밍 (팀원 A 담당)
"""

import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import ChatRequest, ChatResponse
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.chat_log import ChatLog

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
        "template_type": request.template_type,
        "source_page": request.source_page,
        "template_fields": None,
        "extracted_text": None,
        "document_id": request.document_id,
        "document_content": None,
        "google_services_result": None,
        "stream_mode": stream_mode,
        "intent_candidates": None,
    }


def _get_agent_type(intent: str) -> str:
    """intent에 대응하는 agent_type 반환"""
    if intent == "judgment":
        return "judgment_agent"
    elif intent in ("doc_search", "doc_generate", "doc_summary", "doc_qa"):
        return "document_agent"
    elif intent.startswith("schedule_"):
        return "schedule_agent"
    return "general"


@router.post("/stream")
async def chat_stream(request: ChatRequest, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """SSE 스트리밍 챗봇 응답"""
    session_id = request.session_id or str(uuid.uuid4())

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

            # document_id가 있으면 DB에서 문서 내용 로딩
            if request.document_id:
                try:
                    from sqlalchemy import select
                    from app.models.document import Document
                    result = await db.execute(select(Document).where(Document.id == request.document_id))
                    doc = result.scalar_one_or_none()
                    if doc:
                        initial_state["document_content"] = doc.content
                        print(f"[Chat] document_id={request.document_id} → content 로딩 ({len(doc.content) if doc.content else 0}자)")
                except Exception as doc_err:
                    print(f"[Chat] document_id 로딩 실패: {doc_err}")

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
                        print(f"[Chat] Intent 분류 결과: intent={intent}, confidence={confidence:.4f}")

                        yield f"data: {json.dumps({'type': 'intent', 'intent': intent, 'confidence': confidence, 'agent_type': agent_type}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'status', 'value': f'{agent_type} 처리 중...'}, ensure_ascii=False)}\n\n"

                    elif node_name == "clarify_with_candidates":
                        # top-3 후보 제시
                        agent_response = node_output.get("agent_response", {})
                        candidates = agent_response.get("candidates", [])
                        print(f"[Chat] clarify_with_candidates: {candidates}")
                        yield f"data: {json.dumps({'type': 'clarify_candidates', 'data': {'candidates': candidates, 'message': agent_response.get('message', '')}}, ensure_ascii=False)}\n\n"

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

                    elif node_name == "judgment_agent":
                        # 2-4. 판단 Agent 스트리밍 (judgment_agent_stream)
                        agent_response = node_output.get("agent_response", {})
                        print(f"[Chat] judgment_agent 노드 진입. stream_pending={agent_response.get('stream_pending')}")

                        if agent_response.get("stream_pending"):
                            from ai.agents.judgment_agent import judgment_agent_stream

                            judgment_state = dict(final_state)
                            judgment_state["user_input"] = final_state.get("user_input", "")
                            judgment_state["chat_history"] = final_state.get("chat_history", [])

                            full_judgment = ""
                            judgment_result = {}
                            async for chunk in judgment_agent_stream(judgment_state):
                                stripped = chunk.strip()
                                if stripped.startswith("[DONE]"):
                                    # 최종 구조화 JSON 파싱
                                    judgment_result = json.loads(stripped[len("[DONE]"):])
                                else:
                                    full_judgment += chunk

                            # 최종 응답 저장
                            if not judgment_result:
                                judgment_result = {
                                    "type": "judgment",
                                    "message": full_judgment,
                                }

                            # reasoning 텍스트를 단어 단위로 스트리밍 (LLM 응답이 JSON이라 원문은 보내면 안 됨)
                            reasoning_text = judgment_result.get("reasoning", full_judgment)
                            if reasoning_text:
                                words = reasoning_text.split(" ")
                                for i, word in enumerate(words):
                                    token = word if i == 0 else " " + word
                                    yield f"data: {json.dumps({'type': 'token', 'value': token}, ensure_ascii=False)}\n\n"

                            # document_agent와 동일하게 원본 dict를 in-place 수정
                            # (LangGraph 내부 state에 반영 → format_response가 올바른 데이터 수신)
                            agent_response.pop("stream_pending", None)
                            agent_response.update(judgment_result)
                            final_state["agent_response"] = agent_response
                            print(f"[Chat] judgment_agent 스트리밍 완료. 응답 길이: {len(full_judgment)}자")
                        else:
                            yield f"data: {json.dumps({'type': 'status', 'value': 'judgment_agent 처리 완료'}, ensure_ascii=False)}\n\n"

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
                        resp_type = agent_response.get("type", intent)
                        message = agent_response.get("message", "")

                        # message가 비어있으면 preview/summary에서 가져오기
                        if not message:
                            message = agent_response.get("preview", "") or agent_response.get("summary", "")
                            if message:
                                agent_response["message"] = message

                        print(f"[Chat] format_response 노드. type={resp_type}, intent={intent}, message 길이={len(message)}자")

                        if resp_type == "clarify_candidates":
                            # clarify로 전송해야 프론트에서 버튼 카드로 렌더링됨
                            yield f"data: {json.dumps({'type': 'result', 'intent': 'clarify', 'data': agent_response}, ensure_ascii=False)}\n\n"
                        else:
                            # 이미 스트리밍한 경우 token 전송 건너뛰기
                            if not agent_response.get("stream_pending") and intent not in ("general", "doc_search", "doc_summary", "doc_qa", "judgment"):
                                yield f"data: {json.dumps({'type': 'token', 'value': message}, ensure_ascii=False)}\n\n"

                            yield f"data: {json.dumps({'type': 'result', 'intent': intent, 'data': agent_response}, ensure_ascii=False)}\n\n"

                    else:
                        # 기타 노드 완료 시 상태 업데이트
                        yield f"data: {json.dumps({'type': 'status', 'value': f'{node_name} 처리 완료'}, ensure_ascii=False)}\n\n"

            # 4. chat_logs에 저장
            _t_done = time.time() - _t_total
            response_time_ms = int(_t_done * 1000)
            try:
                intent = final_state.get("intent", "general")
                agent_response = final_state.get("agent_response", {})
                log = ChatLog(
                    session_id=session_id,
                    user_id=user.id,
                    user_message=request.message,
                    intent=intent,
                    intent_confidence=final_state.get("confidence", 0.0),
                    agent_type=_get_agent_type(intent),
                    agent_response=json.dumps(agent_response, ensure_ascii=False, default=str)[:5000],
                    response_time_ms=response_time_ms,
                )
                db.add(log)
                await db.commit()
                print(f"[Chat] chat_log 저장 완료 (id={log.id})")
            except Exception as log_err:
                print(f"[Chat] chat_log 저장 실패: {log_err}")

            # 5. 완료
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
async def chat(request: ChatRequest, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """일반 (비스트리밍) 챗봇 응답"""
    _t_start = time.time()
    session_id = request.session_id or str(uuid.uuid4())
    try:
        from ai.agents.orchestrator import get_graph

        graph = get_graph()
        initial_state = _build_initial_state(request, user)

        # document_id가 있으면 DB에서 문서 내용 로딩
        if request.document_id:
            try:
                from sqlalchemy import select
                from app.models.document import Document
                result_doc = await db.execute(select(Document).where(Document.id == request.document_id))
                doc = result_doc.scalar_one_or_none()
                if doc:
                    initial_state["document_content"] = doc.content
            except Exception as doc_err:
                logger.warning("document_id 로딩 실패: %s", doc_err)

        result = await graph.ainvoke(initial_state)

        intent = result.get("intent", "general")
        confidence = result.get("confidence", 0.0)
        agent_response = result.get("agent_response", {})

        # chat_logs에 저장
        try:
            log = ChatLog(
                session_id=session_id,
                user_id=user.id,
                user_message=request.message,
                intent=intent,
                intent_confidence=confidence,
                agent_type=_get_agent_type(intent),
                agent_response=json.dumps(agent_response, ensure_ascii=False, default=str)[:5000],
                response_time_ms=int((time.time() - _t_start) * 1000),
            )
            db.add(log)
            await db.commit()
        except Exception as log_err:
            logger.warning("chat_log 저장 실패: %s", log_err)

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
