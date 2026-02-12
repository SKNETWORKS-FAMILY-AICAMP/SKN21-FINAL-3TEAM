"""
판단 Agent

기능:
  - RAG 파이프라인으로 관련 규정 검색
  - LLM API에 규정 context + 사용자 질문 전달
  - 다중 규정 교차 판단 (Yes / No / 조건부 가능 / 규정 없음)
  - confidence score 산출

입출력:
  Input: AgentState (user_input, user_id, chat_history)
  Output: AgentState (context, agent_response 채움)
"""
import json
import logging

import re

from ai.agents.state import AgentState
from ai.llm import get_llm
from ai.llm.prompts import JUDGMENT_SYSTEM_PROMPT
from ai.rag.pipeline import get_pipeline

logger = logging.getLogger(__name__)


def _build_context_prompt(context: list[dict]) -> str:
    """RAG 검색 결과를 LLM에 전달할 텍스트 블록으로 변환"""
    if not context:
        return "관련 규정 문서를 찾지 못했습니다."

    parts = []
    for i, doc in enumerate(context, 1):
        source = doc.get("source", "출처 불명")
        content = doc.get("content", "")
        parts.append(f"[규정 {i}] {source}\n{content}")
    return "\n\n".join(parts)


def _build_user_prompt(user_input: str, context_text: str, chat_history: list[dict] | None = None) -> str:
    """사용자 질문 + 규정 context를 합쳐 최종 프롬프트 구성"""
    prompt_parts = [
        "## 관련 규정 문서",
        context_text,
        "",
        "## 사용자 질문",
        user_input,
    ]

    # 대화 이력이 있으면 참고 context로 추가
    if chat_history:
        recent = chat_history[-6:]  # 최근 3턴 (user+assistant × 3)
        history_text = "\n".join(
            f"{'사용자' if m['role'] == 'user' else '어시스턴트'}: {m['content']}"
            for m in recent
        )
        prompt_parts.insert(0, f"## 이전 대화\n{history_text}\n")

    return "\n".join(prompt_parts)


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
            "conditions": None,
            "alternatives": [],
        }


async def judgment_agent(state: AgentState) -> AgentState:
    """
    판단 Agent 노드 함수 (LangGraph 노드 인터페이스)

    1. RAG 파이프라인으로 관련 규정 검색
    2. 검색 결과를 context에 저장
    3. LLM API에 판단 요청
    4. JSON 응답 파싱 → agent_response에 저장

    응답 형식:
    {
        "type": "judgment",
        "result": "yes" | "no" | "conditional" | "no_regulation",
        "confidence": 0.85,
        "reasoning": "근거 설명...",
        "regulations": [
            {"article": "정보보안 규정 3.2조", "relevance": "높음", "content": "..."}
        ],
        "conditions": "조건부일 때 조건 설명",
        "alternatives": ["대안1", "대안2"]
    }
    """
    user_input = state["user_input"]
    user_id = state.get("user_id")
    chat_history = state.get("chat_history", [])

    try:
        # 1. RAG 검색
        pipeline = get_pipeline()
        context = pipeline.retrieve(query=user_input, user_id=user_id, top_k=5)

        # 2. LLM 호출
        llm = get_llm()
        context_text = _build_context_prompt(context)
        user_prompt = _build_user_prompt(user_input, context_text, chat_history)

        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=JUDGMENT_SYSTEM_PROMPT,
            temperature=0.1,  # 판단은 일관성이 중요하므로 낮은 temperature
        )

        # 3. 응답 파싱
        parsed = _parse_llm_response(response.content)
        parsed["type"] = "judgment"

        return {
            **state,
            "context": context,
            "agent_response": parsed,
            "error": None,
        }

    except Exception as e:
        logger.error(f"judgment_agent 오류: {e}", exc_info=True)
        return {
            **state,
            "agent_response": {
                "type": "judgment",
                "result": "no_regulation",
                "confidence": 0.0,
                "reasoning": f"판단 처리 중 오류가 발생했습니다: {str(e)}",
                "regulations": [],
                "conditions": None,
                "alternatives": [],
            },
            "error": str(e),
        }
