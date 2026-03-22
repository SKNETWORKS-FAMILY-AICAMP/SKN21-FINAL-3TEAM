"""
범용 커스텀 양식 DOCX 빌더

업로드된 원본 DOCX 양식을 열어서, LLM이 생성한 데이터를 필드에 채워넣는다.
- 테이블 셀: 필드명(라벨) 옆 빈 셀에 값 주입
- 본문: "필드명:" 패턴 아래 빈 줄에 값 주입
- 원본 양식이 없으면 범용 레이아웃으로 새로 생성
"""
import json
import re
from pathlib import Path

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


# ── 필드명 매칭 (한글 라벨 → 데이터 key) ──
_LABEL_TO_KEY = {
    # 제목
    "제목": "title", "회의제목": "title", "회의 제목": "title",
    "보고서제목": "title", "보고서 제목": "title",
    "제안서제목": "title", "제안서 제목": "title", "문서제목": "title", "문서 제목": "title",
    "회의안건": "title", "안건": "title", "주제": "title", "회의주제": "title",
    # 날짜/시간
    "날짜": "date", "일시": "date", "작성일": "date", "회의날짜": "date", "회의 날짜": "date",
    "제출일": "date", "회의일시": "date", "회의 일시": "date",
    "시간": "time", "회의시간": "time", "회의 시간": "time",
    # 참석자
    "참석자": "attendees", "참석인원": "attendees", "참석 인원": "attendees",
    "회의자": "attendees", "참여자": "attendees",
    # 작성자/담당자
    "작성자": "author", "담당자": "manager", "기록자": "author",
    # 팀/부서
    "팀": "team", "부서": "department", "소속": "department",
    # 장소
    "장소": "location", "회의장소": "location", "회의 장소": "location",
    # 내용
    "내용": "content", "회의내용": "content", "회의 내용": "content",
    "업무내용": "content", "업무 내용": "content",
    "제안내용": "content", "제안 내용": "content",
    "주요내용": "content", "주요 내용": "content",
    "보고내용": "content", "보고 내용": "content",
    # 요약
    "요약": "summary", "개요": "overview",
    # 결정사항
    "결정사항": "decisions", "결정 사항": "decisions",
    # 기타
    "비고": "notes", "특이사항": "notes", "특이 사항": "notes",
    "다음회의일정": "notes", "다음 회의 일정": "notes",
    "비고/다음회의일정": "notes", "비고 / 다음 회의 일정": "notes",
    "회의유형": "meeting_type", "회의 유형": "meeting_type",
    "목적": "purpose", "배경": "background",
    "기대효과": "expected_effect", "기대 효과": "expected_effect",
    "진행일정": "schedule", "일정": "schedule",
}


def _normalize_label(text: str) -> str | None:
    """라벨 텍스트를 데이터 key로 변환 (공백 제거 후 매칭)"""
    text = text.strip().rstrip(":：")
    # 먼저 원본으로 매칭
    if text in _LABEL_TO_KEY:
        return _LABEL_TO_KEY[text]
    # 모든 공백 제거 후 매칭 (양식 3처럼 "참  석  인  원" → "참석인원")
    collapsed = re.sub(r'\s+', '', text)
    if collapsed in _LABEL_TO_KEY:
        return _LABEL_TO_KEY[collapsed]
    # 공백 1개로 통일 후 매칭
    single_space = re.sub(r'\s+', ' ', text)
    if single_space in _LABEL_TO_KEY:
        return _LABEL_TO_KEY[single_space]
    return None


def _format_value(val) -> str:
    """데이터 값을 문자열로 변환"""
    if val is None:
        return ""
    if isinstance(val, list):
        parts = []
        for item in val:
            if isinstance(item, dict):
                parts.append(", ".join(f"{k}: {v}" for k, v in item.items() if v))
            else:
                parts.append(str(item))
        return "\n".join(parts) if parts else ""
    if isinstance(val, dict):
        return "\n".join(f"{k}: {v}" for k, v in val.items() if v)
    return str(val)


def _inject_cell_text(cell, text: str):
    """셀에 데이터 주입 (기존 내용 대체)"""
    for para in cell.paragraphs:
        for run in para.runs:
            run.clear()
    cell.text = str(text) if text else ""
    para = cell.paragraphs[0]
    if para.runs:
        para.runs[0].font.size = Pt(10)


