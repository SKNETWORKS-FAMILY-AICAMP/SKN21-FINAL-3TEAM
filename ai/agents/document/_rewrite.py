"""sLLM 기반 쿼리 리라이팅 — regex follow-up 미감지 시 fallback

사용자의 모호한 후속 질문("위에 문서 알려줘", "두 번째 거 요약해줘")을
sLLM(Kanana)으로 구체적 문서명이 포함된 쿼리로 변환.

호출 조건: prev_doc 존재 + regex 미매칭 + 구체적 문서명 없음
"""
import asyncio
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("document_agent")

_SLLM_TIMEOUT = 8  # seconds


@dataclass
class RewriteResult:
    """sLLM 쿼리 리라이팅 결과"""
    rewritten_query: str
    is_followup: bool
    matched_source_idx: Optional[int]
    matched_document_id: Optional[int]


async def rewrite_followup_query(
    user_input: str,
    prev_sources: list,
    chat_context: str = "",
) -> RewriteResult:
    """sLLM으로 follow-up 쿼리를 리라이팅한다.

    Args:
        user_input: 원본 사용자 쿼리
        prev_sources: 이전 검색 결과의 sources 리스트
        chat_context: _format_chat_context()로 생성한 최근 대화 텍스트

    Returns:
        RewriteResult
    """
    _fallback = RewriteResult(
        rewritten_query=user_input,
        is_followup=False,
        matched_source_idx=None,
        matched_document_id=None,
    )

    # Guard: VLLM_BASE_URL 미설정
    if not os.getenv("VLLM_BASE_URL"):
        logger.debug("[Rewrite] VLLM_BASE_URL 미설정, 스킵")
        return _fallback

    numbered_titles = _build_numbered_titles(prev_sources)

    from ai.llm.prompts import QUERY_REWRITE_PROMPT
    user_prompt = QUERY_REWRITE_PROMPT.format(
        numbered_titles=numbered_titles,
        chat_context=chat_context,
        user_input=user_input,
    )

    try:
        from ai.serving.vllm_client import VLLMProvider
        llm = VLLMProvider()

        response = await asyncio.wait_for(
            llm.generate(
                prompt=user_prompt,
                max_tokens=128,
                temperature=0.0,
            ),
            timeout=_SLLM_TIMEOUT,
        )
        raw = response.content.strip()
        logger.info("[Rewrite] sLLM 응답: '%s'", raw[:200])

        return _parse_and_validate(raw, user_input, prev_sources)

    except asyncio.TimeoutError:
        logger.warning("[Rewrite] 타임아웃 (%ds)", _SLLM_TIMEOUT)
        return _fallback
    except Exception as e:
        logger.warning("[Rewrite] sLLM 호출 실패: %s", e)
        return _fallback


def _build_numbered_titles(sources: list) -> str:
    """소스 목록을 번호 매긴 문자열로 변환"""
    if not sources:
        return "(이전 검색 결과 없음)"
    lines = []
    for i, src in enumerate(sources, 1):
        title = src.get("title", "제목 없음")
        lines.append(f"{i}. {title}")
    return "\n".join(lines)


def _parse_and_validate(
    raw: str,
    user_input: str,
    prev_sources: list,
) -> RewriteResult:
    """sLLM 응답을 파싱하고 title 매칭으로 검증"""
    _fallback = RewriteResult(
        rewritten_query=user_input,
        is_followup=False,
        matched_source_idx=None,
        matched_document_id=None,
    )

    # ORIGINAL: → follow-up 아님
    if raw.upper().startswith("ORIGINAL:"):
        logger.info("[Rewrite] ORIGINAL 판정")
        return _fallback

    # REWRITE: → 리라이팅된 쿼리 추출
    m = re.match(r"(?i)REWRITE:\s*(.+)", raw, re.DOTALL)
    if not m:
        logger.warning("[Rewrite] 예상치 못한 응답 형식: '%s'", raw[:100])
        return _fallback

    rewritten = m.group(1).strip().split("\n")[0]  # 첫 줄만
    if not rewritten or len(rewritten) > len(user_input) * 3:
        # 할루시네이션 방지: 원본 대비 3배 이상이면 스킵
        logger.warning("[Rewrite] 비정상 길이: %d vs 원본 %d", len(rewritten), len(user_input))
        return _fallback

    # title 매칭 검증
    idx, doc_id = _validate_rewrite(rewritten, prev_sources)

    if idx is not None:
        logger.info("[Rewrite] 매칭 성공: idx=%d, doc_id=%s, query='%s'", idx, doc_id, rewritten[:80])
        return RewriteResult(
            rewritten_query=rewritten,
            is_followup=True,
            matched_source_idx=idx,
            matched_document_id=doc_id,
        )
    else:
        # 매칭 실패 → 쿼리만 교체, follow-up은 아님
        logger.info("[Rewrite] title 매칭 실패, 쿼리만 교체: '%s'", rewritten[:80])
        return RewriteResult(
            rewritten_query=rewritten,
            is_followup=False,
            matched_source_idx=None,
            matched_document_id=None,
        )


def _validate_rewrite(rewritten: str, prev_sources: list) -> tuple:
    """리라이팅된 쿼리에 이전 소스의 title 키워드가 포함되는지 검증

    Returns:
        (matched_index, document_id) or (None, None)
    """
    best_idx = None
    best_score = 0

    for i, src in enumerate(prev_sources):
        title = src.get("title", "")
        keywords = [w for w in title.replace("_", " ").split() if len(w) >= 2]
        if not keywords:
            continue
        match_count = sum(1 for kw in keywords if kw in rewritten)
        threshold = max(len(keywords) // 2, 1)
        if match_count >= threshold and match_count > best_score:
            best_score = match_count
            best_idx = i

    if best_idx is not None:
        doc_id = prev_sources[best_idx].get("document_id")
        return best_idx, doc_id
    return None, None
