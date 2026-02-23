from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def set_cell_shading(cell, fill_color: str):
    """셀 배경색 설정 (hex: 'D9D9D9')"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_color)
    tcPr.append(shd)


def set_row_height(row, height_cm: float):
    tr = row._tr
    trPr = tr.get_or_add_trPr()
    trHeight = OxmlElement("w:trHeight")
    trHeight.set(qn("w:val"), str(int(height_cm * 567)))  # 1cm = 567 twips
    trHeight.set(qn("w:hRule"), "atLeast")
    trPr.append(trHeight)


def style_label_cell(cell, text: str):
    """라벨 셀: 회색 배경 + 굵은 글씨 + 가운데 정렬"""
    set_cell_shading(cell, "D9D9D9")
    cell.text = text
    para = cell.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.runs[0] if para.runs else para.add_run(text)
    run.font.bold = True
    run.font.size = Pt(10)
    if para.runs and para.runs[0].text != text:
        cell.paragraphs[0].clear()
        run = cell.paragraphs[0].add_run(text)
        run.font.bold = True
        run.font.size = Pt(10)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER


def style_value_cell(cell, text: str = ""):
    """값 셀: 기본 글씨"""
    cell.text = text
    para = cell.paragraphs[0]
    for run in para.runs:
        run.font.size = Pt(10)


def _inject_cell_text(cell, text: str):
    """셀에 텍스트 주입 (기존 내용 교체, 폰트 크기 유지)"""
    cell.text = str(text) if text else ""
    para = cell.paragraphs[0]
    if para.runs:
        para.runs[0].font.size = Pt(10)


def create_meeting_minutes(output_path: str = "회의록_test.docx", data: dict = None):
    doc = Document()

    # ── 페이지 여백 설정 ──
    section = doc.sections[0]
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    # ── 제목 ──
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run("회  의  록")
    title_run.font.size = Pt(22)
    title_run.font.bold = True

    doc.add_paragraph()

    # ── 표1: 기본 정보 (5행 4열) ──
    t0 = doc.add_table(rows=5, cols=4)
    t0.style = "Table Grid"

    # 열 너비 조정
    for row in t0.rows:
        row.cells[0].width = Cm(2.5)
        row.cells[1].width = Cm(6.0)
        row.cells[2].width = Cm(2.5)
        row.cells[3].width = Cm(5.0)

    # Row 0: 회의 제목 (값 셀 3개 병합)
    t0.rows[0].cells[1].merge(t0.rows[0].cells[3])
    style_label_cell(t0.rows[0].cells[0], "회의 제목")
    set_row_height(t0.rows[0], 1.0)

    # Row 1: 회의 날짜 / 회의 시간
    style_label_cell(t0.rows[1].cells[0], "회의 날짜")
    style_value_cell(t0.rows[1].cells[1], "2026년    월    일 (   )")
    style_label_cell(t0.rows[1].cells[2], "회의 시간")
    style_value_cell(t0.rows[1].cells[3], "   :   ~   :  ")

    # Row 2: 회의 장소 / 회의 유형
    style_label_cell(t0.rows[2].cells[0], "회의 장소")
    style_value_cell(t0.rows[2].cells[1])
    style_label_cell(t0.rows[2].cells[2], "회의 유형")
    style_value_cell(t0.rows[2].cells[3], "☐ 정기  ☐ 비정기  ☐ 긴급")

    # Row 3: 참석자 (값 셀 3개 병합)
    t0.rows[3].cells[1].merge(t0.rows[3].cells[3])
    style_label_cell(t0.rows[3].cells[0], "참석자")
    style_value_cell(t0.rows[3].cells[1], "(쉼표로 구분하여 작성)")
    set_row_height(t0.rows[3], 1.2)

    # Row 4: 작성자 (값 셀 3개 병합)
    t0.rows[4].cells[1].merge(t0.rows[4].cells[3])
    style_label_cell(t0.rows[4].cells[0], "작성자")

    doc.add_paragraph()

    # ── 표2: 회의 내용 (2행 1열) ──
    t1 = doc.add_table(rows=2, cols=1)
    t1.style = "Table Grid"
    style_label_cell(t1.rows[0].cells[0], "회의 내용")
    t1.rows[1].cells[0].text = ""
    set_row_height(t1.rows[1], 5.0)

    doc.add_paragraph()

    # ── 표3: 결정 사항 (2행 1열) ──
    t2 = doc.add_table(rows=2, cols=1)
    t2.style = "Table Grid"
    style_label_cell(t2.rows[0].cells[0], "결정 사항")
    t2.rows[1].cells[0].text = ""
    set_row_height(t2.rows[1], 3.0)

    doc.add_paragraph()

    # ── 표4: Action Item (4행 5열) ──
    t3 = doc.add_table(rows=4, cols=5)
    t3.style = "Table Grid"

    headers = ["No.", "Action Item", "담당자", "기한", "상태"]
    for i, h in enumerate(headers):
        style_label_cell(t3.rows[0].cells[i], h)

    for r in range(1, 4):
        style_value_cell(t3.rows[r].cells[0], str(r))
        style_value_cell(t3.rows[r].cells[1])
        style_value_cell(t3.rows[r].cells[2])
        style_value_cell(t3.rows[r].cells[3])
        style_value_cell(t3.rows[r].cells[4], "☐ 진행중  ☐ 완료")
        set_row_height(t3.rows[r], 1.0)

    doc.add_paragraph()

    # ── 표5: 비고 / 다음 회의 일정 (2행 1열) ──
    t4 = doc.add_table(rows=2, cols=1)
    t4.style = "Table Grid"
    style_label_cell(t4.rows[0].cells[0], "비고 / 다음 회의 일정")
    t4.rows[1].cells[0].text = ""
    set_row_height(t4.rows[1], 2.0)

    # ── data가 있으면 셀에 실제 데이터 주입 ──
    if data:
        # Row 0: 회의 제목
        _inject_cell_text(t0.rows[0].cells[1], data.get("title", ""))

        # Row 1: 날짜 / 시간
        _inject_cell_text(t0.rows[1].cells[1], data.get("date", ""))
        _inject_cell_text(t0.rows[1].cells[3], data.get("time", ""))

        # Row 2: 장소 / 유형
        _inject_cell_text(t0.rows[2].cells[1], data.get("location", ""))
        meeting_type = data.get("meeting_type", "")
        type_map = {
            "정기": "☑ 정기  ☐ 비정기  ☐ 긴급",
            "비정기": "☐ 정기  ☑ 비정기  ☐ 긴급",
            "긴급": "☐ 정기  ☐ 비정기  ☑ 긴급",
        }
        _inject_cell_text(t0.rows[2].cells[3], type_map.get(meeting_type, "☐ 정기  ☐ 비정기  ☐ 긴급"))

        # Row 3: 참석자
        attendees = data.get("attendees", [])
        attendees_text = ", ".join(attendees) if isinstance(attendees, list) else str(attendees)
        _inject_cell_text(t0.rows[3].cells[1], attendees_text)

        # Row 4: 작성자
        _inject_cell_text(t0.rows[4].cells[1], data.get("author", ""))

        # 표2 Row 1: 회의 내용
        _inject_cell_text(t1.rows[1].cells[0], data.get("content", ""))

        # 표3 Row 1: 결정 사항
        decisions = data.get("decisions", [])
        decisions_text = "\n".join(decisions) if isinstance(decisions, list) else str(decisions)
        _inject_cell_text(t2.rows[1].cells[0], decisions_text)

        # 표4 Row 1~3: Action Items
        action_items = data.get("action_items", [])
        for r in range(1, 4):
            ai_item = action_items[r - 1] if r - 1 < len(action_items) else {}
            _inject_cell_text(t3.rows[r].cells[1], ai_item.get("content", ""))
            _inject_cell_text(t3.rows[r].cells[2], ai_item.get("assignee", ""))
            _inject_cell_text(t3.rows[r].cells[3], ai_item.get("due_date", ""))
            status = ai_item.get("status", "☐ 진행중  ☐ 완료") if ai_item else "☐ 진행중  ☐ 완료"
            _inject_cell_text(t3.rows[r].cells[4], status)

        # 표5 Row 1: 비고
        _inject_cell_text(t4.rows[1].cells[0], data.get("notes", ""))

    doc.save(output_path)
    print(f"회의록 생성 완료: {output_path}")


if __name__ == "__main__":
    create_meeting_minutes()
