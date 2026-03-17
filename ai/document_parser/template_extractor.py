"""
DOCX 양식 필드 추출기 (규칙 기반, LLM 불필요)

회의록/보고서/제안서 등 DOCX 양식 파일을 분석하여
필드 명세(parsed_structure)를 자동 생성한다.

추출 규칙:
  1. 테이블 첫 번째 열 → 필드명 (일시, 장소, 참석자 등)
  2. 헤딩(Heading 1~3) → 섹션 필드명 (회의 내용, 결정 사항 등)
  3. 한국어 필드명 → 영어 키 + 설명 매핑

사용법:
    from ai.document_parser.template_extractor import extract_template_fields
    fields = extract_template_fields("회의록_양식.docx")
    # [{"key": "date", "label": "일시", "description": "회의 날짜 (YYYY-MM-DD 형식)"}, ...]
"""
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 한국어 → 영어 키 매핑 ──
# 회의록/보고서/제안서에서 자주 사용되는 필드명

FIELD_MAPPING = {
    # 공통
    "제목": {"key": "title", "desc": "문서 제목"},
    "일시": {"key": "date", "desc": "날짜 (YYYY-MM-DD 형식, 없으면 오늘 날짜)"},
    "날짜": {"key": "date", "desc": "날짜 (YYYY-MM-DD 형식, 없으면 오늘 날짜)"},
    "일자": {"key": "date", "desc": "날짜 (YYYY-MM-DD 형식, 없으면 오늘 날짜)"},
    "작성일": {"key": "date", "desc": "작성 날짜 (YYYY-MM-DD 형식)"},
    "작성자": {"key": "author", "desc": "작성자 이름 (없으면 빈 문자열)"},

    # 회의록
    "참석자": {"key": "attendees", "desc": "참석자 이름 배열 (없으면 빈 배열)"},
    "참석인원": {"key": "attendees", "desc": "참석자 이름 배열 (없으면 빈 배열)"},
    "회의참석자": {"key": "attendees", "desc": "참석자 이름 배열 (없으면 빈 배열)"},
    "장소": {"key": "location", "desc": "회의 장소 (없으면 빈 문자열)"},
    "회의장소": {"key": "location", "desc": "회의 장소 (없으면 빈 문자열)"},
    "회의명": {"key": "title", "desc": "회의 주제를 반영한 구체적인 제목"},
    "회의주제": {"key": "title", "desc": "회의 주제를 반영한 구체적인 제목"},
    "회의유형": {"key": "meeting_type", "desc": "회의 유형 ('정기', '비정기', '긴급' 중 하나)"},
    "회의종류": {"key": "meeting_type", "desc": "회의 유형 ('정기', '비정기', '긴급' 중 하나)"},
    "시간": {"key": "time", "desc": "회의 시간 (예: '14:00~15:30')"},
    "회의시간": {"key": "time", "desc": "회의 시간 (예: '14:00~15:30')"},
    "진행자": {"key": "moderator", "desc": "진행자/사회자 이름 (없으면 빈 문자열)"},
    "사회자": {"key": "moderator", "desc": "진행자/사회자 이름 (없으면 빈 문자열)"},
    "안건": {"key": "agenda", "desc": "회의 안건 목록 (배열)"},
    "회의안건": {"key": "agenda", "desc": "회의 안건 목록 (배열)"},
    "회의내용": {"key": "content", "desc": "회의 내용을 상세하게 기술"},
    "논의내용": {"key": "content", "desc": "회의 내용을 상세하게 기술"},
    "논의사항": {"key": "content", "desc": "회의 내용을 상세하게 기술"},
    "주요내용": {"key": "content", "desc": "주요 내용을 상세하게 기술"},
    "요약": {"key": "summary", "desc": "주요 내용을 3~5문장으로 요약"},
    "회의요약": {"key": "summary", "desc": "회의에서 논의된 주요 내용을 3~5문장으로 요약"},
    "결정사항": {"key": "decisions", "desc": "결정된 사항 목록 (배열, 없으면 빈 배열)"},
    "결정된사항": {"key": "decisions", "desc": "결정된 사항 목록 (배열, 없으면 빈 배열)"},
    "의결사항": {"key": "decisions", "desc": "결정된 사항 목록 (배열, 없으면 빈 배열)"},
    "후속조치": {"key": "action_items", "desc": '후속 조치 목록 배열. 각 항목은 {"content": "내용", "assignee": "담당자", "due_date": "기한"} 형태'},
    "실행계획": {"key": "action_items", "desc": '후속 조치 목록 배열. 각 항목은 {"content": "내용", "assignee": "담당자", "due_date": "기한"} 형태'},
    "조치사항": {"key": "action_items", "desc": '후속 조치 목록 배열. 각 항목은 {"task": "할 일", "assignee": "담당자", "due_date": "기한"} 형태'},
    "ActionItem": {"key": "action_items", "desc": '후속 조치 목록 배열. 각 항목은 {"task": "할 일", "assignee": "담당자", "due_date": "기한"} 형태'},
    "다음회의": {"key": "next_meeting", "desc": "다음 회의 일정 (없으면 빈 문자열)"},
    "차기회의": {"key": "next_meeting", "desc": "다음 회의 일정 (없으면 빈 문자열)"},
    "비고": {"key": "notes", "desc": "비고 사항 (없으면 빈 문자열)"},
    "특이사항": {"key": "notes", "desc": "비고 사항 (없으면 빈 문자열)"},
    "비고다음회의일정": {"key": "notes", "desc": "비고 및 다음 회의 일정 (없으면 빈 문자열)"},
    "회의목적": {"key": "meeting_purpose", "desc": "회의 목적 (1~2문장)"},
    "목적": {"key": "meeting_purpose", "desc": "회의/업무 목적 (1~2문장)"},

    # 보고서
    "부서": {"key": "department", "desc": "부서명 (없으면 빈 문자열)"},
    "부서명": {"key": "department", "desc": "부서명 (없으면 빈 문자열)"},
    "소속": {"key": "department", "desc": "부서명 (없으면 빈 문자열)"},
    "직급": {"key": "position", "desc": "직급 (없으면 빈 문자열)"},
    "직위": {"key": "position", "desc": "직급 (없으면 빈 문자열)"},
    "보고대상": {"key": "report_to", "desc": "보고 대상 (없으면 빈 문자열)"},
    "수신": {"key": "report_to", "desc": "보고 대상 (없으면 빈 문자열)"},
    "보고유형": {"key": "report_type", "desc": "'일일', '주간', '월간', '수시' 중 하나"},
    "보고종류": {"key": "report_type", "desc": "'일일', '주간', '월간', '수시' 중 하나"},
    "보고기간": {"key": "period", "desc": "보고 기간 (예: '2026년 3월 1주차')"},
    "기간": {"key": "period", "desc": "기간 (예: '2026년 3월 ~ 6월')"},
    "개요": {"key": "overview", "desc": "업무 내용을 요약한 보고 개요 (3~5문장)"},
    "보고개요": {"key": "overview", "desc": "업무 내용을 요약한 보고 개요 (3~5문장)"},
    "업무내용": {"key": "main_content", "desc": "업무 세부 내용을 항목별로 구체적으로 작성"},
    "세부내용": {"key": "main_content", "desc": "세부 내용을 항목별로 구체적으로 작성"},
    "상세내용": {"key": "main_content", "desc": "세부 내용을 항목별로 구체적으로 작성"},
    "진행업무": {"key": "tasks", "desc": '진행 업무 목록 배열. 각 항목은 {"item": "업무명", "assignee": "담당자", "progress": "진행률", "start_date": "시작일", "end_date": "종료일"} 형태'},
    "업무목록": {"key": "tasks", "desc": '진행 업무 목록 배열. 각 항목은 {"item": "업무명", "assignee": "담당자", "progress": "진행률", "start_date": "시작일", "end_date": "종료일"} 형태'},
    "성과": {"key": "achievements", "desc": "주요 성과 목록 (배열)"},
    "주요성과": {"key": "achievements", "desc": "주요 성과 목록 (배열)"},
    "이슈": {"key": "issues", "desc": "이슈 및 건의사항 (없으면 빈 문자열)"},
    "이슈사항": {"key": "issues", "desc": "이슈 및 건의사항 (없으면 빈 문자열)"},
    "건의사항": {"key": "issues", "desc": "이슈 및 건의사항 (없으면 빈 문자열)"},
    "향후계획": {"key": "next_plan", "desc": "향후 계획 (구체적으로 작성)"},
    "차주계획": {"key": "next_plan", "desc": "향후 계획 (구체적으로 작성)"},
    "결론": {"key": "conclusion", "desc": "결론 및 종합 의견"},

    # 제안서
    "제출일": {"key": "submit_date", "desc": "제출 날짜 (YYYY-MM-DD, 없으면 오늘 날짜)"},
    "제출처": {"key": "submit_to", "desc": "제출처 (없으면 빈 문자열)"},
    "제안사": {"key": "company", "desc": "제안사 이름 (없으면 빈 문자열)"},
    "회사명": {"key": "company", "desc": "회사 이름 (없으면 빈 문자열)"},
    "담당자": {"key": "manager", "desc": "담당자 이름 (없으면 빈 문자열)"},
    "연락처": {"key": "contact", "desc": "연락처 (없으면 빈 문자열)"},
    "제안배경": {"key": "background", "desc": "제안 배경 (2~3문장)"},
    "배경": {"key": "background", "desc": "배경 (2~3문장)"},
    "제안목적": {"key": "purpose", "desc": "제안 목적 및 필요성 (3~5문장)"},
    "제안내용": {"key": "content", "desc": "제안 내용을 항목별로 구체적으로 작성"},
    "추진일정": {"key": "schedule", "desc": '추진 일정 배열. 각 항목은 {"item": "추진항목", "phase1": "1단계 내용", "phase2": "2단계 내용", "phase3": "3단계 내용", "phase4": "4단계 내용"} 형태'},
    "일정": {"key": "schedule", "desc": '추진 일정 배열. 각 항목은 {"item": "추진항목", "phase1": "1단계 내용", "phase2": "2단계 내용", "phase3": "3단계 내용", "phase4": "4단계 내용"} 형태'},
    "예산": {"key": "budget", "desc": '예산 배열. 각 항목은 {"item": "항목", "quantity": "수량", "unit_price": "단가", "amount": "금액"} 형태'},
    "소요예산": {"key": "budget", "desc": '예산 배열. 각 항목은 {"item": "항목", "quantity": "수량", "unit_price": "단가", "amount": "금액"} 형태'},
    "기대효과": {"key": "expected_effect", "desc": "기대 효과 (3~5문장)"},
    "리스크": {"key": "risks", "desc": '리스크 목록 배열. 각 항목은 {"description": "설명", "level": "상/중/하", "mitigation": "대응방안"} 형태'},
    "위험요소": {"key": "risks", "desc": '리스크 목록 배열. 각 항목은 {"description": "설명", "level": "상/중/하", "mitigation": "대응방안"} 형태'},
}


