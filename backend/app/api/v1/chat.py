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


def _extract_prev_agent_context(chat_history: list[dict]) -> dict | None:
    """chat_history에서 가장 최근 Agent 결과를 cross-agent 맥락용으로 압축 추출"""
    for i, msg in enumerate(reversed(chat_history)):
        if msg.get("role") != "assistant":
            continue
        ar = msg.get("agentResponse")
        if not ar or not isinstance(ar, dict):
            continue

        ar_type = ar.get("type", "")
        turn_ago = (i // 2) + 1

        # 3턴 이상 전 결과는 무시
        if turn_ago > 3:
            return None

        base = {"intent": ar_type, "turn_ago": turn_ago}

        if ar_type == "doc_retrieve":
            sources = ar.get("sources", [])
            if not sources:
                continue
            best = next((s for s in sources if s.get("document_id")), sources[0])
            base["agent_type"] = "document"
            base["document"] = {
                "title": best.get("title", ""),
                "document_id": best.get("document_id"),
                "summary": ar.get("message", "")[:300],
                "sources_count": len(sources),
            }
            return base

        elif ar_type == "judgment":
            base["agent_type"] = "judgment"
            base["judgment"] = {
                "result": ar.get("result", ""),
                "confidence": ar.get("confidence", 0),
                "reasoning": ar.get("reasoning", "")[:300],
                "cited_regulations": [c.get("article", "") for c in ar.get("citations", [])[:3]],
            }
            return base

        elif ar_type in ("schedule_add", "schedule_followup"):
            sched = ar.get("schedule", {})
            base["agent_type"] = "schedule"
            base["schedule"] = {
                "title": sched.get("title", ""),
                "date": sched.get("date", ""),
                "time": sched.get("time", ""),
                "event_id": ar.get("event_id", ""),
            }
            return base

    return None


async def _load_chat_context(db: AsyncSession, request: ChatRequest, user, initial_state: dict):
    """chat_history + document_content 로딩 (스트리밍/비스트리밍 공통)"""
    # 1. 이전 대화 이력 + 세션 요약 로드
    if request.session_id:
        try:
            hist_result = await db.execute(
                select(ChatLog)
                .where(ChatLog.session_id == request.session_id, ChatLog.user_id == user.id)
                .order_by(ChatLog.created_at.desc())
                .limit(10)  # 최근 5턴
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

            # cross-agent 맥락 추출
            prev_ctx = _extract_prev_agent_context(chat_history)
            if prev_ctx:
                initial_state["prev_agent_context"] = prev_ctx
                logger.debug("[Chat] prev_agent_context: type=%s, turn_ago=%d",
                             prev_ctx.get("agent_type"), prev_ctx.get("turn_ago", 0))

            # 세션 요약 로드
            sess_result = await db.execute(
                select(ChatSession).where(ChatSession.session_id == request.session_id)
            )
            session_row = sess_result.scalar_one_or_none()
            if session_row and session_row.summary:
                initial_state["chat_summary"] = session_row.summary
                logger.debug("[Chat] chat_summary 로드 (%d자)", len(session_row.summary))

            logger.debug("[Chat] chat_history 로드: %d개 메시지", len(chat_history))
        except Exception as hist_err:
            logger.warning("[Chat] chat_history 로드 실패: %s", hist_err)

    # 2. document_id가 있으면 DB에서 문서 내용 로딩
    if request.document_id:
        try:
            from app.models.document import Document
            result = await db.execute(select(Document).where(Document.id == request.document_id))
            doc = result.scalar_one_or_none()
            if doc:
                if not doc.content or not doc.content.strip():
                    logger.warning("[Chat] document_id=%s content 비어있음", request.document_id)
                # AI 분석 결과를 컨텍스트에 포함
                doc_context = ""
                if doc.category or doc.tags or doc.summary:
                    doc_context += "\n[문서 AI 분석 정보]\n"
                    if doc.category:
                        doc_context += f"- 문서 타입: {doc.category}\n"
                    if doc.tags:
                        doc_context += f"- 태그: {', '.join(doc.tags)}\n"
                    if doc.summary:
                        doc_context += f"- 요약: {doc.summary}\n"
                    doc_context += "\n[문서 본문]\n"
                initial_state["document_content"] = doc_context + (doc.content or "")
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


def _build_initial_state(request: ChatRequest, user, stream_mode: bool = False) -> dict:
    """AgentState 필드 초기화"""
    return {
        "user_input": request.message,
        "user_id": user.id,
        "user_team": getattr(user, "team", None),
        "intent": "",
        "confidence": 0.0,
        "context": [],
        "agent_response": {},
        "chat_history": [],
        "chat_summary": None,
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
        "sub_queries": None,
        "sub_responses": None,
        "force_intent": request.force_intent,
        "prev_agent_context": None,
    }


def _get_agent_type(intent: str) -> str:
    """intent에 대응하는 agent_type 반환"""
    if intent == "judgment":
        return "judgment_agent"
    elif intent in ("doc_retrieve", "doc_generate", "doc_search", "doc_summary"):
        return "document_agent"
    elif intent.startswith("schedule_"):
        return "schedule_agent"
    return "general"


async def _maybe_update_summary(db: AsyncSession, session_id: str, user_id: int):
    """대화가 3턴을 초과하면 sLLM으로 요약을 갱신한다.

    최근 5턴(10메시지)은 chat_history로 직접 전달되므로,
    그보다 오래된 메시지만 요약에 포함시킨다.
    """
    from sqlalchemy import func as sa_func
    from ai.llm.summarizer import summarize_chat_history, SUMMARY_TRIGGER_TURNS

    # 현재 세션의 총 메시지(턴) 수
    count_result = await db.execute(
        select(sa_func.count(ChatLog.id))
        .where(ChatLog.session_id == session_id, ChatLog.user_id == user_id)
    )
    total_logs = count_result.scalar() or 0

    if total_logs <= SUMMARY_TRIGGER_TURNS:
        return  # 아직 요약 불필요

    # 세션 정보 로드
    sess_result = await db.execute(
        select(ChatSession).where(ChatSession.session_id == session_id)
    )
    session_row = sess_result.scalar_one_or_none()
    if not session_row:
        return

    # 이미 이 턴 수에 대해 요약 완료했으면 스킵
    if session_row.summary_turn_count >= total_logs:
        return

    # 최근 3턴을 제외한 나머지(요약 대상) 로드
    recent_skip = SUMMARY_TRIGGER_TURNS  # 최근 5턴은 제외
    older_result = await db.execute(
        select(ChatLog)
        .where(ChatLog.session_id == session_id, ChatLog.user_id == user_id)
        .order_by(ChatLog.created_at.asc())
        .limit(total_logs - recent_skip)
    )
    older_logs = older_result.scalars().all()

    if not older_logs:
        return

    # 요약 대상 메시지 구성
    messages_to_summarize = []
    for log in older_logs:
        messages_to_summarize.append({"role": "user", "content": log.user_message})
        try:
            ar = json.loads(log.agent_response) if log.agent_response else {}
        except json.JSONDecodeError:
            ar = {}
        messages_to_summarize.append({
            "role": "assistant",
            "content": ar.get("message", ""),
        })

    # sLLM으로 요약 생성
    new_summary = await summarize_chat_history(
        messages=messages_to_summarize,
        existing_summary=None,  # 매번 전체 재요약 (점진적 누적보다 정확)
    )

    # DB 업데이트
    session_row.summary = new_summary
    session_row.summary_turn_count = total_logs
    await db.commit()
    logger.info("[Chat] 대화 요약 갱신 완료: session=%s, turns=%d, summary=%d자",
                session_id, total_logs, len(new_summary))


@router.post("/stream")
async def chat_stream(request: ChatRequest, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """SSE 스트리밍 챗봇 응답"""
    session_id = request.session_id or str(uuid.uuid4())

    async def event_generator():
        try:
            _t_total = time.time()
            logger.info("[Chat] 요청 수신 | user_id=%s, template_id=%s, template_type=%s, force_intent=%s, msg=%s",
                        user.id, request.template_id, request.template_type, request.force_intent, request.message[:30])

            # lazy import (AI 의존성 없을 때 서버 기동 안 깨지게)
            from ai.agents.orchestrator import get_graph

            graph = get_graph()
            initial_state = _build_initial_state(request, user, stream_mode=True)
            await _load_chat_context(db, request, user, initial_state)

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

                    if node_name == "decompose_query":
                        # 복합 질문 감지 결과
                        sub_queries = node_output.get("sub_queries", [])
                        if sub_queries:
                            yield f"data: {json.dumps({'type': 'status', 'value': f'복합 질문 감지: {len(sub_queries)}개 하위 질문'}, ensure_ascii=False)}\n\n"

                    elif node_name == "compound_pending":
                        # 복합 질문: 각 sub_query를 순차 처리 + 스트리밍
                        agent_response = node_output.get("agent_response", {})
                        sub_queries = agent_response.get("sub_queries", [])

                        yield f"data: {json.dumps({'type': 'compound_start', 'total': len(sub_queries)}, ensure_ascii=False)}\n\n"

                        all_sub_responses = []
                        for i, sq in enumerate(sub_queries):
                            sq_query = sq["query"]
                            sq_hint = sq.get("hint", "general")

                            yield f"data: {json.dumps({'type': 'compound_sub', 'index': i, 'total': len(sub_queries), 'query': sq_query, 'hint': sq_hint}, ensure_ascii=False)}\n\n"

                            # sub_query를 독립 state로 graph 실행 (비스트리밍)
                            # force_intent: 플래너가 결정한 intent를 강제 적용 (ONNX 재분류 방지)
                            sub_state = {
                                **initial_state,
                                "user_input": sq_query,
                                "stream_mode": False,
                                "sub_queries": None,  # 재귀 방지
                                "sub_responses": None,
                                "force_intent": sq_hint,
                                "prev_agent_context": all_sub_responses[-1]["response"] if all_sub_responses else None,
                            }

                            try:
                                import asyncio as _aio
                                sub_result = await _aio.wait_for(
                                    graph.ainvoke(sub_state), timeout=60,
                                )
                                sub_response = sub_result.get("agent_response", {})
                            except _aio.TimeoutError:
                                logger.error("[Chat] compound sub_query 타임아웃 (60초): %s", sq_query[:50])
                                sub_response = {
                                    "type": sq_hint,
                                    "message": "처리 시간이 초과되었습니다. 개별적으로 다시 질문해주세요.",
                                }
                            except Exception as sub_err:
                                logger.error("[Chat] compound sub_query 처리 실패: %s", sub_err)
                                sub_response = {
                                    "type": sq_hint,
                                    "message": f"처리 중 오류: {sub_err}",
                                }

                            sub_intent = sq_hint
                            if sub_result and isinstance(sub_result, dict):
                                sub_intent = sub_result.get("intent", sq_hint)

                            all_sub_responses.append({
                                "query": sq_query,
                                "intent": sub_intent,
                                "response": sub_response,
                            })

                            yield f"data: {json.dumps({'type': 'compound_sub_done', 'index': i}, ensure_ascii=False)}\n\n"

                        # 전체 병합
                        compound_response = {
                            "type": "compound",
                            "message": "\n\n---\n\n".join(
                                r["response"].get("message", "") for r in all_sub_responses
                            ),
                            "sub_responses": all_sub_responses,
                        }
                        final_state["agent_response"] = compound_response
                        final_state["sub_responses"] = all_sub_responses
                        final_state["intent"] = "compound"

                    elif node_name == "classify_intent":
                        # 1. Intent 분류 결과 즉시 전송
                        intent = node_output.get("intent", "general")
                        confidence = node_output.get("confidence", 0.0)
                        agent_type = _get_agent_type(intent)
                        logger.info("[Chat] intent=%s confidence=%.4f", intent, confidence)

                        # confidence가 라우팅 threshold 미만이면 확정 intent 대신 "분석 중" 표시 (배지 깜빡임 방지)
                        from ai.agents.config import INTENT_CONFIDENCE_THRESHOLD as _ICT
                        if confidence >= _ICT:  # config.py INTENT_CONFIDENCE_THRESHOLD (0.85)
                            yield f"data: {json.dumps({'type': 'intent', 'intent': intent, 'confidence': confidence, 'agent_type': agent_type}, ensure_ascii=False)}\n\n"
                            yield f"data: {json.dumps({'type': 'status', 'value': f'{agent_type} 처리 중...'}, ensure_ascii=False)}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'status', 'value': '질문 분석 중...'}, ensure_ascii=False)}\n\n"

                    elif node_name == "clarify_with_candidates":
                        # top-3 후보 제시
                        agent_response = node_output.get("agent_response", {})
                        candidates = agent_response.get("candidates", [])
                        yield f"data: {json.dumps({'type': 'clarify_candidates', 'data': {'candidates': candidates, 'message': agent_response.get('message', '')}}, ensure_ascii=False)}\n\n"

                    elif node_name == "general_response":
                        # 2-1. 일반 응답 스트리밍 (vLLM 우선, API fallback)
                        import os as _os
                        from openai import AsyncOpenAI
                        import httpx

                        user_input = final_state.get("user_input", "")
                        chat_history = final_state.get("chat_history", [])

                        from datetime import date as _date
                        from ai.llm.prompts import GENERAL_SYSTEM_PROMPT
                        _gen_sys = f"{GENERAL_SYSTEM_PROMPT}\n오늘 날짜: {_date.today().isoformat()}"
                        _chat_summary = final_state.get("chat_summary")
                        if _chat_summary:
                            _gen_sys += f"\n\n[이전 대화 요약]\n{_chat_summary}"

                        _messages = [
                            {"role": "system", "content": _gen_sys},
                            *chat_history,
                            {"role": "user", "content": user_input},
                        ]

                        # vLLM 우선 → API fallback
                        _vllm_base = _os.getenv("VLLM_BASE_URL")
                        _vllm_key = _os.getenv("VLLM_API_KEY", "EMPTY")
                        _vllm_model = _os.getenv("VLLM_MODEL", "kakaocorp/kanana-1.5-8b-instruct-2505")

                        if _vllm_base:
                            client = AsyncOpenAI(api_key=_vllm_key, base_url=_vllm_base, timeout=httpx.Timeout(90.0, connect=15.0))
                            _model = _vllm_model
                        else:
                            _api_key = _os.getenv("OPENAI_API_KEY")
                            if not _api_key:
                                yield f"data: {json.dumps({'type': 'error', 'message': 'LLM API 키가 설정되지 않았습니다.'}, ensure_ascii=False)}\n\n"
                                continue
                            client = AsyncOpenAI(api_key=_api_key)
                            _model = _os.getenv("OPENAI_MODEL", "gpt-4o-mini")

                        stream = await client.chat.completions.create(
                            model=_model, messages=_messages,
                            temperature=0.7, max_tokens=1024, stream=True,
                            frequency_penalty=0.3,
                        )

                        full_response = ""
                        async for chunk in stream:
                            if chunk.choices and chunk.choices[0].delta.content:
                                token = chunk.choices[0].delta.content
                                full_response += token
                                yield f"data: {json.dumps({'type': 'token', 'value': token}, ensure_ascii=False)}\n\n"

                        _model_label = _model.split("/")[-1] if "/" in _model else _model
                        final_state["agent_response"] = {
                            "type": "general",
                            "message": full_response,
                            "model_name": _model_label,
                        }

                    elif node_name == "judgment_agent":
                        # 2-4. 판단 Agent 스트리밍 → judgment_stream.py로 위임
                        agent_response = node_output.get("agent_response", {})
                        if agent_response.get("stream_pending"):
                            from ai.agents.judgment_stream import execute_judgment_stream

                            logger.info("[Chat] judgment_agent 스트리밍 위임")
                            async for token in execute_judgment_stream(agent_response, final_state.get("user_input", "")):
                                yield f"data: {json.dumps({'type': 'token', 'value': token}, ensure_ascii=False)}\n\n"

                            final_state["agent_response"] = agent_response
                        else:
                            yield f"data: {json.dumps({'type': 'status', 'value': 'judgment_agent 처리 완료'}, ensure_ascii=False)}\n\n"

                    elif node_name == "document_agent":
                        # 2-2. 문서 Agent 스트리밍
                        agent_response = node_output.get("agent_response", {})

                        # sub_type 조기 알림 → 프론트에서 "문서 검색 중..." 등 표시
                        _status_hint = agent_response.pop("_status_hint", None)
                        _SUB_TYPE_LABELS = {
                            "search": "문서 검색 중...",
                            "qa": "문서 질의응답 준비 중...",
                            "summary": "문서 요약 준비 중...",
                            "generate": "문서 생성 준비 중...",
                        }
                        if _status_hint and _status_hint in _SUB_TYPE_LABELS:
                            yield f"data: {json.dumps({'type': 'status', 'value': _SUB_TYPE_LABELS[_status_hint]}, ensure_ascii=False)}\n\n"
                            yield f"data: {json.dumps({'type': 'doc_sub_type', 'value': _status_hint}, ensure_ascii=False)}\n\n"

                        # 관련 문서 없음 등 stream_pending 없이 바로 응답하는 경우
                        if not agent_response.get("stream_pending") and agent_response.get("message"):
                            msg = agent_response["message"]
                            # 검색 결과는 청크 단위로 스트리밍 (자연스러운 UX)
                            if agent_response.get("sub_type") == "search" and len(msg) > 100:
                                lines = msg.split("\n")
                                for line in lines:
                                    yield f"data: {json.dumps({'type': 'token', 'value': line + chr(10)}, ensure_ascii=False)}\n\n"
                            else:
                                yield f"data: {json.dumps({'type': 'token', 'value': msg}, ensure_ascii=False)}\n\n"

                        elif agent_response.get("stream_pending") and agent_response.get("generate_config"):
                            # ── 문서 생성 단계별 실행 (토큰 스트리밍 아님, 블로킹 + 상태 표시) ──
                            gen_cfg = agent_response["generate_config"]
                            t_type = gen_cfg.get("template_type", "report")
                            type_label = {"meeting_minutes": "회의록", "report": "보고서", "proposal": "제안서"}.get(t_type, "문서")

                            yield f"data: {json.dumps({'type': 'status', 'value': f'{type_label} 생성 중... (내용 분석)'}, ensure_ascii=False)}\n\n"

                            try:
                                from ai.agents.document._generate import generate_document
                                result = await generate_document(
                                    category=gen_cfg["template_type"],
                                    user_input=gen_cfg["user_input"],
                                    template_id=gen_cfg.get("template_id"),
                                )
                                yield f"data: {json.dumps({'type': 'status', 'value': 'DOCX 생성 완료'}, ensure_ascii=False)}\n\n"

                                agent_response.update(result)

                                # ── 일정 제안 추출 (비차단, 기존 흐름 변경 없음) ──
                                try:
                                    from ai.agents.document._schedule_suggest import extract_suggested_schedules
                                    _suggested = extract_suggested_schedules(agent_response)
                                    if _suggested:
                                        agent_response["suggested_schedules"] = _suggested
                                        agent_response["schedule_suggest_message"] = (
                                            f"문서에서 {len(_suggested)}건의 일정 항목을 발견했습니다. "
                                            f"캘린더에 등록할까요?"
                                        )
                                except Exception as _exc:
                                    logger.warning("[Chat] 일정 제안 추출 실패 (비차단): %s", _exc)

                            except Exception as e:
                                logger.error("[Chat] 문서 생성 실패: %s", e)
                                agent_response["message"] = f"문서 생성 중 오류가 발생했습니다: {e}"
                                agent_response["type"] = "doc_generate"

                            agent_response.pop("stream_pending", None)
                            agent_response.pop("generate_config", None)
                            final_state["agent_response"] = agent_response

                        elif agent_response.get("stream_pending"):
                            # ── StreamRequest 프로토콜: QA/summary 토큰 스트리밍 ──
                            from ai.agents.document._stream import execute_doc_stream

                            cfg = agent_response.get("llm_config", {})
                            post = agent_response.get("post_stream", {})
                            logger.info("[Chat] document_agent 스트리밍 위임: task=%s", cfg.get("task"))

                            async for token in execute_doc_stream(cfg, post, db, user.id, agent_response):
                                yield f"data: {json.dumps({'type': 'token', 'value': token}, ensure_ascii=False)}\n\n"

                            # regulation 후처리 결과가 있으면 추가 전송
                            if agent_response.get("regulation_check"):
                                reg_summary = agent_response["regulation_check"].get("summary", "")
                                if reg_summary:
                                    yield f"data: {json.dumps({'type': 'token', 'value': reg_summary}, ensure_ascii=False)}\n\n"

                            final_state["agent_response"] = agent_response
                        elif agent_response.get("type") in ("doc_pick", "template_pick"):
                            # 선택지 응답 → final_state에 저장하여 format_response에서 전달
                            final_state["agent_response"] = agent_response
                        else:
                            yield f"data: {json.dumps({'type': 'status', 'value': 'document_agent 처리 완료'}, ensure_ascii=False)}\n\n"

                    elif node_name == "schedule_agent":
                        # 2-3. 일정 Agent (스트리밍 불필요 — JSON 파싱 + API 호출 결과)
                        agent_response = node_output.get("agent_response", {})
                        yield f"data: {json.dumps({'type': 'status', 'value': 'schedule_agent 처리 완료'}, ensure_ascii=False)}\n\n"

                    elif node_name == "action_agent":
                        # 2-5. 액션 Agent (파이프라인/결재 — 스트리밍 불필요, 결과만 전송)
                        agent_response = node_output.get("agent_response", {})
                        message = agent_response.get("message", "")
                        if message:
                            chunk_size = 10
                            for j in range(0, len(message), chunk_size):
                                token = message[j:j + chunk_size]
                                yield f"data: {json.dumps({'type': 'token', 'value': token}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'status', 'value': 'action_agent 처리 완료'}, ensure_ascii=False)}\n\n"

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
                            # 선택지(template_pick, doc_pick) / clarify는 token 스트리밍 불필요
                            skip_token = agent_response.get("stream_pending") or resp_type in ("template_pick", "doc_pick", "clarify")
                            if not skip_token and intent not in ("general", "doc_retrieve", "doc_search", "doc_summary", "judgment", "compound"):
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

                # DB 저장용: sources 내 content를 200자로 잘라 저장 크기 절감
                save_response = agent_response.copy()
                if "sources" in save_response:
                    save_response["sources"] = [
                        {**s, "content": s.get("content", "")[:200]}
                        for s in save_response["sources"]
                    ]

                log = ChatLog(
                    session_id=session_id,
                    user_id=user.id,
                    user_message=request.message,
                    intent=intent,
                    intent_confidence=final_state.get("confidence", 0.0),
                    agent_type=_get_agent_type(intent),
                    agent_response=json.dumps(save_response, ensure_ascii=False, default=str),
                    response_time_ms=response_time_ms,
                )
                db.add(log)
                await db.commit()
                logger.debug("[Chat] chat_log 저장 완료 (id=%s)", log.id)
            except Exception as log_err:
                logger.warning("[Chat] chat_log 저장 실패: %s", log_err)

            # 5. 대화 요약 갱신 (비동기, 사용자 응답 차단 안 함)
            try:
                await _maybe_update_summary(db, session_id, user.id)
            except Exception as sum_err:
                logger.warning("[Chat] 요약 갱신 실패 (무시): %s", sum_err)

            logger.info("[Chat] 스트림 완료 (%.2fs)", _t_done)
            _done_payload = {'type': 'done'}
            if log and log.id:
                _done_payload['log_id'] = log.id
            yield f"data: {json.dumps(_done_payload)}\n\n"

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
        await _load_chat_context(db, request, user, initial_state)

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
        # agent_response.type이 있으면 우선 사용 (template_pick, doc_pick, clarify 등)
        result_intent = agent_response.get("type") or log.intent
        messages.append({
            "role": "assistant",
            "content": content,
            "resultIntent": result_intent,
            "agentResponse": agent_response,
            "logId": log.id,
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


class _PatchLogBody(BaseModel):
    agent_response: dict


@router.patch("/sessions/{session_id}/logs/{log_id}")
async def patch_chat_log(
    session_id: str,
    log_id: int,
    body: _PatchLogBody,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """채팅 로그의 agent_response 업데이트 (일정 등록 완료 등 상태 반영)"""
    result = await db.execute(
        select(ChatLog).where(
            ChatLog.id == log_id,
            ChatLog.session_id == session_id,
            ChatLog.user_id == user.id,
        )
    )
    log = result.scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="로그를 찾을 수 없습니다")

    log.agent_response = json.dumps(body.agent_response, ensure_ascii=False, default=str)
    log.intent = body.agent_response.get("type", log.intent)
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
