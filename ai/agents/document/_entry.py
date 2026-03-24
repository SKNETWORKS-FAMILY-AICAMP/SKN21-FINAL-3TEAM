"""document_agent() 메인 라우터"""
import logging
import re
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

from ai.agents.state import AgentState
from ai.agents.document._common import get_last_model_name
from ai.agents.document._generate import (
    _handle_doc_generate,
    _llm_detect_template_type,
)
from ai.agents.document._search import _handle_doc_search, _needs_llm_answer
from ai.agents.document._qa import _handle_doc_qa
from ai.agents.document._summary import _handle_doc_summary
# from ai.agents.document._risk import _handle_risk_detect  # 비활성화 (2026-03-22)


async def document_agent(state: AgentState) -> AgentState:
    """
    문서 Agent 노드 함수 (LangGraph 노드 인터페이스)

    intent에 따라 분기:
      - doc_retrieve: 문서 검색/조회/요약/QA (내부적으로 search vs summary 판단)
      - doc_generate: 문서 생성 (보고서/회의록/JD/제안서)
    """
    intent = state.get("intent", "").lower()
    user_input = state.get("user_input", "")
    context = state.get("context", [])
    user_id = state.get("user_id")
    user_team = state.get("user_team")

    chat_history = state.get("chat_history", [])

    _t_agent = time.time()
    print(f"[DocumentAgent] 진입 | intent={intent}, user_input='{user_input[:50]}...', user_id={user_id}, user_team={user_team}")

    response_data = {}
    _sub_type_hint = None

    stream_mode = state.get("stream_mode", False)
    print(f"[DocumentAgent] stream_mode={stream_mode}, context 길이={len(context)}")

    try:
        if intent == "doc_retrieve":
            # doc_retrieve 통합 파이프라인: SUMMARY → SEARCH → QA(fallback)
            document_content = state.get("document_content") or state.get("extracted_text")
            document_id = state.get("document_id")

            # force_sub_type: 후속 액션 버튼에서 강제 지정 → regex 스킵
            force_sub_type = state.get("force_sub_type")

            # sub_type 힌트를 state에 저장 → chat.py에서 조기 상태 알림용
            _sub_type_hint = force_sub_type or None

            if force_sub_type:
                print(f"[DocumentAgent] force_sub_type={force_sub_type} → regex 스킵")
                if force_sub_type == "summary":
                    response_data = await _handle_doc_summary(
                        user_input, document_content=document_content,
                        document_id=document_id, user_id=user_id,
                        user_team=user_team, stream_mode=stream_mode,
                        chat_history=chat_history,
                    )
                elif force_sub_type == "search":
                    response_data = await _handle_doc_search(user_input, context, user_id, user_team=user_team, stream_mode=stream_mode)
                else:  # "qa" 또는 기타
                    response_data = await _handle_doc_qa(
                        user_input, context, user_id=user_id,
                        user_team=user_team, stream_mode=stream_mode,
                        chat_history=chat_history,
                        document_content=document_content,
                    )
            else:
                # ── regex + RAG 점수 혼합 라우팅 ──
                # 1) 요약 판별: 문서 내용/ID 있거나, 요약 키워드 + 동사어미
                _is_summary = bool(
                    document_content
                    or document_id
                    or re.search(r"(요약|정리|핵심|간추리|간추려|줄여).{0,6}(해|해줘|해주세요|부탁|하자|할래|줘|주세요)", user_input)
                    or re.search(r"(요약|정리|핵심|간추리|간추려|줄여)\s*$", user_input)
                )

                if _is_summary:
                    _sub_type_hint = "summary"
                    print("[DocumentAgent] doc_retrieve → summary 경로")
                    response_data = await _handle_doc_summary(
                        user_input,
                        document_content=document_content,
                        document_id=document_id,
                        user_id=user_id,
                        user_team=user_team,
                        stream_mode=stream_mode,
                        chat_history=chat_history,
                    )
                else:
                    # 2) 항상 RAG 검색 먼저 (search/QA 공통)
                    from ai.agents.document._common import _retrieve_context
                    search_results, rag_context, sources, rag_status = await _retrieve_context(
                        user_input, user_id, user_team,
                        top_k=10, use_reranker=False, score_threshold=0.1,
                    )
                    top_score = max((r.get("score", 0) for r in search_results), default=0) if search_results else 0
                    print(f"[DocumentAgent] RAG 선검색 완료: {len(sources)}건, top_score={top_score:.2f}")

                    # 3) QA 판별: 의문형 패턴 + RAG 점수 충분할 때만 QA
                    is_qa_query = _needs_llm_answer(user_input)
                    if is_qa_query and top_score > 0.5:
                        _sub_type_hint = "qa"
                        print(f"[DocumentAgent] doc_retrieve → QA 경로 (의문형 + score={top_score:.2f})")
                        response_data = await _handle_doc_qa(
                            user_input, rag_context, user_id=user_id,
                            user_team=user_team, stream_mode=stream_mode,
                            chat_history=chat_history,
                            document_content=document_content,
                            pre_sources=sources,
                            pre_top_score=top_score,
                        )
                    else:
                        # 4) 기본값: search (빠른 검색 카드 반환)
                        _sub_type_hint = "search"
                        reason = "기본값" if not is_qa_query else f"score 부족({top_score:.2f})"
                        print(f"[DocumentAgent] doc_retrieve → search 경로 ({reason})")
                        response_data = await _handle_doc_search(
                            user_input, rag_context, user_id, user_team=user_team,
                            pre_fetched=(search_results, rag_context, sources, rag_status),
                        )

        elif intent == "doc_generate":
            _sub_type_hint = "generate"
            document_content = state.get("document_content") or state.get("extracted_text")
            template_id = state.get("template_id")
            # template_type 결정: ① state에서 프론트 전달 ② template_id로 DB 조회 ③ regex fallback
            from ai.agents.document._generate import _detect_template_type, _get_template_info
            template_type = state.get("template_type")
            if not template_type and template_id:
                # 프론트에서 template_type 안 왔지만 template_id는 있음 → DB에서 category 조회
                tpl_info = await _get_template_info(template_id)
                if tpl_info:
                    template_type = tpl_info.get("category") or _detect_template_type(user_input)
                    print(f"[DocumentAgent] template_type DB 보정: {template_type}")
            if not template_type:
                template_type = _detect_template_type(user_input)
            print(f"[DocumentAgent] → _handle_doc_generate 호출 | template={template_type}, template_id={template_id}, stream_mode={stream_mode}")
            response_data = await _handle_doc_generate(user_input, template_type, document_content, template_id=template_id, stream_mode=stream_mode)

        elif intent == "risk_detect":
            # NOTE: 비활성화 (2026-03-22) — 핸들러 미완성, 향후 별도 구현 예정
            print("[DocumentAgent] risk_detect 요청 → 현재 비활성화")
            response_data = {
                "type": "doc_retrieve",
                "message": "규정 위험 분석 기능은 현재 준비 중입니다.",
            }

        else:
            print(f"[DocumentAgent] !!! 지원하지 않는 intent: {intent}")
            response_data = {"error": f"지원하지 않는 intent입니다: {intent}"}

    except Exception as e:
        print(f"[DocumentAgent] !!! 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        response_data = {
            "type": "doc_retrieve",
            "message": "문서 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            "error": str(e),
        }

    print(f"[DocumentAgent] 완료 ({time.time()-_t_agent:.2f}s) | response type={response_data.get('type')}, keys={list(response_data.keys())}")

    # sub_type 힌트 (chat.py에서 조기 상태 메시지 전송용)
    _hint = _sub_type_hint or response_data.get("sub_type")
    if _hint:
        response_data["_status_hint"] = _hint

    # NOTE: follow_up_actions는 프론트엔드(ChatPage.jsx)에서 하드코딩으로 구현 완료
    # 백엔드에서 중복 전송하지 않음

    # 규정 검증 활성화: 문서 생성 시 규정 위반 여부 체크
    if response_data.get("sub_type") in ("generate", "qa", "summary"):
        try:
            from ai.agents.regulation_validator import validate_document_regulations
            reg_result = await validate_document_regulations(
                response_data, response_data.get("template_type", "report"), user_id=state.get("user_id"),
            )
            if reg_result.get("notes"):
                response_data["regulation_check"] = reg_result
                response_data["warnings"] = []
                if reg_result.get("has_violations"):
                    response_data["warnings"].append("규정 위반 사항이 발견되었습니다.")
                if reg_result.get("has_conditions"):
                    response_data["warnings"].append("조건부 허용 사항이 있습니다.")
        except Exception as e:
            logger.warning("[DocumentEntry] 규정 검증 실패 (비차단): %s", e)

    # 모델명 추가 (프론트에서 표시용)
    if response_data.get("sub_type") == "search":
        response_data["model_name"] = "RAG (BM25+Vector)"
    elif response_data.get("stream_pending"):
        # stream_pending=True면 chat.py에서 LLM 호출 → 거기서 모델명 설정
        response_data["model_name"] = response_data.get("model_name", "streaming")
    else:
        response_data["model_name"] = get_last_model_name()

    # State 업데이트
    state["agent_response"] = response_data
    return state
