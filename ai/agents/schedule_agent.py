"""
일정/액션 Agent (팀원 D 담당)

기능:
  - 자연어 → 구조화 일정 데이터 파싱 (Solar API json_mode)
  - Google Calendar 일정 등록 + Meet 링크 (schedule_add)
  - Google Calendar 일정 조회 (schedule_view)
  - 참석자 이메일 초대 메일 발송 (schedule_followup)
  - 파이프라인 태스크 생성 (schedule_add → pipeline 서브타입)
  - 결재/승인 요청 생성 (schedule_add → approval 서브타입)

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
            # 키워드 기반 2차 분기: 일정 / 태스크 / 결재
            sub_type = _classify_add_type(user_input)
            if sub_type == "pipeline":
                response_data = await _handle_pipeline_create(user_input, user_id, user_team=state.get("user_team"))
            elif sub_type == "approval":
                response_data = await _handle_approval_create(user_input, user_id, user_team=state.get("user_team"))
            else:
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

    # 규정 검증: 일정/태스크/결재 추가 시 규정 위반 여부 체크
    _reg_types = ("schedule_add", "schedule_confirm", "pipeline_create", "approval_create")
    if response_data.get("type") in _reg_types:
        try:
            from ai.agents.regulation_checker import regulation_check
            resp_type = response_data["type"]
            if resp_type in ("schedule_add", "schedule_confirm"):
                sched = response_data.get("schedule", {})
                query = f"'{sched.get('title', '')}' 일정 등록이 내부 규정에 부합하는지 확인: {sched.get('description', '')} (일시: {sched.get('start_time', '')}~{sched.get('end_time', '')})"
            elif resp_type == "pipeline_create":
                task = response_data.get("task", {})
                query = f"'{task.get('title', '')}' 태스크가 내부 규정에 부합하는지 확인: {task.get('description', '')}"
            else:  # approval_create
                approval = response_data.get("approval", {})
                query = f"'{approval.get('title', '')}' 결재 요청이 내부 규정 절차에 부합하는지 확인: {approval.get('detail', '')}"
            reg_result = await regulation_check(query, user_id=user_id)
            if reg_result.get("checked") and reg_result.get("result") != "no_regulation":
                response_data["regulation_check"] = reg_result
                warnings = []
                if reg_result["result"] == "no":
                    warnings.append(f"규정 위반: {reg_result.get('reason', '')}")
                elif reg_result["result"] == "conditional":
                    warnings.append(f"조건부 허용: {reg_result.get('reason', '')}")
                if warnings:
                    response_data["warnings"] = warnings
        except Exception as e:
            logger.warning("[ScheduleAgent] 규정 체크 실패 (비차단): %s", e)

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

    return {
        "type": "schedule_confirm",
        "schedule": parsed,
        "message": f"'{parsed['title']}' 일정을 확인하고 등록해주세요.",
    }


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
            "schedule_type": parsed.get("schedule_type", "google"),
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
        "schedule_type": clarify_schedule.get("schedule_type", "google"),
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
    """일정 조회: LLM 파싱 → DB 조회(schedule_type 필터) + Google Calendar 조회"""
    # 1. LLM으로 조회 범위 + schedule_type 파싱
    logger.debug("[ScheduleAgent] schedule_view 파싱 시작")
    parsed = await _parse_view_request(user_input)
    schedule_type = parsed.get("schedule_type")
    logger.debug("[ScheduleAgent] schedule_view 파싱 결과: %s", parsed)

    import sys
    from pathlib import Path
    backend_path = str(Path(__file__).parent.parent.parent / "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    from app.db.session import async_session

    # 2. DB 조회 (schedule_type 필터 적용)
    db_events = []
    try:
        from app.services.schedule_service import list_schedules as db_list_schedules

        async with async_session() as db:
            db_schedules = await db_list_schedules(
                db, user_id=user_id, schedule_type=schedule_type
            )

        time_min = parsed.get("time_min")
        time_max = parsed.get("time_max")

        for s in db_schedules:
            # 기간 필터 적용
            if time_min and s.start_time:
                try:
                    t_min = datetime.fromisoformat(time_min.replace("Z", "+00:00")).replace(tzinfo=None)
                    if s.start_time < t_min:
                        continue
                except (ValueError, TypeError):
                    pass
            if time_max and s.start_time:
                try:
                    t_max = datetime.fromisoformat(time_max.replace("Z", "+00:00")).replace(tzinfo=None)
                    if s.start_time > t_max:
                        continue
                except (ValueError, TypeError):
                    pass
            db_events.append({
                "title": s.title,
                "start": s.start_time.isoformat() if s.start_time else "",
                "end": s.end_time.isoformat() if s.end_time else "",
                "schedule_type": s.schedule_type,
                "source": "db",
            })
    except Exception as e:
        logger.warning(f"DB 일정 조회 실패: {e}")

    # 3. Google Calendar 조회 + schedule_type 필터
    google_events = []
    try:
        from app.services.calendar_service import GoogleCalendarService

        calendar_service = GoogleCalendarService()
        async with async_session() as db:
            raw_events = await calendar_service.pull_events(
                db, user_id,
                time_min=parsed.get("time_min"),
                time_max=parsed.get("time_max"),
            )

        # schedule_type 필터: Google Calendar 이벤트는 제목 키워드로 판별
        _meeting_kw = ("회의", "미팅", "meeting", "스탠드업", "킥오프")
        _deadline_kw = ("마감", "데드라인", "deadline", "제출")

        db_titles = {e["title"] for e in db_events}
        for ev in raw_events:
            title = ev.get("title", "")
            if title in db_titles:
                continue  # DB에 이미 있는 것은 중복 제거
            if schedule_type == "meeting" and not any(kw in title for kw in _meeting_kw):
                continue
            if schedule_type == "deadline" and not any(kw in title for kw in _deadline_kw):
                continue
            google_events.append({**ev, "source": "google"})
    except Exception as e:
        logger.warning(f"Google Calendar 조회 실패: {e}")

    # 4. 합치기 + 시간순 정렬
    all_events = sorted(
        db_events + google_events,
        key=lambda e: e.get("start") or e.get("start_time") or "",
    )

    if not all_events:
        type_label = {"meeting": "회의", "deadline": "마감"}.get(schedule_type, "")
        msg_suffix = f" {type_label}" if type_label else ""
        return {
            "type": "schedule_view",
            "schedules": [],
            "message": f"해당 기간에 등록된{msg_suffix} 일정이 없습니다.",
        }

    # 5. 메시지 생성
    schedule_lines = []
    for ev in all_events[:10]:
        title = ev.get("title", "제목 없음")
        start_raw = ev.get("start") or ev.get("start_time") or ""
        try:
            start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00") if "Z" in start_raw else start_raw)
            start_display = start_dt.strftime("%m/%d %H:%M")
        except (ValueError, AttributeError):
            start_display = start_raw
        schedule_lines.append(f"- {title} ({start_display})")

    type_label = {"meeting": "회의", "deadline": "마감"}.get(schedule_type, "")
    header = f"총 {len(all_events)}개의{f' {type_label}' if type_label else ''} 일정이 있습니다.\n"
    message = header + "\n".join(schedule_lines)
    if len(all_events) > 10:
        message += f"\n... 외 {len(all_events) - 10}개"

    return {
        "type": "schedule_view",
        "schedules": all_events,
        "message": message,
    }


async def _parse_schedule_input(user_input: str) -> dict:
    """자연어 입력 → 일정 데이터 파싱 (Solar API json_mode → fallback: 직접 파싱)"""
    now = datetime.now()
    current_datetime = now.strftime("%Y-%m-%dT%H:%M:%S")
    current_weekday = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")

    # 이번 주 월요일, 저번 주 월요일 계산
    this_monday = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    next_monday = (now - timedelta(days=now.weekday()) + timedelta(weeks=1)).strftime("%Y-%m-%d")
    last_monday = (now - timedelta(days=now.weekday()) - timedelta(weeks=1)).strftime("%Y-%m-%d")
    current_hour_min = now.strftime("%H:%M")

    sys_prompt = f"""당신은 일정 파싱 전문가입니다. 사용자의 자연어 입력을 구조화된 일정 JSON으로 변환하세요.

