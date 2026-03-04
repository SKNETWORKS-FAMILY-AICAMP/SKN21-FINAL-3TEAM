"""
챗봇 API + SSE 스트리밍 (팀원 A 담당)
"""

import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import ChatRequest, ChatResponse
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.chat_log import ChatLog
from app.models.chat_session import ChatSession

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
            logger.info("[Chat] 요청 수신 | user_id=%s", user.id)

            # lazy import (AI 의존성 없을 때 서버 기동 안 깨지게)
            from ai.agents.orchestrator import get_graph

            graph = get_graph()
            initial_state = _build_initial_state(request, user, stream_mode=True)

            # session_id로 이전 대화 이력 로드 (schedule_followup 등 맥락 판단용)
            if request.session_id:
                try:
                    hist_result = await db.execute(
                        select(ChatLog)
                        .where(ChatLog.session_id == request.session_id, ChatLog.user_id == user.id)
                        .order_by(ChatLog.created_at.desc())
                        .limit(6)  # 최근 3턴
                    )
                    hist_logs = list(reversed(hist_result.scalars().all()))
                    chat_history = []
                    for log in hist_logs:
                        chat_history.append({"role": "user", "content": log.user_message})
                        try:
                            ar = json.loads(log.agent_response) if log.agent_response else {}
                        except json.JSONDecodeError:
                            ar = {}
                        chat_history.append({
                            "role": "assistant",
                            "content": ar.get("message", ""),
                            "agentResponse": ar,
                        })
                    initial_state["chat_history"] = chat_history
                    logger.debug("[Chat] chat_history 로드: %d개 메시지", len(chat_history))
                except Exception as hist_err:
                    logger.warning("[Chat] chat_history 로드 실패: %s", hist_err)

            # document_id가 있으면 DB에서 문서 내용 로딩
            if request.document_id:
                try:
                    from app.models.document import Document
                    result = await db.execute(select(Document).where(Document.id == request.document_id))
                    doc = result.scalar_one_or_none()
                    if doc:
                        if not doc.content or not doc.content.strip():
                            logger.warning("[Chat] document_id=%s content 비어있음", request.document_id)
                        initial_state["document_content"] = doc.content or None
                    else:
                        try:
                            from ai.rag.qdrant_pipeline import get_qdrant_pipeline
                            pipeline = get_qdrant_pipeline()
                            content = pipeline.get_document_content(request.document_id)
                            if content:
                                initial_state["document_content"] = content
                            else:
                                logger.warning("[Chat] Qdrant fallback: content 없음")
                        except Exception as qdrant_err:
                            logger.warning("[Chat] Qdrant fallback 실패: %s", qdrant_err)
                except Exception as doc_err:
                    logger.warning("[Chat] document_id 로딩 실패: %s", doc_err)

            # astream으로 노드별 실시간 이벤트 전송
            final_state = {}

            async for event in graph.astream(initial_state):
                for node_name, node_output in event.items():
                    # agent_response가 스트리밍으로 이미 채워졌으면 덮어쓰지 않음
                    if "agent_response" in node_output and "agent_response" in final_state:
                        existing = final_state["agent_response"]
                        incoming = node_output["agent_response"]
                        # 이미 실제 메시지가 있는데 stream_pending으로 되돌리면 안 됨
                        if existing.get("message") and incoming.get("stream_pending"):
                            node_output = {k: v for k, v in node_output.items() if k != "agent_response"}
                    final_state.update(node_output)

                    if node_name == "classify_intent":
                        # 1. Intent 분류 결과 즉시 전송
                        intent = node_output.get("intent", "general")
                        confidence = node_output.get("confidence", 0.0)
                        agent_type = _get_agent_type(intent)
                        logger.info("[Chat] intent=%s confidence=%.4f", intent, confidence)

                        yield f"data: {json.dumps({'type': 'intent', 'intent': intent, 'confidence': confidence, 'agent_type': agent_type}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'status', 'value': f'{agent_type} 처리 중...'}, ensure_ascii=False)}\n\n"

                    elif node_name == "clarify_with_candidates":
                        # top-3 후보 제시
                        agent_response = node_output.get("agent_response", {})
                        candidates = agent_response.get("candidates", [])
                        yield f"data: {json.dumps({'type': 'clarify_candidates', 'data': {'candidates': candidates, 'message': agent_response.get('message', '')}}, ensure_ascii=False)}\n\n"

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

                        final_state["agent_response"] = {
                            "type": "general",
                            "message": full_response,
                        }

                    elif node_name == "judgment_agent":
                        # 2-4. 판단 Agent 스트리밍 (document_agent와 동일한 패턴)
                        agent_response = node_output.get("agent_response", {})
                        if agent_response.get("stream_pending"):
                            import os as _os_j
                            from openai import AsyncOpenAI as _AsyncOpenAI_j

                            openai_key = _os_j.getenv("OPENAI_API_KEY")
                            openai_model = _os_j.getenv("OPENAI_MODEL", "gpt-4o-mini")
                            openai_base = _os_j.getenv("LLM_BASE_URL") or None

                            if not openai_key:
                                yield f"data: {json.dumps({'type': 'error', 'message': 'OPENAI_API_KEY가 설정되지 않았습니다.'}, ensure_ascii=False)}\n\n"
                                continue

                            j_client = _AsyncOpenAI_j(
                                api_key=openai_key,
                                base_url=openai_base,
                            )

                            j_stream = await j_client.chat.completions.create(
                                model=openai_model,
                                messages=[
                                    {"role": "system", "content": agent_response["sys_prompt"]},
                                    {"role": "user", "content": agent_response["user_prompt"]},
                                ],
                                temperature=0.1,
                                max_tokens=2048,
                                stream=True,
                            )

                            # 토큰 즉시 전송, ```json 이후만 숨김 (버퍼링으로 ``` 누출 방지)
                            _JSON_PREFIXES = ("`", "``", "```", "```j", "```js", "```jso", "```json")
                            full_response = ""
                            in_json_block = False
                            token_count = 0
                            pending_tokens = []

                            async for chunk in j_stream:
                                delta = chunk.choices[0].delta
                                if delta.content:
                                    token = delta.content
                                    full_response += token

                                    if in_json_block:
                                        continue

                                    if "```json" in full_response:
                                        in_json_block = True
                                        pending_tokens.clear()
                                    elif full_response.rstrip().endswith(_JSON_PREFIXES):
                                        # 백틱이 쌓이는 중 — ```json 될 수 있으므로 버퍼에 보관
                                        pending_tokens.append(token)
                                    else:
                                        # 안전 — 버퍼 flush 후 전송
                                        for pt in pending_tokens:
                                            token_count += 1
                                            yield f"data: {json.dumps({'type': 'token', 'value': pt}, ensure_ascii=False)}\n\n"
                                        pending_tokens.clear()
                                        token_count += 1
                                        yield f"data: {json.dumps({'type': 'token', 'value': token}, ensure_ascii=False)}\n\n"

                            # JSON 파싱 + 3중 검증
                            from ai.agents.judgment_agent import (
                                _parse_llm_response,
                                _validate_result_category,
                                _check_keyword_match,
                                _validate_article_exists,
                                _calibrate_confidence,
                                _check_consistency,
                                _group_regulations,
                            )

                            parsed = _parse_llm_response(full_response)
                            parsed["type"] = "judgment"
                            parsed = _validate_result_category(parsed)

                            rag_context = agent_response.get("_rag_context", [])
                            keyword_match = _check_keyword_match(parsed, rag_context)
                            article_validations = _validate_article_exists(parsed, rag_context)

                            calibrated, confidence_breakdown = _calibrate_confidence(
                                parsed, rag_context,
                                keyword_match=keyword_match,
                                article_validations=article_validations,
                            )
                            parsed["confidence"] = calibrated
                            parsed["confidence_breakdown"] = confidence_breakdown
                            parsed.setdefault("cross_references", [])

                            groups = _group_regulations(rag_context)
                            parsed["regulation_groups"] = list(groups.keys())

                            if article_validations:
                                parsed["article_validations"] = article_validations
                                hallucinated = [v["article"] for v in article_validations if not v["exists"]]
                                if hallucinated:
                                    parsed.setdefault("warnings", []).append(
                                        f"환각 의심 조항: {', '.join(hallucinated)} (RAG 검색 결과에 미존재)"
                                    )

                            inconsistency = _check_consistency(final_state.get("user_input", ""), parsed)
                            if inconsistency:
                                parsed["consistency_flag"] = inconsistency

                            # message = ```json 이전 자연어 부분
                            if "```json" in full_response:
                                clean_natural = full_response.split("```json")[0].strip()
                            else:
                                clean_natural = ""
                            parsed["message"] = clean_natural or parsed.get("reasoning", "")

                            # agent_response 업데이트 (document_agent와 동일 패턴)
                            agent_response.pop("stream_pending", None)
                            agent_response.pop("sys_prompt", None)
                            agent_response.pop("user_prompt", None)
                            agent_response.pop("_rag_context", None)
                            agent_response.update(parsed)
                            final_state["agent_response"] = agent_response
                        else:
                            yield f"data: {json.dumps({'type': 'status', 'value': 'judgment_agent 처리 완료'}, ensure_ascii=False)}\n\n"

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
                        elif agent_response.get("type") == "doc_pick":
                            pass
                        else:
                            yield f"data: {json.dumps({'type': 'status', 'value': 'document_agent 처리 완료'}, ensure_ascii=False)}\n\n"

                    elif node_name == "schedule_agent":
                        # 2-3. 일정 Agent (스트리밍 불필요 — JSON 파싱 + API 호출 결과)
                        agent_response = node_output.get("agent_response", {})
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

                        if resp_type == "clarify_candidates":
                            # clarify로 전송해야 프론트에서 버튼 카드로 렌더링됨
                            yield f"data: {json.dumps({'type': 'result', 'intent': 'clarify', 'data': agent_response}, ensure_ascii=False)}\n\n"
                        else:
                            # 이미 스트리밍한 경우 token 전송 건너뛰기
                            if not agent_response.get("stream_pending") and intent not in ("general", "doc_search", "doc_summary", "doc_qa", "judgment"):
                                yield f"data: {json.dumps({'type': 'token', 'value': message}, ensure_ascii=False)}\n\n"

                            yield f"data: {json.dumps({'type': 'result', 'intent': resp_type, 'data': agent_response}, ensure_ascii=False)}\n\n"

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
                    agent_response=json.dumps(agent_response, ensure_ascii=False, default=str),
                    response_time_ms=response_time_ms,
                )
                db.add(log)
                await db.commit()
                logger.debug("[Chat] chat_log 저장 완료 (id=%s)", log.id)
            except Exception as log_err:
                logger.warning("[Chat] chat_log 저장 실패: %s", log_err)

            logger.info("[Chat] 스트림 완료 (%.2fs)", _t_done)
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error("[Chat] 스트림 에러: %s", e, exc_info=True)

            # 에러 시에도 ChatLog 저장 (답변 유실 방지)
            try:
                err_response = final_state.get("agent_response", {}) if final_state else {}
                err_response["error"] = str(e)
                log = ChatLog(
                    session_id=session_id,
                    user_id=user.id,
                    user_message=request.message,
                    intent=final_state.get("intent", "general") if final_state else "general",
                    intent_confidence=final_state.get("confidence", 0.0) if final_state else 0.0,
                    agent_type="error",
                    agent_response=json.dumps(err_response, ensure_ascii=False, default=str),
                    response_time_ms=int((time.time() - _t_total) * 1000),
                )
                db.add(log)
                await db.commit()
                logger.debug("[Chat] 에러 시 chat_log 저장 완료 (id=%s)", log.id)
            except Exception as save_err:
                logger.warning("[Chat] 에러 시 chat_log 저장 실패: %s", save_err)

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

        # session_id로 이전 대화 이력 로드
        if request.session_id:
            try:
                hist_result = await db.execute(
                    select(ChatLog)
                    .where(ChatLog.session_id == request.session_id, ChatLog.user_id == user.id)
                    .order_by(ChatLog.created_at.desc())
                    .limit(6)
                )
                hist_logs = list(reversed(hist_result.scalars().all()))
                chat_history = []
                for log in hist_logs:
                    chat_history.append({"role": "user", "content": log.user_message})
                    try:
                        ar = json.loads(log.agent_response) if log.agent_response else {}
                    except json.JSONDecodeError:
                        ar = {}
                    chat_history.append({
                        "role": "assistant",
                        "content": ar.get("message", ""),
                        "agentResponse": ar,
                    })
                initial_state["chat_history"] = chat_history
            except Exception as hist_err:
                logger.warning("chat_history 로드 실패: %s", hist_err)

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
                agent_response=json.dumps(agent_response, ensure_ascii=False, default=str),
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


