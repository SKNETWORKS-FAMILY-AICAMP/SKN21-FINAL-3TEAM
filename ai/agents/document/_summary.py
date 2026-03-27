"""문서 요약"""
import re
import time
from typing import Any, Dict

from sqlalchemy import select as sa_select
from app.db.session import async_session as _AsyncSessionLocal
from app.models.document import Document as _Document

from ai.agents.document._common import (
    _call_llm,
    _retrieve_context,
    truncate_by_paragraph,
)


async def _get_document(document_id: int):
    """DB에서 Document 조회 (단일 세션)"""
    async with _AsyncSessionLocal() as db:
        result = await db.execute(sa_select(_Document).where(_Document.id == document_id))
        return result.scalar_one_or_none()


def _format_cached_summary(doc) -> dict | None:
    """DB에 저장된 요약이 있으면 응답 dict 반환, 없으면 None"""
    if not (doc and doc.summary):
        return None
    tags = doc.tags or []
    tags_str = " ".join(f"#{t}" for t in tags)
    answer = f"태그: {tags_str}\n요약: {doc.summary}"
    return {
        "type": "doc_retrieve",
        "sub_type": "summary",
        "answer": answer,
        "message": answer,
        "tags": tags,
        "summary": doc.summary,
        "document_id": doc.id,
        "model_name": "DB 캐시 (LLM 미사용)",
    }