현재 시각: {current_datetime} ({current_weekday}요일)
오늘 날짜: {today}
내일 날짜: {tomorrow}
이번 주 월요일: {this_monday}
다음 주 월요일: {next_monday}
저번 주 월요일: {last_monday}

반드시 실제 날짜와 시간을 계산하여 출력하세요. 절대로 "YYYY-MM-DD" 같은 형식 문자열을 출력하지 마세요.

예시:
입력: "내일 오후 3시 점심 회의"
출력: {{"title": "점심 회의", "start_time": "{tomorrow}T15:00:00", "end_time": "{tomorrow}T16:00:00", "description": "", "include_meet": true, "schedule_type": "meeting"}}

입력: "오늘 저녁 6시 팀 식사"
출력: {{"title": "팀 식사", "start_time": "{today}T18:00:00", "end_time": "{today}T19:00:00", "description": "", "include_meet": false, "schedule_type": "google"}}

입력: "다음주 금요일까지 보고서 마감"
출력: {{"title": "보고서 마감", "start_time": "...", "end_time": "...", "description": "", "include_meet": false, "schedule_type": "deadline"}}

규칙:
- "내일"은 {tomorrow}
- "모레"는 현재 날짜 + 2일
- "글피"는 현재 날짜 + 3일
- "N시간 뒤/후/있다가"는 현재 시각({current_hour_min})에서 +N시간 (예: 현재 14:30이고 "1시간 뒤" → 15:30)
- "N분 뒤/후"는 현재 시각에서 +N분
- "반시간 뒤/후"는 현재 시각에서 +30분
- "N일 뒤/후"는 오늘 + N일
- "이번주 X요일"은 이번 주 월요일({this_monday}) 기준으로 해당 요일 계산 (월=0, 화=1, 수=2, 목=3, 금=4, 토=5, 일=6)
- "다음주 X요일"은 다음 주 월요일({next_monday}) 기준으로 해당 요일 계산
- "저번주/지난주 X요일"은 저번 주 월요일({last_monday}) 기준으로 해당 요일 계산
- "이번 달 말"은 이번 달 마지막 날
- "다음 달 N일"은 다음 달 N일
- 종료 시간이 명시되지 않으면 시작 시간 + 1시간
- 시간이 명시되지 않으면 start_time을 null로 설정 (절대 임의로 시간을 넣지 마세요)
- "오후", "저녁" 같은 모호한 표현만 있고 구체적 시간이 없으면 start_time을 null로 설정
- "오후 N시"는 N+12시 (오후 3시 = 15:00)
- include_meet: "회의", "미팅", "meeting" 키워드가 있으면 true, 아니면 false
- schedule_type: "회의"/"미팅"/"meeting"/"스탠드업"/"킥오프" → "meeting", "마감"/"데드라인"/"deadline"/"제출" → "deadline", 그 외 → "google"
- 반드시 유효한 JSON만 출력하세요. 실제 날짜를 넣으세요."""

    user_prompt = f"일정 입력: {user_input}"
    result_str = await _call_llm(sys_prompt, user_prompt, json_mode=True)

    try:
        parsed = json.loads(result_str)
    except json.JSONDecodeError:
        logger.error(f"일정 파싱 실패 (JSON 에러): {result_str}")
        parsed = {}

    # LLM 반환값과 무관하게 user_input에서 schedule_type 확정
    valid_types = {"meeting", "deadline", "google"}
    if parsed.get("schedule_type") not in valid_types:
        _meeting_kw = ("회의", "미팅", "meeting", "스탠드업", "킥오프")
        _deadline_kw = ("마감", "데드라인", "deadline", "제출")
        if any(kw in user_input for kw in _meeting_kw):
            parsed["schedule_type"] = "meeting"
        elif any(kw in user_input for kw in _deadline_kw):
            parsed["schedule_type"] = "deadline"
        else:
            parsed["schedule_type"] = "meeting"

    # LLM이 title을 비워둔 경우, user_input에서 핵심어 추출
    if not parsed.get("title"):
        _t_clean = re.sub(
            r'(내일|모레|글피|오늘|다음\s*주|이번\s*주|저번\s*주|지난\s*주|오전|오후|저녁|아침|점심)'
            r'|\d{1,2}\s*시간?\s*(뒤|후|있다가|있다)|\d{1,2}\s*분\s*(뒤|후)'
            r'|반\s*시간\s*(뒤|후)|\d{1,2}\s*일\s*(뒤|후)|\d{1,2}\s*시(\s*\d{1,2}\s*분)?'
            r'|(월|화|수|목|금|토|일)\s*요일'
            r'|잡아줘|등록해줘|추가해줘|넣어줘|만들어줘|해줘|잡아|등록|추가|넣어|잡고'
            r'|비는\s*날에?|빈\s*날에?',
            '', user_input
        ).strip()
        _t_clean = re.sub(r'^에\s*', '', _t_clean).strip()
        if _t_clean:
            parsed["title"] = _t_clean

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

    WEEKDAY_MAP = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}

    # 제목 추출: 시간/날짜 관련 키워드 제거 후 남은 것
    title = title_hint
    if not title:
        clean = re.sub(
            r'(내일|모레|글피|오늘|다음\s*주|이번\s*주|저번\s*주|지난\s*주|오전|오후|저녁|아침|점심)'
            r'|\d{1,2}\s*시간?\s*(뒤|후|있다가|있다)'
            r'|\d{1,2}\s*분\s*(뒤|후)'
            r'|반\s*시간\s*(뒤|후)'
            r'|\d{1,2}\s*일\s*(뒤|후)'
            r'|\d{1,2}\s*시(\s*\d{1,2}\s*분)?'
            r'|(월|화|수|목|금|토|일)\s*요일'
            r'|잡아줘|등록해줘|추가해줘|넣어줘|만들어줘|해줘|에',
            '', text
        ).strip()
        title = clean if clean else "새 일정"

    # --- 상대 시간 (N시간 뒤, N분 뒤, 반시간 뒤) → 날짜+시간 동시 결정 ---
    use_relative_time = False

    # "반시간 뒤/후"
    half_hour_match = re.search(r'반\s*시간\s*(뒤|후|있다가|있다)', text)
    if half_hour_match:
        start = now + timedelta(minutes=30)
        start = start.replace(second=0, microsecond=0)
        use_relative_time = True

    # "N시간 뒤/후"
    if not use_relative_time:
        rel_hour_match = re.search(r'(\d{1,2})\s*시간\s*(뒤|후|있다가|있다)', text)
        if rel_hour_match:
            delta_hours = int(rel_hour_match.group(1))
            start = now + timedelta(hours=delta_hours)
            start = start.replace(second=0, microsecond=0)
            use_relative_time = True

    # "N분 뒤/후"
    if not use_relative_time:
        rel_min_match = re.search(r'(\d{1,2})\s*분\s*(뒤|후|있다가|있다)', text)
        if rel_min_match:
            delta_min = int(rel_min_match.group(1))
            start = now + timedelta(minutes=delta_min)
            start = start.replace(second=0, microsecond=0)
            use_relative_time = True

    if use_relative_time:
        end = start + timedelta(hours=1)
        meeting_kw = ("회의", "미팅", "meeting", "스탠드업", "킥오프")
        deadline_kw = ("마감", "데드라인", "deadline", "제출")
        if any(kw in text for kw in meeting_kw):
            schedule_type = "meeting"
        elif any(kw in text for kw in deadline_kw):
            schedule_type = "deadline"
        else:
            schedule_type = "google"
        include_meet = any(kw in text for kw in ("회의", "미팅", "meeting", "미트"))
        return {
            "title": title,
            "start_time": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "end_time": end.strftime("%Y-%m-%dT%H:%M:%S"),
            "description": "",
            "include_meet": include_meet,
            "schedule_type": schedule_type,
        }

    # --- 날짜 추출 ---
    date = None

    # "N일 뒤/후"
    n_days_match = re.search(r'(\d{1,3})\s*일\s*(뒤|후)', text)
    if n_days_match:
        date = now + timedelta(days=int(n_days_match.group(1)))

    # "글피" (모레 다음날)
    if date is None and "글피" in text:
        date = now + timedelta(days=3)
    elif date is None and "모레" in text:
        date = now + timedelta(days=2)
    elif date is None and "내일" in text:
        date = now + timedelta(days=1)
    elif date is None and "오늘" in text:
        date = now

    # "이번주/다음주/저번주/지난주 X요일"
    if date is None:
        week_day_match = re.search(
            r'(이번\s*주|다음\s*주|저번\s*주|지난\s*주|차주)?\s*(월|화|수|목|금|토|일)\s*요일',
            text
        )
        if week_day_match:
            week_prefix = week_day_match.group(1) or ""
            target_weekday = WEEKDAY_MAP[week_day_match.group(2)]
            this_monday = now - timedelta(days=now.weekday())
            if "다음" in week_prefix or "차주" in week_prefix:
                base_monday = this_monday + timedelta(weeks=1)
            elif "저번" in week_prefix or "지난" in week_prefix:
                base_monday = this_monday - timedelta(weeks=1)
            else:
                base_monday = this_monday
            date = base_monday + timedelta(days=target_weekday)

    # 기본값: 내일
    if date is None:
        date = now + timedelta(days=1)

    # --- 시간 추출 ---
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

    # schedule_type 추론
    meeting_kw = ("회의", "미팅", "meeting", "스탠드업", "킥오프")
    deadline_kw = ("마감", "데드라인", "deadline", "제출")
    if any(kw in text for kw in meeting_kw):
        schedule_type = "meeting"
    elif any(kw in text for kw in deadline_kw):
        schedule_type = "deadline"
    else:
        schedule_type = "google"

    include_meet = any(kw in text for kw in ("회의", "미팅", "meeting", "미트"))

    if hour is None:
        return {
            "title": title,
            "start_time": None,
            "end_time": None,
            "description": "",
            "include_meet": include_meet,
            "schedule_type": schedule_type,
        }

    start = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    end = start + timedelta(hours=1)

    return {
        "title": title,
        "start_time": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "end_time": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "description": "",
        "include_meet": include_meet,
        "schedule_type": schedule_type,
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
    """자연어 입력 → 조회 범위 + schedule_type 파싱 (Solar API json_mode)"""
    now = datetime.now()
    current_datetime = now.strftime("%Y-%m-%dT%H:%M:%S")
    current_weekday = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]

    this_monday = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    next_monday = (now - timedelta(days=now.weekday()) + timedelta(weeks=1)).strftime("%Y-%m-%d")
    last_monday = (now - timedelta(days=now.weekday()) - timedelta(weeks=1)).strftime("%Y-%m-%d")

    sys_prompt = f"""당신은 일정 조회 범위 파싱 전문가입니다. 사용자의 자연어 입력에서 조회 기간과 일정 유형을 추출하세요.

