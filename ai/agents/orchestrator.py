"""
LangGraph Agent 오케스트레이터 (팀원 A 담당)

그래프 구조:
  [사용자 입력]
       |
  [decompose_query]  ← 복합 질문 감지 (규칙 기반)
       | (route_after_decompose)
    +-- compound       → compound_pending (chat.py에서 스트리밍 처리)
    +-- single         ↓
  [classify_intent]  ← BERT (→ Solar fallback → 임베딩 fallback)
       | (route_by_intent)
    +-- low_confidence  → clarify_with_candidates (top-3 후보 제시)
    +-- judgment        → judgment_agent
    +-- doc_*           → document_agent
    +-- schedule_*      → schedule_agent
    +-- general         → general_response
       |
  [format_response] → END
"""

import logging
import time

from langgraph.graph import StateGraph, END

from ai.agents.state import AgentState
from ai.agents.intent_classifier import get_classifier, detect_compound_query, _split_compound_text
from ai.agents.config import INTENT_CONFIDENCE_THRESHOLD, ENABLE_COMPLEX_QUERY

logger = logging.getLogger(__name__)

# 컴파일된 그래프 캐시
_compiled_graph = None


# ── 유틸 ──


def _get_settings():
    """config import — FastAPI 실행 시 / 단독 실행 시 모두 대응"""
    from backend.app.config import get_settings
    return get_settings()


# ── Agent 노드 ──


async def general_response_node(state: AgentState) -> AgentState:
    """일반 응답 노드 — LLM API 호출

    stream_mode=True이면 LLM 호출을 건너뛰고 chat.py에서 직접 스트리밍 처리.
    """
    _t = time.time()
    logger.info("[Orchestrator] general_response_node 진입 | stream_mode=%s", state.get('stream_mode'))
    # 스트리밍 모드면 chat.py에서 직접 LLM 스트리밍 처리
    if state.get("stream_mode"):
        state["agent_response"] = {
            "type": "general",
            "message": "",
            "stream_pending": True,
        }
        return state

    # 비스트리밍 모드 (POST /chat/) — vLLM 또는 API fallback
    try:
        import os as _os
        from datetime import date as _date

        from ai.llm.prompts import GENERAL_SYSTEM_PROMPT
        sys_prompt = f"{GENERAL_SYSTEM_PROMPT}\n오늘 날짜: {_date.today().isoformat()}"
        chat_summary = state.get("chat_summary")
        if chat_summary:
            sys_prompt += f"\n\n[이전 대화 요약]\n{chat_summary}"

        messages = [
            {"role": "system", "content": sys_prompt},
            *state.get("chat_history", []),
            {"role": "user", "content": state["user_input"]},
        ]

        # sLLM 우선 → API fallback
        vllm_base = _os.getenv("VLLM_BASE_URL")
        vllm_key = _os.getenv("VLLM_API_KEY", "EMPTY")
        vllm_model = _os.getenv("VLLM_MODEL", "kakaocorp/kanana-1.5-8b-instruct-2505")

        if vllm_base:
            from openai import AsyncOpenAI
            import httpx
            client = AsyncOpenAI(api_key=vllm_key, base_url=vllm_base, timeout=httpx.Timeout(60.0, connect=15.0))
            response = await client.chat.completions.create(
                model=vllm_model, messages=messages, temperature=0.7, max_tokens=1024,
            )
            model_name = vllm_model.split("/")[-1]
        else:
            settings = _get_settings()
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL, messages=messages, temperature=0.7, max_tokens=1024,
            )
            model_name = settings.OPENAI_MODEL

        state["agent_response"] = {
            "type": "general",
            "message": response.choices[0].message.content,
            "model_name": model_name,
        }
    except Exception as e:
        logger.error("General response error: %s", e)
        state["agent_response"] = {
            "type": "general",
            "message": f"응답 생성 중 오류가 발생했습니다: {e}",
        }
        state["error"] = str(e)

    return state


# ── Safe Agent Wrappers (팀원 Agent NotImplementedError 대응) ──


