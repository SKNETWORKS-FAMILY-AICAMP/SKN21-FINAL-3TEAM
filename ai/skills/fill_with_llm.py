"""
sLLM 매핑 보조 DOCX 채우기

원본 DOCX 양식을 열어서 셀 구조를 추출하고,
sLLM에게 "어느 셀에 어떤 data key를 넣을지" 매핑만 판단시킨 후,
값은 원본 data dict에서 직접 주입. 원본 레이아웃 100% 보존.
"""
import json
import re
from docx import Document
from docx.shared import Pt


def _extract_cell_structure(doc: Document) -> list[dict]:
    """원본 DOCX의 전체 셀 구조를 추출 (병합셀 감지, 공백 정규화)"""
    cells = []
    for ti, table in enumerate(doc.tables):
        for ri, row in enumerate(table.rows):
            seen_tcs = set()
            for ci, cell in enumerate(row.cells):
                tc_id = id(cell._tc)
                is_merged = tc_id in seen_tcs
                seen_tcs.add(tc_id)
                raw_text = cell.text.strip()
                text = re.sub(r'\s+', ' ', raw_text).strip() if raw_text else ""
                cells.append({
                    "pos": f"T{ti}R{ri}C{ci}",
                    "table": ti, "row": ri, "col": ci,
                    "text": text,
                    "is_empty": not text or bool(re.match(r'^[\s☐□✓✔○●◎\d.·\-~:：()（）년월일시분/]*$', text)),
                    "is_merged_dup": is_merged,
                })
    return cells


def _format_value(val) -> str:
    """data 값을 문자열로 변환"""
    if val is None:
        return ""
    if isinstance(val, list):
        parts = []
        for item in val:
            if isinstance(item, dict):
                parts.append(", ".join(f"{v}" for v in item.values() if v))
            else:
                parts.append(str(item))
        return "\n".join(parts) if parts else ""
    if isinstance(val, dict):
        return "\n".join(f"{v}" for v in val.values() if v)
    return str(val)


def _build_mapping_prompt(cells: list[dict], data: dict, field_mapping: list[dict] = None) -> tuple[str, str]:
    """sLLM에게 보낼 매핑 프롬프트

    field_mapping: parsed_structure의 필드 목록 [{key, label, description}, ...]
    이걸 활용해서 "양식 라벨 ↔ data key" 연결 힌트를 제공.
    """
    # 양식 구조
    structure_lines = []
    for c in cells:
        if c.get("is_merged_dup"):
            continue
        if c["text"] and not c["is_empty"]:
            structure_lines.append(f'{c["pos"]}=[라벨]"{c["text"][:25]}"')
        else:
            structure_lines.append(f'{c["pos"]}=(빈칸)')

    # 라벨-빈칸 쌍 힌트
    label_cells = [c for c in cells if c["text"] and not c["is_empty"] and not c.get("is_merged_dup")]
    empty_cells = [c for c in cells if c["is_empty"] and not c.get("is_merged_dup")]

    pair_hints = []
    for c in label_cells:
        next_empty = next(
            (e for e in empty_cells
             if e["table"] == c["table"] and e["row"] == c["row"] and e["col"] == c["col"] + 1),
            None
        )
        if not next_empty:
            next_empty = next(
                (e for e in empty_cells
                 if e["table"] == c["table"] and e["row"] == c["row"] + 1 and e["col"] == c["col"]),
                None
            )
        if next_empty:
            pair_hints.append(f'  "{c["text"][:15]}" → {next_empty["pos"]}')

    # 핵심: 양식 라벨 ↔ data key 매핑 정보
    key_label_hints = []
    if field_mapping:
        for f in field_mapping:
            key = f.get("key", "")
            label = f.get("label", "")
            val = data.get(key)
            if val is None or val == "" or val == []:
                continue
            if isinstance(val, list):
                if val and isinstance(val[0], dict):
                    sub_keys = list(val[0].keys())
                    key_label_hints.append(f'  양식라벨="{label}" → data key="{key}" (dict배열 {len(val)}개, 하위키: {", ".join(sub_keys)}, 매핑형식: {key}[0].{sub_keys[0]})')
                else:
                    key_label_hints.append(f'  양식라벨="{label}" → data key="{key}" (문자열배열 {len(val)}개, 매핑형식: {key}[0], {key}[1]... 하위키 없음!)')
            else:
                key_label_hints.append(f'  양식라벨="{label}" → data key="{key}"')
    else:
        # field_mapping 없으면 data key만 나열
        for k, v in data.items():
            if v is None or v == "" or v == []:
                continue
            if isinstance(v, list):
                key_label_hints.append(f'  {k}: (배열, {len(v)}개 항목)')
            else:
                key_label_hints.append(f'  {k}: "{str(v)[:30]}"')

    # 배열 테이블 컬럼 헤더 감지 (같은 테이블에서 컬럼 헤더행 → 하위키 매핑 힌트)
    array_col_hints = []
    for f in (field_mapping or []):
        key = f.get("key", "")
        val = data.get(key)
        if isinstance(val, list) and val and isinstance(val[0], dict):
            sub_keys = list(val[0].keys())
            # 양식에서 이 배열의 컬럼 헤더를 찾기
            label_text = re.sub(r'\s+', ' ', f.get("label", "")).strip()
            for c in label_cells:
                if label_text and label_text in c["text"]:
                    # 같은 행의 다른 라벨 셀 = 컬럼 헤더
                    col_headers = [
                        lc["text"] for lc in label_cells
                        if lc["table"] == c["table"] and lc["row"] == c["row"] and lc["col"] != c["col"]
                    ]
                    if col_headers:
                        for ci, ch in enumerate(col_headers):
                            if ci < len(sub_keys):
                                array_col_hints.append(f'  "{ch}" 컬럼 → {key}[N].{sub_keys[ci]}')
                    break

    array_hint_text = "\n".join(array_col_hints) if array_col_hints else ""

    sys_prompt = (
        "당신은 문서 양식 전문가입니다. DOCX 양식의 셀 구조와 데이터가 주어지면, "
        "각 데이터 key를 어느 빈칸에 넣을지 매핑합니다.\n\n"
        "## 절대 규칙\n"
        "1. [라벨] 셀에는 절대 매핑하지 마세요\n"
        "2. (빈칸) 셀에만 매핑하세요\n"
        "3. '양식 라벨↔data key 매핑'의 key를 **그대로** 사용하세요. 번역하거나 변환하지 마세요!\n"
        "   예: data key가 '회의일시'면 반드시 '회의일시'로 쓰세요. 'meeting_date'로 바꾸지 마세요.\n"
        "4. 배열은 key[0], key[1] 인덱스로, dict배열은 key[0].subkey\n"
        "5. 반드시 JSON 배열로만 응답하세요\n\n"
        f"## 양식 라벨 ↔ data key 매핑\n" + "\n".join(key_label_hints) + "\n\n"
        + (f"## 배열 컬럼 ↔ 하위키 매핑\n{array_hint_text}\n\n" if array_hint_text else "")
        + f"## 라벨→빈칸 위치 힌트\n" + "\n".join(pair_hints) + "\n\n"
        '응답 형식: [{"pos":"T0R0C1","key":"date"}, {"pos":"T3R1C1","key":"decisions[0].content"}]'
    )

    user_prompt = (
        f"[양식 구조]\n" + "\n".join(structure_lines) + "\n\n"
        f"위 양식의 빈칸에 데이터 key를 매핑해서 JSON 배열로 반환하세요."
    )

    return sys_prompt, user_prompt