def _normalize_label(text: str) -> str:
    """필드 레이블 정규화: 공백/특수문자 제거, 소문자화"""
    text = re.sub(r"[\s·:：\-_/()（）\[\]【】]", "", text)
    return text.strip()


def _match_field(label: str) -> dict | None:
    """한국어 레이블 → 매핑된 필드 반환"""
    normalized = _normalize_label(label)
    if not normalized:
        return None

    # 정확히 매핑 테이블에 있는지
    if normalized in FIELD_MAPPING:
        mapping = FIELD_MAPPING[normalized]
        return {"key": mapping["key"], "label": label.strip(), "description": mapping["desc"]}

    # 부분 매칭 (예: "회의 일시" → "일시")
    for map_key, mapping in FIELD_MAPPING.items():
        if map_key in normalized or normalized in map_key:
            return {"key": mapping["key"], "label": label.strip(), "description": mapping["desc"]}

    return None


def extract_template_fields(file_path: str) -> list[dict]:
    """
    DOCX 양식에서 필드 명세를 추출한다.

    Args:
        file_path: DOCX 파일 경로

    Returns:
        필드 목록: [{"key": "date", "label": "일시", "description": "날짜 (YYYY-MM-DD)"}, ...]
    """
    from docx import Document

    doc = Document(file_path)
    fields = []
    seen_keys = set()

    def _add_field(field: dict):
        if field and field["key"] not in seen_keys:
            seen_keys.add(field["key"])
            fields.append(field)

    # 1. 테이블에서 필드 추출
    for table in doc.tables:
        rows = table.rows
        num_cols = len(table.columns) if table.columns else 0

        for ri, row in enumerate(rows):
            cells = [cell.text.strip() for cell in row.cells]

            # 1-a. 다열 테이블: 첫 번째 열 = 필드명
            if len(cells) >= 2 and cells[0]:
                label = cells[0]
                if len(label) <= 20:
                    field = _match_field(label)
                    _add_field(field)

            # 1-b. 1열 섹션 테이블: 첫 행이 섹션 헤더, 두 번째 행이 값 영역
            #      예: [회의 내용] / [빈칸],  [결정 사항] / [빈칸]
            elif num_cols == 1 and ri == 0 and cells[0]:
                label = cells[0]
                # 공백 제거 후 매칭 (예: "비고 / 다음 회의 일정")
                normalized = re.sub(r'\s+', '', label)
                if len(normalized) <= 20:
                    field = _match_field(label)
                    _add_field(field)

        # 1-c. 다열 테이블의 첫 행이 병합 헤더인 경우 (Action Item 등)
        if len(rows) >= 2 and num_cols > 1:
            first_cells = [cell.text.strip() for cell in rows[0].cells]
            # 모든 셀이 같은 텍스트 = 병합된 섹션 헤더
            unique_texts = set(first_cells)
            if len(unique_texts) == 1 and first_cells[0]:
                label = first_cells[0]
                if len(label) <= 20:
                    field = _match_field(label)
                    _add_field(field)

    # 2. 헤딩에서 필드 추출
    for para in doc.paragraphs:
        style_name = para.style.name if para.style else ""
        text = para.text.strip()

        if not text or len(text) > 30:
            continue

        if "Heading" in style_name or style_name.startswith("제목"):
            field = _match_field(text)
            _add_field(field)

    # 3. 본문에서 "항목명:" 패턴 추출 (예: "결정사항:")
    for para in doc.paragraphs:
        text = para.text.strip()
        match = re.match(r"^([가-힣]{2,10})\s*[:：]\s*$", text)
        if match:
            label = match.group(1)
            field = _match_field(label)
            _add_field(field)

    logger.info("양식 필드 추출 완료: %s → %d개 필드", file_path, len(fields))
    return fields


def fields_to_parsed_structure(fields: list[dict]) -> str:
    """추출된 필드를 parsed_structure JSON 문자열로 변환 (DB 저장용)"""
    return json.dumps(fields, ensure_ascii=False)


def fields_to_prompt(fields: list[dict]) -> str:
    """추출된 필드를 [필드 명세] 프롬프트 문자열로 변환 (sLLM 호출용)"""
    lines = []
    for f in fields:
        desc = f.get('description') or f.get('label', f['key'])
        lines.append(f"- {f['key']}: {desc}")
    return "\n".join(lines)
