"""
일정 Agent (팀원 D 담당)

기능:
  - 자연어 → 구조화 일정 데이터 파싱 (Solar API json_mode)
  - Google Calendar 일정 등록 + Meet 링크 (schedule_add)
  - Google Calendar 일정 조회 (schedule_view)
  - 참석자 이메일 초대 메일 발송 (schedule_followup)

입출력:
  Input: AgentState (user_input, intent, user_id)
  Output: AgentState (agent_response + google_services_result 채움)

schedule_add 응답 형식:
  {
      "type": "schedule_add",
      "schedule": {
          "title": "...",
          "start_time": "2025-02-10T09:00:00",
          "end_time": "2025-02-10T10:00:00",
          "description": "...",
          "include_meet": true
      },
      "google_services": {
          "calendar_synced": true,
          "event_id": "...",
          "html_link": "...",
          "meet_link": "...",
          "email_sent": false
      },
      "message": "일정이 등록되었습니다."
  }

schedule_followup 응답 형식:
  {
      "type": "schedule_followup",
      "email_sent": true,
      "email_count": 2,
      "message": "2명에게 초대 메일을 보냈습니다."
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
import re
import time
from datetime import datetime, timedelta

from ai.agents.state import AgentState

logger = logging.getLogger(__name__)


async def schedule_agent(state: AgentState) -> AgentState:
    """
    일정 Agent 노드 함수 (LangGraph 노드 인터페이스)

    intent에 따라 분기:
      - schedule_add: 일정 추가 + Google Calendar 연동
      - schedule_view: 일정 조회
    """
    intent = state.get("intent", "").lower()
    user_input = state.get("user_input", "")
    user_id = state.get("user_id")

    # followup 감지: 이전 대화에 schedule_clarify가 있고 시간 입력이면 → clarify 후속
    chat_history = state.get("chat_history", [])
    clarify_info = _extract_clarify_from_history(chat_history)
    if clarify_info and re.search(r'\d{1,2}\s*시|\d{1,2}:\d{2}|오전|오후|저녁|아침|점심', user_input):
        logger.info("[ScheduleAgent] schedule_clarify 후속 감지 → schedule_followup")
        intent = "schedule_followup"
        state["intent"] = "schedule_followup"

    # 일반 followup 감지 (Meet/이메일 등)
    if intent not in ("schedule_add", "schedule_view", "schedule_followup"):
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', user_input)
        meet_kw = any(kw in user_input.lower() for kw in ("meet", "미트", "미팅", "링크", "화상", "네", "응", "좋아", "생성", "만들어", "초대", "메일", "보내"))
        if (emails or meet_kw) and _has_schedule_in_history(chat_history):
            logger.info("[ScheduleAgent] intent '%s' → schedule_followup", intent)
            intent = "schedule_followup"
            state["intent"] = "schedule_followup"

    _t_agent = time.time()
    logger.info("[ScheduleAgent] 진입 | intent=%s, user_id=%s", intent, user_id)

    response_data = {}

    try:
        if intent == "schedule_add":
            response_data = await _handle_schedule_add(user_input, user_id)
        elif intent == "schedule_view":
            response_data = await _handle_schedule_view(user_input, user_id)
        elif intent == "schedule_followup":
            response_data = await _handle_schedule_followup(user_input, user_id, state)
        else:
            response_data = {
                "type": intent,
                "message": f"지원하지 않는 일정 intent입니다: {intent}",
            }
    except Exception as e:
        logger.error("[ScheduleAgent] 에러: %s", e, exc_info=True)
        response_data = {
            "type": intent or "schedule",
            "message": f"일정 처리 중 오류가 발생했습니다: {e}",
            "error": str(e),
        }

    logger.info("[ScheduleAgent] 완료 (%.2fs)", time.time() - _t_agent)
    state["agent_response"] = response_data

    if response_data.get("google_services"):
        state["google_services_result"] = response_data["google_services"]

    return state


async def _handle_schedule_add(user_input: str, user_id: int) -> dict:
    """일정 추가: LLM 파싱 → 캘린더 등록 (Meet 없이) → 후속 질문"""
    parsed = await _parse_schedule_input(user_input)
    logger.info("[ScheduleAgent] 파싱 결과: %s", parsed)

    if not parsed.get("title"):
        return {
            "type": "schedule_add",
            "message": "일정 제목을 파악하지 못했습니다. 다시 입력해주세요.",
            "schedule": parsed,
        }

    # 시간이 불명확하면 되물어보기
    missing = _check_missing_info(parsed)
    if missing:
        return {
            "type": "schedule_clarify",
            "schedule": parsed,
            "missing": missing,
            "message": _build_clarify_message(parsed, missing),
        }

    return await _register_schedule(parsed, user_id)


async def _register_schedule(parsed: dict, user_id: int) -> dict:
    """파싱된 일정 데이터를 Google Calendar에 등록"""
    try:
        import sys
        from pathlib import Path
        backend_path = str(Path(__file__).parent.parent.parent / "backend")
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)

        from app.db.session import async_session
        from app.services.schedule_service import create_with_google_services

        from datetime import datetime as _dt
        start_str = parsed["start_time"]
        end_str = parsed.get("end_time", parsed["start_time"])
        start_dt = _dt.fromisoformat(start_str) if isinstance(start_str, str) else start_str
        end_dt = _dt.fromisoformat(end_str) if isinstance(end_str, str) else end_str

        schedule_data = {
            "title": parsed["title"],
            "start_time": start_dt,
            "end_time": end_dt,
            "description": parsed.get("description", ""),
            "schedule_type": "task",
        }

        async with async_session() as db:
            result = await create_with_google_services(
                db, user_id, schedule_data, include_meet=False,
            )
            await db.commit()

        google_services = result.get("google_services", {})
        schedule_obj = result.get("schedule")
        event_id = schedule_obj.google_event_id if schedule_obj else None

        message = f"'{parsed['title']}' 일정이 Google Calendar에 등록되었습니다.\n\n"
        message += "추가로 필요한 사항이 있으면 알려주세요:\n"
        message += "- Google Meet 링크를 생성할까요?\n"
        message += "- 참석자에게 초대 메일을 보낼까요? (이메일 주소를 알려주세요)"

        return {
            "type": "schedule_add",
            "schedule": parsed,
            "google_services": {
                "calendar_synced": google_services.get("calendar_synced", False),
                "event_id": event_id,
                "html_link": google_services.get("html_link"),
                "meet_link": None,
                "email_sent": False,
            },
            "message": message,
        }

    except Exception as e:
        logger.warning("Google Calendar 연동 실패: %s", e)
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


async def _handle_schedule_followup(user_input: str, user_id: int, state: dict) -> dict:
    """후속 처리: 시간 보충(schedule_clarify) / Meet 링크 생성 / 참석자 초대 메일 발송"""
    chat_history = state.get("chat_history", [])

    # schedule_clarify 후속인지 확인 → 시간 보충 후 등록
    clarify_info = _extract_clarify_from_history(chat_history)
    if clarify_info:
        return await _handle_clarify_response(user_input, user_id, clarify_info)

    schedule_info = _extract_last_schedule_from_history(chat_history)

    if not schedule_info:
        return {
            "type": "schedule_followup",
            "message": "이전에 등록한 일정 정보를 찾을 수 없습니다. 먼저 일정을 등록해주세요.",
        }

    text = user_input.lower()
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', user_input)
    want_meet = any(kw in text for kw in ("meet", "미트", "미팅", "링크", "화상", "네", "응", "좋아", "생성", "만들어", "yes"))

    import sys
    from pathlib import Path
    backend_path = str(Path(__file__).parent.parent.parent / "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    from app.db.session import async_session

    results = []
    meet_link = schedule_info.get("meet_link")
    event_id = schedule_info.get("event_id")

    # 1. Meet 링크 생성 (아직 없는 경우)
    if want_meet and not meet_link:
        try:
            from app.services.calendar_service import GoogleCalendarService

            calendar_service = GoogleCalendarService()
            event_data = {
                "title": schedule_info["title"],
                "start_time": schedule_info["start_time"],
                "end_time": schedule_info.get("end_time", schedule_info["start_time"]),
                "description": "",
            }

            async with async_session() as db:
                meet_result = await calendar_service.create_event_with_meet(
                    db, user_id, event_data, attendee_emails=emails or None,
                )
                await db.commit()

            meet_link = meet_result.get("meet_link")
            event_id = meet_result.get("event_id")
            if meet_link:
                results.append(f"Google Meet 링크가 생성되었습니다: {meet_link}")
            else:
                results.append("Meet 링크 생성을 요청했지만 링크를 받지 못했습니다.")
        except Exception as e:
            logger.warning(f"Meet 링크 생성 실패: {e}")
            results.append(f"Meet 링크 생성에 실패했습니다: {e}")

    # 2. 초대 메일 발송
    if emails:
        try:
            from app.services.gmail_service import GmailService

            gmail_service = GmailService()
            async with async_session() as db:
                mail_result = await gmail_service.send_meeting_invite(
                    db,
                    user_id,
                    recipient_emails=emails,
                    meeting_title=schedule_info["title"],
                    meeting_time=schedule_info["start_time"],
                    meet_link=meet_link,
                )

            sent_count = mail_result.get("sent_count", len(emails))
            results.append(f"{sent_count}명에게 초대 메일을 보냈습니다.")
        except Exception as e:
            logger.warning(f"초대 메일 발송 실패: {e}")
            results.append(f"초대 메일 발송에 실패했습니다: {e}")

    # 3. Meet만 요청 + 이메일 없는 경우, 이메일도 안내
    if want_meet and not emails:
        if meet_link:
            results.append("참석자에게 초대 메일을 보내시려면 이메일 주소를 알려주세요.")

    # 4. 둘 다 아닌 경우
    if not want_meet and not emails:
        return {
            "type": "schedule_followup",
            "message": (
                "어떤 작업을 원하시나요?\n"
                "- **Meet 링크 생성**: \"Meet 링크 만들어줘\"\n"
                "- **초대 메일 발송**: 이메일 주소를 입력해주세요 (예: user@gmail.com)"
            ),
        }

    message = "\n".join(results)
    return {
        "type": "schedule_followup",
        "meet_link": meet_link,
        "email_sent": bool(emails),
        "email_count": len(emails) if emails else 0,
        "message": message,
    }


def _extract_clarify_from_history(chat_history: list[dict]) -> dict | None:
    """대화 이력에서 가장 최근 schedule 응답이 clarify일 때만 반환"""
    for msg in reversed(chat_history):
        ar = msg.get("agentResponse") or msg.get("agent_response")
        if ar and isinstance(ar, dict):
            ar_type = ar.get("type", "")
            # 가장 최근 schedule 관련 응답 확인
            if ar_type == "schedule_clarify":
                return ar.get("schedule", {})
            # schedule_add/followup이 더 최근이면 → clarify는 이미 해결된 것
            if ar_type in ("schedule_add", "schedule_followup"):
                return None
        content = msg.get("content", "")
        if "몇 시에 잡을까요" in content:
            if ar and isinstance(ar, dict):
                return ar.get("schedule", {})
    return None


async def _handle_clarify_response(user_input: str, user_id: int, clarify_schedule: dict) -> dict:
    """schedule_clarify 후속: 사용자가 시간을 보충 → 일정 등록"""
    # 사용자 입력에서 시간 파싱
    time_info = _parse_time_from_input(user_input)
    if not time_info:
        return {
            "type": "schedule_clarify",
            "schedule": clarify_schedule,
            "missing": ["time"],
            "message": "시간을 인식하지 못했습니다. 다시 입력해주세요. (예: 오후 3시, 14:00, 19시)",
        }

    hour, minute = time_info

    # 기존 clarify 정보에서 날짜 가져오기
    now = datetime.now()
    # clarify_schedule에 start_time이 없으면 오늘 날짜 사용
    base_date = now
    start_time_str = clarify_schedule.get("start_time")
    if start_time_str:
        try:
            base_date = datetime.fromisoformat(start_time_str)
        except (ValueError, TypeError):
            pass

    start_dt = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    end_dt = start_dt + timedelta(hours=1)

    # 완성된 parsed로 _handle_schedule_add 로직 재실행
    completed = {
        "title": clarify_schedule.get("title", "새 일정"),
        "start_time": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "end_time": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "description": clarify_schedule.get("description", ""),
        "include_meet": clarify_schedule.get("include_meet", False),
    }

    return await _register_schedule(completed, user_id)


def _parse_time_from_input(text: str) -> tuple | None:
    """사용자 입력에서 시간(hour, minute) 추출"""
    text = text.strip()

    # "14:00", "19:30" 형태
    m = re.search(r'(\d{1,2}):(\d{2})', text)
    if m:
        return int(m.group(1)), int(m.group(2))

    # "오후 3시 30분", "19시", "3시" 형태
    m = re.search(r'(\d{1,2})\s*시\s*(\d{1,2}\s*분)?', text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2).replace('분', '').strip()) if m.group(2) else 0
        if "오후" in text or "저녁" in text:
            if hour < 12:
                hour += 12
        return hour, minute

    # 숫자만 입력 ("19", "3")
    m = re.match(r'^(\d{1,2})$', text)
    if m:
        hour = int(m.group(1))
        if 0 <= hour <= 23:
            return hour, 0

    return None


def _has_schedule_in_history(chat_history: list[dict]) -> bool:
    """대화 이력에 schedule_add 응답이 있는지 확인"""
    for msg in reversed(chat_history):
        ar = msg.get("agentResponse") or msg.get("agent_response")
        if ar and isinstance(ar, dict) and ar.get("type") in ("schedule_add", "schedule_followup"):
            return True
        content = msg.get("content", "")
        if "일정이 Google Calendar에 등록" in content or "Meet 링크" in content:
            return True
    return False


def _extract_last_schedule_from_history(chat_history: list[dict]) -> dict | None:
    """대화 이력에서 가장 최근 schedule_add 결과 추출"""
    for msg in reversed(chat_history):
        agent_response = msg.get("agentResponse") or msg.get("agent_response")
        if agent_response and isinstance(agent_response, dict):
            if agent_response.get("type") in ("schedule_add", "schedule_followup"):
                schedule = agent_response.get("schedule", {})
                google = agent_response.get("google_services", {})
                title = schedule.get("title") or agent_response.get("title", "")
                if not title:
                    continue
                return {
                    "title": title,
                    "start_time": schedule.get("start_time", ""),
                    "end_time": schedule.get("end_time", ""),
                    "meet_link": google.get("meet_link") or agent_response.get("meet_link"),
                    "event_id": google.get("event_id"),
                }
    return None


async def _handle_schedule_view(user_input: str, user_id: int) -> dict:
    """일정 조회: LLM 파싱 → Google Calendar 조회"""
    # 1. LLM으로 조회 범위 파싱
    logger.debug("[ScheduleAgent] schedule_view 파싱 시작")
    parsed = await _parse_view_request(user_input)
    logger.debug("[ScheduleAgent] schedule_view 파싱 결과: %s", parsed)

    # 2. Google Calendar API 호출
    try:
        import sys
        from pathlib import Path
        # backend 디렉토리를 sys.path에 추가
        backend_path = str(Path(__file__).parent.parent.parent / "backend")
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)

        from app.db.session import async_session
        from app.services.calendar_service import GoogleCalendarService

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
            start_raw = ev.get("start", "")
            # ISO datetime → "HH:MM" 시간만 표시
            try:
                start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                start_display = start_dt.strftime("%H:%M")
            except (ValueError, AttributeError):
                start_display = start_raw
            schedule_lines.append(f"- {title} ({start_display})")

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


async def _parse_schedule_input(user_input: str) -> dict:
    """자연어 입력 → 일정 데이터 파싱 (Solar API json_mode → fallback: 직접 파싱)"""
    now = datetime.now()
    current_datetime = now.strftime("%Y-%m-%dT%H:%M:%S")
    current_weekday = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")

    sys_prompt = f"""당신은 일정 파싱 전문가입니다. 사용자의 자연어 입력을 구조화된 일정 JSON으로 변환하세요.

