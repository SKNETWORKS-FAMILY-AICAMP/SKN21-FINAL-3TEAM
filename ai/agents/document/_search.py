"""문서 검색"""
import re
import time
from typing import Any, Dict, List

from ai.agents.document._common import _retrieve_context


def _is_pure_search(query: str) -> bool:
    """순수 검색 요청인지 판별 (찾아/검색/목록 키워드 있고, 설명/요약 요청 없음)

    "보고서 찾아줘" → True (순수 검색)
    "보고서 찾아서 정리해줘" → False (복합 → QA로 넘김)
    "출장비 규정 알려줘" → False (QA)
    """
    has_search = bool(re.search(r"(찾아|검색|목록|있어\s*\?|있나요|어디|어떤\s*문서)", query))
    has_explain = bool(re.search(r"(정리|설명|알려|요약|비교|분석)", query))
    return has_search and not has_explain


async def _handle_doc_search(query: str, context: List[str], user_id: int = None, user_team: str = None, **_kwargs) -> Dict[str, Any]:
    """문서 검색 — RAG 결과를 카드형으로 반환 (LLM 호출 없음, 스트리밍 불필요)"""
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_search | query='{query[:50]}'")

    # 1. 공통 RAG 검색 (reranker 비활성화 — EC2 메모리 부족)
    search_results, context, sources, rag_status = await _retrieve_context(
        query, user_id, user_team,
        top_k=10, use_reranker=False, score_threshold=0.1,
    )

    # 2. 검색 실패 — 타임아웃과 결과 없음 구분
    if not sources:
        if rag_status == "timeout":
            msg = "문서 검색이 시간 초과되었습니다. 더 구체적인 키워드로 다시 시도해주세요."
        elif rag_status == "error":
            msg = "문서 검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        else:
            msg = "관련 문서를 찾지 못했습니다. 다른 키워드로 검색해보세요."
        print(f"[DocumentAgent] search: {rag_status}")
        return {
            "type": "doc_retrieve",
            "sub_type": "search",
            "answer": msg,
            "message": msg,
            "sources": [],
            "context": [],
            "total_found": 0,
            "rag_status": rag_status,
        }

    # 3. 중복 제거 (document_id 우선, 없으면 title 기준)
    seen_doc_ids = set()
    seen_titles = set()
    unique_sources = []
    for s in sources:
        did = s.get("document_id")
        title = s.get("title", "")
        if did:
            if did in seen_doc_ids:
                continue
            seen_doc_ids.add(did)
        elif title:
            if title in seen_titles:
                continue
            seen_titles.add(title)
        unique_sources.append(s)

    # 4. LLM 없이 검색 결과 메시지 구성
    n = len(unique_sources)
    lines = [f"'{query}' 키워드로 문서 제목+내용을 검색한 결과, **{n}건**의 관련 문서를 찾았습니다:\n"]
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
        "total_found": n,
        "search_info": {
            "query_used": query,
            "method": "BM25+Vector (Hybrid)",
            "reranker": False,
            "threshold": 0.1,
        },
    }