def _resolve_key(data: dict, key_path: str) -> str:
    """key 경로에서 값을 추출. 예: "decisions[0].content" """
    if key_path in data:
        return _format_value(data[key_path])

    match = re.match(r'^(\w+)\[(\d+)\](?:\.(\w+))?$', key_path)
    if match:
        base_key, idx, sub_key = match.group(1), int(match.group(2)), match.group(3)
        arr = data.get(base_key, [])
        if isinstance(arr, list) and idx < len(arr):
            item = arr[idx]
            if sub_key and isinstance(item, dict):
                return str(item.get(sub_key, ""))
            return _format_value(item)

    return ""


def _inject_to_cell(doc: Document, table_idx: int, row_idx: int, col_idx: int, value: str):
    """원본 DOCX의 특정 셀에 값 주입"""
    try:
        table = doc.tables[table_idx]
        cell = table.rows[row_idx].cells[col_idx]
        for para in cell.paragraphs:
            for run in para.runs:
                run.clear()
        cell.text = str(value)
        para = cell.paragraphs[0]
        if para.runs:
            para.runs[0].font.size = Pt(10)
    except (IndexError, AttributeError) as e:
        print(f"[fill_with_llm] 셀 주입 실패 T{table_idx}R{row_idx}C{col_idx}: {e}")


