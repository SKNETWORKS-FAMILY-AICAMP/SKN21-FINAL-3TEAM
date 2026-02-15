"""
일정 Agent (팀원 D 담당)

기능:
  - 자연어 → 구조화 일정 데이터 파싱 (Solar API json_mode)
  - Google Calendar 일정 등록 (schedule_add)
  - Google Calendar 일정 조회 (schedule_view)
  - 자연어 → 구조화 일정 데이터 파싱 (Solar API json_mode)
  - Google Calendar 일정 등록 (schedule_add)
  - Google Calendar 일정 조회 (schedule_view)

입출력:
  Input: AgentState (user_input, intent, user_id)
  Input: AgentState (user_input, intent, user_id)
  Output: AgentState (agent_response + google_services_result 채움)

schedule_add 응답 형식:
  {
      "type": "schedule_add",
      "schedule": {
          "title": "...",
          "start_time": "2025-02-10T09:00:00",
          "end_time": "2025-02-10T10:00:00",
          "description": "..."
          "description": "..."
      },
      "google_services": {
          "calendar_synced": true,
          "event_id": "...",
          "html_link": "..."
          "event_id": "...",
          "html_link": "..."
      },
      "message": "일정이 등록되었습니다."
  }

schedule_view 응답 형식:
  {
      "type": "schedule_view",
      "schedules": [...],
      "message": "일정 목록입니다."
  }
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta

from ai.agents.state import AgentState

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


async def schedule_agent(state: AgentState) -> AgentState:
    """
    일정 Agent 노드 함수 (LangGraph 노드 인터페이스)

    intent에 따라 분기:
      - schedule_add: 일정 추가 + Google Calendar 연동
      - schedule_add: 일정 추가 + Google Calendar 연동
      - schedule_view: 일정 조회
    """
    intent = state.get("intent", "").lower()
    user_input = state.get("user_input", "")
    user_id = state.get("user_id")

    _t_agent = time.time()
    print(f"[ScheduleAgent] 진입 | intent={intent}, user_input='{user_input}', user_id={user_id}")

    response_data = {}

    try:
        if intent == "schedule_add":
            print("[ScheduleAgent] → _handle_schedule_add 호출")
            response_data = await _handle_schedule_add(user_input, user_id)
        elif intent == "schedule_view":
            print("[ScheduleAgent] → _handle_schedule_view 호출")
            response_data = await _handle_schedule_view(user_input, user_id)
        else:
            response_data = {
                "type": intent,
                "message": f"지원하지 않는 일정 intent입니다: {intent}",
            }
    except Exception as e:
        print(f"[ScheduleAgent] !!! 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        response_data = {
            "type": intent or "schedule",
            "message": f"일정 처리 중 오류가 발생했습니다: {e}",
            "error": str(e),
        }

    print(f"[ScheduleAgent] 완료 ({time.time()-_t_agent:.2f}s) | response_data={response_data}")
    state["agent_response"] = response_data

    if response_data.get("google_services"):
        state["google_services_result"] = response_data["google_services"]

    return state


async def _handle_schedule_add(user_input: str, user_id: int) -> dict:
    """일정 추가: LLM 파싱 → Google Calendar 등록"""
    # 1. LLM으로 자연어 → 구조화 데이터 파싱
    print(f"[ScheduleAgent] _handle_schedule_add | LLM 파싱 시작...")
    parsed = _parse_schedule_input(user_input)
    print(f"[ScheduleAgent] _handle_schedule_add | 파싱 결과: {parsed}")

    if not parsed.get("title"):
        return {
            "type": "schedule_add",
            "message": "일정 제목을 파악하지 못했습니다. 다시 입력해주세요.",
            "schedule": parsed,
        }

    # 2. Google Calendar API 호출
    try:
        from backend.app.db.session import async_session
        from backend.app.services.calendar_service import GoogleCalendarService

        calendar_service = GoogleCalendarService()
        event_data = {
            "title": parsed["title"],
            "start_time": parsed["start_time"],
            "end_time": parsed.get("end_time", parsed["start_time"]),
            "description": parsed.get("description", ""),
        }

        async with async_session() as db:
            google_result = await calendar_service.push_event(db, user_id, event_data)

        return {
            "type": "schedule_add",
            "schedule": parsed,
            "google_services": {
                "calendar_synced": True,
                "event_id": google_result.get("event_id"),
                "html_link": google_result.get("html_link"),
            },
            "message": f"'{parsed['title']}' 일정이 Google Calendar에 등록되었습니다.",
        }

    except Exception as e:
        logger.warning(f"Google Calendar 연동 실패: {e}")
        return {
            "type": "schedule_add",
            "schedule": parsed,
            "google_services": {
                "calendar_synced": False,
                "error": str(e),
            },
            "message": (
                f"'{parsed['title']}' 일정을 파싱했지만 Google Calendar 등록에 실패했습니다. "
                "Google 캘린더 연동이 필요합니다."
            ),
        }


async def _handle_schedule_view(user_input: str, user_id: int) -> dict:
    """일정 조회: LLM 파싱 → Google Calendar 조회"""
    # 1. LLM으로 조회 범위 파싱
    print(f"[ScheduleAgent] _handle_schedule_view | LLM 파싱 시작...")
    parsed = _parse_view_request(user_input)
    print(f"[ScheduleAgent] _handle_schedule_view | 파싱 결과: {parsed}")

    # 2. Google Calendar API 호출
    try:
        from backend.app.db.session import async_session
        from backend.app.services.calendar_service import GoogleCalendarService

        calendar_service = GoogleCalendarService()

        async with async_session() as db:
            events = await calendar_service.pull_events(
                db, user_id,
                time_min=parsed.get("time_min"),
                time_max=parsed.get("time_max"),
            )

        if not events:
            return {
                "type": "schedule_view",
                "schedules": [],
                "message": "해당 기간에 등록된 일정이 없습니다.",
            }

        # 일정 목록 메시지 생성
        schedule_lines = []
        for ev in events[:10]:
            title = ev.get("title", "제목 없음")
            start = ev.get("start", "")
            schedule_lines.append(f"- {title} ({start})")

        message = f"총 {len(events)}개의 일정이 있습니다.\n" + "\n".join(schedule_lines)
        if len(events) > 10:
            message += f"\n... 외 {len(events) - 10}개"

        return {
            "type": "schedule_view",
            "schedules": events,
            "message": message,
        }

    except Exception as e:
        logger.warning(f"Google Calendar 조회 실패: {e}")
        return {
            "type": "schedule_view",
            "schedules": [],
            "message": (
                "Google Calendar 일정을 조회하지 못했습니다. "
                "Google 캘린더 연동이 필요합니다."
            ),
            "error": str(e),
        }


def _parse_schedule_input(user_input: str) -> dict:
    """자연어 입력 → 일정 데이터 파싱 (Solar API json_mode)"""
    now = datetime.now()
    current_datetime = now.strftime("%Y-%m-%dT%H:%M:%S")
    current_weekday = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]

    sys_prompt = f"""당신은 일정 파싱 전문가입니다. 사용자의 자연어 입력을 구조화된 일정 JSON으로 변환하세요.