async def safe_judgment_agent(state: AgentState) -> AgentState:
    """판단 Agent 안전 래퍼 (팀원 B)"""
    _t = time.time()
    logger.info("[Orchestrator] safe_judgment_agent 진입 | stream_mode=%s", state.get('stream_mode'))
    try:
        # 스트리밍 모드: RAG 검색 + 프롬프트 빌드 → chat.py에서 직접 스트리밍
        if state.get("stream_mode"):
            from ai.agents.judgment_agent import (
                _build_context_prompt,
                _build_user_prompt,
                _extract_judgment_history,
            )
            from ai.llm.prompts import JUDGMENT_STREAMING_SYSTEM_PROMPT
            from ai.rag.qdrant_pipeline import get_qdrant_pipeline

            user_input = state["user_input"]
            user_id = state.get("user_id")
            chat_history = state.get("chat_history", [])

            # RAG 검색
            _t_rag = time.time()
            logger.debug("[Orchestrator] judgment 스트리밍: RAG 검색 시작 (top_k=10)...")
            pipeline = get_qdrant_pipeline()
            context = pipeline.retrieve(query=user_input, user_id=user_id, top_k=10, filter={"source": "regulations"})
            logger.debug("[Orchestrator] judgment RAG 완료 (%.2fs) | %d개 문서", time.time()-_t_rag, len(context))

            # 프롬프트 빌드
            judgment_history = _extract_judgment_history(chat_history)
            context_text = _build_context_prompt(context)
            user_prompt = _build_user_prompt(
                user_input, context_text, chat_history, judgment_history
            )

            state["context"] = context
            state["agent_response"] = {
                "type": "judgment",
                "message": "",
                "stream_pending": True,
                "sys_prompt": JUDGMENT_STREAMING_SYSTEM_PROMPT,
                "user_prompt": user_prompt,
                "_rag_context": context,
            }
            logger.debug("[Orchestrator] judgment stream_pending 반환 (%.2fs)", time.time()-_t)
            return state

        from ai.agents.judgment_agent import judgment_agent

        result = await judgment_agent(state)
        logger.info("[Orchestrator] safe_judgment_agent 완료 (%.2fs)", time.time()-_t)
        return result
    except NotImplementedError:
        state["agent_response"] = {
            "type": "judgment",
            "message": "판단 Agent는 현재 구현 중입니다. 곧 사용 가능합니다.",
        }
        return state
    except Exception as e:
        logger.error("Judgment agent error: %s", e)
        state["agent_response"] = {
            "type": "judgment",
            "message": f"판단 처리 중 오류가 발생했습니다: {e}",
        }
        state["error"] = str(e)
        return state


async def safe_document_agent(state: AgentState) -> AgentState:
    """문서 Agent 안전 래퍼 (팀원 C)"""
    _t = time.time()
    logger.info("[Orchestrator] safe_document_agent 진입")
    try:
        from ai.agents.document_agent import document_agent

        result = await document_agent(state)
        logger.info("[Orchestrator] safe_document_agent 완료 (%.2fs)", time.time()-_t)
        return result
    except NotImplementedError:
        state["agent_response"] = {
            "type": state.get("intent", "doc_retrieve"),
            "message": "문서 Agent는 현재 구현 중입니다. 곧 사용 가능합니다.",
        }
        return state
    except Exception as e:
        logger.error("Document agent error: %s", e)
        state["agent_response"] = {
            "type": state.get("intent", "doc_retrieve"),
            "message": f"문서 처리 중 오류가 발생했습니다: {e}",
        }
        state["error"] = str(e)
        return state


async def safe_action_agent(state: AgentState) -> AgentState:
    """액션 Agent 안전 래퍼 (파이프라인/결재)"""
    _t = time.time()
    logger.info("[Orchestrator] safe_action_agent 진입 | intent=%s", state.get('intent'))
    try:
        from ai.agents.action_agent import action_agent

        result = await action_agent(state)
        logger.info("[Orchestrator] safe_action_agent 완료 (%.2fs) | response type=%s", time.time()-_t, result.get('agent_response', {}).get('type'))
        return result
    except NotImplementedError:
        state["agent_response"] = {
            "type": state.get("intent", "pipeline_create"),
            "message": "액션 Agent는 현재 구현 중입니다. 곧 사용 가능합니다.",
        }
        return state
    except Exception as e:
        logger.error("Action agent error: %s", e)
        state["agent_response"] = {
            "type": state.get("intent", "pipeline_create"),
            "message": f"액션 처리 중 오류가 발생했습니다: {e}",
        }
        state["error"] = str(e)
        return state


