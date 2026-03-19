"""문서 검색"""
import re
import time
from typing import Any, Dict, List

from ai.agents.document._common import _retrieve_context


def _detect_search_intent(query: str) -> str:
    """사용자 질문에서 검색 의도 감지

    Args:
        query: 사용자 질문

    Returns:
        "summarize" | "find" | "explain"
    """
    query_lower = query.lower()

    # 요약 키워드 (최우선) — 동사어미 확인으로 오탐 방지
    # "정리된 자료 찾아줘" → find, "정리해줘" → summarize
    if re.search(r"(요약|정리|핵심|간추리|간추려|줄여)\s*(해|해줘|해주세요|부탁|하자|할래|줘|주세요)", query_lower):
        return "summarize"
    if re.search(r"간단히|짧게", query_lower):
        return "summarize"

    # 찾기 키워드
    if re.search(r"찾아|검색|문서|어디|목록", query_lower):
        return "find"

    # 기본값: 설명
    return "explain"


def _is_pure_search(query: str) -> bool:
    """순수 검색 요청인지 판별 (찾아/검색/목록 키워드 있고, 설명/요약 요청 없음)

    "보고서 찾아줘" → True (순수 검색)
    "보고서 찾아서 정리해줘" → False (복합 → QA로 넘김)
    "출장비 규정 알려줘" → False (QA)
    """
    has_search = bool(re.search(r"(찾아|검색|목록|있어\s*\?|있나요|어디|어떤\s*문서)", query))
    has_explain = bool(re.search(r"(정리|설명|알려|요약|비교|분석)", query))
    return has_search and not has_explain


async def _handle_doc_search(query: str, context: List[str], user_id: int = None, user_team: str = None, stream_mode: bool = False) -> Dict[str, Any]:
    """문서 검색 — RAG 결과를 카드형으로 반환 (LLM 호출 없음)"""
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_search | query='{query[:50]}', stream_mode={stream_mode}")

    # 1. 공통 RAG 검색
    search_results, context, sources = await _retrieve_context(query, user_id, user_team, top_k=7)

    # 2. 검색 실패
    if not sources:
        print("[DocumentAgent] search: 관련 문서 없음")
        return {
            "type": "doc_retrieve",
            "sub_type": "search",
            "answer": "관련 문서를 찾지 못했습니다. 다른 키워드로 검색해보세요.",
            "message": "관련 문서를 찾지 못했습니다. 다른 키워드로 검색해보세요.",
            "sources": [],
            "context": [],
            "total_found": 0,
        }

    # 3. document_id 기준 중복 제거 (같은 문서의 여러 chunk)
    seen_doc_ids = set()
    unique_sources = []
    for s in sources:
        did = s.get("document_id")
        if did and did in seen_doc_ids:
            continue
        if did:
            seen_doc_ids.add(did)
        unique_sources.append(s)

    # 4. LLM 없이 검색 결과 메시지 구성
    n = len(unique_sources)
    lines = [f"**{n}건**의 관련 문서를 찾았습니다:\n"]
    for i, s in enumerate(unique_sources, 1):
        title = s.get("title", "제목 없음")
        preview = s.get("content", "")[:80].replace("\n", " ")
        score = s.get("score", 0)
        lines.append(f"{i}. **{title}** (관련도 {score:.0%})\n   {preview}...")
    message = "\n".join(lines)

    print(f"[DocumentAgent] search 완료 ({time.time()-_t:.2f}s): {n}건 (LLM 미사용)")
    return {
        "type": "doc_retrieve",
        "sub_type": "search",
        "answer": message,
        "message": message,
        "sources": unique_sources,
        "context": context,
        "total_found": n,
    }
