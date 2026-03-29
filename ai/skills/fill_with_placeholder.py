"""
docxtpl 기반 DOCX 채우기 — 플레이스홀더 {{key}}를 데이터로 치환

placeholder_inject.py가 만든 _tpl.docx를 열어서 데이터를 렌더링.
sLLM 호출 없이 단순 치환으로 동작.
"""
import re

from docxtpl import DocxTemplate


# 날짜/일정 관련 sub_key 키워드
_DATE_SUB_KEYS = {"진행일정", "기한", "일정", "마감일", "완료일", "due_date", "deadline", "date", "end_date"}

# 날짜 패턴: "X월 Y일", "X/Y", "YYYY-MM-DD", "이번주", "다음주" 등
_DATE_PATTERN = re.compile(
    r'\d{4}[-./]\d{1,2}[-./]\d{1,2}'   # 2026-04-01, 2026/4/1
    r'|\d{1,2}월\s*\d{1,2}일'           # 4월 1일
    r'|\d{1,2}/\d{1,2}'                 # 4/1
    r'|이번\s*주|다음\s*주|금주|차주'
)


def _extract_date_from_text(text: str) -> str:
    """텍스트에서 날짜 패턴을 추출하여 반환. 없으면 빈 문자열."""
    m = _DATE_PATTERN.search(text)
    return m.group(0) if m else ""


def fill_docx_with_placeholder(
    placeholder_path: str,
    output_path: str,
    data: dict,
    fields: list[dict] | None = None,
) -> dict:
    """플레이스홀더 DOCX에 데이터를 렌더링하여 저장.

    Args:
        placeholder_path: {{key}} 마커가 삽입된 DOCX 경로
        output_path: 결과 DOCX 저장 경로
        data: 필드 데이터 dict
        fields: parsed_structure 필드 목록 (키 매핑용, optional)

    Returns:
        {"success": bool, "filled_count": int}
    """
    try:
        tpl = DocxTemplate(placeholder_path)

        # 컨텍스트 구성: data dict를 그대로 사용
        # 배열 필드의 sub_keys를 안전한 변수명으로 변환
        context = {}
        for key, val in data.items():
            if val is None:
                val = ""
            if isinstance(val, list) and val and isinstance(val[0], dict):
                # dict 배열: data의 sub_key를 placeholder의 sub_key로 변환
                from ai.skills.fill_with_llm import _SUB_KEY_ALIASES

                # fields에서 이 key의 sub_keys 가져오기
                tpl_sub_keys = []
                if fields:
                    for f in fields:
                        if f.get("key") == key and f.get("sub_keys"):
                            tpl_sub_keys = f["sub_keys"]
                            break

                # safe 변환된 tpl_sub_keys
                safe_tpl_map = {}  # safe_name → safe_name (자기 자신)
                for tsk in tpl_sub_keys:
                    safe = re.sub(r'[^가-힣a-zA-Z0-9]', '', tsk)
                    if safe and safe[0].isdigit():
                        safe = 'f_' + safe
                    safe_tpl_map[tsk] = safe

                # data key → tpl safe key 매핑 (이름 기반)
                data_keys = list(val[0].keys())
                key_map = {}
                used_tpl = set()
                for dk in data_keys:
                    # 1) 직접 매칭: data key와 tpl sub_key가 같은 이름
                    dk_norm = re.sub(r'[^가-힣a-zA-Z0-9]', '', dk)
                    for tsk, safe in safe_tpl_map.items():
                        if safe in used_tpl:
                            continue
                        tsk_norm = re.sub(r'[^가-힣a-zA-Z0-9]', '', tsk)
                        if dk_norm == tsk_norm or dk_norm in tsk_norm or tsk_norm in dk_norm:
                            key_map[dk] = safe
                            used_tpl.add(safe)
                            break
                    if dk in key_map:
                        continue
                    # 2) alias 매칭
                    aliases = _SUB_KEY_ALIASES.get(dk.lower(), [])
                    for alias in aliases:
                        alias_norm = re.sub(r'[^가-힣a-zA-Z0-9]', '', alias)
                        for tsk, safe in safe_tpl_map.items():
                            if safe in used_tpl:
                                continue
                            tsk_norm = re.sub(r'[^가-힣a-zA-Z0-9]', '', tsk)
                            if alias_norm == tsk_norm or alias_norm in tsk_norm or tsk_norm in alias_norm:
                                key_map[dk] = safe
                                used_tpl.add(safe)
                                break
                        if dk in key_map:
                            break
                    if dk not in key_map:
                        # 3) fallback: 자기 자신
                        safe_dk = re.sub(r'[^가-힣a-zA-Z0-9]', '', dk)
                        if safe_dk and safe_dk[0].isdigit():
                            safe_dk = 'f_' + safe_dk
                        key_map[dk] = safe_dk

                # 날짜 관련 sub_key 식별 (진행일정, 기한 등)
                date_safe_key = None
                content_safe_key = None
                for tsk, safe in safe_tpl_map.items():
                    tsk_lower = tsk.lower()
                    if tsk_lower in _DATE_SUB_KEYS or any(k in tsk_lower for k in ("일정", "기한", "날짜", "date")):
                        date_safe_key = safe
                    else:
                        if content_safe_key is None:
                            content_safe_key = safe

                safe_items = []
                for item in val:
                    safe_item = {}
                    for sk, sv in item.items():
                        mapped_key = key_map.get(sk, sk)
                        safe_item[mapped_key] = sv if sv is not None else ""
                    # 누락된 sub_key에 빈 문자열 기본값 보충
                    for tsk, safe in safe_tpl_map.items():
                        if safe not in safe_item:
                            safe_item[safe] = ""
                    # 날짜 sub_key가 비어있으면 내용에서 날짜 추출
                    if date_safe_key and not safe_item.get(date_safe_key) and content_safe_key:
                        extracted = _extract_date_from_text(safe_item.get(content_safe_key, ""))
                        if extracted:
                            safe_item[date_safe_key] = extracted
                    safe_items.append(safe_item)
                context[key] = safe_items
            elif isinstance(val, str) and fields:
                # 배열 필드인데 sLLM이 문자열로 반환한 경우
                array_field = next((f for f in fields if f.get("key") == key and f.get("sub_keys")), None)
                if array_field and val:
                    # 첫 번째 sub_key에 전체 텍스트 넣기
                    first_sk = array_field["sub_keys"][0]
                    safe_sk = re.sub(r'[^가-힣a-zA-Z0-9]', '', first_sk)
                    if safe_sk and safe_sk[0].isdigit():
                        safe_sk = 'f_' + safe_sk
                    context[key] = [{safe_sk: val}]
                else:
                    context[key] = val if val else ""
            elif isinstance(val, list):
                # 문자열 배열 → 쉼표 구분
                context[key] = ", ".join(str(v) for v in val)
            elif isinstance(val, dict):
                # dict → 값만 쉼표 구분
                context[key] = ", ".join(str(v) for v in val.values() if v)
            else:
                context[key] = str(val) if val else ""

        filled_count = sum(1 for v in context.values() if v)

        tpl.render(context)
        tpl.save(output_path)

        print(f"[fill_placeholder] 렌더링 완료: {filled_count}개 필드 → {output_path}")
        return {"success": True, "filled_count": filled_count}

    except Exception as e:
        print(f"[fill_placeholder] 렌더링 실패: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "filled_count": 0, "error": str(e)}
