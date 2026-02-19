"""
판단 Agent (3단계 고도화 #12)

기능:
  - RAG 파이프라인으로 관련 규정 검색
  - 다중 규정 교차 판단 (규정 간 충돌/보완 분석)
  - confidence score 산출 (RAG 점수 + 규정 커버리지 기반 보정)
  - 조건부 판단 (조건 분기별 상세 판단)
  - 판단 이력 참조 (대화 이력에서 이전 판단 추출 → 일관성 유지)
  - SSE 스트리밍 대응

입출력:
  Input: AgentState (user_input, user_id, chat_history)
  Output: AgentState (context, agent_response 채움)
"""
import json
import logging
import re
import time
from collections import defaultdict
from typing import AsyncGenerator

from ai.agents.state import AgentState
from ai.llm import get_llm
from ai.llm.prompts import JUDGMENT_SYSTEM_PROMPT
from ai.rag.qdrant_pipeline import get_qdrant_pipeline

logger = logging.getLogger(__name__)


# ── 다중 규정 그룹핑 ──


def _group_regulations(context: list[dict]) -> dict[str, list[dict]]:
    """RAG 검색 결과를 규정 출처별로 그룹핑한다.

    Returns:
        {"제3장 근로시간 및 휴가": [doc1, doc2], "제5장 정보보호 관리체계": [doc3]} 형태
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for doc in context:
        # 1순위: chapter 메타데이터 (조항 기반 청킹에서 제공)
        chapter = doc.get("chapter", "")
        if chapter:
            groups[chapter].append(doc)
            continue

        # 2순위: source에서 규정명 추출 (예: "인사규정.pdf" → "인사규정")
        source = doc.get("source", "출처 불명")
        reg_name = re.sub(r"\.(pdf|md|txt)$", "", source, flags=re.IGNORECASE).strip()
        # "제N조" 형태면 article 메타로 대체 시도
        if re.match(r"^제\s*\d+\s*조", reg_name):
            reg_name = doc.get("title", "") or reg_name
        if not reg_name:
            reg_name = source
        groups[reg_name].append(doc)
    return dict(groups)


def _build_context_prompt(context: list[dict]) -> str:
    """RAG 검색 결과를 규정별로 그룹핑하여 LLM에 전달할 텍스트 블록으로 변환"""
    if not context:
        return "관련 규정 문서를 찾지 못했습니다."

    groups = _group_regulations(context)

    parts = []
    doc_idx = 1
    for reg_name, docs in groups.items():
        parts.append(f"### 📋 {reg_name} ({len(docs)}건)")
        for doc in docs:
            source = doc.get("source", "출처 불명")
            content = doc.get("content", "")
            score = doc.get("score", 0.0)
            parts.append(f"[규정 {doc_idx}] {source} (관련도: {score:.3f})\n{content}")
            doc_idx += 1
        parts.append("")  # 규정 그룹 간 빈 줄

    if len(groups) > 1:
        reg_names = ", ".join(groups.keys())
        parts.insert(0, f"⚠️ 다중 규정 교차 분석 필요: {reg_names}\n")

    return "\n".join(parts)


# ── 판단 이력 추출 ──


def _extract_judgment_history(chat_history: list[dict]) -> list[dict]:
    """대화 이력에서 이전 판단 결과를 추출한다.

    assistant 메시지 중 judgment 타입 JSON을 포함한 응답을 찾아 반환.
    """
    history = []
    if not chat_history:
        return history

    for msg in chat_history:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        # JSON 블록 추출 시도
        match = re.search(r"\{.*?\"type\"\s*:\s*\"judgment\".*?\}", content, re.DOTALL)
        if not match:
            continue
        try:
            parsed = json.loads(match.group(0))
            if parsed.get("type") == "judgment":
                history.append(parsed)
        except json.JSONDecodeError:
            continue

    return history


def _build_user_prompt(
    user_input: str,
    context_text: str,
    chat_history: list[dict] | None = None,
    judgment_history: list[dict] | None = None,
) -> str:
    """사용자 질문 + 규정 context + 판단 이력을 합쳐 최종 프롬프트 구성"""
    prompt_parts = []

    # 1. 이전 대화 컨텍스트
    if chat_history:
        recent = chat_history[-6:]  # 최근 3턴 (user+assistant × 3)
        history_text = "\n".join(
            f"{'사용자' if m['role'] == 'user' else '어시스턴트'}: {m['content']}"
            for m in recent
        )
        prompt_parts.append(f"## 이전 대화\n{history_text}\n")

    # 2. 판단 이력 (일관성 유지용)
    if judgment_history:
        history_parts = []
        for i, jh in enumerate(judgment_history[-3:], 1):  # 최근 3건
            history_parts.append(
                f"[이전 판단 {i}] 결과: {jh.get('result', '?')}, "
                f"신뢰도: {jh.get('confidence', 0):.2f}, "
                f"근거: {jh.get('reasoning', '없음')[:100]}"
            )
        prompt_parts.append(
            "## 이전 판단 이력 (일관성 유지 참고)\n"
            + "\n".join(history_parts) + "\n"
        )

    # 3. 규정 문서
    prompt_parts.append(f"## 관련 규정 문서\n{context_text}")

    # 4. 사용자 질문
    prompt_parts.append(f"\n## 사용자 질문\n{user_input}")

    return "\n".join(prompt_parts)


# ── 응답 파싱 + confidence 보정 ──


def _parse_llm_response(raw: str) -> dict:
    """LLM 응답에서 JSON을 파싱한다. 실패하면 fallback 응답 반환."""
    text = raw.strip()

    # 1차: ```json ... ``` 코드블록에서 추출 (앞뒤 텍스트 무시)
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    # 2차: 코드블록이 없으면 첫 번째 { ... } 블록 추출
    if not text.startswith("{"):
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM 응답 JSON 파싱 실패, 원문을 reasoning에 저장")
        return {
            "result": "no_regulation",
            "confidence": 0.0,
            "reasoning": raw,
            "regulations": [],
            "cross_references": [],
            "conditions": None,
            "alternatives": [],
        }


def _calibrate_confidence(parsed: dict, context: list[dict]) -> float:
    """LLM이 출력한 confidence를 RAG 검색 품질 기반으로 보정한다.

    보정 기준:
    - RAG 평균 score가 높으면 상향 (규정 근거가 명확)
    - 검색된 규정 수가 적으면 하향 (근거 부족)
    - 교차 참조에 충돌이 있으면 하향 (판단 불확실성)
    """
    llm_conf = parsed.get("confidence", 0.5)

    if not context:
        return min(llm_conf, 0.3)  # 규정 없으면 최대 0.3

    # RAG 점수 기반 보정
    avg_score = sum(d.get("score", 0) for d in context) / len(context)
    rag_factor = min(avg_score / 0.8, 1.0)  # 0.8 이상이면 1.0

    # 규정 커버리지 보정
    groups = _group_regulations(context)
    coverage_factor = min(len(groups) / 2.0, 1.0)  # 2개 이상 규정이면 1.0

    # 충돌 감지 보정
    cross_refs = parsed.get("cross_references", [])
    conflict_count = sum(
        1 for cr in cross_refs if cr.get("relationship") == "충돌"
    )
    conflict_penalty = 0.1 * conflict_count

    calibrated = llm_conf * 0.6 + rag_factor * 0.25 + coverage_factor * 0.15 - conflict_penalty
    return round(max(0.0, min(1.0, calibrated)), 3)


# ── 메인 Agent 함수 ──


async def judgment_agent(state: AgentState) -> AgentState:
    """
    판단 Agent 노드 함수 (LangGraph 노드 인터페이스)

    1. RAG 파이프라인으로 관련 규정 검색
    2. 규정을 출처별로 그룹핑 (다중 규정 교차 분석)
    3. 대화 이력에서 이전 판단 추출 (일관성 유지)
    4. LLM API에 판단 요청
    5. JSON 응답 파싱 + confidence 보정
    6. agent_response에 저장

    응답 형식:
    {
        "type": "judgment",
        "result": "yes" | "no" | "conditional" | "no_regulation",
        "confidence": 0.85,
        "reasoning": "근거 설명...",
        "regulations": [
            {"article": "정보보안 규정 3.2조", "relevance": "높음", "content": "..."}
        ],
        "cross_references": [
            {"articles": ["조항A", "조항B"], "relationship": "보완", "detail": "..."}
        ],
        "conditions": "조건부일 때 조건 설명",
        "alternatives": ["대안1", "대안2"],
        "regulation_groups": ["규정명1", "규정명2"]
    }
    """
    user_input = state["user_input"]
    user_id = state.get("user_id")
    chat_history = state.get("chat_history", [])

    _t_agent = time.time()
    print(f"[JudgmentAgent] 진입 | user_input='{user_input[:80]}', user_id={user_id}")

    try:
        # 1. RAG 검색 (다중 규정 교차 분석을 위해 top_k 확대)
        _t_rag = time.time()
        print("[JudgmentAgent] RAG 검색 시작 (top_k=7)...")
        pipeline = get_qdrant_pipeline()
        context = pipeline.retrieve(query=user_input, user_id=user_id, top_k=7)
        print(f"[JudgmentAgent] RAG 검색 완료 ({time.time()-_t_rag:.2f}s) | {len(context)}개 문서 검색됨")

        # 2. 판단 이력 추출
        judgment_history = _extract_judgment_history(chat_history)
        print(f"[JudgmentAgent] 판단 이력: {len(judgment_history)}건")

        # 3. 규정 그룹핑 정보
        groups = _group_regulations(context)
        print(f"[JudgmentAgent] 규정 그룹: {list(groups.keys())}")

        # 4. LLM 호출
        _t_llm = time.time()
        print("[JudgmentAgent] LLM 호출 중...")
        llm = get_llm()
        context_text = _build_context_prompt(context)
        user_prompt = _build_user_prompt(
            user_input, context_text, chat_history, judgment_history
        )

        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=JUDGMENT_SYSTEM_PROMPT,
            temperature=0.1,
        )
        print(f"[JudgmentAgent] LLM 응답 ({time.time()-_t_llm:.2f}s) 길이: {len(response.content)}자")

        # 5. 응답 파싱 + confidence 보정
        parsed = _parse_llm_response(response.content)
        parsed["type"] = "judgment"
        parsed["confidence"] = _calibrate_confidence(parsed, context)
        parsed.setdefault("cross_references", [])
        parsed["regulation_groups"] = list(groups.keys())
        parsed["message"] = parsed.get("reasoning", "")

        print(f"[JudgmentAgent] 완료 ({time.time()-_t_agent:.2f}s) | result={parsed.get('result')}, confidence={parsed.get('confidence')}")

        return {
            **state,
            "context": context,
            "agent_response": parsed,
            "error": None,
        }

    except Exception as e:
        print(f"[JudgmentAgent] !!! 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        return {
            **state,
            "agent_response": {
                "type": "judgment",
                "result": "no_regulation",
                "confidence": 0.0,
                "reasoning": f"판단 처리 중 오류가 발생했습니다: {str(e)}",
                "regulations": [],
                "cross_references": [],
                "conditions": None,
                "alternatives": [],
                "regulation_groups": [],
            },
            "error": str(e),
        }


# ── 스트리밍 Agent (SSE 대응) ──


async def judgment_agent_stream(state: AgentState) -> AsyncGenerator[str, None]:
    """
    판단 Agent 스트리밍 버전 (SSE 엔드포인트용)

    토큰 단위로 yield하며, 완료 후 최종 JSON을 별도로 yield한다.
    오케스트레이터에서 SSE 스트리밍 시 이 함수를 호출.

    Yields:
        str: 토큰 단위 텍스트 (스트리밍 중)
        str: "[DONE]" + JSON (스트리밍 완료 후 최종 구조화 응답)
    """
    user_input = state["user_input"]
    user_id = state.get("user_id")
    chat_history = state.get("chat_history", [])

    try:
        # RAG 검색
        pipeline = get_qdrant_pipeline()
        context = pipeline.retrieve(query=user_input, user_id=user_id, top_k=7)

        # 판단 이력 추출
        judgment_history = _extract_judgment_history(chat_history)

        # 프롬프트 구성
        llm = get_llm()
        context_text = _build_context_prompt(context)
        user_prompt = _build_user_prompt(
            user_input, context_text, chat_history, judgment_history
        )

        # 스트리밍 호출
        full_response = ""
        async for token in llm.stream_generate(
            prompt=user_prompt,
            system_prompt=JUDGMENT_SYSTEM_PROMPT,
            temperature=0.1,
        ):
            full_response += token
            yield token

        # 스트리밍 완료 후 구조화 응답 생성
        parsed = _parse_llm_response(full_response)
        parsed["type"] = "judgment"
        parsed["confidence"] = _calibrate_confidence(parsed, context)
        parsed.setdefault("cross_references", [])
        groups = _group_regulations(context)
        parsed["regulation_groups"] = list(groups.keys())
        parsed["message"] = parsed.get("reasoning", "")

        yield "\n[DONE]" + json.dumps(parsed, ensure_ascii=False)

    except Exception as e:
        logger.error(f"judgment_agent_stream 오류: {e}", exc_info=True)
        error_response = {
            "type": "judgment",
            "result": "no_regulation",
            "confidence": 0.0,
            "reasoning": f"판단 처리 중 오류가 발생했습니다: {str(e)}",
            "regulations": [],
            "cross_references": [],
            "conditions": None,
            "alternatives": [],
            "regulation_groups": [],
        }
        yield "\n[DONE]" + json.dumps(error_response, ensure_ascii=False)