async def fill_docx_with_llm(template_path: str, output_path: str, data: dict, field_mapping: list[dict] = None) -> dict:
    """
    sLLM 매핑 보조로 원본 DOCX 양식을 채운다.

    Args:
        template_path: 원본 DOCX 양식 경로
        output_path: 출력 DOCX 경로
        data: LoRA가 생성한 데이터 dict (값은 여기서 직접 주입)
        field_mapping: parsed_structure의 필드 목록 (양식 라벨↔key 연결용)
    """
    from ai.agents.document._common import _call_llm

    doc = Document(template_path)
    cells = _extract_cell_structure(doc)
    print(f"[fill_with_llm] 양식 구조 추출: {len(cells)}개 셀")

    sys_prompt, user_prompt = _build_mapping_prompt(cells, data, field_mapping)

    print(f"[fill_with_llm] sLLM 매핑 요청 (key만)...")
    try:
        response = await _call_llm(sys_prompt, user_prompt, json_mode=True, task="generate")
        print(f"[fill_with_llm] sLLM 응답 ({len(response)}자): {response[:300]}")

        # JSON 파싱 (잘려도 복구)
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            mappings = json.loads(json_match.group())
        else:
            cleaned = response.strip()
            if cleaned.startswith('[') and not cleaned.endswith(']'):
                last_brace = cleaned.rfind('}')
                if last_brace > 0:
                    cleaned = cleaned[:last_brace + 1] + ']'
            mappings = json.loads(cleaned)
    except Exception as e:
        print(f"[fill_with_llm] sLLM 매핑 실패: {e}")
        return {"success": False, "filled_count": 0, "total_cells": len(cells), "error": str(e)}

    if not isinstance(mappings, list):
        mappings = []

    # 영어→한글 key 역매핑 테이블 구축 (LoRA가 영어 key로 반환할 때 대비)
    _ENGLISH_TO_KOREAN = {
        "date": "회의일시", "meeting_date": "회의일시",
        "department": "부서", "author": "작성자", "writer": "작성자",
        "attendees": "참석자", "participants": "참석자",
        "agenda": "회의안건", "topic": "회의안건",
        "content": "회의내용", "meeting_content": "회의내용",
        "decisions": "결정사항", "decision": "결정사항",
        "notes": "특이사항", "note": "특이사항", "remarks": "특이사항",
    }
    # field_mapping 기반 동적 역매핑 추가
    if field_mapping:
        for f in field_mapping:
            label_normalized = re.sub(r'\s+', '', f.get("label", ""))
            _ENGLISH_TO_KOREAN[label_normalized] = f["key"]

    def _resolve_with_fallback(key_path: str) -> str:
        """영어 key → 한글 key fallback 포함 resolve"""
        val = _resolve_key(data, key_path)
        if val:
            return val
        # 영어→한글 역매핑 시도
        base_match = re.match(r'^(\w+?)(?:\[|$)', key_path)
        if base_match:
            eng_base = base_match.group(1)
            kor_base = _ENGLISH_TO_KOREAN.get(eng_base)
            if kor_base:
                kor_path = key_path.replace(eng_base, kor_base, 1)
                val = _resolve_key(data, kor_path)
                if val:
                    return val
        return ""

    # 매핑 결과로 원본 DOCX에 data 값 주입
    # 같은 key가 여러 셀에 매핑된 경우 배열 자동 인덱싱
    key_occurrence = {}  # key → 등장 횟수 (배열 자동 분배용)
    filled = 0
    for m in mappings:
        pos = m.get("pos", "")
        key_path = m.get("key", "")
        if not pos or not key_path:
            continue

        match = re.match(r"T(\d+)R(\d+)C(\d+)", pos)
        if not match:
            continue

        # 배열 자동 분배: 같은 key가 반복되면 인덱스 자동 부여
        value = _resolve_with_fallback(key_path)

        if not value:
            continue

        # value가 리스트 전체인지 확인 (단일 key로 배열이 resolve된 경우)
        raw_val = data.get(key_path)
        if raw_val is None:
            # 영어→한글 역매핑
            base_match2 = re.match(r'^(\w+?)$', key_path)
            if base_match2:
                kor_key = _ENGLISH_TO_KOREAN.get(key_path, key_path)
                raw_val = data.get(kor_key)

        if isinstance(raw_val, list) and raw_val:
            # 같은 key가 전체 매핑에서 몇 번 나오는지 확인
            total_same_key = sum(1 for m2 in mappings if m2.get("key") == key_path)

            if total_same_key <= 1:
                # 1번만 매핑 → 전체 값을 한 셀에 (참석자 등)
                value = ", ".join(str(v) for v in raw_val) if all(isinstance(v, str) for v in raw_val) else _format_value(raw_val)
            else:
                # 여러 행에 매핑 → 배열 자동 인덱싱 (결정사항 등)
                idx = key_occurrence.get(key_path, 0)
                key_occurrence[key_path] = idx + 1
                if idx < len(raw_val):
                    item = raw_val[idx]
                    value = _format_value(item) if not isinstance(item, str) else item
                else:
                    continue

        ti, ri, ci = int(match.group(1)), int(match.group(2)), int(match.group(3))
        _inject_to_cell(doc, ti, ri, ci, value)
        filled += 1
        print(f"[fill_with_llm] {pos} ← {key_path}[{key_occurrence.get(key_path, 1)-1}] = {value[:40]}")

    doc.save(output_path)
    print(f"[fill_with_llm] 완료: {filled}개 셀 채움 → {output_path}")
    return {"success": True, "filled_count": filled, "total_cells": len(cells)}
