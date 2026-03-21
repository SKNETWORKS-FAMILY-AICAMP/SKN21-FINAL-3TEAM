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


def create_generic_document(output_path: str, data: dict, fields: list[dict], doc_title: str = "문서") -> str:
    """
    범용 DOCX 생성 (원본 양식이 없을 때 사용)

    Args:
        output_path: 출력 파일 경로
        data: LLM이 생성한 데이터 dict
        fields: parsed_structure 필드 목록
        doc_title: 문서 제목 (카테고리명)
    """
    doc = Document()

    section = doc.sections[0]
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    # 제목
    title = data.get("title", doc_title)
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

    # 단답형 필드: 테이블로 렌더링
    short_fields = [f for f in fields if f.get("type") in ("text", "date", "list") and f["key"] != "title"]
    long_fields = [f for f in fields if f.get("type") in ("textarea",)]

    if short_fields:
        # 2열 테이블: 라벨 | 값
        t = doc.add_table(rows=len(short_fields), cols=2)
        t.style = "Table Grid"
        for i, field in enumerate(short_fields):
            t.rows[i].cells[0].width = Cm(3)
            t.rows[i].cells[1].width = Cm(13)
            _style_label(t.rows[i].cells[0], field.get("label", field["key"]))
            val = _format_value(data.get(field["key"], ""))
            _style_value(t.rows[i].cells[1], val)
        doc.add_paragraph()

    # 장문 필드: 섹션 테이블로 렌더링
    for field in long_fields:
        t = doc.add_table(rows=2, cols=1)
        t.style = "Table Grid"
        _style_section(t.rows[0].cells[0], field.get("label", field["key"]))
        val = _format_value(data.get(field["key"], ""))
        _style_value(t.rows[1].cells[0], val)

        # 높이 설정
        tr = t.rows[1]._tr
        trPr = tr.get_or_add_trPr()
        trHeight = OxmlElement("w:trHeight")
        trHeight.set(qn("w:val"), str(int(4.0 * 567)))
        trHeight.set(qn("w:hRule"), "atLeast")
        trPr.append(trHeight)
        doc.add_paragraph()

    # action_items가 있으면 별도 테이블
    action_items = data.get("action_items", [])
    if action_items and isinstance(action_items, list) and len(action_items) > 0:
        row_count = len(action_items) + 2  # 섹션헤더 + 컬럼헤더 + 데이터
        t = doc.add_table(rows=row_count, cols=4)
        t.style = "Table Grid"

        # 섹션 헤더
        for i in range(1, 4):
            t.rows[0].cells[0].merge(t.rows[0].cells[i])
        _style_section(t.rows[0].cells[0], "Action Items")

        # 컬럼 헤더
        for i, h in enumerate(["No.", "할 일", "담당자", "기한"]):
            _style_label(t.rows[1].cells[i], h)

        # 데이터
        for r, item in enumerate(action_items):
            row_idx = r + 2
            bg = _ALT_BG if r % 2 == 0 else "FFFFFF"
            for c in range(4):
                _set_shading(t.rows[row_idx].cells[c], bg)

            _style_value(t.rows[row_idx].cells[0], str(r + 1))
            if isinstance(item, dict):
                _style_value(t.rows[row_idx].cells[1], item.get("task", item.get("content", "")))
                _style_value(t.rows[row_idx].cells[2], item.get("assignee", ""))
                _style_value(t.rows[row_idx].cells[3], item.get("due_date", ""))
            else:
                _style_value(t.rows[row_idx].cells[1], str(item))
        doc.add_paragraph()

    # 남은 필드 (fields에 없는 data key) — 추가 섹션으로 렌더링
    rendered_keys = {f["key"] for f in fields} | {"title", "action_items"}
    extra_keys = [k for k in data if k not in rendered_keys and data[k]]
    for key in extra_keys:
        val = _format_value(data[key])
        if not val:
            continue
        t = doc.add_table(rows=2, cols=1)
        t.style = "Table Grid"
        _style_section(t.rows[0].cells[0], key)
        _style_value(t.rows[1].cells[0], val)
        doc.add_paragraph()

    doc.save(output_path)
    print(f"[create_from_template] 범용 DOCX 생성 완료: {output_path}")
    return output_path
