"""
범용 커스텀 양식 DOCX 빌더

업로드된 DOCX 양식의 필드 스펙을 기반으로, LLM이 생성한 데이터를
시스템 빌더와 동일한 스타일의 범용 레이아웃 DOCX로 생성한다.
"""
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


# ── 스타일 상수 ──
_HEADER_BG = "1E293B"
_NAVY = RGBColor(0x1E, 0x29, 0x3B)


def _is_short_value(val) -> bool:
    """짧은 값인지 판별 (2열 테이블 렌더링용)"""
    if val is None or val == "":
        return True
    if isinstance(val, list):
        return False
    return isinstance(val, str) and len(val) <= 50


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
    title_para.paragraph_format.space_after = Pt(4)
    title_run = title_para.add_run(title)
    title_run.font.size = Pt(22)
    title_run.font.bold = True
    title_run.font.color.rgb = _NAVY

    # 구분선
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
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
        first = short_items[0]
        rest = short_items[1:]

        row_count = 1 + (len(rest) + 1) // 2
        t = doc.add_table(rows=row_count, cols=4)
        t.style = "Table Grid"

        for row in t.rows:
            row.cells[0].width = Cm(2.5)
            row.cells[1].width = Cm(6.0)
            row.cells[2].width = Cm(2.5)
            row.cells[3].width = Cm(5.0)
            set_row_height(row, 0.8)

        # 첫 행: 값 셀 병합
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

        # 섹션 간 간격
        spacer = doc.add_paragraph()
        spacer.paragraph_format.space_before = Pt(6)
        spacer.paragraph_format.space_after = Pt(0)

    # ── 2. 본문: 섹션 헤더 + 내용 (기본 템플릿과 동일) ──
    for label, val in long_items:
        t = doc.add_table(rows=2, cols=1)
        t.style = "Table Grid"
        style_section_header(t.rows[0].cells[0], label)
        style_value_cell(t.rows[1].cells[0], val)
        # 내용 셀 줄간격 개선
        for para in t.rows[1].cells[0].paragraphs:
            para.paragraph_format.line_spacing = Pt(16)
        # 내용 길이 기반 행 높이
        line_count = max(val.count('\n') + 1, len(val) // 60 + 1)
        height = max(3.0, min(line_count * 0.8, 8.0))
        set_row_height(t.rows[1], height)

        spacer = doc.add_paragraph()
        spacer.paragraph_format.space_before = Pt(6)
        spacer.paragraph_format.space_after = Pt(0)

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

            # No. 열 좁게
            t.columns[0].width = Cm(1.0)

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
            val = "\n".join(f"- {item}" for item in items)
            style_value_cell(t.rows[1].cells[0], val)
            set_row_height(t.rows[1], max(2.0, len(items) * 0.6))

        spacer = doc.add_paragraph()
        spacer.paragraph_format.space_before = Pt(6)
        spacer.paragraph_format.space_after = Pt(0)

    doc.save(output_path)
    print(f"[create_from_template] 범용 DOCX 생성 완료: {output_path}")
    return output_path