async def safe_schedule_agent(state: AgentState) -> AgentState:
    """일정 Agent 안전 래퍼 (팀원 D)"""
    _t = time.time()
    logger.info("[Orchestrator] safe_schedule_agent 진입")
    try:
        from ai.agents.schedule_agent import schedule_agent

        result = await schedule_agent(state)
        logger.info("[Orchestrator] safe_schedule_agent 완료 (%.2fs) | response type=%s", time.time()-_t, result.get('agent_response', {}).get('type'))
        return result
    except NotImplementedError:
        state["agent_response"] = {
            "type": state.get("intent", "schedule_view"),
            "message": "일정 Agent는 현재 구현 중입니다. 곧 사용 가능합니다.",
        }
        return state
    except Exception as e:
        logger.error("Schedule agent error: %s", e)
        state["agent_response"] = {
            "type": state.get("intent", "schedule_view"),
            "message": f"일정 처리 중 오류가 발생했습니다: {e}",
        }
        state["error"] = str(e)
        return state


# ── 복합 질문 노드 ──

# ── Planner 프롬프트 (Hybrid: 기본 + Few-shot) ──

_PLANNER_BASE_PROMPT = """당신은 업무 자동화 시스템의 Task Planner입니다.
사용자 요청을 분석하여 실행 가능한 단계별 계획을 JSON으로 출력하세요.

## 사용 가능한 intent (6개)
- judgment: 사규/규정 기반 판단 ("~해도 되나요?", "규정 확인", "규정 알려줘", "기준이 어떻게 돼?")
- doc_retrieve: 문서 검색/조회/요약 ("~문서 찾아줘", "~자료 검색", "회의록 조회")
- doc_generate: 문서 생성 ("보고서 만들어줘", "회의록 작성해줘")
- schedule_add: 일정 등록 ("~에 회의 잡아줘", "휴가 등록")
- schedule_view: 일정 조회 ("다음 주 일정 보여줘")
- general: 일반 질문 (위에 해당하지 않는 경우)

## 출력 형식 (반드시 이 JSON 형식만 출력)
{"plan": [{"step_id": 1, "intent": "intent_name", "query": "구체적 요청", "depends_on": []}]}

## 규칙
1. depends_on: 이 단계가 실행되기 전에 완료되어야 하는 step_id 목록
2. depends_on이 비어있으면 즉시 실행 가능
3. 단순 요청은 1단계로 처리
4. 최대 4단계까지만 분해
5. JSON만 출력하고 다른 설명은 하지 마세요"""

_PLANNER_FEWSHOT_PROMPT = _PLANNER_BASE_PROMPT + """

## 예시

사용자: 연차 규정 확인하고 다음 주 금요일에 휴가 등록해줘
{"plan": [{"step_id": 1, "intent": "judgment", "query": "연차 규정 확인", "depends_on": []}, {"step_id": 2, "intent": "schedule_add", "query": "다음 주 금요일에 휴가 등록", "depends_on": [1]}]}

사용자: 지난달 매출 보고서 찾아서 요약하고, 그 내용으로 이번 달 보고서 작성해줘
{"plan": [{"step_id": 1, "intent": "doc_retrieve", "query": "지난달 매출 보고서 검색 및 요약", "depends_on": []}, {"step_id": 2, "intent": "doc_generate", "query": "이번 달 보고서 작성", "depends_on": [1]}]}

사용자: 이번 주 회의 일정 확인하고, 회의록 양식 만들어줘
{"plan": [{"step_id": 1, "intent": "schedule_view", "query": "이번 주 회의 일정 확인", "depends_on": []}, {"step_id": 2, "intent": "doc_generate", "query": "회의록 양식 만들기", "depends_on": [1]}]}"""

# knowledge_query 매핑: planner가 judgment/doc_retrieve를 혼동하는 문제 해결
# 두 intent를 knowledge_query로 통합 → 실제 라우팅은 ONNX 개별 분류로 결정
_KNOWLEDGE_QUERY_INTENTS = {"judgment", "doc_retrieve"}


def _is_complex_input(text: str) -> bool:
    """입력이 복합(complex)인지 판별 — 접속사/동사 개수 기반

    Hybrid 프롬프트 선택에 사용:
      복합 → Few-shot 프롬프트 (예시 포함)
      단순 → 기본 프롬프트
    """
    import re
    connectors = len(re.findall(r"(하고|해서|한 다음|그리고|그런 다음|바탕으로|기반으로|확인하고|찾아서)", text))
    verbs = len(re.findall(r"(해줘|만들어줘|작성해줘|등록해줘|잡아줘|보여줘|알려줘|찾아줘|확인해줘|검색해줘)", text))
    return connectors >= 1 or verbs >= 2


