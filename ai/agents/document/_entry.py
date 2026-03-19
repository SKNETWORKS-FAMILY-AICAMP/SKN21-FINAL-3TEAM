"""document_agent() 메인 라우터"""
import re
import time
from typing import Any, Dict

from ai.agents.state import AgentState
from ai.agents.document._common import get_last_model_name
from ai.agents.document._generate import (
    _handle_doc_generate,
    _llm_detect_template_type,
)
from ai.agents.document._search import _handle_doc_search, _is_pure_search
from ai.agents.document._qa import _handle_doc_qa
from ai.agents.document._summary import _handle_doc_summary
from ai.agents.document._risk import _handle_risk_detect


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

    _t_agent = time.time()
    print(f"[DocumentAgent] 진입 | intent={intent}, user_input='{user_input[:50]}...', user_id={user_id}, user_team={user_team}")

    response_data = {}

    stream_mode = state.get("stream_mode", False)
    print(f"[DocumentAgent] stream_mode={stream_mode}, context 길이={len(context)}")

    try:
        if intent == "doc_retrieve":
            # doc_retrieve 통합 파이프라인: SUMMARY → SEARCH → QA(fallback)
            document_content = state.get("document_content") or state.get("extracted_text")
            document_id = state.get("document_id")

            # 1) 요약 판별: 문서 내용/ID 있거나, 요약 키워드 + 동사어미
            _is_summary = bool(
                document_content
                or document_id
                or re.search(r"(요약|정리|핵심|간추리|간추려|줄여).{0,6}(해|해줘|해주세요|부탁|하자|할래|줘|주세요)", user_input)
                or re.search(r"(요약|정리|핵심|간추리|간추려|줄여)\s*$", user_input)
            )

            if _is_summary:
                print("[DocumentAgent] doc_retrieve → summary 경로")
                response_data = await _handle_doc_summary(
                    user_input,
                    document_content=document_content,
                    document_id=document_id,
                    user_id=user_id,
                    user_team=user_team,
                    stream_mode=stream_mode,
                )
            elif _is_pure_search(user_input):
                # 2) 명시적 검색: 찾아/검색/목록 키워드 + 설명/요약 요청 없음
                print("[DocumentAgent] doc_retrieve → search 경로")
                response_data = await _handle_doc_search(user_input, context, user_id, user_team=user_team, stream_mode=stream_mode)
            else:
                # 3) fallback → QA (질문형 + 기타 전부)
                print("[DocumentAgent] doc_retrieve → QA 경로")
                response_data = await _handle_doc_qa(user_input, context, user_id=user_id, user_team=user_team, stream_mode=stream_mode)

        elif intent == "doc_search":
            # 레거시 호환: BERT가 doc_search로 분류한 경우
            print("[DocumentAgent] → _handle_doc_search 호출 (legacy)")
            response_data = await _handle_doc_search(user_input, context, user_id, user_team=user_team, stream_mode=stream_mode)

        elif intent == "doc_generate":
            # template_type 결정: ① state에서 프론트가 보낸 값 ② LLM 판단 ③ 키워드 fallback
            document_content = state.get("document_content") or state.get("extracted_text")
            template_type = state.get("template_type") or await _llm_detect_template_type(user_input)
            template_id = state.get("template_id")  # 커스텀 양식 ID (DB)
            print(f"[DocumentAgent] → _handle_doc_generate 호출 | template={template_type}, template_id={template_id}")
            response_data = await _handle_doc_generate(user_input, template_type, document_content, template_id=template_id)

        elif intent == "doc_summary":
            # 레거시 호환: BERT가 doc_summary로 분류한 경우
            print("[DocumentAgent] → _handle_doc_summary 호출 (legacy)")
            document_content = state.get("document_content") or state.get("extracted_text")
            document_id = state.get("document_id")
            response_data = await _handle_doc_summary(
                user_input,
                document_content=document_content,
                document_id=document_id,
                user_id=user_id,
                user_team=user_team,
                stream_mode=stream_mode,
            )

        elif intent == "risk_detect":
             print("[DocumentAgent] → _handle_risk_detect 호출")
             response_data = _handle_risk_detect(user_input)

        else:
            print(f"[DocumentAgent] !!! 지원하지 않는 intent: {intent}")
            response_data = {"error": f"지원하지 않는 intent입니다: {intent}"}

    except Exception as e:
        print(f"[DocumentAgent] !!! 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        response_data = {"error": str(e)}

    print(f"[DocumentAgent] 완료 ({time.time()-_t_agent:.2f}s) | response type={response_data.get('type')}, keys={list(response_data.keys())}")

    # ── 규정 검증 파이프라인 (Document + Judgment Agent 결합) ──
    # doc_generate: 생성된 문서를 판단 agent가 규정 검증
    # doc_retrieve (비스트리밍): 검색/요약 결과에 규정 연결
    if response_data.get("type") == "doc_generate" and response_data.get("data"):
        try:
            from ai.agents.regulation_validator import (
                validate_document_regulations,
                append_regulation_section_to_docx,
            )
            _t_reg = time.time()
            print("[DocumentAgent] 규정 검증 파이프라인 시작")

            reg_result = await validate_document_regulations(
                response_data["data"],
                response_data.get("template_type", ""),
                user_id=user_id,
            )

            if reg_result.get("notes"):
                # 응답에 규정 검증 결과 포함
                response_data["regulation_check"] = reg_result

                # 프리뷰에 규정 검증 결과 추가
                if reg_result.get("summary"):
                    response_data["preview"] = (
                        response_data.get("preview", "") + reg_result["summary"]
                    )

                # DOCX에 규정 검증 섹션 추가
                docx_path = response_data.get("docx_path")
                if docx_path:
                    append_regulation_section_to_docx(docx_path, reg_result["notes"])

                print(
                    f"[DocumentAgent] 규정 검증 완료 ({time.time()-_t_reg:.2f}s) | "
                    f"{len(reg_result['notes'])}건, "
                    f"violations={reg_result['has_violations']}, "
                    f"conditions={reg_result['has_conditions']}"
                )
            else:
                print(f"[DocumentAgent] 규정 검증 완료 ({time.time()-_t_reg:.2f}s) | 관련 규정 없음")

        except Exception as e:
            print(f"[DocumentAgent] 규정 검증 실패 (비차단): {e}")
            import traceback
            traceback.print_exc()

    elif (
        response_data.get("type") == "doc_retrieve"
        and response_data.get("sub_type") in ("qa", "summary")
        and not stream_mode
    ):
        # 비스트리밍 doc_retrieve: 검색/요약 결과에 규정 연결
        answer_text = response_data.get("answer", "") or response_data.get("message", "")
        if answer_text and len(answer_text) > 50:
            try:
                from ai.agents.regulation_validator import check_content_regulations
                _t_reg = time.time()
                print("[DocumentAgent] 컨텐츠 규정 연결 시작")

                reg_result = await check_content_regulations(answer_text, user_id=user_id)

                if reg_result.get("notes"):
                    response_data["regulation_check"] = reg_result
                    reg_summary = reg_result["summary"]
                    response_data["message"] = response_data.get("message", "") + reg_summary
                    response_data["answer"] = response_data.get("answer", "") + reg_summary
                    print(
                        f"[DocumentAgent] 컨텐츠 규정 연결 완료 ({time.time()-_t_reg:.2f}s) | "
                        f"{len(reg_result['notes'])}건"
                    )
                else:
                    print(f"[DocumentAgent] 컨텐츠 규정 연결 완료 ({time.time()-_t_reg:.2f}s) | 관련 규정 없음")

            except Exception as e:
                print(f"[DocumentAgent] 컨텐츠 규정 연결 실패 (비차단): {e}")

    # 모델명 추가 (프론트에서 표시용)
    response_data["model_name"] = get_last_model_name()

    # State 업데이트
    state["agent_response"] = response_data
    return state
