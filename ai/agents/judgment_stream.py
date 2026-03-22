"""판단 Agent 스트리밍 실행기 — chat.py에서 분리된 judgment 2단계 스트리밍 로직"""
import asyncio
import logging
import os
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


async def execute_judgment_stream(
    agent_response: dict,
    user_input: str,
) -> AsyncGenerator[str, None]:
    """판단 Agent 스트리밍 실행 — sLLM 2단계 또는 API 모드

    sLLM 모드:
      1단계: LoRA로 JSON 추출 (비스트리밍)
      2단계: base 모델로 자연어 설명 스트리밍

    API 모드:
      OpenAI 스트리밍 (자연어 + JSON 혼합, JSON 블록 숨김)

    Yields:
        각 토큰 문자열

    Side effects:
        agent_response dict를 in-place로 업데이트
    """
    import httpx
    from openai import AsyncOpenAI

    mode = os.getenv("JUDGMENT_AGENT_MODE", "api")
    use_sllm = mode == "sllm"
    stream_model = None
    full_response = ""

    if use_sllm:
        # === sLLM 2단계 호출 ===
        vllm_base = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        vllm_api_key = os.getenv("VLLM_API_KEY", "EMPTY")
        vllm_model = os.getenv("VLLM_MODEL", "kakaocorp/kanana-1.5-8b-instruct-2505")
        use_lora = os.getenv("VLLM_USE_LORA", "false").lower() == "true"
        lora_model = "v1_judgment" if use_lora else vllm_model

        client = AsyncOpenAI(
            api_key=vllm_api_key, base_url=vllm_base,
            timeout=httpx.Timeout(60.0, connect=15.0), max_retries=0,
        )
        stream_model = lora_model
        logger.info("[JudgmentStream] sLLM 2단계: model=%s", lora_model)

        # ── 1단계: LoRA로 JSON 추출 (비스트리밍) ──
        from ai.llm.prompts import JUDGMENT_SYSTEM_PROMPT
        try:
            resp = await client.chat.completions.create(
                model=lora_model,
                messages=[
                    {"role": "system", "content": JUDGMENT_SYSTEM_PROMPT},
                    {"role": "user", "content": agent_response["user_prompt"]},
                ],
                temperature=0.1,
                max_tokens=2048,
            )
            full_response = resp.choices[0].message.content or ""
            logger.info("[JudgmentStream] 1단계 JSON 수신 (%d자)", len(full_response))
        except Exception as e:
            logger.warning("[JudgmentStream] 1단계 실패, API fallback: %s", e)
            use_sllm = False
            full_response = ""

        # ── 2단계: base 모델로 자연어 설명 스트리밍 ──
        if use_sllm and full_response:
            from ai.agents.judgment_agent import _parse_llm_response
            parsed_check = _parse_llm_response(full_response)

            if parsed_check.get("confidence", 0) > 0:
                async for token in _stream_explanation(client, vllm_model, agent_response, parsed_check):
                    yield token
            else:
                logger.warning("[JudgmentStream] 1단계 JSON 파싱 실패, API fallback")
                use_sllm = False
                full_response = ""

    if not use_sllm:
        # === API 모드: OpenAI 스트리밍 ===
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            yield "OPENAI_API_KEY가 설정되지 않았습니다."
            return

        openai_base = os.getenv("LLM_BASE_URL") or None
        client = AsyncOpenAI(api_key=openai_key, base_url=openai_base) if openai_base else AsyncOpenAI(api_key=openai_key)
        stream_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini") + (" (fallback)" if mode == "sllm" else "")

        stream = await client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
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

        async for chunk in stream:
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
                        yield pt
                    pending_tokens.clear()
                    yield token

    # ── JSON 파싱 + 3중 검증 ──
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

    inconsistency = _check_consistency(user_input, parsed)
    if inconsistency:
        parsed["consistency_flag"] = inconsistency

    parsed["message"] = parsed.get("reasoning", "")

    # agent_response 업데이트
    for k in ("stream_pending", "sys_prompt", "user_prompt", "_rag_context"):
        agent_response.pop(k, None)
    agent_response.update(parsed)
    agent_response["model_name"] = stream_model


async def _stream_explanation(client, base_model: str, agent_response: dict, parsed: dict) -> AsyncGenerator[str, None]:
    """2단계: JSON 파싱 결과를 바탕으로 자연어 설명 스트리밍"""
    user_prompt = agent_response["user_prompt"]
    user_q = user_prompt.split("## 사용자 질문")[-1].strip() if "## 사용자 질문" in user_prompt else user_prompt.split("\n")[-1]

    reasoning = parsed.get("reasoning", "")
    result = parsed.get("result", "")
    conditions = parsed.get("conditions", "")
    regs = parsed.get("regulations", [])
    reg_info = ", ".join(f"{r.get('article', '')} ({r.get('content', '')})" for r in regs[:3]) if regs else ""

    # RAG 규정 원문 상위 2개 포함
    rag_ctx = agent_response.get("_rag_context", [])
    rag_text = ""
    for rc in rag_ctx[:2]:
        rc_content = rc.get("content", "") if isinstance(rc, dict) else str(rc)
        if rc_content:
            rag_text += f"\n- {rc_content[:200]}"

    result_kr = {"yes": "가능", "no": "불가", "conditional": "조건부 가능", "no_regulation": "관련 규정 없음"}.get(result, result)

    sys_prompt = """당신은 사내 규정 안내 전문가입니다.
아래 판단 데이터를 바탕으로 사용자에게 친절하고 구체적으로 답변하세요.

규칙:
- 반드시 제공된 판단 근거(reasoning) 안에서만 답변하세요. 없는 내용을 지어내지 마세요.
- 관련 규정 조항을 자연스럽게 언급하세요 (예: "제8조에 따르면...")
- 조건부(conditional)이면 필요한 조건을 구체적으로 안내하세요
- 불가(no)이면 왜 안 되는지 명확히 설명하세요
- 3~5문장으로 간결하게 답변하세요
- "1부", "2부", "##" 같은 섹션 헤더 없이 바로 설명을 시작하세요"""

    user_msg = f"""사용자 질문: {user_q}

판단 결과: {result_kr}
판단 근거: {reasoning}
{f'조건: {conditions}' if conditions else ''}
관련 규정: {reg_info}
{f'규정 원문 참고:{rag_text}' if rag_text else ''}"""

    try:
        stream = await client.chat.completions.create(
            model=base_model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.4,
            max_tokens=512,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
        logger.info("[JudgmentStream] 2단계 자연어 스트리밍 완료")
    except Exception as e:
        logger.warning("[JudgmentStream] 2단계 실패: %s", e)
        yield reasoning