현재 시각: {current_datetime} ({current_weekday}요일)

출력 형식(JSON):
{{
    "title": "일정 제목",
    "start_time": "YYYY-MM-DDTHH:MM:SS",
    "end_time": "YYYY-MM-DDTHH:MM:SS",
    "description": "일정 설명 (없으면 빈 문자열)"
}}

규칙:
- "내일"은 현재 날짜 + 1일
- "다음 주 월요일"은 다음 주 월요일 날짜
- "모레"는 현재 날짜 + 2일
- 종료 시간이 명시되지 않으면 시작 시간 + 1시간
- 시간이 명시되지 않으면 09:00:00으로 설정
- 반드시 유효한 JSON만 출력하세요"""

    user_prompt = f"일정 입력: {user_input}"
    result_str = _call_llm(sys_prompt, user_prompt, json_mode=True)

    try:
        return json.loads(result_str)
    except json.JSONDecodeError:
        logger.error(f"일정 파싱 실패: {result_str}")
        return {"title": "", "start_time": "", "end_time": "", "description": ""}


def _parse_view_request(user_input: str) -> dict:
    """자연어 입력 → 조회 범위 파싱 (Solar API json_mode)"""
    now = datetime.now()
    current_datetime = now.strftime("%Y-%m-%dT%H:%M:%S")
    current_weekday = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]

    sys_prompt = f"""당신은 일정 조회 범위 파싱 전문가입니다. 사용자의 자연어 입력에서 조회 기간을 추출하세요.

