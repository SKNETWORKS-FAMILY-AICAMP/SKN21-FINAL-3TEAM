"""문서 QA (질의응답)"""
import json
import time
from typing import Any, Dict

from ai.agents.document._common import _call_llm, _retrieve_context


async def _handle_doc_qa(query: str, context: list = None, user_id: int = None, user_team: str = None, stream_mode: bool = False) -> Dict[str, Any]:
    """문서 내용 기반 질의응답"""
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_qa | query='{query[:50]}', context_len={len(context) if context else 0}, stream_mode={stream_mode}")

    # 공통 RAG 검색 (context가 미리 채워진 경우에도 sources 확보를 위해 검색)
    search_results, rag_context, sources = await _retrieve_context(query, user_id, user_team, top_k=7)
    if not context:
        context = rag_context

    # Context가 없으면 실패
    if not context:
        print("[DocumentAgent] context 비어있음 → 관련 문서 없음 응답")
        return {
            "type": "doc_retrieve",
            "sub_type": "qa",
            "answer": "관련 문서를 찾지 못했습니다. 다른 질문을 시도해보세요.",
            "message": "관련 문서를 찾지 못했습니다. 다른 질문을 시도해보세요.",
            "sources": [],
            "citations": [],
            "confidence": 0.0,
        }

    from ai.llm.prompts import DOC_QA_SYSTEM_PROMPT

    # 스트리밍 모드: answer 텍스트만 토큰으로 전송, sources는 result 이벤트로
    if stream_mode:
        # 스트리밍용 프롬프트 (자연어 답변 → sources는 별도 전달)
        sys_prompt = """당신은 기업 문서 기반 질의응답 전문가입니다.
    주어진 문서 내용을 근거로 사용자의 질문에 정확하게 답변하세요.

    규칙:
    - 반드시 제공된 문서 내용만을 근거로 답변하세요.
    - 답변 근거가 되는 문서를 언급하세요.
    - 문서에서 답을 찾을 수 없으면 솔직히 답하세요.
    - 한국어로 답변하세요."""

        user_prompt = f"Context:\n{json.dumps(context, ensure_ascii=False)}\n\nQuestion: {query}"

        print(f"[DocumentAgent] stream_mode=True → stream_pending 반환 ({time.time()-_t:.2f}s)")
        return {
            "type": "doc_retrieve",
            "sub_type": "qa",
            "stream_pending": True,
            "sys_prompt": sys_prompt,
            "user_prompt": user_prompt,
            "answer": "",
            "message": "",
            "sources": sources,
        }

    # 비스트리밍: JSON mode로 구조화된 응답
    user_prompt = f"Context:\n{json.dumps(context, ensure_ascii=False)}\n\nQuestion: {query}"
    print("[DocumentAgent] stream_mode=False → LLM 직접 호출 (doc_qa, json_mode)")
    answer_json_str = await _call_llm(DOC_QA_SYSTEM_PROMPT, user_prompt, json_mode=True, task="qa")

    try:
        qa_result = json.loads(answer_json_str)
    except json.JSONDecodeError:
        qa_result = {"answer": answer_json_str, "citations": [], "confidence": 0.5}

    return {
        "type": "doc_retrieve",
        "sub_type": "qa",
        "answer": qa_result.get("answer", ""),
        "message": qa_result.get("answer", ""),
        "citations": qa_result.get("citations", []),
        "confidence": qa_result.get("confidence", 0.5),
        "sources": sources,
    }