def _get_planner_prompt(user_input: str) -> str:
    """Hybrid 프롬프트 — 단순/복합 자동 선택"""
    if _is_complex_input(user_input):
        logger.debug("[Orchestrator] Hybrid: Few-shot 프롬프트 선택")
        return _PLANNER_FEWSHOT_PROMPT
    logger.debug("[Orchestrator] Hybrid: 기본 프롬프트 선택")
    return _PLANNER_BASE_PROMPT


async def decompose_query(state: AgentState) -> AgentState:
    """복합 질문 분해 — ONNX intent 활용 + planner LoRA or 규칙 기반 쿼리 분리

    classify_intent에서 _is_compound=True로 판단된 후 호출됨.
    ONNX가 이미 intent를 정확히 분류했으므로, 여기서는 쿼리 분리만 담당.
    """
    _t = time.time()
    user_input = state["user_input"]
    compound_intents = state.get("_compound_intents", [])

    import os
    use_planner_sllm = os.getenv("PLANNER_MODE", "rule") == "sllm"

    sub_queries = []

    if use_planner_sllm:
        # planner LoRA로 쿼리 분리 (Hybrid 프롬프트 + knowledge_query 매핑)
        try:
            planner_result = await _planner_sllm_decompose(user_input)
            if planner_result:
                # knowledge_query → ONNX로 실제 intent 해소 (judgment vs doc_retrieve)
                # 그 외 intent(doc_generate, schedule_* 등)도 ONNX로 검증
                classifier = get_classifier()
                for sq in planner_result:
                    part_result = classifier.predict(sq["query"])
                    sq["hint"] = part_result["intent"]
                sub_queries = planner_result
                logger.info(
                    "[Orchestrator] planner sLLM + ONNX (%.2fs) | %d단계: %s",
                    time.time() - _t, len(sub_queries), [sq["hint"] for sq in sub_queries],
                )
        except Exception as e:
            logger.error("[Orchestrator] planner sLLM 실패, 규칙 기반 fallback: %s", e)

    # planner 실패 or rule 모드 → 규칙 기반 분리 + 각 part를 ONNX로 개별 분류
    if not sub_queries:
        classifier = get_classifier()
        parts = _split_compound_text(user_input)
        if parts and len(parts) >= 2:
            for i, part in enumerate(parts):
                part_result = classifier.predict(part)
                sub_queries.append({
                    "query": part,
                    "hint": part_result["intent"],
                    "step_id": i + 1,
                    "depends_on": [i] if i > 0 else [],
                })
        else:
            # 분리 실패 → ONNX intent 순서대로 원문 그대로
            for i, intent_info in enumerate(compound_intents):
                sub_queries.append({
                    "query": user_input,
                    "hint": intent_info["intent"],
                    "step_id": i + 1,
                    "depends_on": [i] if i > 0 else [],
                })

    state["sub_queries"] = sub_queries
    logger.info(
        "[Orchestrator] decompose_query 완료 (%.2fs) | %d개 서브쿼리: %s",
        time.time() - _t, len(sub_queries), [sq["hint"] for sq in sub_queries],
    )
    return state


