"""문서 생성 후 action_items → 일정 제안 추출

doc_generate 응답에서 기한이 있는 항목을 ScheduleCreate 호환 형태로 변환한다.
실패해도 기존 기능에 영향 없음 (호출부에서 try/except 비차단 처리).
"""
import logging
import re
from datetime import date, datetime

logger = logging.getLogger(__name__)


def extract_suggested_schedules(response_data: dict) -> list[dict]:
    """doc_generate 응답에서 일정 제안 데이터를 추출한다.

    Args:
        response_data: doc_generate agent_response dict.
            - data.action_items (회의록): [{"task", "assignee", "due_date"}]
            - data.tasks (보고서): [{"item", "assignee", "end_date"}]

    Returns:
        ScheduleCreate 호환 dict 리스트. 빈 리스트이면 프론트에서 제안 UI 미표시.
    """
    template_type = response_data.get("template_type", "")
    data = response_data.get("data") or {}
    doc_title = data.get("title", "문서")

    items: list[dict] = []

    if template_type == "meeting_minutes":
        items = _extract_from_meeting_minutes(data, doc_title)
    elif template_type == "report":
        items = _extract_from_report(data, doc_title)
    # proposal: phase 기반이라 1차 범위에서 제외

    if items:
        logger.info(
            "[ScheduleSuggest] %s에서 %d건 일정 제안 추출 (template=%s)",
            doc_title, len(items), template_type,
        )

    return items


def _extract_from_meeting_minutes(data: dict, doc_title: str) -> list[dict]:
    """회의록 action_items에서 due_date가 있는 항목 추출."""
    action_items = data.get("action_items", [])
    if not isinstance(action_items, list):
        return []

    results = []
    for idx, item in enumerate(action_items):
        if not isinstance(item, dict):
            continue

        task = item.get("task", "").strip()
        assignee = item.get("assignee", "").strip()
        due_date_str = item.get("due_date", "").strip()

        if not task or not due_date_str:
            continue

        parsed = _parse_date(due_date_str)
        if parsed is None:
            continue

        desc_parts = []
        if assignee:
            desc_parts.append(f"담당: {assignee}")
        desc_parts.append(f"출처: {doc_title}")

        results.append({
            "title": task,
            "description": " | ".join(desc_parts),
            "start_time": _to_iso(parsed, hour=9),
            "end_time": _to_iso(parsed, hour=10),
            "schedule_type": "task",
            "priority": _calc_priority(parsed),
            "source": "action_item",
            "original_index": idx,
        })

    return results


def _extract_from_report(data: dict, doc_title: str) -> list[dict]:
    """보고서 tasks에서 end_date가 있는 항목 추출."""
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        return []

    results = []
    for idx, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue

        item_name = task.get("item", "").strip()
        assignee = task.get("assignee", "").strip()
        end_date_str = task.get("end_date", "").strip()

        if not item_name or not end_date_str:
            continue

        parsed = _parse_date(end_date_str)
        if parsed is None:
            continue

        desc_parts = []
        if assignee:
            desc_parts.append(f"담당: {assignee}")
        desc_parts.append(f"출처: {doc_title}")

        results.append({
            "title": item_name,
            "description": " | ".join(desc_parts),
            "start_time": _to_iso(parsed, hour=9),
            "end_time": _to_iso(parsed, hour=10),
            "schedule_type": "task",
            "priority": _calc_priority(parsed),
            "source": "report_task",
            "original_index": idx,
        })

    return results


# ── 날짜 파싱 ──

# 패턴: "2026-03-28", "2026.03.28", "2026/03/28"
_DATE_FULL_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
# 패턴: "3월 28일", "3월28일"
_DATE_KR_RE = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
# 패턴: "3/28", "03-28" (연도 없음)
_DATE_SHORT_RE = re.compile(r"^(\d{1,2})[/\-](\d{1,2})$")


def _parse_date(s: str) -> date | None:
    """다양한 날짜 문자열을 date 객체로 파싱. 실패 시 None."""
    s = s.strip()
    if not s:
        return None

    # "2026-03-28" / "2026.03.28"
    m = _DATE_FULL_RE.search(s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    # "3월 28일"
    m = _DATE_KR_RE.search(s)
    if m:
        try:
            return date(date.today().year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None

    # "3/28"
    m = _DATE_SHORT_RE.search(s)
    if m:
        try:
            return date(date.today().year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None

    return None


def _to_iso(d: date, hour: int = 9) -> str:
    """date → ISO datetime 문자열 (기본 시간 적용)."""
    return datetime(d.year, d.month, d.day, hour, 0, 0).isoformat()


def _calc_priority(due: date) -> str:
    """기한까지 남은 일수 기반 우선순위 계산."""
    days_left = (due - date.today()).days
    if days_left <= 1:
        return "high"
    if days_left <= 3:
        return "medium"
    return "low"
