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


# ── document_agent 스트리밍 헬퍼 ──────────────────────────────────


def _get_vllm_client(task: str) -> tuple:
    """vLLM 클라이언트 + task별 모델명(LoRA) 반환

    Returns: (AsyncOpenAI client, model_name str)
    - task="summary" → v3_summary (LoRA)
    - task="qa" → base model (LoRA 없음)
    - task="generate" → v3_generate (LoRA)
    - 기타 → base model
    """
    import os
    import httpx
    from openai import AsyncOpenAI

    vllm_base = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    vllm_api_key = os.getenv("VLLM_API_KEY", "EMPTY")
    vllm_model = os.getenv("VLLM_MODEL", "kakaocorp/kanana-1.5-8b-instruct-2505")
    use_lora = os.getenv("VLLM_USE_LORA", "false").lower() == "true"

    LORA_MAP = {"summary": "v3_summary", "generate": "v3_generate"}
    model = LORA_MAP.get(task, vllm_model) if use_lora else vllm_model

    client = AsyncOpenAI(
        api_key=vllm_api_key, base_url=vllm_base,
        timeout=httpx.Timeout(60.0, connect=15.0), max_retries=0,
    )
    return client, model


async def _update_summary_db(db, document_id: int, response_text: str):
    """요약 결과 파싱 → DB 업데이트"""
    try:
        from ai.agents.document._summary import parse_summary_output
        from app.models.document import Document

        parsed = parse_summary_output(response_text)
        if not parsed["tags"]:
            return
        result = await db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.summary = parsed["summary"]
            doc.tags = parsed["tags"]
            await db.commit()
            logger.info("[Chat] doc_summary DB 업데이트 완료: document_id=%s", document_id)
    except Exception as e:
        logger.warning("[Chat] doc_summary DB 업데이트 실패: %s", e)


async def _stream_regulation(text: str, user_id: int) -> dict | None:
    """규정 연결 → 결과 반환 (있으면)"""
    try:
        from ai.agents.regulation_validator import check_content_regulations
        result = await check_content_regulations(text, user_id=user_id)
        return result if result.get("notes") else None
    except Exception as e:
        logger.warning("[Chat] 규정 연결 실패 (비차단): %s", e)
        return None


def _filter_sources(sources: list, response_text: str) -> list:
    """LLM 답변에 실제 언급된 소스만 필터링"""
    if not sources or not response_text:
        return sources
    # "관련 문서 없음" 판단
    if "찾지 못했습니다" in response_text or "관련 문서가 없" in response_text:
        return []
    filtered = []
    for src in sources:
        title = src.get("title", "")
        keywords = [w for w in title.replace("_", " ").split() if len(w) >= 3]
        if not keywords:
            continue
        match = sum(1 for kw in keywords if kw in response_text)
        if match >= max(len(keywords) // 2, 1):
            filtered.append(src)
    return filtered if filtered else sources  # 전부 필터되면 원본 유지


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
    }


def _get_agent_type(intent: str) -> str:
    """intent에 대응하는 agent_type 반환"""
    if intent == "judgment":
        return "judgment_agent"
    elif intent in ("doc_retrieve", "doc_generate", "doc_search", "doc_summary"):
        return "document_agent"
    elif intent.startswith("schedule_"):
        return "schedule_agent"
    elif intent in ("pipeline_create", "approval_create"):
        return "action_agent"
    return "general"


