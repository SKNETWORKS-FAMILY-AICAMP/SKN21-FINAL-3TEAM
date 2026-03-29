"""문서 검색"""
import re
import time
from typing import Any, Dict, List

from ai.agents.document._common import _retrieve_context


def _needs_llm_answer(query: str) -> bool:
    """QA(LLM 답변)가 필요한 질문인지 판별

    기본값은 search(검색 카드). 명확한 의문형/설명 요청만 QA로 보냄.

    "출장비 정산 절차가 뭐야?" → True  (내용 질문)
    "계약서 비교해줘"          → True  (분석 요청)
    "계약서 찾아줘"            → False (검색)
    "계약서 알려줘"            → False (애매 → 검색이 안전)
    "계약서 내용 자세히 알려줘" → True  (내용 질문)
    "출장 관련 문서"           → False (목록 요청)
    """
    # 의문형: 내용을 물어보는 패턴
    if re.search(r"(뭐야|뭔가요|무엇인|어떻게|어떤\s*방법|왜\s|인가요|인지|절차|방법이|차이|의미|뜻)", query):
        return True
    # "내용/자세히/구체적으로" + "알려줘" → 내용 질문 (단순 "알려줘"는 제외)
    if re.search(r"(내용|자세히|자세하게|구체적|상세).{0,6}(알려|알려줘|알려주세요)", query):
        return True
    # 설명/분석 요청 (단, "찾아서 설명" 같은 복합은 검색 우선)
    if re.search(r"(설명|분석|비교|해석|정리).{0,4}(해|해줘|해주세요|줘|주세요|하자)", query):
        if not re.search(r"(찾아|검색)", query):
            return True
    return False


async def _handle_doc_search(
    query: str, context: List[str], user_id: int = None, user_team: str = None,
    pre_fetched: tuple = None, **_kwargs,
) -> Dict[str, Any]:
    """문서 검색 — RAG 결과를 카드형으로 반환 (LLM 호출 없음, 스트리밍 불필요)

    Args:
        pre_fetched: (search_results, context, sources, rag_status) — _entry.py에서 이미 검색한 경우
    """
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_search | query='{query[:50]}', pre_fetched={'Y' if pre_fetched else 'N'}")

    # 1. 공통 RAG 검색 (pre_fetched 있으면 스킵)
    if pre_fetched:
        search_results, context, sources, rag_status = pre_fetched
    else:
        search_results, context, sources, rag_status = await _retrieve_context(
            query, user_id, user_team,
            top_k=5, use_reranker=False, score_threshold=0.0, use_hyde=True,
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

    # 4. 상위 5건만 반환
    unique_sources = unique_sources[:5]
    n = len(unique_sources)
    message = f"**{n}건**의 관련 문서를 찾았습니다."

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
