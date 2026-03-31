"""
내부 규정 검증 도구 (비스트리밍)

다른 Agent/서비스에서 내부적으로 규정 체크할 때 사용.
사용자에게 직접 보여주지 않고, 추천/생성 결과에 경고 태그를 붙이는 용도.

사용법:
    from ai.agents.regulation_checker import regulation_check

    result = await regulation_check("이 직원이 재택근무 가능한가?")
    # {"result": "conditional", "reason": "주 2회까지 가능", ...}
"""

import json
import logging
import os
import time

logger = logging.getLogger(__name__)

REGULATION_CHECK_PROMPT = """\
당신은 회사 내부 규정 전문가입니다. 주어진 질문에 대해 규정 위반 여부만 간결하게 판단하세요.

## 검색된 관련 규정
{context}

## 판단 기준
- 관련 규정이 있으면 해당 규정에 근거하여 판단
- 관련 규정이 없으면 "no_regulation"으로 응답
- 불확실하면 "conditional"로 응답

## 출력 형식 (JSON만 출력)
{{
    "result": "yes" | "no" | "conditional" | "no_regulation",
    "reason": "한 줄 판단 근거",
    "regulation": "관련 규정명과 조항 (없으면 null)",
    "confidence": 0.0~1.0
}}

규칙:
- JSON 외 텍스트 금지
- reason은 반드시 한국어, 1~2문장
- 확실하지 않으면 confidence를 낮게\
"""


async def regulation_check(
    query: str,
    user_id: int | None = None,
    top_k: int = 3,
) -> dict:
    """내부 규정 검증 (비스트리밍, 경량)

    Args:
        query: 검증할 질문 (예: "재택근무가 규정상 가능한가?")
        user_id: 사용자 ID (RAG 필터용)
        top_k: 검색할 규정 수

    Returns:
        {
            "result": "yes" | "no" | "conditional" | "no_regulation" | "error",
            "reason": "판단 근거 한 줄",
            "regulation": "관련 규정명 (없으면 null)",
            "confidence": 0.0~1.0,
            "checked": True/False  # 실제 검증이 수행됐는지
        }
    """
    _t = time.time()
    _default = {
        "result": "unknown",
        "reason": "규정 확인 불가",
        "regulation": None,
        "confidence": 0.0,
        "checked": False,
    }

    # 1. RAG 검색 (동기 함수를 executor에서 실행하여 스레드 안전성 확보)
    try:
        import asyncio
        from ai.rag.qdrant_pipeline import get_qdrant_pipeline
        pipeline = get_qdrant_pipeline()

        def _do_retrieve():
            return pipeline.retrieve(
                query=query,
                user_id=user_id,
                top_k=top_k,
                filter={"source": "regulations"},
                use_reranker=True,
                score_threshold=0.0,
                use_hyde=True,
            )

        loop = asyncio.get_event_loop()
        context = await loop.run_in_executor(None, _do_retrieve)
    except Exception as e:
        logger.warning("[RegCheck] RAG 검색 실패: %s", e)
        return _default

    # context가 list면 문자열로 변환
    if isinstance(context, list):
        context_str = "\n\n".join(
            doc if isinstance(doc, str) else str(doc) for doc in context
        )
    else:
        context_str = str(context) if context else ""

    if not context_str.strip():
        logger.info("[RegCheck] 관련 규정 없음 (query=%s)", query[:50])
        return {
            "result": "no_regulation",
            "reason": "관련 규정을 찾을 수 없음",
            "regulation": None,
            "confidence": 0.0,
            "checked": True,
        }

    # 2. LLM 호출
    try:
        from ai.llm import get_llm, create_llm

        sys_prompt = REGULATION_CHECK_PROMPT.format(context=context_str[:3000])

        # sLLM 우선, 실패(타임아웃 포함) 시 GPT fallback
        response = None
        try:
            llm = create_llm(provider="vllm")
            response = await llm.generate(
                prompt=query,
                system_prompt=sys_prompt,
                json_mode=True,
                temperature=0.1,
                max_tokens=500,
            )
        except Exception as vllm_err:
            logger.info("[RegCheck] sLLM 실패 (%s), GPT fallback", vllm_err)
            llm = get_llm()
            response = await llm.generate(
                prompt=query,
                system_prompt=sys_prompt,
                json_mode=True,
                temperature=0.1,
                max_tokens=500,
            )

        raw = response.content.strip()
        # 코드블록 제거
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        parsed = json.loads(raw)

        result = {
            "result": parsed.get("result", "unknown"),
            "reason": parsed.get("reason", ""),
            "regulation": parsed.get("regulation"),
            "confidence": min(1.0, max(0.0, float(parsed.get("confidence", 0.5)))),
            "checked": True,
        }

        # result 값 검증
        valid_results = {"yes", "no", "conditional", "no_regulation"}
        if result["result"] not in valid_results:
            result["result"] = "unknown"

        logger.info(
            "[RegCheck] 완료 (%.2fs) | query='%s' → %s (%.0f%%)",
            time.time() - _t, query[:40], result["result"], result["confidence"] * 100,
        )
        return result

    except json.JSONDecodeError as e:
        logger.warning("[RegCheck] JSON 파싱 실패: %s", e)
        return _default
    except Exception as e:
        logger.warning("[RegCheck] LLM 호출 실패: %s", e)
        return _default
