"""문서 Agent 스트리밍 실행기 — chat.py에서 분리된 vLLM 스트리밍 로직"""
import asyncio
import logging
import os
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

    model = LORA_ADAPTER_NAMES.get(task, vllm_model) if use_lora else vllm_model

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

    # 토큰 스트리밍
    full_response = ""
    stream_iter = stream.__aiter__()
    while True:
        try:
            chunk = await asyncio.wait_for(stream_iter.__anext__(), timeout=30)
        except StopAsyncIteration:
            break
        except asyncio.TimeoutError:
            logger.warning("[DocStream] chunk 타임아웃 (30초)")
            if not full_response:
                full_response = "응답 생성 중 시간이 초과되었습니다."
                yield full_response
            break
        if chunk.choices and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            full_response += token
            yield token

    # 빈 응답 방어 (vLLM cold start 시 토큰 0개로 종료될 수 있음)
    if not full_response.strip():
        full_response = "응답을 생성하지 못했습니다. 잠시 후 다시 시도해주세요. (모델 워커 준비 중일 수 있습니다)"
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
        agent_response["sources"] = _filter_sources(
            agent_response.get("sources", []), full_response
        )
        # 스트리밍 QA: sources → citations 변환 (프론트 QA 카드 인용 표시용)
        if not agent_response.get("citations") and agent_response.get("sources"):
            agent_response["citations"] = [
                {
                    "source": s.get("title", ""),
                    "content": s.get("content", "")[:200],
                    "relevance": "높음" if s.get("score", 0) >= 0.7 else "중간" if s.get("score", 0) >= 0.4 else "낮음",
                }
                for s in agent_response["sources"][:3]  # 상위 3개만
            ]

    # cleanup
    for k in ("stream_pending", "llm_config", "post_stream"):
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