async def _update_document_summary(document_id: int, summary: str, tags: list):
    """DB에 요약 결과 업데이트"""
    async with _AsyncSessionLocal() as db:
        result = await db.execute(sa_select(_Document).where(_Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.summary = summary
            doc.tags = tags
            await db.commit()
            return True
    return False


def parse_summary_output(text: str) -> dict:
    """
    sLLM 요약 출력을 파싱하여 category, tags, summary를 추출한다.

    입력 형식:
        분류: 회의록
        태그: #태그1 #태그2 #태그3
        요약: 요약문 2~3문장

    Returns:
        {"category": "회의록" | None, "tags": ["태그1", ...], "summary": "요약문", "raw": "원본 텍스트"}
    """
    category = None
    tags = []
    summary = ""

    for line in text.strip().splitlines():
        line = line.strip()
        if line.startswith("분류:"):
            category = line[len("분류:"):].strip()
        elif line.startswith("태그:"):
            tag_part = line[len("태그:"):].strip()
            tags = [t.strip().lstrip("#").strip() for t in tag_part.split("#") if t.strip()]
        elif line.startswith("요약:"):
            summary = line[len("요약:"):].strip()

    # 요약이 여러 줄일 수 있음 (요약: 이후 전체)
    if "요약:" in text:
        summary_part = text.split("요약:", 1)[1].strip()
        summary = summary_part

    # 폴백: 파싱 실패 시 전체 텍스트를 요약으로 사용
    if not summary and text.strip():
        summary = text.strip()
        if not tags:
            tags = ["자동요약"]

    return {"category": category, "tags": tags, "summary": summary, "raw": text}


async def summarize_document(text: str) -> dict:
    """
    공통 문서 요약 함수 (문서 업로드 / 채팅 모두 사용)

    Args:
        text: 파싱된 문서 텍스트

    Returns:
        {"tags": list[str], "summary": str, "raw": str}
    """
    from ai.llm.prompts import DOC_SUMMARY_SLLM_PROMPT

    truncated = truncate_by_paragraph(text, max_chars=10000)
    user_prompt = f"다음 문서를 요약해주세요.\n\n문서 내용:\n{truncated}"

    answer = await _call_llm(DOC_SUMMARY_SLLM_PROMPT, user_prompt, task="summary")
    return parse_summary_output(answer)


async def summarize_and_save(document_id: int, text: str) -> dict:
    """문서 요약 + DB 저장 통합 함수 (업로드/채팅/스트리밍 후처리 공통)

    Returns:
        parse_summary_output 결과 dict
    """
    parsed = await summarize_document(text)
    if document_id and parsed["tags"]:
        try:
            ok = await _update_document_summary(document_id, parsed["summary"], parsed["tags"])
            if ok:
                print(f"[DocumentAgent] summarize_and_save | DB 업데이트 완료 (document_id={document_id})")
        except Exception as e:
            print(f"[DocumentAgent] summarize_and_save | DB 업데이트 실패: {e}")
    return parsed


async def _handle_doc_summary(user_input: str, document_content: str = None, document_id: int = None, user_id: int = None, user_team: str = None, stream_mode: bool = False, chat_history: list = None) -> Dict[str, Any]:
    """문서 요약 처리 — DB 저장된 요약 우선, 없으면 sLLM 호출"""
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_summary | document_id={document_id}, content_len={len(document_content) if document_content else 0}, stream_mode={stream_mode}")

    # 문서 내용이 없으면 문서 식별 시도
    if not document_content:
        # 요약 키워드 + 부가 표현 제거하여 실질적 검색어 추출
        _search_query = re.sub(
            r"(이\s*문서|위\s*문서|문서)?\s*(요약|정리|핵심|간추리|간추려|줄여)\s*(해줘|해주세요|해\s*줘|해\s*주세요|해|부탁|하자|할래|줘|주세요|좀)*",
            "", user_input
        ).strip()
        _search_query = re.sub(r"\s*(있어\??|있나\??|있어요\??|찾아줘?|보여줘?|알려줘?|좀|줘|해줘)\s*", "", _search_query).strip()
        # 남은 공백 정리
        _search_query = re.sub(r"\s+", " ", _search_query).strip()

        if not _search_query:
            # 케이스 1: "문서 요약해줘" — 문서명 미지정 → 전체 목록
            print("[DocumentAgent] 문서명 미지정 → 전체 문서 목록 조회")
            try:
                from ai.rag.qdrant_pipeline import get_qdrant_pipeline
                pipeline = get_qdrant_pipeline()
                doc_list = pipeline.list_documents(source="documents", user_id=user_id)
                print(f"[DocumentAgent] Qdrant 문서 목록 {len(doc_list)}개 조회됨")
            except Exception as e:
                print(f"[DocumentAgent] Qdrant 문서 목록 조회 실패: {e}")
                doc_list = []
            return {
                "type": "doc_pick",
                "message": "어떤 문서를 요약할까요? 아래에서 선택해주세요:",
                "documents": doc_list,
                "model_name": "RAG (문서 목록)",
            }

        # 케이스 2: "ERP 제안서 요약해줘" — 문서명 있음 → 키워드로 RAG 검색
        print(f"[DocumentAgent] 문서 검색어 추출: '{_search_query}' (원본: '{user_input}')")
        search_results, _, _, _rag_status = await _retrieve_context(_search_query, user_id, user_team, top_k=5)

        if search_results:
            # document_id 기준 중복 제거
            seen = set()
            unique_docs = []
            for r in search_results:
                did = r.get("document_id")
                if did and did not in seen:
                    seen.add(did)
                    unique_docs.append({"document_id": did, "title": r.get("title", ""), "score": r.get("score", 0)})

            if len(unique_docs) == 1:
                matched_id = unique_docs[0]["document_id"]
                print(f"[DocumentAgent] RAG 1개 매칭 → document_id={matched_id} 전체 content 조회")
                try:
                    doc = await _get_document(matched_id)
                    if doc and doc.content:
                        document_content = doc.content
                        document_id = matched_id
                        print(f"[DocumentAgent] DB content 확보: {len(document_content)}자")
                        cached = _format_cached_summary(doc)
                        if cached:
                            print(f"[DocumentAgent] DB 요약 사용 (document_id={document_id}, {time.time()-_t:.2f}s)")
                            return cached
                except Exception as e:
                    print(f"[DocumentAgent] DB content 조회 실패: {e}")

            elif len(unique_docs) > 1:
                print(f"[DocumentAgent] RAG {len(unique_docs)}개 매칭 → 선택지 제공")
                return {
                    "type": "doc_pick",
                    "message": f"'{_search_query}' 관련 문서가 {len(unique_docs)}건 있습니다. 요약할 문서를 선택해주세요:",
                    "documents": unique_docs,
                    "model_name": "RAG (문서 식별)",
                }

        # RAG로도 못 찾으면 전체 목록 제공
        if not document_content:
            print(f"[DocumentAgent] '{_search_query}' RAG 식별 실패 → 전체 문서 목록 조회")
            try:
                from ai.rag.qdrant_pipeline import get_qdrant_pipeline
                pipeline = get_qdrant_pipeline()
                doc_list = pipeline.list_documents(source="documents", user_id=user_id)
                print(f"[DocumentAgent] Qdrant 문서 목록 {len(doc_list)}개 조회됨")
            except Exception as e:
                print(f"[DocumentAgent] Qdrant 문서 목록 조회 실패: {e}")
                doc_list = []
            return {
                "type": "doc_pick",
                "message": f"'{_search_query}' 관련 문서를 찾지 못했습니다. 아래에서 선택해주세요:",
                "documents": doc_list,
                "model_name": "RAG (문서 목록)",
            }

    # ── DB에 이미 요약이 있으면 바로 반환 (sLLM 호출 스킵) ──
    if document_id:
        try:
            doc = await _get_document(document_id)
            cached = _format_cached_summary(doc)
            if cached:
                print(f"[DocumentAgent] DB 요약 사용 (document_id={document_id}, {time.time()-_t:.2f}s)")
                return cached
            elif doc and doc.summary and not doc.tags:
                print(f"[DocumentAgent] 구 형식 요약 감지 (tags 없음) → sLLM 재호출")
        except Exception as e:
            print(f"[DocumentAgent] DB 요약 조회 실패, sLLM fallback: {e}")

    # ── DB에 요약 없음 → sLLM 호출 ──
    from ai.llm.prompts import DOC_SUMMARY_SLLM_PROMPT
    sys_prompt = DOC_SUMMARY_SLLM_PROMPT
    truncated = truncate_by_paragraph(document_content, max_chars=10000)
    user_prompt = f"다음 문서를 요약해주세요.\n\n사용자 요청: {user_input}\n\n문서 내용:\n{truncated}"

    # 스트리밍 모드: StreamRequest 프로토콜
    if stream_mode:
        print(f"[DocumentAgent] stream_mode=True → StreamRequest 반환 ({time.time()-_t:.2f}s)")
        return {
            "type": "doc_retrieve",
            "sub_type": "summary",
            "stream_pending": True,
            "llm_config": {
                "sys_prompt": sys_prompt,
                "user_prompt": user_prompt,
                "temperature": 0.1,
                "max_tokens": 2048,
                "task": "summary",
            },
            "post_stream": {
                "update_summary_db": document_id,
                "check_regulation": True,
                "filter_sources": False,
            },
            "answer": "",
            "message": "",
        }

    # 비스트리밍: sLLM 직접 호출 + DB 저장 통합
    print("[DocumentAgent] stream_mode=False → sLLM 직접 호출 (doc_summary)")
    answer = await _call_llm(sys_prompt, user_prompt, task="summary")
    parsed = parse_summary_output(answer)
    print(f"[DocumentAgent] sLLM 응답 | tags={parsed['tags']}, summary_len={len(parsed['summary'])}자")

    # DB에 요약 결과 업데이트
    if document_id and parsed["tags"]:
        try:
            await _update_document_summary(document_id, parsed["summary"], parsed["tags"])
            print(f"[DocumentAgent] DB 요약 업데이트 완료 (document_id={document_id})")
        except Exception as e:
            print(f"[DocumentAgent] DB 요약 업데이트 실패: {e}")

    return {
        "type": "doc_retrieve",
        "sub_type": "summary",
        "answer": answer,
        "message": answer,
        "tags": parsed["tags"],
        "summary": parsed["summary"],
        "document_id": document_id,
    }