def _inject_array_to_table(table, header_row_idx: int, items: list[dict]) -> bool:
    """배열 데이터를 테이블 데이터 행에 분배 주입.

    구조: header_row(병합) → column_header_row → data_rows
    items의 각 dict 값을 data_rows 셀에 순서대로 넣는다.
    """
    rows = table.rows
    # 헤더 다음 행이 컬럼 헤더인지 확인
    col_header_idx = header_row_idx + 1
    if col_header_idx >= len(rows):
        return False

    # 데이터 행 시작: 컬럼 헤더 다음
    data_start = col_header_idx + 1
    if data_start >= len(rows):
        return False

    # 컬럼 헤더에서 키 매핑 추출 (No., 추진 항목, 1단계, ...)
    col_headers = [c.text.strip() for c in rows[col_header_idx].cells]

    for item_idx, item in enumerate(items):
        row_idx = data_start + item_idx
        if row_idx >= len(rows):
            break  # 테이블 행이 부족하면 거기까지만

        row_cells = rows[row_idx].cells
        vals = list(item.values())

        for ci in range(len(row_cells)):
            if ci == 0:
                # No. 열: 번호
                _inject_cell_text(row_cells[ci], str(item_idx + 1))
            elif ci - 1 < len(vals):
                _inject_cell_text(row_cells[ci], str(vals[ci - 1]) if vals[ci - 1] else "")

    return True


def _find_data_key(cell_text: str, data: dict) -> str | None:
    """셀 텍스트에서 data 키를 찾는다. 추출 시와 동일한 정규화 적용."""
    from ai.document_parser.template_extractor import _normalize_label as _extract_normalize

    # 1순위: 추출기와 같은 정규화 → 한글 키 직접 매칭
    normalized = _extract_normalize(cell_text)
    if normalized in data:
        return normalized

    # 2순위: _LABEL_TO_KEY → 영어 키 매칭 (기본 템플릿 호환)
    eng_key = _normalize_label(cell_text)
    if eng_key and eng_key in data:
        return eng_key

    return None


def fill_template_docx(template_path: str, output_path: str, data: dict) -> bool:
    """
    원본 양식 DOCX를 열어서 데이터를 채워넣는다.

    Args:
        template_path: 원본 DOCX 양식 파일 경로
        output_path: 출력 DOCX 파일 경로
        data: LLM이 생성한 데이터 dict (한글 키 또는 영어 키)

    Returns:
        True if successful
    """
    doc = Document(template_path)
    filled_keys = set()

    # 1. 테이블 셀에서 필드명 찾아 값 주입
    for table in doc.tables:
        rows = table.rows
        for ri, row in enumerate(rows):
            cells = row.cells
            for i, cell in enumerate(cells):
                cell_text = cell.text.strip()
                if not cell_text or len(cell_text) > 35:
                    continue

                key = _find_data_key(cell_text, data)
                if not key or key in filled_keys:
                    continue

                val = _format_value(data[key])
                if not val:
                    continue

                raw_val = data[key]

                # 배열 데이터 + 다중 행 테이블: 데이터 행에 분배
                if isinstance(raw_val, list) and len(raw_val) > 0 and isinstance(raw_val[0], dict):
                    injected = _inject_array_to_table(table, ri, raw_val)
                    if injected:
                        filled_keys.add(key)
                        continue

                # 같은 행의 다음 셀(옆)에 주입 시도
                injected = False
                for j in range(i + 1, len(cells)):
                    if cells[j]._tc != cells[i]._tc:  # 다른 셀인지 확인
                        _inject_cell_text(cells[j], val)
                        filled_keys.add(key)
                        injected = True
                        break

                # 옆 셀이 없으면 (1열 테이블 등) 다음 행의 같은 열(아래)에 주입
                if not injected and ri + 1 < len(rows):
                    next_row_cells = rows[ri + 1].cells
                    if i < len(next_row_cells):
                        _inject_cell_text(next_row_cells[i], val)
                        filled_keys.add(key)

    # 2. 본문 "필드명:" 패턴 아래에 값 주입
    paragraphs = doc.paragraphs
    for i, para in enumerate(paragraphs):
        text = para.text.strip()
        match = re.match(r"^([가-힣a-zA-Z\s]{2,15})\s*[:：]\s*$", text)
        if not match:
            continue

        label = match.group(1).strip()
        key = _find_data_key(label, data)
        if not key or key in filled_keys:
            continue

        val = _format_value(data[key])
        if not val:
            continue

        # 다음 빈 문단에 값 주입
        if i + 1 < len(paragraphs):
            next_para = paragraphs[i + 1]
            if not next_para.text.strip():
                next_para.clear()
                run = next_para.add_run(val)
                run.font.size = Pt(10)
                filled_keys.add(key)

    doc.save(output_path)
    print(f"[create_from_template] 양식 채우기 완료: {output_path} | 채운 필드: {filled_keys}")
    return True


# ── 스타일 헬퍼 (범용 레이아웃용) ──
_HEADER_BG = "1E293B"
_LABEL_BG = "F1F5F9"
_ALT_BG = "F8FAFC"
_NAVY = RGBColor(0x1E, 0x29, 0x3B)
_WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def _set_shading(cell, fill_color: str):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_color)
    tcPr.append(shd)