현재 시각: {current_datetime} ({current_weekday}요일)
이번 주 월요일: {this_monday}
다음 주 월요일: {next_monday}
저번 주 월요일: {last_monday}

출력 형식(JSON):
{{
    "time_min": "YYYY-MM-DDTHH:MM:SSZ",
    "time_max": "YYYY-MM-DDTHH:MM:SSZ",
    "schedule_type": null
}}

규칙:
- "오늘 일정" → 오늘 00:00:00Z ~ 오늘 23:59:59Z
- "내일 일정" → 내일 00:00:00Z ~ 내일 23:59:59Z
- "이번 주 일정" → 이번 주 월요일({this_monday}) 00:00:00Z ~ 일요일 23:59:59Z
- "다음 주 일정" → 다음 주 월요일({next_monday}) 00:00:00Z ~ 일요일 23:59:59Z
- "저번 주/지난 주 일정" → 저번 주 월요일({last_monday}) 00:00:00Z ~ 일요일 23:59:59Z
- "이번 달 일정" → 이번 달 1일 00:00:00Z ~ 말일 23:59:59Z
- "저번 달/지난 달 일정" → 지난 달 1일 00:00:00Z ~ 말일 23:59:59Z
- "다음 달 일정" → 다음 달 1일 00:00:00Z ~ 말일 23:59:59Z
- "최근 일정", "일정 조회" 등 명확하지 않으면 → 오늘 00:00:00Z ~ 오늘로부터 +30일 23:59:59Z (향후 한 달)
- 시간대는 UTC(Z) 형식으로 출력 (한국시간 KST = UTC+9 이므로 -9시간 보정)
- schedule_type: "회의"/"미팅"/"meeting"/"스탠드업"/"킥오프" → "meeting", "마감"/"데드라인"/"deadline"/"제출" → "deadline", 특정 유형 언급 없으면 → null
- 반드시 유효한 JSON만 출력하세요"""

    user_prompt = f"조회 요청: {user_input}"
    result_str = await _call_llm(sys_prompt, user_prompt, json_mode=True)

    try:
        parsed = json.loads(result_str)
    except json.JSONDecodeError:
        logger.error(f"조회 범위 파싱 실패: {result_str}")
        parsed = {}

    # LLM 결과와 무관하게 키워드로 schedule_type 재확인
    if not parsed.get("schedule_type"):
        _meeting_kw = ("회의", "미팅", "meeting", "스탠드업", "킥오프")
        _deadline_kw = ("마감", "데드라인", "deadline", "제출")
        if any(kw in user_input for kw in _meeting_kw):
            parsed["schedule_type"] = "meeting"
        elif any(kw in user_input for kw in _deadline_kw):
            parsed["schedule_type"] = "deadline"

    return parsed


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


# ── 키워드 기반 2차 분류 (schedule_add → 일정/태스크/결재) ──


_PIPELINE_KEYWORDS = ("태스크", "task", "파이프라인", "pipeline", "칸반", "보드", "프로젝트 추가", "프로젝트 생성")
_APPROVAL_KEYWORDS = ("결재", "승인", "연차", "휴가", "반차", "조퇴", "병가", "품의", "출장 신청", "출장신청")


def _classify_add_type(user_input: str) -> str:
    """schedule_add intent 내에서 일정/태스크/결재 서브타입 분류"""
    text = user_input.lower()
    if any(kw in text for kw in _PIPELINE_KEYWORDS):
        return "pipeline"
    if any(kw in text for kw in _APPROVAL_KEYWORDS):
        return "approval"
    return "schedule"


# ── Pipeline Task 생성 (action_agent에서 통합) ──


async def _handle_pipeline_create(user_input: str, user_id: int, user_team: str | None = None) -> dict:
    """파이프라인 태스크 생성: LLM 파싱 → DB 저장"""
    parsed = await _parse_pipeline_input(user_input)
    logger.info("[ScheduleAgent] pipeline 파싱 결과: %s", parsed)

    if not parsed.get("title"):
        return {
            "type": "pipeline_create",
            "message": "태스크 제목을 파악하지 못했습니다. 다시 입력해주세요.",
        }

    import sys
    from pathlib import Path
    backend_path = str(Path(__file__).parent.parent.parent / "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    from app.db.session import async_session
    from app.models.pipeline_task import PipelineTask

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
        logger.error("[ScheduleAgent] pipeline 파싱 실패: %s", result_str)
        parsed = _fallback_parse_pipeline(user_input)

    valid_stages = {"todo", "in_progress", "review", "done"}
    if parsed.get("stage") not in valid_stages:
        parsed["stage"] = "todo"

    valid_priorities = {"high", "medium", "low"}
    if parsed.get("priority") not in valid_priorities:
        parsed["priority"] = "medium"

    return parsed


def _fallback_parse_pipeline(user_input: str) -> dict:
    """LLM 파싱 실패 시 규칙 기반 파싱"""
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


# ── Approval 결재 요청 생성 (action_agent에서 통합) ──


async def _handle_approval_create(user_input: str, user_id: int, user_team: str | None = None) -> dict:
    """결재/승인 요청 생성: LLM 파싱 → DB 저장"""
    parsed = await _parse_approval_input(user_input)
    logger.info("[ScheduleAgent] approval 파싱 결과: %s", parsed)

    if not parsed.get("title"):
        return {
            "type": "approval_create",
            "message": "결재 요청 제목을 파악하지 못했습니다. 다시 입력해주세요.",
        }

    import sys
    from pathlib import Path
    backend_path = str(Path(__file__).parent.parent.parent / "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

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
        logger.error("[ScheduleAgent] approval 파싱 실패: %s", result_str)
        parsed = _fallback_parse_approval(user_input)

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
    approval_type = _infer_approval_type(user_input)

    type_titles = {
        "leave": "연차 신청",
        "review": "리뷰 요청",
        "budget": "예산 신청",
        "business_trip": "출장 신청",
        "general": "결재 요청",
    }
    title = type_titles.get(approval_type, "결재 요청")

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