현재 시각: {current_datetime} ({current_weekday}요일)
오늘 날짜: {today}
내일 날짜: {tomorrow}

반드시 실제 날짜와 시간을 계산하여 출력하세요. 절대로 "YYYY-MM-DD" 같은 형식 문자열을 출력하지 마세요.

예시:
입력: "내일 오후 3시 점심 회의"
출력: {{"title": "점심 회의", "start_time": "{tomorrow}T15:00:00", "end_time": "{tomorrow}T16:00:00", "description": "", "include_meet": true}}

입력: "오늘 저녁 6시 팀 식사"
출력: {{"title": "팀 식사", "start_time": "{today}T18:00:00", "end_time": "{today}T19:00:00", "description": "", "include_meet": false}}

규칙:
- "내일"은 {tomorrow}
- "모레"는 현재 날짜 + 2일
- 종료 시간이 명시되지 않으면 시작 시간 + 1시간
- 시간이 명시되지 않으면 start_time을 null로 설정 (절대 임의로 시간을 넣지 마세요)
- "오후", "저녁" 같은 모호한 표현만 있고 구체적 시간이 없으면 start_time을 null로 설정
- "오후 N시"는 N+12시 (오후 3시 = 15:00)
- include_meet: "회의", "미팅", "meeting" 키워드가 있으면 true, 아니면 false
- 반드시 유효한 JSON만 출력하세요. 실제 날짜를 넣으세요."""

    user_prompt = f"일정 입력: {user_input}"
    result_str = await _call_llm(sys_prompt, user_prompt, json_mode=True)

    try:
        parsed = json.loads(result_str)
    except json.JSONDecodeError:
        logger.error(f"일정 파싱 실패 (JSON 에러): {result_str}")
        parsed = {}

    # LLM이 null로 반환한 경우 → 시간 불명확, 그대로 둠 (되물어보기 트리거)
    start_time = parsed.get("start_time")
    if start_time is None:
        # 제목이라도 있으면 그대로 반환 (되물어보기용)
        if parsed.get("title"):
            return parsed
        parsed = _fallback_parse(user_input, "")
        parsed["start_time"] = None
        return parsed

    # "YYYY" 같은 포맷 문자열이 들어왔거나 무효하면 직접 파싱
    if "YYYY" in str(start_time) or not _is_valid_datetime(str(start_time)):
        logger.warning("[ScheduleAgent] LLM 파싱 무효 (start_time='%s') → fallback", start_time)
        parsed = _fallback_parse(user_input, parsed.get("title", ""))

    return parsed


def _is_valid_datetime(s: str) -> bool:
    """ISO datetime 문자열 유효성 검사"""
    try:
        datetime.fromisoformat(s)
        return True
    except (ValueError, TypeError):
        return False


def _fallback_parse(user_input: str, title_hint: str = "") -> dict:
    """LLM 파싱 실패 시 규칙 기반 직접 파싱"""
    now = datetime.now()
    text = user_input

    # 제목 추출: 시간/날짜 관련 키워드 제거 후 남은 것
    title = title_hint
    if not title:
        # 간단한 제목 추출 — 시간/날짜 키워드 제거
        clean = re.sub(
            r'(내일|모레|오늘|다음\s*주|이번\s*주|오전|오후|저녁|아침|점심)'
            r'|\d{1,2}\s*시(\s*\d{1,2}\s*분)?'
            r'|잡아줘|등록해줘|추가해줘|넣어줘|만들어줘|해줘',
            '', text
        ).strip()
        title = clean if clean else "새 일정"

    # 날짜 추출
    if "모레" in text:
        date = now + timedelta(days=2)
    elif "내일" in text:
        date = now + timedelta(days=1)
    elif "오늘" in text:
        date = now
    else:
        date = now + timedelta(days=1)  # 기본: 내일

    # 시간 추출
    hour = None
    minute = 0
    time_match = re.search(r'(\d{1,2})\s*시\s*(\d{1,2}\s*분)?', text)
    if time_match:
        hour = int(time_match.group(1))
        if time_match.group(2):
            minute = int(time_match.group(2).replace('분', '').strip())

    # 오후 보정
    if hour is not None:
        if "오후" in text or "저녁" in text:
            if hour < 12:
                hour += 12
        elif "점심" in text:
            if hour < 12:
                hour = 12
    elif "점심" in text:
        hour = 12
    # "오후", "저녁" 등만 있고 구체적 시간 없으면 hour는 None 유지

    if hour is None:
        # 시간 불명확 → start_time을 None으로
        return {
            "title": title,
            "start_time": None,
            "end_time": None,
            "description": "",
            "include_meet": any(kw in text for kw in ("회의", "미팅", "meeting", "미트")),
        }

    start = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    end = start + timedelta(hours=1)

    # include_meet 판단
    include_meet = any(kw in text for kw in ("회의", "미팅", "meeting", "미트"))

    return {
        "title": title,
        "start_time": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "end_time": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "description": "",
        "include_meet": include_meet,
    }


def _check_missing_info(parsed: dict) -> list:
    """파싱 결과에서 누락된 필수 정보 확인"""
    missing = []
    start_time = parsed.get("start_time")

    # start_time이 null이거나 없으면 시간 누락
    if not start_time:
        missing.append("time")

    return missing


def _build_clarify_message(parsed: dict, missing: list) -> str:
    """누락 정보에 따른 되묻기 메시지 생성"""
    title = parsed.get("title", "일정")
    parts = []

    if "time" in missing:
        parts.append("몇 시에 잡을까요? (예: 오후 3시, 14:00)")

    msg = f"'{title}' 일정을 등록하려고 합니다.\n"
    msg += "\n".join(f"- {p}" for p in parts)
    return msg


async def _parse_view_request(user_input: str) -> dict:
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
    result_str = await _call_llm(sys_prompt, user_prompt, json_mode=True)

    try:
        return json.loads(result_str)
    except json.JSONDecodeError:
        logger.error(f"조회 범위 파싱 실패: {result_str}")
        return {}


async def _call_llm(sys_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
    """LLM 호출 (LLM Factory 사용 — 환경변수 LLM_PROVIDER로 Provider 선택)"""
    _t_llm = time.time()
    logger.debug("[ScheduleAgent] _call_llm | json_mode=%s", json_mode)
    try:
        from ai.llm import get_llm

        llm = get_llm()
        logger.debug("[ScheduleAgent] Provider: %s", llm.__class__.__name__)

        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=sys_prompt,
            temperature=0.3,
            json_mode=json_mode,
        )

        result = response.content
        logger.debug("[ScheduleAgent] LLM 응답 (%.2fs)", time.time() - _t_llm)
        return result

    except Exception as e:
        logger.error("[ScheduleAgent] _call_llm 에러: %s", e)
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

    include_meet = any(kw in user_prompt for kw in ("회의", "미팅", "meeting"))
    return json.dumps({
        "title": "회의 (Mock)",
        "start_time": tomorrow.strftime("%Y-%m-%dT14:00:00"),
        "end_time": tomorrow.strftime("%Y-%m-%dT15:00:00"),
        "description": "",
        "include_meet": include_meet,
    }, ensure_ascii=False)