현재 시각: {current_datetime} ({current_weekday}요일)

출력 형식(JSON):
{{
    "time_min": "YYYY-MM-DDTHH:MM:SSZ",
    "time_max": "YYYY-MM-DDTHH:MM:SSZ"
}}

규칙:
- "오늘 일정" → 오늘 00:00:00Z ~ 오늘 23:59:59Z
- "내일 일정" → 내일 00:00:00Z ~ 내일 23:59:59Z
- "이번 주 일정" → 이번 주 월요일 00:00:00Z ~ 일요일 23:59:59Z
- "다음 주 일정" → 다음 주 월요일 00:00:00Z ~ 일요일 23:59:59Z
- "이번 달 일정" → 이번 달 1일 00:00:00Z ~ 말일 23:59:59Z
- "최근 일정", "일정 조회" 등 명확하지 않으면 → 오늘 00:00:00Z ~ 오늘로부터 +30일 23:59:59Z (향후 한 달)
- 시간대는 UTC(Z) 형식으로 출력 (한국시간 KST = UTC+9 이므로 -9시간 보정)
- 반드시 유효한 JSON만 출력하세요"""

    user_prompt = f"조회 요청: {user_input}"
    result_str = _call_llm(sys_prompt, user_prompt, json_mode=True)

    try:
        return json.loads(result_str)
    except json.JSONDecodeError:
        logger.error(f"조회 범위 파싱 실패: {result_str}")
        return {}


def _call_llm(sys_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
    """LLM 호출 (Solar API) — document_agent._call_llm() 패턴 재사용"""
    _t_llm = time.time()
    print(f"[ScheduleAgent] _call_llm 호출 | json_mode={json_mode}")
    try:
        from openai import OpenAI

        api_key = os.getenv("SOLAR_API_KEY")
        print(f"[ScheduleAgent] _call_llm | SOLAR_API_KEY 존재: {bool(api_key)}")
        if not api_key:
            print("[ScheduleAgent] _call_llm | API 키 없음 → mock 응답")
            return _get_mock_response(user_prompt, json_mode)

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.upstage.ai/v1/solar",
        )

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]

        print(f"[ScheduleAgent] _call_llm | Solar API 호출 중...")
        response = client.chat.completions.create(
            model="solar-1-mini-chat",
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"} if json_mode else {"type": "text"},
        )

        result = response.choices[0].message.content
        print(f"[ScheduleAgent] _call_llm | Solar API 응답 ({time.time()-_t_llm:.2f}s): {result}")
        return result

    except ImportError:
        print("[ScheduleAgent] _call_llm | !!! openai 패키지 없음")
        return _get_mock_response(user_prompt, json_mode)
    except Exception as e:
        print(f"[ScheduleAgent] _call_llm | !!! 에러: {e}")
        import traceback
        traceback.print_exc()
        return _get_mock_response(user_prompt, json_mode)


def _get_mock_response(user_prompt: str, json_mode: bool) -> str:
    """API 키 없을 때 Mock 응답"""
    if not json_mode:
        return "일정 처리 결과입니다. (Mock Response)"

    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    if "조회" in user_prompt or "보여" in user_prompt or "알려" in user_prompt:
        return json.dumps({
            "time_min": now.strftime("%Y-%m-%dT00:00:00Z"),
            "time_max": (now + timedelta(days=7)).strftime("%Y-%m-%dT23:59:59Z"),
        }, ensure_ascii=False)

    return json.dumps({
        "title": "회의 (Mock)",
        "start_time": tomorrow.strftime("%Y-%m-%dT14:00:00"),
        "end_time": tomorrow.strftime("%Y-%m-%dT15:00:00"),
        "description": "",
    }, ensure_ascii=False)
