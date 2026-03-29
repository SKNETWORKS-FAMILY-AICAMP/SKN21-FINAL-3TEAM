"""문서 QA (질의응답)"""
import time
from typing import Any, Dict

from ai.agents.document._common import (
    _call_llm,
    _retrieve_context,
    _format_chat_context,
    filter_and_build_citations,
    truncate_by_paragraph,
)


async def _handle_doc_qa(
    query: str,
    context: list = None,
    user_id: int = None,
    user_team: str = None,
    stream_mode: bool = False,
    chat_history: list = None,
    document_content: str = None,
    pre_sources: list = None,
    pre_top_score: float = None,
) -> Dict[str, Any]:
    """문서 내용 기반 질의응답

    Args:
        query: 사용자 질문
        context: 미리 채워진 RAG context (있으면 RAG 스킵)
        user_id: 사용자 ID
        user_team: 사용자 소속 팀
        stream_mode: 스트리밍 모드 (True → StreamRequest 반환)
        chat_history: 이전 대화 이력 (멀티턴)
        document_content: 특정 문서 내용 (있으면 RAG 스킵)
        pre_sources: _entry.py에서 이미 검색한 sources (인용 표시용)
        pre_top_score: _entry.py에서 이미 계산한 RAG 최고 점수
    """
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_qa | query='{query[:50]}', "
          f"context_len={len(context) if context else 0}, "
          f"doc_content={'Y' if document_content else 'N'}, "
          f"stream_mode={stream_mode}")

    sources = pre_sources or []
    rag_top_score = pre_top_score if pre_top_score is not None else 0.0

    # ── 1. context 확보 (RAG 중복 호출 방지) ──
    if document_content:
        # 특정 문서가 선택된 경우 → 해당 문서만 context로 사용
        # vLLM max_model_len=8192 제약: sys(200)+history(300)+question(50)+max_tokens(2048)=2600
        # → context 가용 ≈ 5500토큰 ≈ 4000자
        context = [f"[선택된 문서]\n{truncate_by_paragraph(document_content, max_chars=4000)}"]
        rag_top_score = 1.0  # 사용자가 직접 선택 → 최대 신뢰도
        print("[DocumentAgent] document_content 사용 (RAG 스킵)")
    elif context:
        # 이미 context가 있으면 그대로 사용 (pre_sources/pre_top_score도 활용)
        print(f"[DocumentAgent] 기존 context 사용 ({len(context)}개), sources={len(sources)}개")
    else:
        # 둘 다 없으면 RAG 검색
        search_results, rag_context, rag_sources, _rag_status = await _retrieve_context(
            query, user_id, user_team,
            top_k=5, use_reranker=True, use_hyde=False,
        )
        context = rag_context
        sources = rag_sources
        if search_results:
            rag_top_score = max(r.get("score", 0) for r in search_results)

    # ── 2. context 없으면 실패 ──
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
            "model_name": "RAG (검색 결과 없음)",
        }

    # ── 3. user_prompt 구성 (컨텍스트 크기 가드) ──
    # RunPod vLLM max_model_len=8192
    # 시스템프롬프트(~200) + 대화이력(~300) + 질문(~50) + max_tokens(2048) = ~2600
    # → context에 쓸 수 있는 토큰 ≈ 5500 → 한국어 ~5000자
    MAX_CONTEXT_CHARS = 5000

    parts = []

    # 이전 대화 컨텍스트
    chat_ctx = _format_chat_context(chat_history)
    if chat_ctx:
        parts.append(chat_ctx)

    # 참고 문서 — 크기 제한 적용 (높은 점수 chunk 우선)
    parts.append("[참고 문서]")
    total_ctx_len = 0
    for c in context:
        if total_ctx_len + len(c) > MAX_CONTEXT_CHARS:
            print(f"[DocumentAgent] QA context 상한 도달 ({total_ctx_len}자), 이후 chunk 생략")
            break
        parts.append(c)
        total_ctx_len += len(c)

    # 질문
    parts.append(f"\n[질문]\n{query}")

    user_prompt = "\n\n".join(parts)

    # ── 4. stream_mode 분기 ──
    if stream_mode:
        from ai.llm.prompts import DOC_QA_STREAMING_PROMPT

        print(f"[DocumentAgent] stream_mode=True → StreamRequest 반환 ({time.time()-_t:.2f}s)")
        return {
            "type": "doc_retrieve",
            "sub_type": "qa",
            "stream_pending": True,
            "llm_config": {
                "sys_prompt": DOC_QA_STREAMING_PROMPT,
                "user_prompt": user_prompt,
                "temperature": 0.1,
                "max_tokens": 2048,
                "task": "qa",
            },
            "post_stream": {
                "update_summary_db": None,
                # "check_regulation": True,  # 시연용 비활성화
                "filter_sources": False,  # RAG가 찾은 전체 소스 표시
            },
            "answer": "",
            "message": "",
            "sources": sources,
            "confidence": round(rag_top_score, 2),
        }

    # ── 5. 비스트리밍: sLLM 직접 호출 (스트리밍과 동일 프롬프트) ──
    from ai.llm.prompts import DOC_QA_STREAMING_PROMPT

    print("[DocumentAgent] stream_mode=False → sLLM 직접 호출 (doc_qa, 자연어)")
    answer_text = await _call_llm(
        DOC_QA_STREAMING_PROMPT, user_prompt,
        task="qa",
    )

    # [참고:] 파싱 + sources 필터링
    clean_answer, filtered_sources, _ = filter_and_build_citations(sources, answer_text)

    confidence = round(rag_top_score, 2)

    print(f"[DocumentAgent] QA 완료 ({time.time()-_t:.2f}s) | "
          f"answer_len={len(clean_answer)}, sources={len(filtered_sources)}")

    return {
        "type": "doc_retrieve",
        "sub_type": "qa",
        "answer": clean_answer,
        "message": clean_answer,
        "confidence": confidence,
        "sources": filtered_sources,
    }
