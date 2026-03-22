"""문서 요약"""
import time
from typing import Any, Dict

from ai.agents.document._common import (
    _call_llm,
    _retrieve_context,
    truncate_by_paragraph,
)


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


async def _handle_doc_summary(user_input: str, document_content: str = None, document_id: int = None, user_id: int = None, user_team: str = None, stream_mode: bool = False, chat_history: list = None) -> Dict[str, Any]:
    """문서 요약 처리 — DB 저장된 요약 우선, 없으면 sLLM 호출"""
    _t = time.time()
    print(f"[DocumentAgent] _handle_doc_summary | document_id={document_id}, content_len={len(document_content) if document_content else 0}, stream_mode={stream_mode}")

    # 문서 내용이 없으면 RAG로 문서 식별 시도, 실패 시 doc_pick
    if not document_content:
        print("[DocumentAgent] document_content 없음 → RAG로 문서 식별 시도")

        search_results, _, _ = await _retrieve_context(user_input, user_id, user_team, top_k=5)

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
                    from sqlalchemy import select
                    from app.db.session import AsyncSessionLocal
                    from app.models.document import Document

                    async with AsyncSessionLocal() as db:
                        result = await db.execute(select(Document).where(Document.id == matched_id))
                        doc = result.scalar_one_or_none()
                        if doc and doc.content:
                            document_content = doc.content
                            document_id = matched_id
                            print(f"[DocumentAgent] DB content 확보: {len(document_content)}자")
                except Exception as e:
                    print(f"[DocumentAgent] DB content 조회 실패: {e}")

            elif len(unique_docs) > 1:
                print(f"[DocumentAgent] RAG {len(unique_docs)}개 매칭 → 선택지 제공")
                return {
                    "type": "doc_pick",
                    "message": "요약할 문서를 선택해주세요:",
                    "documents": unique_docs,
                }

        # RAG로도 못 찾으면 전체 목록 제공 (기존 fallback)
        if not document_content:
            print("[DocumentAgent] RAG 식별 실패 → 전체 문서 목록 조회")
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
                "message": "요약할 문서를 선택해주세요:",
                "documents": doc_list,
            }

    # ── DB에 이미 요약이 있으면 바로 반환 (sLLM 호출 스킵) ──
    if document_id:
        try:
            from sqlalchemy import select
            from app.db.session import AsyncSessionLocal
            from app.models.document import Document

            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Document).where(Document.id == document_id))
                doc = result.scalar_one_or_none()
                if doc and doc.summary and doc.tags:
                    # 새 형식 체크: tags가 있으면 새 형식으로 간주
                    tags = doc.tags or []
                    tags_str = " ".join(f"#{t}" for t in tags)
                    answer = f"태그: {tags_str}\n요약: {doc.summary}"
                    print(f"[DocumentAgent] DB 요약 사용 (document_id={document_id}, {time.time()-_t:.2f}s)")
                    return {
                        "type": "doc_retrieve",
                        "sub_type": "summary",
                        "answer": answer,
                        "message": answer,
                        "tags": tags,
                        "summary": doc.summary,
                        "document_id": document_id,
                    }
                elif doc and doc.summary and not doc.tags:
                    # 구 형식: summary만 있고 tags 없음 → sLLM 재호출로 넘어감
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
                "max_tokens": 1024,
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

    # 비스트리밍: sLLM 직접 호출
    print("[DocumentAgent] stream_mode=False → sLLM 직접 호출 (doc_summary)")
    answer = await _call_llm(sys_prompt, user_prompt, task="summary")
    parsed = parse_summary_output(answer)
    print(f"[DocumentAgent] sLLM 응답 | tags={parsed['tags']}, summary_len={len(parsed['summary'])}자")

    # DB에 요약 결과 업데이트 (구 형식 갱신 또는 신규 저장)
    if document_id and parsed["tags"]:
        try:
            from sqlalchemy import select
            from app.db.session import AsyncSessionLocal
            from app.models.document import Document

            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Document).where(Document.id == document_id))
                doc = result.scalar_one_or_none()
                if doc:
                    doc.summary = parsed["summary"]
                    doc.tags = parsed["tags"]
                    await db.commit()
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