def _set_valign(cell, align: str = "center"):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    vAlign = OxmlElement("w:vAlign")
    vAlign.set(qn("w:val"), align)
    tcPr.append(vAlign)


def _style_label(cell, text: str):
    _set_shading(cell, _LABEL_BG)
    _set_valign(cell)
    para = cell.paragraphs[0]
    para.clear()
    run = para.add_run(text)
    run.font.bold = True
    run.font.size = Pt(10)
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER


def _style_value(cell, text: str = ""):
    _set_valign(cell)
    para = cell.paragraphs[0]
    para.clear()
    if text:
        run = para.add_run(str(text))
        run.font.size = Pt(10)


def _style_section(cell, text: str):
    _set_shading(cell, _HEADER_BG)
    _set_valign(cell)
    para = cell.paragraphs[0]
    para.clear()
    run = para.add_run(text)
    run.font.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = _WHITE
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT


def _is_short_value(val) -> bool:
    """짧은 값인지 판별 (2열 테이블 렌더링용)"""
    if val is None or val == "":
        return True
    if isinstance(val, list):
        return False
    return isinstance(val, str) and len(val) <= 50


def _add_spacer(doc, pt_size: int = 4):
    """작은 빈 줄 추가 (섹션 간 간격 조절)"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(pt_size)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run("")
    run.font.size = Pt(1)


def _render_array_section(doc, label: str, items: list):
    """배열 데이터를 섹션으로 렌더링 (헤더 + 테이블)"""
    if not items:
        return

    if isinstance(items[0], dict):
        # dict 배열: 컬럼 헤더 + 데이터 행
        cols = list(items[0].keys())
        row_count = len(items) + 2
        col_count = len(cols) + 1

        t = doc.add_table(rows=row_count, cols=col_count)
        t.style = "Table Grid"

        for i in range(1, col_count):
            t.rows[0].cells[0].merge(t.rows[0].cells[i])
        _style_section(t.rows[0].cells[0], label)

        _style_label(t.rows[1].cells[0], "No.")
        for ci, col in enumerate(cols):
            _style_label(t.rows[1].cells[ci + 1], col)

        for ri, item in enumerate(items):
            row_idx = ri + 2
            bg = _ALT_BG if ri % 2 == 0 else "FFFFFF"
            for c in range(col_count):
                _set_shading(t.rows[row_idx].cells[c], bg)
            _style_value(t.rows[row_idx].cells[0], str(ri + 1))
            for ci, col in enumerate(cols):
                _style_value(t.rows[row_idx].cells[ci + 1], str(item.get(col, "")))
    else:
        # 문자열 배열: 섹션 헤더 + 번호 테이블
        t = doc.add_table(rows=len(items) + 1, cols=2)
        t.style = "Table Grid"
        t.rows[0].cells[0].merge(t.rows[0].cells[1])
        _style_section(t.rows[0].cells[0], label)
        for ri, item in enumerate(items):
            bg = _ALT_BG if ri % 2 == 0 else "FFFFFF"
            _set_shading(t.rows[ri + 1].cells[0], bg)
            _set_shading(t.rows[ri + 1].cells[1], bg)
            t.rows[ri + 1].cells[0].width = Cm(1)
            _style_value(t.rows[ri + 1].cells[0], str(ri + 1))
            _style_value(t.rows[ri + 1].cells[1], str(item))

    _add_spacer(doc, 2)


def _set_row_height(row, height_cm: float):
    """행 높이 설정"""
    tr = row._tr
    trPr = tr.get_or_add_trPr()
    trHeight = OxmlElement("w:trHeight")
    trHeight.set(qn("w:val"), str(int(height_cm * 567)))
    trHeight.set(qn("w:hRule"), "atLeast")
    trPr.append(trHeight)


def create_generic_document(output_path: str, data: dict, fields: list[dict], doc_title: str = "문서") -> str:
    """
    범용 DOCX 생성 — 기본 템플릿(meeting.docx, proposal.docx)과 동일한 스타일

    기본 템플릿 빌더(create_meeting_minutes 등)의 스타일 함수를 재사용하여
    동일한 품질의 문서를 동적 필드로 생성한다.
    """
    from ai.skills.create_meeting_minutes import (
        style_section_header, style_label_cell, style_value_cell,
        set_row_height, _set_shading, _BLUE_ALT,
    )

    doc = Document()

    section = doc.sections[0]
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    # ── 제목 ──
    title = doc_title
    title_keys = ["title", "제목", "제안명", "보고서제목", "회의제목", "제안서제목"]
    for tk in title_keys:
        if tk in data and data[tk]:
            title = str(data[tk])
            break

    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run(title)
    title_run.font.size = Pt(22)
    title_run.font.bold = True
    title_run.font.color.rgb = _NAVY

    # 구분선
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), _HEADER_BG)
    pBdr.append(bottom)
    pPr.append(pBdr)

    # ── 필드 분류 ──
    skip_keys = {tk for tk in title_keys if tk in data}
    short_items = []
    long_items = []
    array_items = []

    for f in fields:
        key = f["key"]
        if key in skip_keys:
            continue
        val = data.get(key)
        if val is None or val == "" or val == []:
            continue
        label = f.get("label", key)

        if isinstance(val, list):
            array_items.append((label, val))
        elif _is_short_value(val):
            short_items.append((label, str(val)))
        else:
            long_items.append((label, str(val)))

    # ── 1. 기본 정보: 4열 테이블 (기본 템플릿과 동일) ──
    if short_items:
        # 첫 번째 항목은 전체 너비 (제목 행처럼)
        first = short_items[0]
        rest = short_items[1:]

        row_count = 1 + (len(rest) + 1) // 2  # 첫 행 + 나머지 2개씩
        t = doc.add_table(rows=row_count, cols=4)
        t.style = "Table Grid"

        for row in t.rows:
            row.cells[0].width = Cm(2.5)
            row.cells[1].width = Cm(6.0)
            row.cells[2].width = Cm(2.5)
            row.cells[3].width = Cm(5.0)

        # 첫 행: 값 셀 병합 (제목처럼)
        t.rows[0].cells[1].merge(t.rows[0].cells[3])
        style_label_cell(t.rows[0].cells[0], first[0])
        style_value_cell(t.rows[0].cells[1], first[1])
        set_row_height(t.rows[0], 1.0)

        # 나머지: 2개씩 배치
        for i, (label, val) in enumerate(rest):
            ri = 1 + i // 2
            ci = (i % 2) * 2
            style_label_cell(t.rows[ri].cells[ci], label)
            style_value_cell(t.rows[ri].cells[ci + 1], val)

        # 홀수면 마지막 행 오른쪽 빈칸
        if len(rest) % 2 == 1:
            last_ri = 1 + len(rest) // 2
            if last_ri < row_count:
                style_label_cell(t.rows[last_ri].cells[2], "")
                style_value_cell(t.rows[last_ri].cells[3], "")

        doc.add_paragraph()

    # ── 2. 본문: 섹션 헤더 + 내용 (기본 템플릿과 동일) ──
    for label, val in long_items:
        t = doc.add_table(rows=2, cols=1)
        t.style = "Table Grid"
        style_section_header(t.rows[0].cells[0], label)
        style_value_cell(t.rows[1].cells[0], val)
        # 내용 길이 기반 행 높이
        line_count = max(val.count('\n') + 1, len(val) // 60 + 1)
        height = max(3.0, min(line_count * 0.8, 8.0))
        set_row_height(t.rows[1], height)
        doc.add_paragraph()

    # ── 3. 배열: 기본 템플릿 Action Item/추진일정 스타일 ──
    for label, items in array_items:
        if not items:
            continue

        if isinstance(items[0], dict):
            cols = list(items[0].keys())
            col_count = len(cols) + 1
            row_count = len(items) + 2

            t = doc.add_table(rows=row_count, cols=col_count)
            t.style = "Table Grid"

            # 섹션 헤더 (병합)
            for i in range(1, col_count):
                t.rows[0].cells[0].merge(t.rows[0].cells[i])
            style_section_header(t.rows[0].cells[0], label)

            # 컬럼 헤더
            style_label_cell(t.rows[1].cells[0], "No.")
            for ci, col in enumerate(cols):
                style_label_cell(t.rows[1].cells[ci + 1], col)

            # 데이터 행 (교대 색상)
            for ri, item in enumerate(items):
                row_idx = ri + 2
                bg = _BLUE_ALT if ri % 2 == 0 else "FFFFFF"
                for c in range(col_count):
                    _set_shading(t.rows[row_idx].cells[c], bg)
                style_value_cell(t.rows[row_idx].cells[0], str(ri + 1))
                for ci, col in enumerate(cols):
                    style_value_cell(t.rows[row_idx].cells[ci + 1], str(item.get(col, "")))
                set_row_height(t.rows[row_idx], 0.8)
        else:
            # 문자열 배열
            t = doc.add_table(rows=2, cols=1)
            t.style = "Table Grid"
            style_section_header(t.rows[0].cells[0], label)
            val = "\n".join(f"• {item}" for item in items)
            style_value_cell(t.rows[1].cells[0], val)
            set_row_height(t.rows[1], max(2.0, len(items) * 0.6))

        doc.add_paragraph()

    doc.save(output_path)
    print(f"[create_from_template] 범용 DOCX 생성 완료: {output_path}")
    return output_path