async def _maybe_update_summary(db: AsyncSession, session_id: str, user_id: int):
    """대화가 3턴을 초과하면 sLLM으로 요약을 갱신한다.

    최근 3턴(6메시지)은 chat_history로 직접 전달되므로,
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
    recent_skip = SUMMARY_TRIGGER_TURNS  # 최근 3턴은 제외
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
            logger.info("[Chat] 요청 수신 | user_id=%s", user.id)

            # lazy import (AI 의존성 없을 때 서버 기동 안 깨지게)
            from ai.agents.orchestrator import get_graph

            graph = get_graph()
            initial_state = _build_initial_state(request, user, stream_mode=True)

            # session_id로 이전 대화 이력 + 요약 로드
            if request.session_id:
                try:
                    # 최근 3턴 메시지 로드
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

            # document_id가 있으면 DB에서 문서 내용 로딩
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
                            doc_context += f"\n[문서 AI 분석 정보]\n"
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
                            sub_state = {
                                **initial_state,
                                "user_input": sq_query,
                                "stream_mode": False,
                                "sub_queries": None,  # 재귀 방지
                                "sub_responses": None,
                            }

                            try:
                                sub_result = await graph.ainvoke(sub_state)
                                sub_response = sub_result.get("agent_response", {})
                            except Exception as sub_err:
                                logger.error("[Chat] compound sub_query 처리 실패: %s", sub_err)
                                sub_response = {
                                    "type": sq_hint,
                                    "message": f"처리 중 오류: {sub_err}",
                                }

                            # sub_response 메시지를 토큰 단위로 스트리밍
                            sub_message = sub_response.get("message", "")
                            if sub_message:
                                # 적당한 크기로 잘라서 스트리밍 (자연스러운 UX)
                                chunk_size = 10
                                for j in range(0, len(sub_message), chunk_size):
                                    token = sub_message[j:j + chunk_size]
                                    yield f"data: {json.dumps({'type': 'token', 'value': token}, ensure_ascii=False)}\n\n"

                            sub_intent = sq_hint
                            try:
                                sub_intent = sub_result.get("intent", sq_hint)
                            except NameError:
                                pass

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

                        yield f"data: {json.dumps({'type': 'intent', 'intent': intent, 'confidence': confidence, 'agent_type': agent_type}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'status', 'value': f'{agent_type} 처리 중...'}, ensure_ascii=False)}\n\n"

                    elif node_name == "clarify_with_candidates":
                        # top-3 후보 제시
                        agent_response = node_output.get("agent_response", {})
                        candidates = agent_response.get("candidates", [])
                        yield f"data: {json.dumps({'type': 'clarify_candidates', 'data': {'candidates': candidates, 'message': agent_response.get('message', '')}}, ensure_ascii=False)}\n\n"

                    elif node_name == "general_response":
                        # 2-1. 일반 응답 스트리밍 (GPT API)
                        import os as _os
                        from openai import AsyncOpenAI

                        openai_key = _os.getenv("OPENAI_API_KEY")

                        if not openai_key:
                            yield f"data: {json.dumps({'type': 'error', 'message': 'OPENAI_API_KEY가 설정되지 않았습니다.'}, ensure_ascii=False)}\n\n"
                            continue

                        client = AsyncOpenAI(api_key=openai_key)

                        user_input = final_state.get("user_input", "")
                        chat_history = final_state.get("chat_history", [])

                        # 대화 요약이 있으면 시스템 프롬프트에 포함
                        from datetime import date as _date
                        _gen_sys = f"당신은 업무 도우미 '듀듀'입니다. 한국어로 친절하게 답변하세요.\n오늘 날짜: {_date.today().isoformat()}"
                        _chat_summary = final_state.get("chat_summary")
                        if _chat_summary:
                            _gen_sys += f"\n\n[이전 대화 요약]\n{_chat_summary}"

                        stream = await client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": _gen_sys},
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
                            "model_name": "gpt-4o-mini",
                        }

                    elif node_name == "judgment_agent":
                        # 2-4. 판단 Agent 2단계 sLLM (1: JSON 추출, 2: 자연어 설명 스트리밍)
                        agent_response = node_output.get("agent_response", {})
                        if agent_response.get("stream_pending"):
                            import os as _os_j
                            from openai import AsyncOpenAI as _AsyncOpenAI_j
                            import httpx as _httpx_j

                            # sLLM 모드 판별
                            _j_mode = _os_j.getenv("JUDGMENT_AGENT_MODE", "api")
                            _j_use_sllm = _j_mode == "sllm"
                            _j_stream_model = None
                            j_client = None
                            full_response = ""

                            if _j_use_sllm:
                                # === sLLM 2단계 호출 ===
                                vllm_base = _os_j.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
                                vllm_api_key = _os_j.getenv("VLLM_API_KEY", "EMPTY")
                                vllm_model = _os_j.getenv("VLLM_MODEL", "kakaocorp/kanana-1.5-8b-instruct-2505")
                                _j_use_lora = _os_j.getenv("VLLM_USE_LORA", "false").lower() == "true"
                                lora_model = "v1_judgment" if _j_use_lora else vllm_model
                                j_client = _AsyncOpenAI_j(
                                    api_key=vllm_api_key,
                                    base_url=vllm_base,
                                    timeout=_httpx_j.Timeout(60.0, connect=15.0),
                                    max_retries=0,
                                )
                                _j_stream_model = lora_model
                                logger.info("[Chat] judgment sLLM 2단계: model=%s", lora_model)

                                # ── 1단계: LoRA로 JSON 추출 (비스트리밍) ──
                                from ai.llm.prompts import JUDGMENT_SYSTEM_PROMPT as _J_SYS
                                try:
                                    _j_resp = await j_client.chat.completions.create(
                                        model=lora_model,
                                        messages=[
                                            {"role": "system", "content": _J_SYS},
                                            {"role": "user", "content": agent_response["user_prompt"]},
                                        ],
                                        temperature=0.1,
                                        max_tokens=2048,
                                    )
                                    full_response = _j_resp.choices[0].message.content or ""
                                    logger.info("[Chat] judgment 1단계 JSON 수신 (%d자)", len(full_response))
                                except Exception as _sllm_err:
                                    logger.warning("[Chat] judgment 1단계 실패, API fallback: %s", _sllm_err)
                                    _j_use_sllm = False
                                    full_response = ""

                                # ── 2단계: base 모델로 자연어 설명 스트리밍 ──
                                if _j_use_sllm and full_response:
                                    from ai.agents.judgment_agent import _parse_llm_response as _plr
                                    _j_parsed_check = _plr(full_response)

                                    if _j_parsed_check.get("confidence", 0) > 0:
                                        _user_q = agent_response["user_prompt"].split("## 사용자 질문")[-1].strip() if "## 사용자 질문" in agent_response["user_prompt"] else agent_response["user_prompt"].split("\n")[-1]
                                        _reasoning = _j_parsed_check.get("reasoning", "")
                                        _result = _j_parsed_check.get("result", "")
                                        _conditions = _j_parsed_check.get("conditions", "")
                                        _regs = _j_parsed_check.get("regulations", [])
                                        _reg_info = ", ".join(f"{r.get('article', '')} ({r.get('content', '')})" for r in _regs[:3]) if _regs else ""

                                        # RAG 규정 원문 상위 2개 포함
                                        _rag_ctx = agent_response.get("_rag_context", [])
                                        _rag_text = ""
                                        for _rc in _rag_ctx[:2]:
                                            _rc_content = _rc.get("content", "") if isinstance(_rc, dict) else str(_rc)
                                            if _rc_content:
                                                _rag_text += f"\n- {_rc_content[:200]}"

                                        _result_kr = {"yes": "가능", "no": "불가", "conditional": "조건부 가능", "no_regulation": "관련 규정 없음"}.get(_result, _result)

                                        _explain_sys = """당신은 사내 규정 안내 전문가입니다.
