"""
Action Agent — Pipeline Task / Approval Request 생성

기능:
  - 자연어 → 파이프라인 태스크 생성 (pipeline_create)
  - 자연어 → 결재/승인 요청 생성 (approval_create)

입출력:
  Input: AgentState (user_input, intent, user_id, user_team)
  Output: AgentState (agent_response 채움)

pipeline_create 응답 형식:
  {
      "type": "pipeline_create",
      "task": {"id": 1, "title": "...", "stage": "todo", "project": "..."},
      "message": "'코드 리뷰' 태스크가 Pipeline에 추가되었습니다."
  }

approval_create 응답 형식:
  {
      "type": "approval_create",
      "approval": {"id": 1, "type": "leave", "title": "연차 신청", "status": "pending"},
      "message": "'연차 신청' 결재 요청이 등록되었습니다."
  }
"""
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from ai.agents.state import AgentState

logger = logging.getLogger(__name__)

# backend 경로 추가
_backend_path = str(Path(__file__).parent.parent.parent / "backend")
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)


async def action_agent(state: AgentState) -> AgentState:
    """
    Action Agent 노드 함수 (LangGraph 노드 인터페이스)

    intent에 따라 분기:
      - pipeline_create: 파이프라인 태스크 생성
      - approval_create: 결재/승인 요청 생성
    """
    intent = state.get("intent", "").lower()
    user_input = state.get("user_input", "")
    user_id = state.get("user_id")
    user_team = state.get("user_team")

    _t_agent = time.time()
    logger.info("[ActionAgent] 진입 | intent=%s, user_id=%s", intent, user_id)

    response_data = {}

    try:
        if intent == "pipeline_create":
            response_data = await _handle_pipeline_create(user_input, user_id, user_team)
        elif intent == "approval_create":
            response_data = await _handle_approval_create(user_input, user_id, user_team)
        else:
            response_data = {
                "type": intent,
                "message": f"지원하지 않는 액션 intent입니다: {intent}",
            }
    except Exception as e:
        logger.error("[ActionAgent] 에러: %s", e, exc_info=True)
        response_data = {
            "type": intent or "action",
            "message": f"처리 중 오류가 발생했습니다: {e}",
            "error": str(e),
        }

    logger.info("[ActionAgent] 완료 (%.2fs)", time.time() - _t_agent)
    state["agent_response"] = response_data
    return state


# ── Pipeline Task ──


