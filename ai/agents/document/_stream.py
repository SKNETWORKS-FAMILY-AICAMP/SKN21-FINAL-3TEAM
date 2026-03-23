"""문서 Agent 스트리밍 실행기 — chat.py에서 분리된 vLLM 스트리밍 로직"""
import asyncio
import logging
import os
import re
from typing import AsyncGenerator

from ai.agents.document._common import LORA_ADAPTER_NAMES

logger = logging.getLogger(__name__)


def get_streaming_client(task: str) -> tuple:
    """vLLM 스트리밍 클라이언트 + 모델명 반환 (문서 Agent 전용)

    Returns: (AsyncOpenAI client, model_name str)
    """
    import httpx
    from openai import AsyncOpenAI

    vllm_base = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    vllm_api_key = os.getenv("VLLM_API_KEY", "EMPTY")
    vllm_model = os.getenv("VLLM_MODEL", "kakaocorp/kanana-1.5-8b-instruct-2505")
    use_lora = os.getenv("VLLM_USE_LORA", "false").lower() == "true"

    model = (LORA_ADAPTER_NAMES.get(task) or vllm_model) if use_lora else vllm_model

    client = AsyncOpenAI(
        api_key=vllm_api_key, base_url=vllm_base,
        timeout=httpx.Timeout(60.0, connect=15.0), max_retries=0,
    )
    return client, model


async def execute_doc_stream(
    llm_config: dict,
    post_stream: dict,
    db,
    user_id: int,
    agent_response: dict,
) -> AsyncGenerator[str, None]:
    """문서 Agent StreamRequest 실행 — 토큰 스트리밍 + 후처리

    chat.py는 이 제너레이터를 순회하며 SSE 이벤트만 발송하면 됨.

    Yields:
        각 토큰 문자열 (type: "token" 이벤트 value)

    Side effects:
        agent_response dict를 in-place로 업데이트 (message, answer, model_name 등)
    """
    task = llm_config.get("task", "qa")
    client, model = get_streaming_client(task)
    logger.info("[DocStream] 스트리밍 시작: model=%s, task=%s", model, task)

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": llm_config["sys_prompt"]},
                {"role": "user", "content": llm_config["user_prompt"]},
            ],
            temperature=llm_config.get("temperature", 0.1),
            max_tokens=llm_config.get("max_tokens", 1024),
            stream=True,
        )
    except Exception as e:
        # LoRA 실패 → base 모델로 폴백 (같은 클라이언트, 모델명만 변경)
        vllm_model = os.getenv("VLLM_MODEL", "kakaocorp/kanana-1.5-8b-instruct-2505")
        if model != vllm_model:
            logger.warning("[DocStream] LoRA(%s) 실패, base 폴백: %s", model, e)
            stream = await client.chat.completions.create(
                model=vllm_model,
                messages=[
                    {"role": "system", "content": llm_config["sys_prompt"]},
                    {"role": "user", "content": llm_config["user_prompt"]},
                ],
                temperature=llm_config.get("temperature", 0.1),
                max_tokens=llm_config.get("max_tokens", 1024),
                stream=True,
            )
            model = vllm_model + " (base, LoRA fallback)"
        else:
            raise

    # 토큰 스트리밍 (빈 응답 시 1회 재시도)
    logger.info("[DocStream] 스트림 생성 완료, 토큰 수신 시작 | model=%s, prompt_len=%d",
                model, len(llm_config.get("user_prompt", "")))
    full_response = ""
    max_attempts = 2
    for attempt in range(max_attempts):
        if attempt > 0:
            logger.info("[DocStream] 빈 응답 → 재시도 %d/%d", attempt + 1, max_attempts)
            try:
                stream = await client.chat.completions.create(
                    model=model.replace(" (base, LoRA fallback)", ""),
                    messages=[
                        {"role": "system", "content": llm_config["sys_prompt"]},
                        {"role": "user", "content": llm_config["user_prompt"]},
                    ],
                    temperature=llm_config.get("temperature", 0.1),
                    max_tokens=llm_config.get("max_tokens", 1024),
                    stream=True,
                )
            except Exception:
                break

        stream_iter = stream.__aiter__()
        chunk_count = 0
        while True:
            try:
                chunk = await asyncio.wait_for(stream_iter.__anext__(), timeout=90)
                chunk_count += 1
            except StopAsyncIteration:
                logger.info("[DocStream] 스트림 종료: %d chunks, %d자 수신", chunk_count, len(full_response))
                break
            except asyncio.TimeoutError:
                logger.warning("[DocStream] chunk 타임아웃 (90초)")
                if not full_response:
                    full_response = "응답 생성 중 시간이 초과되었습니다."
                    yield full_response
                break
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                full_response += token
                yield token

        if full_response.strip():
            break  # 응답 있으면 재시도 안 함

    # 재시도 후에도 빈 응답
    if not full_response.strip():
        full_response = "응답을 생성하지 못했습니다. 잠시 후 다시 시도해주세요."
        yield full_response

    # agent_response 업데이트
    agent_response["message"] = full_response
    agent_response["answer"] = full_response
    agent_response["model_name"] = model

    # ── post_stream 처리 ──
    if post_stream.get("update_summary_db") and full_response:
        parsed = await _post_update_summary(db, post_stream["update_summary_db"], full_response)
        # 파싱 결과를 agent_response에 반영 (프론트 요약 카드에서 태그/요약 표시용)
        if parsed:
            agent_response["tags"] = parsed.get("tags", [])
            agent_response["summary"] = parsed.get("summary", "")
            agent_response["document_id"] = post_stream["update_summary_db"]
            agent_response.setdefault("sub_type", "summary")

    if post_stream.get("check_regulation") and full_response and len(full_response) > 50:
        reg = await _post_check_regulation(full_response, user_id)
        if reg:
            agent_response["regulation_check"] = reg
            agent_response["message"] = full_response + reg["summary"]
            agent_response["answer"] = full_response + reg["summary"]

    if post_stream.get("filter_sources"):
        # 원본 sources 보존 (최종 보장용)
        agent_response["_original_sources"] = list(agent_response.get("sources", []))
        # sLLM이 답변 끝에 [참고: 문서제목] 형식으로 실제 참고 문서를 표기
        ref_titles = list(dict.fromkeys(re.findall(r"\[참고[:\s]*([^\]]+)\]", full_response)))  # 중복 제거, 순서 유지
        # 답변 텍스트에서 [참고: ...] 줄 제거 (프론트에 깔끔하게 전달)
        clean_response = re.sub(r"\n*\[참고[:\s]*[^\]]+\]\n*", "", full_response).rstrip()
        if clean_response:
            full_response = clean_response
            agent_response["answer"] = clean_response
            agent_response["message"] = clean_response

        if ref_titles:
            # A방식: sLLM이 명시한 문서만 sources에 남김
            logger.info("[DocStream] sLLM 참고 문서: %s", ref_titles)
            ref_set = {t.strip() for t in ref_titles}
            agent_response["sources"] = [
                s for s in agent_response.get("sources", [])
                if s.get("title", "") in ref_set
            ]
        else:
            # fallback: sLLM이 [참고:] 태그 안 붙인 경우 → 기존 키워드 매칭
            logger.info("[DocStream] [참고] 태그 없음 → 키워드 매칭 fallback")
            original_sources = agent_response.get("sources", [])
            filtered = _filter_sources(original_sources, full_response)
            # 필터 결과 0건이면 상위 1건은 남김 (RAG에서 찾아서 답변한 건 확실하므로)
            if not filtered and original_sources:
                filtered = original_sources[:1]
                logger.info("[DocStream] 키워드 매칭 0건 → 상위 1건 유지: %s", filtered[0].get("title", ""))
            agent_response["sources"] = filtered

        # 최종 보장: 어떤 경로든 sources 0건이면 원본 상위 1건 유지
        if not agent_response.get("sources"):
            _orig = agent_response.get("_original_sources", [])
            if _orig:
                agent_response["sources"] = _orig[:1]
                logger.info("[DocStream] sources 최종 보장: %s", _orig[0].get("title", ""))

        # citations 생성 (filtered sources 기반)
        if agent_response.get("sources"):
            agent_response["citations"] = [
                {
                    "source": s.get("title", ""),
                    "content": s.get("content", "")[:200],
                    "relevance": "높음" if s.get("score", 0) >= 0.7 else "중간" if s.get("score", 0) >= 0.4 else "낮음",
                }
                for s in agent_response["sources"][:3]
            ]

    # cleanup
    for k in ("stream_pending", "llm_config", "post_stream", "_original_sources"):
        agent_response.pop(k, None)