async def _planner_sllm_decompose(user_input: str) -> list[dict]:
    """vLLM planner LoRA로 복합질문 분해

    Hybrid 프롬프트 + knowledge_query 매핑 적용.

    Returns:
        단일이면 [] (classify_intent로 넘김)
        복합이면 [{"query": "...", "hint": "intent_name"}, ...]
    """
    import json
    import re
    import asyncio
    from ai.serving.vllm_client import VLLMProvider

    # Hybrid: 단순/복합에 따라 프롬프트 자동 선택
    system_prompt = _get_planner_prompt(user_input)

    llm = VLLMProvider().with_lora("planner")

    # cold start 대응: 최대 2회 재시도
    response = None
    for attempt in range(3):
        try:
            response = await llm.generate(
                prompt=user_input,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=512,
            )
            break
        except Exception as e:
            if attempt < 2 and ("404" in str(e) or "timeout" in str(e).lower()):
                logger.warning("[Orchestrator] planner 호출 실패 (시도 %d/3), 재시도: %s", attempt + 1, e)
                await asyncio.sleep(2)
            else:
                raise

    if response is None:
        return []

    # 응답에서 JSON 블록만 추출 (설명 텍스트 섞여있을 수 있음)
    content = response.content.strip()
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r'\{[^{}]*"plan"\s*:\s*\[.*?\]\s*\}', content, re.DOTALL)
        if not match:
            logger.warning("[Orchestrator] planner 응답에서 JSON 추출 실패: %s", content[:200])
            return []
        result = json.loads(match.group())

    plan = result.get("plan", [])

    # 1단계면 단일 질문 → 빈 리스트 (classify_intent로)
    if len(plan) <= 1:
        return []

    # 복합: sub_queries 형식으로 변환 + knowledge_query 매핑
    sub_queries = []
    for step in plan:
        intent = step.get("intent", "general")
        # knowledge_query 매핑: judgment/doc_retrieve → knowledge_query로 통합
        # 실제 라우팅은 ONNX 개별 분류에서 결정
        if intent in _KNOWLEDGE_QUERY_INTENTS:
            intent = "knowledge_query"
        sub_queries.append({
            "query": step.get("query", user_input),
            "hint": intent,
            "step_id": step.get("step_id", 0),
            "depends_on": step.get("depends_on", []),
        })

    logger.info(
        "[Orchestrator] planner 분해: %d단계 (매핑 후: %s)",
        len(sub_queries), [sq["hint"] for sq in sub_queries],
    )
    return sub_queries


def route_after_decompose(state: AgentState) -> str:
    """decompose 후 라우팅: 복합이면 compound_pending, 단일이면 classify_intent"""
    if state.get("sub_queries"):
        return "compound_pending"
    return "classify_intent"


def compound_pending(state: AgentState) -> AgentState:
    """복합 질문 처리 대기 — chat.py에서 각 sub_query를 순차 스트리밍"""
    sub_queries = state.get("sub_queries", [])
    state["agent_response"] = {
        "type": "compound",
        "message": "",
        "stream_pending": True,
        "sub_queries": sub_queries,
    }
    logger.info("[Orchestrator] compound_pending | %d개 서브쿼리 대기", len(sub_queries))
    return state


# ── 핵심 노드 ──


def classify_intent(state: AgentState) -> AgentState:
    """Intent 분류 — ONNX 멀티라벨 (복합 감지 포함)

    멀티라벨 결과로 compound 여부도 판단:
      - is_compound=True → sub_queries 생성 → decompose_query로
      - is_compound=False → 단일 intent → route_by_intent로

    force_intent가 있으면 BERT 분류를 건너뛰고 직접 라우팅:
      - "doc_retrieve" → intent=doc_retrieve
      - "doc_retrieve:qa" → intent=doc_retrieve, force_sub_type=qa
    """
    _t = time.time()
    user_input = state["user_input"]

    # ── force_intent: 후속 액션 버튼에서 intent 강제 지정 ──
    force_intent = state.get("force_intent")
    if force_intent:
        parts = force_intent.split(":", 1)
        state["intent"] = parts[0]
        state["confidence"] = 1.0
        state["intent_candidates"] = [{"intent": parts[0], "confidence": 1.0}]
        state["_is_compound"] = False
        if len(parts) > 1:
            state["force_sub_type"] = parts[1]  # "qa" | "summary" | "search"
        logger.info("[Orchestrator] force_intent 적용 (BERT 스킵) | intent=%s, sub_type=%s (%.2fs)",
                    parts[0], parts[1] if len(parts) > 1 else "none", time.time()-_t)
        return state

    logger.info("[Orchestrator] classify_intent 시작 | input='%s'", user_input)

    classifier = get_classifier()

    if ENABLE_COMPLEX_QUERY:
        # 멀티라벨로 복합 감지 + intent 분류 동시 수행
        ml_result = classifier.predict_multilabel(user_input)
        state["intent"] = ml_result["primary_intent"]
        state["confidence"] = ml_result["primary_confidence"]
        state["intent_candidates"] = [
            {"intent": i["intent"], "confidence": i["confidence"]}
            for i in ml_result["intents"]
        ]
        state["_is_compound"] = ml_result["is_compound"]
        state["_compound_intents"] = ml_result["intents"]

        logger.info(
            "[Orchestrator] classify_intent 완료 (%.2fs) | intent=%s, confidence=%.4f, compound=%s",
            time.time()-_t, state['intent'], state['confidence'], ml_result['is_compound']
        )
    else:
        # 단일 라벨 분류 (기존)
        result = classifier.predict(user_input, return_candidates=True)
        state["intent"] = result["intent"]
        state["confidence"] = result["confidence"]
        state["intent_candidates"] = result.get("candidates", [
            {"intent": result["intent"], "confidence": result["confidence"]}
        ])
        state["_is_compound"] = False

        logger.info(
            "[Orchestrator] classify_intent 완료 (%.2fs) | intent=%s, confidence=%.4f",
            time.time()-_t, state['intent'], state['confidence']
        )

    return state