async def _handle_pipeline_create(user_input: str, user_id: int, user_team: str | None) -> dict:
    """파이프라인 태스크 생성: LLM 파싱 → DB 저장"""
    parsed = await _parse_pipeline_input(user_input)
    logger.info("[ActionAgent] pipeline 파싱 결과: %s", parsed)

    if not parsed.get("title"):
        return {
            "type": "pipeline_create",
            "message": "태스크 제목을 파악하지 못했습니다. 다시 입력해주세요.",
        }

    from app.db.session import async_session
    from app.models.pipeline_task import PipelineTask

    # due_date 처리
    due_date = None
    due_date_str = parsed.get("due_date")
    if due_date_str:
        try:
            due_date = datetime.fromisoformat(due_date_str)
        except (ValueError, TypeError):
            pass

    async with async_session() as db:
        task = PipelineTask(
            title=parsed["title"],
            description=parsed.get("description", ""),
            assignee=parsed.get("assignee"),
            stage=parsed.get("stage", "todo"),
            priority=parsed.get("priority", "medium"),
            due_date=due_date,
            project=parsed.get("project"),
            team=user_team,
            created_by=user_id,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        task_data = {
            "id": task.id,
            "title": task.title,
            "stage": task.stage,
            "priority": task.priority,
            "project": task.project,
        }

    return {
        "type": "pipeline_create",
        "task": task_data,
        "message": f"'{parsed['title']}' 태스크가 Pipeline에 추가되었습니다.",
    }


async def _parse_pipeline_input(user_input: str) -> dict:
    """자연어 입력 → 파이프라인 태스크 데이터 파싱"""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    sys_prompt = f"""당신은 태스크 파싱 전문가입니다. 사용자의 자연어 입력을 구조화된 태스크 JSON으로 변환하세요.

현재 날짜: {today}
내일 날짜: {tomorrow}

출력 형식(JSON):
{{
    "title": "태스크 제목",
    "description": "상세 설명 (없으면 빈 문자열)",
    "assignee": "담당자 이름 (없으면 null)",
    "stage": "todo",
    "priority": "medium",
    "due_date": "YYYY-MM-DD 또는 null",
    "project": "프로젝트명 (없으면 null)"
}}

규칙:
- stage: "todo" (기본값), "in_progress", "review", "done" 중 하나
- priority: "high" (긴급/중요), "medium" (기본값), "low" (나중에/여유)
- "긴급", "급한", "중요한", "ASAP" → priority: "high"
- "나중에", "여유", "천천히" → priority: "low"
- "내일"은 {tomorrow}
- 프로젝트명이 언급되면 project 필드에 넣기
- 반드시 유효한 JSON만 출력하세요"""

    user_prompt = f"태스크 입력: {user_input}"
    result_str = await _call_llm(sys_prompt, user_prompt, json_mode=True)

    try:
        parsed = json.loads(result_str)
    except json.JSONDecodeError:
        logger.error("[ActionAgent] pipeline 파싱 실패 (JSON 에러): %s", result_str)
        parsed = _fallback_parse_pipeline(user_input)

    # stage/priority 유효성 검증
    valid_stages = {"todo", "in_progress", "review", "done"}
    if parsed.get("stage") not in valid_stages:
        parsed["stage"] = "todo"

    valid_priorities = {"high", "medium", "low"}
    if parsed.get("priority") not in valid_priorities:
        parsed["priority"] = "medium"

    return parsed


def _fallback_parse_pipeline(user_input: str) -> dict:
    """LLM 파싱 실패 시 규칙 기반 파싱"""
    import re

    # 간단한 제목 추출 — 액션 키워드 제거
    clean = re.sub(
        r'(태스크|task|파이프라인|pipeline|칸반|보드)'
        r'|만들어줘|생성해줘|추가해줘|등록해줘|만들어|생성해|추가해|등록해'
        r'|해줘|해 줘|해주세요|부탁',
        '', user_input
    ).strip()
    title = clean if clean else "새 태스크"

    priority = "medium"
    if any(kw in user_input for kw in ("긴급", "급한", "중요", "ASAP", "asap")):
        priority = "high"
    elif any(kw in user_input for kw in ("나중에", "여유", "천천히")):
        priority = "low"

    return {
        "title": title,
        "description": "",
        "assignee": None,
        "stage": "todo",
        "priority": priority,
        "due_date": None,
        "project": None,
    }


# ── Approval Request ──


async def _handle_approval_create(user_input: str, user_id: int, user_team: str | None) -> dict:
    """결재/승인 요청 생성: LLM 파싱 → DB 저장"""
    parsed = await _parse_approval_input(user_input)
    logger.info("[ActionAgent] approval 파싱 결과: %s", parsed)

    if not parsed.get("title"):
        return {
            "type": "approval_create",
            "message": "결재 요청 제목을 파악하지 못했습니다. 다시 입력해주세요.",
        }

    from app.db.session import async_session
    from app.models.approval_request import ApprovalRequest

    async with async_session() as db:
        approval = ApprovalRequest(
            type=parsed.get("type", "leave"),
            title=parsed["title"],
            detail=parsed.get("detail", ""),
            status="pending",
            requester_id=user_id,
            target_team=parsed.get("target_team") or user_team,
        )
        db.add(approval)
        await db.commit()
        await db.refresh(approval)

        approval_data = {
            "id": approval.id,
            "type": approval.type,
            "title": approval.title,
            "status": approval.status,
        }

    return {
        "type": "approval_create",
        "approval": approval_data,
        "message": f"'{parsed['title']}' 결재 요청이 등록되었습니다.",
    }


async def _parse_approval_input(user_input: str) -> dict:
    """자연어 입력 → 결재 요청 데이터 파싱"""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    sys_prompt = f"""당신은 결재/승인 요청 파싱 전문가입니다. 사용자의 자연어 입력을 구조화된 결재 요청 JSON으로 변환하세요.

현재 날짜: {today}
내일 날짜: {tomorrow}

출력 형식(JSON):
{{
    "type": "leave",
    "title": "결재 요청 제목",
    "detail": "상세 내용 (없으면 빈 문자열)",
    "target_team": "대상 팀 (없으면 null)"
}}

type 규칙:
- "연차", "휴가", "반차", "조퇴", "병가" → "leave"
- "코드 리뷰", "리뷰", "검토", "PR" → "review"
- "예산", "품의", "비용", "구매", "지출" → "budget"
- "출장" → "business_trip"
- 그 외 → "general"

title 규칙:
- 유형에 맞는 자연스러운 제목 생성
- 예: "내일 연차 쓸게요" → title: "연차 신청 ({tomorrow})"
- 예: "코드 리뷰 결재 올려줘" → title: "코드 리뷰 요청"

- 반드시 유효한 JSON만 출력하세요"""

    user_prompt = f"결재 요청: {user_input}"
    result_str = await _call_llm(sys_prompt, user_prompt, json_mode=True)

    try:
        parsed = json.loads(result_str)
    except json.JSONDecodeError:
        logger.error("[ActionAgent] approval 파싱 실패 (JSON 에러): %s", result_str)
        parsed = _fallback_parse_approval(user_input)

    # type 유효성 검증
    valid_types = {"leave", "review", "budget", "business_trip", "general"}
    if parsed.get("type") not in valid_types:
        parsed["type"] = _infer_approval_type(user_input)

    return parsed


def _infer_approval_type(user_input: str) -> str:
    """키워드 기반 결재 유형 추론"""
    if any(kw in user_input for kw in ("연차", "휴가", "반차", "조퇴", "병가")):
        return "leave"
    if any(kw in user_input for kw in ("코드 리뷰", "리뷰", "검토", "PR", "pr")):
        return "review"
    if any(kw in user_input for kw in ("예산", "품의", "비용", "구매", "지출")):
        return "budget"
    if "출장" in user_input:
        return "business_trip"
    return "general"


def _fallback_parse_approval(user_input: str) -> dict:
    """LLM 파싱 실패 시 규칙 기반 파싱"""
    import re

    approval_type = _infer_approval_type(user_input)

    type_titles = {
        "leave": "연차 신청",
        "review": "리뷰 요청",
        "budget": "예산 신청",
        "business_trip": "출장 신청",
        "general": "결재 요청",
    }
    title = type_titles.get(approval_type, "결재 요청")

    # 간단한 상세 추출
    clean = re.sub(
        r'(결재|승인|결재요청|결재 요청)'
        r'|올려줘|신청해줘|등록해줘|만들어줘|올려|신청|등록|만들어'
        r'|해줘|해 줘|해주세요|부탁',
        '', user_input
    ).strip()
    detail = clean if clean != title else ""

    return {
        "type": approval_type,
        "title": title,
        "detail": detail,
        "target_team": None,
    }


# ── LLM 호출 ──


async def _call_llm(sys_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
    """LLM 호출 (LLM Factory 사용)"""
    _t_llm = time.time()
    logger.debug("[ActionAgent] _call_llm | json_mode=%s", json_mode)
    try:
        from ai.llm import get_llm

        llm = get_llm()
        logger.debug("[ActionAgent] Provider: %s", llm.__class__.__name__)

        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=sys_prompt,
            temperature=0.3,
            json_mode=json_mode,
        )

        result = response.content
        logger.debug("[ActionAgent] LLM 응답 (%.2fs)", time.time() - _t_llm)
        return result

    except Exception as e:
        logger.error("[ActionAgent] _call_llm 에러: %s", e)
        return "{}"