async def _post_update_summary(db, document_id: int, response_text: str) -> dict | None:
    """요약 스트리밍 후 DB 업데이트 (파싱 실패 시 폴백 포함)

    Returns:
        parse_summary_output 결과 dict (tags, summary 포함) 또는 None
    """
    try:
        from ai.agents.document._summary import parse_summary_output
        from app.models.document import Document
        from sqlalchemy import select

        parsed = parse_summary_output(response_text)
        if not parsed["summary"]:
            logger.warning("[DocStream] 요약 파싱 결과 비어있음, 스킵")
            return parsed  # 비어있어도 반환 (호출측에서 판단)

        result = await db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.summary = parsed["summary"]
            doc.tags = parsed["tags"]
            await db.commit()
            logger.info("[DocStream] DB 요약 업데이트 완료: document_id=%s", document_id)
        return parsed
    except Exception as e:
        logger.warning("[DocStream] DB 요약 업데이트 실패: %s", e)
        return None


async def _post_check_regulation(text: str, user_id: int) -> dict | None:
    """규정 연결 체크 (비차단)"""
    try:
        from ai.agents.regulation_validator import check_content_regulations
        result = await check_content_regulations(text, user_id=user_id)
        return result if result.get("notes") else None
    except Exception as e:
        logger.warning("[DocStream] 규정 연결 실패 (비차단): %s", e)
        return None


def _filter_sources(sources: list, response_text: str) -> list:
    """LLM 답변에 실제 언급된 소스만 필터링"""
    if not sources or not response_text:
        return sources
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
    return filtered if filtered else sources