아래 판단 데이터를 바탕으로 사용자에게 친절하고 구체적으로 답변하세요.

규칙:
- 반드시 제공된 판단 근거(reasoning) 안에서만 답변하세요. 없는 내용을 지어내지 마세요.
- 관련 규정 조항을 자연스럽게 언급하세요 (예: "제8조에 따르면...")
- 조건부(conditional)이면 필요한 조건을 구체적으로 안내하세요
- 불가(no)이면 왜 안 되는지 명확히 설명하세요
- 3~5문장으로 간결하게 답변하세요
- "1부", "2부", "##" 같은 섹션 헤더 없이 바로 설명을 시작하세요"""

                                        _explain_user = f"""사용자 질문: {_user_q}

판단 결과: {_result_kr}
판단 근거: {_reasoning}
{f'조건: {_conditions}' if _conditions else ''}
관련 규정: {_reg_info}
{f'규정 원문 참고:{_rag_text}' if _rag_text else ''}"""

                                        try:
                                            _explain_stream = await j_client.chat.completions.create(
                                                model=vllm_model,  # base 모델 (LoRA 없이)
                                                messages=[
                                                    {"role": "system", "content": _explain_sys},
                                                    {"role": "user", "content": _explain_user},
                                                ],
                                                temperature=0.4,
                                                max_tokens=512,
                                                stream=True,
                                            )
                                            async for chunk in _explain_stream:
                                                if chunk.choices[0].delta.content:
                                                    yield f"data: {json.dumps({'type': 'token', 'value': chunk.choices[0].delta.content}, ensure_ascii=False)}\n\n"
                                            logger.info("[Chat] judgment 2단계 자연어 스트리밍 완료")
                                        except Exception as _exp_err:
                                            logger.warning("[Chat] judgment 2단계 실패: %s", _exp_err)
                                            yield f"data: {json.dumps({'type': 'token', 'value': _reasoning}, ensure_ascii=False)}\n\n"
                                    else:
                                        logger.warning("[Chat] judgment 1단계 JSON 파싱 실패, API fallback")
                                        _j_use_sllm = False
                                        full_response = ""

                            if not _j_use_sllm:
                                # API 모드: OpenAI 스트리밍 (자연어 + JSON)
                                openai_key = _os_j.getenv("OPENAI_API_KEY")
                                if not openai_key:
                                    yield f"data: {json.dumps({'type': 'error', 'message': 'OPENAI_API_KEY가 설정되지 않았습니다.'}, ensure_ascii=False)}\n\n"
                                    continue
                                openai_base = _os_j.getenv("LLM_BASE_URL") or None
                                j_client = _AsyncOpenAI_j(api_key=openai_key, base_url=openai_base) if openai_base else _AsyncOpenAI_j(api_key=openai_key)
                                _j_stream_model = _os_j.getenv("OPENAI_MODEL", "gpt-4o-mini") + (" (fallback)" if _j_mode == "sllm" else "")

                                j_stream = await j_client.chat.completions.create(
                                    model=_os_j.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                                    messages=[
                                        {"role": "system", "content": agent_response["sys_prompt"]},
                                        {"role": "user", "content": agent_response["user_prompt"]},
                                    ],
                                    temperature=0.1,
                                    max_tokens=2048,
                                    stream=True,
                                )

                                full_response = ""
                                _JSON_PREFIXES = ("`", "``", "```", "```j", "```js", "```jso", "```json")
                                in_json_block = False
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
                                            pending_tokens.append(token)
                                        else:
                                            for pt in pending_tokens:
                                                yield f"data: {json.dumps({'type': 'token', 'value': pt}, ensure_ascii=False)}\n\n"
                                            pending_tokens.clear()
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

                            # message: 2단계 스트리밍에서는 reasoning 사용
                            parsed["message"] = parsed.get("reasoning", "")

                            # agent_response 업데이트
                            agent_response.pop("stream_pending", None)
                            agent_response.pop("sys_prompt", None)
                            agent_response.pop("user_prompt", None)
                            agent_response.pop("_rag_context", None)
                            agent_response.update(parsed)
                            agent_response["model_name"] = _j_stream_model
                            final_state["agent_response"] = agent_response
                        else:
                            yield f"data: {json.dumps({'type': 'status', 'value': 'judgment_agent 처리 완료'}, ensure_ascii=False)}\n\n"

                    elif node_name == "document_agent":
                        # 2-2. 문서 Agent 스트리밍
                        agent_response = node_output.get("agent_response", {})

                        # 관련 문서 없음 등 stream_pending 없이 바로 응답하는 경우 → token으로 메시지 전송
                        if not agent_response.get("stream_pending") and agent_response.get("message"):
                            msg = agent_response["message"]
                            yield f"data: {json.dumps({'type': 'token', 'value': msg}, ensure_ascii=False)}\n\n"

                        if agent_response.get("stream_pending"):
                            # ── StreamRequest 프로토콜: agent가 준비한 설정대로 vLLM 스트리밍 ──
                            cfg = agent_response.get("llm_config", {})
                            post = agent_response.get("post_stream", {})

                            doc_client, _stream_model = _get_vllm_client(cfg.get("task", "qa"))
                            logger.info("[Chat] document_agent 스트리밍: model=%s, task=%s", _stream_model, cfg.get("task"))

                            doc_stream = await doc_client.chat.completions.create(
                                model=_stream_model,
                                messages=[
                                    {"role": "system", "content": cfg["sys_prompt"]},
                                    {"role": "user", "content": cfg["user_prompt"]},
                                ],
                                temperature=cfg.get("temperature", 0.1),
                                max_tokens=cfg.get("max_tokens", 1024),
                                stream=True,
                            )

                            full_doc_response = ""
                            async for chunk in doc_stream:
                                if chunk.choices[0].delta.content:
                                    token = chunk.choices[0].delta.content
                                    full_doc_response += token
                                    yield f"data: {json.dumps({'type': 'token', 'value': token}, ensure_ascii=False)}\n\n"

                            # 응답 채우기
                            agent_response["message"] = full_doc_response
                            agent_response["answer"] = full_doc_response
                            agent_response["model_name"] = _stream_model

                            # post_stream 처리
                            if post.get("update_summary_db"):
                                await _update_summary_db(db, post["update_summary_db"], full_doc_response)
                            if post.get("check_regulation") and full_doc_response and len(full_doc_response) > 50:
                                yield f"data: {json.dumps({'type': 'status', 'value': '규정 연관성 확인 중...'}, ensure_ascii=False)}\n\n"
                                reg = await _stream_regulation(full_doc_response, user.id)
                                if reg:
                                    agent_response["regulation_check"] = reg
                                    yield f"data: {json.dumps({'type': 'token', 'value': reg['summary']}, ensure_ascii=False)}\n\n"
                                    agent_response["message"] = full_doc_response + reg["summary"]
                                    agent_response["answer"] = full_doc_response + reg["summary"]
                            if post.get("filter_sources"):
                                agent_response["sources"] = _filter_sources(agent_response.get("sources", []), full_doc_response)

                            # cleanup
                            for k in ("stream_pending", "llm_config", "post_stream"):
                                agent_response.pop(k, None)
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
                            if not skip_token and intent not in ("general", "doc_retrieve", "doc_search", "doc_summary", "judgment", "compound", "pipeline_create", "approval_create"):
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

            # 5. 대화 요약 갱신 (비동기, 사용자 응답 차단 안 함)
            try:
                await _maybe_update_summary(db, session_id, user.id)
            except Exception as sum_err:
                logger.warning("[Chat] 요약 갱신 실패 (무시): %s", sum_err)

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