# ── 채팅 세션 CRUD ──────────────────────────────────────────────


class _RenameBody(BaseModel):
    name: str


@router.get("/sessions")
async def list_sessions(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """현재 유저의 채팅 세션 목록 (최신순)"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()
    return [
        {
            "session_id": s.session_id,
            "name": s.name,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]


@router.post("/sessions")
async def create_session(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """새 채팅 세션 생성"""
    session_id = str(uuid.uuid4())
    session = ChatSession(session_id=session_id, user_id=user.id, name="새 대화")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {
        "session_id": session.session_id,
        "name": session.name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """세션의 메시지 목록 (chat_logs에서 복원)"""
    # 세션 소유권 확인
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.session_id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없습니다")

    # chat_logs에서 메시지 복원
    result = await db.execute(
        select(ChatLog)
        .where(ChatLog.session_id == session_id, ChatLog.user_id == user.id)
        .order_by(ChatLog.created_at.asc())
    )
    logs = result.scalars().all()

    messages = []
    for log in logs:
        messages.append({"role": "user", "content": log.user_message})
        try:
            agent_response = json.loads(log.agent_response) if log.agent_response else {}
        except json.JSONDecodeError:
            agent_response = {}
        content = agent_response.get("message") or agent_response.get("answer") or ""
        messages.append({
            "role": "assistant",
            "content": content,
            "resultIntent": log.intent,
            "agentResponse": agent_response,
        })

    return messages


@router.patch("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    body: _RenameBody,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """세션 이름 변경"""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.session_id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없습니다")

    session.name = body.name[:100]
    await db.commit()
    return {"ok": True}


@router.delete("/sessions/{session_id}/messages")
async def clear_session_messages(
    session_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """세션 메시지 초기화 (화면에서만 비움 — chat_logs는 관리자 로그 보존을 위해 삭제하지 않음)"""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.session_id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없습니다")

    session.name = "새 대화"
    await db.commit()
    return {"ok": True}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """세션 삭제 (chat_logs는 관리자 로그 보존을 위해 삭제하지 않음)"""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.session_id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없습니다")

    await db.delete(session)
    await db.commit()
    return {"ok": True}