def _is_schedule_followup(user_input: str, chat_history: list[dict]) -> bool:
    """이전 대화가 schedule 관련이고, 현재 입력이 후속 응답이면 followup"""
    import re
    text = user_input.lower()
    has_email = bool(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', user_input))
    has_meet_keyword = any(kw in text for kw in (
        "meet", "미트", "미팅", "링크", "화상",
        "네", "응", "좋아", "생성", "만들어", "yes", "ok",
        "초대", "메일", "보내", "참석",
    ))
    # 시간 관련 입력 (schedule_clarify 후속 응답)
    has_time_input = bool(re.search(r'\d{1,2}\s*시|\d{1,2}:\d{2}|오전|오후|저녁|아침|점심', text))

    # 이전 assistant 응답에서 schedule 관련 타입 확인
    last_schedule_type = None
    for msg in reversed(chat_history):
        agent_response = msg.get("agentResponse") or msg.get("agent_response")
        if agent_response and isinstance(agent_response, dict):
            if agent_response.get("type") in ("schedule_add", "schedule_followup", "schedule_clarify"):
                last_schedule_type = agent_response.get("type")
                break
        content = msg.get("content", "")
        if "일정이 Google Calendar에 등록" in content or "Meet 링크" in content or "초대 메일" in content:
            last_schedule_type = "schedule_add"
            break
        if "몇 시에 잡을까요" in content:
            last_schedule_type = "schedule_clarify"
            break

    if not last_schedule_type:
        return False

    # schedule_clarify 후속 → 시간 입력이면 followup
    if last_schedule_type == "schedule_clarify" and has_time_input:
        return True

    # schedule_add/followup 후속 → 이메일/meet 키워드면 followup
    if has_email or has_meet_keyword:
        return True

    return False


def route_by_intent(state: AgentState) -> str:
    """조건부 라우팅 — intent + confidence 기반 분기

    복합질문이면 decompose_query로, 단일이면 Agent로 직접 라우팅.
    """
    intent = state.get("intent", "")
    confidence = state.get("confidence", 0)

    # 복합질문 감지 (classify_intent에서 멀티라벨 결과로 판단)
    if state.get("_is_compound"):
        logger.info("[Orchestrator] 라우팅: compound 감지 → decompose_query")
        return "decompose_query"

    # schedule followup 감지 (confidence 체크보다 우선 — 이전 대화 맥락 기반)
    user_input = state.get("user_input", "")
    chat_history = state.get("chat_history", [])
    logger.debug("[Orchestrator] followup 체크: chat_history=%d개, input='%s'", len(chat_history), user_input[:50])
    is_followup = _is_schedule_followup(user_input, chat_history)
    logger.debug("[Orchestrator] _is_schedule_followup 결과: %s", is_followup)
    if is_followup:
        state["intent"] = "schedule_followup"
        logger.info("[Orchestrator] 라우팅: schedule_followup 감지 → schedule_agent")
        return "schedule_agent"

    # 낮은 confidence → top-3 후보 제시
    if confidence < INTENT_CONFIDENCE_THRESHOLD:
        candidates = state.get("intent_candidates", [])
        if len(candidates) >= 2:
            logger.info("[Orchestrator] 라우팅: low_confidence → clarify_with_candidates")
            return "clarify_with_candidates"
        logger.info("[Orchestrator] 라우팅: low_confidence → general_response")
        return "general_response"

    # intent별 Agent 라우팅
    if intent == "general":
        route = "general_response"
    elif intent == "judgment":
        route = "judgment_agent"
    elif intent in ("doc_retrieve", "doc_generate"):
        route = "document_agent"
    elif intent.startswith("schedule_") or intent in ("pipeline_create", "approval_create"):
        route = "schedule_agent"
    else:
        route = "general_response"

    logger.info("[Orchestrator] 라우팅: %s (confidence=%.4f) → %s", intent, confidence, route)
    return route


def clarify_with_candidates(state: AgentState) -> AgentState:
    """top-3 후보 제시 노드 (confidence < 0.7)"""
    candidates = state.get("intent_candidates", [])
    logger.debug("[Orchestrator] clarify_with_candidates 진입 | candidates=%s", candidates)

    # 후보 목록 구성
    intent_labels_kr = {
        "judgment": "규정 판단",
        "doc_retrieve": "문서 검색/조회/요약",
        "doc_generate": "문서 작성",
        "schedule_add": "일정 추가",
        "schedule_view": "일정 조회",
        "pipeline_create": "태스크 생성",
        "approval_create": "결재 요청",
        "general": "일반 질문",
    }

    candidate_list = []
    for c in candidates[:3]:
        label = intent_labels_kr.get(c["intent"], c["intent"])
        pct = int(c["confidence"] * 100)
        candidate_list.append({
            "intent": c["intent"],
            "label": label,
            "confidence": c["confidence"],
            "display": f"{label} ({pct}%)",
        })

    state["agent_response"] = {
        "type": "clarify_candidates",
        "message": "다음 중 어느 것에 가까운가요?\n" + "\n".join(
            f"  {i+1}. {c['display']}" for i, c in enumerate(candidate_list)
        ),
        "candidates": candidate_list,
    }

    return state


def format_response(state: AgentState) -> AgentState:
    """응답 포맷팅 노드 — agent_response에 type/message 필드 보장"""
    logger.debug("[Orchestrator] format_response 진입 | agent_response type=%s", state.get('agent_response', {}).get('type', 'none'))
    resp = state.get("agent_response", {})
    if not resp:
        state["agent_response"] = {
            "type": state.get("intent", "general"),
            "message": "응답을 생성하지 못했습니다.",
        }
    else:
        if "type" not in resp:
            resp["type"] = state.get("intent", "general")
        if "message" not in resp:
            resp["message"] = ""
    return state


# ── 그래프 빌드 ──


def build_graph():
    """LangGraph StateGraph 빌드 + 컴파일

    흐름:
      classify_intent (ONNX 멀티라벨: intent 분류 + 복합 감지)
        ├─ compound → decompose_query (planner LoRA or 규칙 기반 쿼리 분리)
        │              → compound_pending → format_response → END
        ├─ single → Agent (judgment/document/schedule/general)
        │           → format_response → END
        └─ low_confidence → clarify_with_candidates → format_response → END
    """
    graph = StateGraph(AgentState)

    # 노드 등록
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("decompose_query", decompose_query)
    graph.add_node("compound_pending", compound_pending)
    graph.add_node("clarify_with_candidates", clarify_with_candidates)
    graph.add_node("judgment_agent", safe_judgment_agent)
    graph.add_node("document_agent", safe_document_agent)
    graph.add_node("schedule_agent", safe_schedule_agent)
    graph.add_node("general_response", general_response_node)
    graph.add_node("format_response", format_response)

    # 엔트리 포인트 — intent 분류 먼저 (복합 감지 포함)
    graph.set_entry_point("classify_intent")

    # classify_intent → compound면 decompose, 아니면 Agent 직행
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "decompose_query": "decompose_query",
            "clarify_with_candidates": "clarify_with_candidates",
            "judgment_agent": "judgment_agent",
            "document_agent": "document_agent",
            "schedule_agent": "schedule_agent",
            "general_response": "general_response",
        },
    )

    # decompose_query → compound_pending (chat.py에서 순차 스트리밍)
    graph.add_edge("decompose_query", "compound_pending")

    # 모든 Agent/노드 → format_response → END
    graph.add_edge("compound_pending", "format_response")
    graph.add_edge("judgment_agent", "format_response")
    graph.add_edge("document_agent", "format_response")
    graph.add_edge("schedule_agent", "format_response")
    graph.add_edge("general_response", "format_response")
    graph.add_edge("clarify_with_candidates", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile()


def get_graph():
    """컴파일된 그래프 인스턴스 반환 (캐시)"""
    global _compiled_graph
    if _compiled_graph is None:
        try:
            _compiled_graph = build_graph()
            logger.info("Orchestrator graph compiled successfully")
        except Exception as e:
            logger.error("Graph build error: %s", e, exc_info=True)
            raise
    return _compiled_graph
