"""
한글 키 LoRA 테스트 — DB 없이 추출 → 프롬프트 → LoRA 직접 호출

사용법:
  python tests/test_korean_keys.py
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from ai.document_parser.template_extractor import extract_template_fields, fields_to_prompt
from ai.llm.prompts import DOC_GENERATE_SLLM_PROMPT


async def test_generate(name, fields, user_input, doc_type="회의록"):
    """필드 리스트 + 입력 → 프롬프트 → LoRA → 결과"""
    field_spec = fields_to_prompt(fields)

    user_prompt = (
        f"다음 내용을 바탕으로 문서를 JSON 형식으로 작성해주세요.\n\n"
        f"[문서 유형] {doc_type}\n\n"
        f"[필드 명세]\n{field_spec}\n\n"
        f"[내용]\n{user_input}"
    )

    from ai.agents.document._common import _call_llm, get_last_model_name
    t0 = time.time()
    result_str = await _call_llm(DOC_GENERATE_SLLM_PROMPT, user_prompt, json_mode=True, task="generate")
    elapsed = time.time() - t0
    model = get_last_model_name()

    try:
        data = json.loads(result_str)
    except json.JSONDecodeError:
        data = {}

    filled = sum(1 for f in fields if data.get(f["key"]) not in ("", [], None, {}))
    total = len(fields)

    result = {
        "name": name,
        "field_count": total,
        "filled": filled,
        "rate": f"{filled}/{total} ({filled/total*100:.0f}%)" if total else "0/0",
        "elapsed": f"{elapsed:.1f}s",
        "model": model,
        "data": data,
        "fields": [f["key"] for f in fields],
    }
    return result


async def main():
    results = []

    # ── 테스트 1: 회의록 시스템 양식 (11개 필드) ──
    fields1 = extract_template_fields("data/doc_generate/meeting/회의록 양식(doc) (시스템템플릿).docx")
    r = await test_generate(
        "회의록-시스템(11필드)",
        fields1,
        "오늘 오후 3시에 회의실B에서 김철수, 이영희 참석해서 신규 프로젝트 킥오프 회의했어. DB 설계 이번주까지 끝내기로 했고, API 문서는 김철수가 담당하기로 함. 다음 회의는 금요일 2시.",
        "회의록",
    )
    results.append(r)

    # ── 테스트 2: 회의록 Form2 (8개 필드) ──
    fields2 = extract_template_fields("data/doc_generate/meeting/회의록 양식(doc) (2).docx")
    r = await test_generate(
        "회의록-Form2(8필드)",
        fields2,
        "3월 19일 마케팅팀 주간회의. 참석: 박지훈, 최수아, 정민호. 안건은 Q2 캠페인 예산 확정. 온라인 광고비 3000만원으로 결정. 특이사항: 경쟁사 신제품 출시 예정.",
        "회의록",
    )
    results.append(r)

    # ── 테스트 3: 회의록 Form3 (5개 필드 — 적은 필드) ──
    fields3 = extract_template_fields("data/doc_generate/meeting/회의록 양식(doc) (3).docx")
    r = await test_generate(
        "회의록-Form3(5필드)",
        fields3,
        "2026년 3월 18일 본사 대회의실에서 김대표, 이사장, 부장 3명 참석. 주제는 하반기 사업 계획 수립. 해외 진출 방안과 신규 인력 충원에 대해 논의.",
        "회의록",
    )
    results.append(r)

    # ── 테스트 4: 보고서 양식 (13개 필드) ──
    fields4 = extract_template_fields("ai/templates/업무보고서_양식.docx")
    r = await test_generate(
        "보고서(13필드)",
        fields4,
        "이번 주 AI 챗봇 개발 진행 보고. 작성자 신지용, 개발팀. 보고 대상: 김팀장. LangGraph 기반 오케스트레이터 구현 완료, RAG 파이프라인 연동 중. 이슈: Qdrant 인덱싱 속도 느림. 다음 주 계획: 문서 생성 Agent 테스트 및 프론트 연동.",
        "업무보고서",
    )
    results.append(r)

    # ── 테스트 5: 제안서 양식 (16개 필드 — 많은 필드) ──
    fields5 = extract_template_fields("ai/templates/제안서_양식.docx")
    r = await test_generate(
        "제안서(16필드)",
        fields5,
        "AI 기반 업무 자동화 플랫폼 도입 제안. 제안사: 듀듀테크, 담당자: 신지용, 제출처: SK네트웍스. 배경: 반복 업무에 소요되는 시간이 전체 업무의 40%. 목적: AI Agent를 활용한 문서 자동 생성 및 일정 관리 자동화. 예산 5000만원, 기간 6개월. 기대효과: 업무 효율 30% 향상.",
        "제안서",
    )
    results.append(r)

    # ── 테스트 6: 커스텀 필드 (FIELD_MAPPING에 없는 한글 키만) ──
    custom_fields = [
        {"key": "프로젝트명", "label": "프로젝트명", "description": "프로젝트의 공식 이름"},
        {"key": "고객사", "label": "고객사", "description": "고객사/발주처 회사 이름"},
        {"key": "PM", "label": "PM", "description": "프로젝트 매니저 이름"},
        {"key": "시작일", "label": "시작일", "description": "프로젝트 시작 날짜 (YYYY-MM-DD)"},
        {"key": "종료일", "label": "종료일", "description": "프로젝트 종료 예정 날짜 (YYYY-MM-DD)"},
        {"key": "목표", "label": "목표", "description": "프로젝트의 핵심 목표를 2~3문장으로 작성"},
        {"key": "범위", "label": "범위", "description": "프로젝트 수행 범위를 구체적으로 작성"},
        {"key": "산출물", "label": "산출물", "description": "프로젝트 주요 산출물 목록 (배열)"},
    ]
    r = await test_generate(
        "커스텀-기획서(8필드,순수한글)",
        custom_fields,
        "워크플로우 에이전트 프로젝트. 고객사 SK네트웍스, PM 신지용. 4월 1일 시작해서 6월 30일까지. 목표는 AI 기반 업무 자동화 플랫폼 개발. 범위는 챗봇, 문서생성, 일정관리 3개 모듈. 산출물: 웹 애플리케이션, API 서버, 사용자 매뉴얼.",
        "프로젝트 기획서",
    )
    results.append(r)

    # ── 테스트 7: 필드 20개 (학습 분포 크게 초과) ──
    many_fields = [
        {"key": "문서제목", "label": "문서제목", "description": "문서의 공식 제목"},
        {"key": "작성일", "label": "작성일", "description": "작성 날짜 (YYYY-MM-DD)"},
        {"key": "작성자", "label": "작성자", "description": "작성자 이름"},
        {"key": "부서", "label": "부서", "description": "소속 부서명"},
        {"key": "프로젝트명", "label": "프로젝트명", "description": "프로젝트 이름"},
        {"key": "고객사", "label": "고객사", "description": "고객사 이름"},
        {"key": "배경", "label": "배경", "description": "프로젝트 배경 (2~3문장)"},
        {"key": "목적", "label": "목적", "description": "프로젝트 목적 (2~3문장)"},
        {"key": "범위", "label": "범위", "description": "수행 범위"},
        {"key": "일정", "label": "일정", "description": "추진 일정 요약"},
        {"key": "예산", "label": "예산", "description": "총 예산 금액"},
        {"key": "인력구성", "label": "인력구성", "description": "투입 인력 구성"},
        {"key": "기술스택", "label": "기술스택", "description": "사용 기술 목록 (배열)"},
        {"key": "위험요소", "label": "위험요소", "description": "예상 리스크 목록 (배열)"},
        {"key": "대응방안", "label": "대응방안", "description": "리스크 대응 방안"},
        {"key": "기대효과", "label": "기대효과", "description": "기대 효과 (3~5문장)"},
        {"key": "산출물", "label": "산출물", "description": "주요 산출물 목록 (배열)"},
        {"key": "검수기준", "label": "검수기준", "description": "검수/완료 기준"},
        {"key": "특이사항", "label": "특이사항", "description": "특이사항 및 참고"},
        {"key": "승인자", "label": "승인자", "description": "최종 승인자 이름"},
    ]
    r = await test_generate(
        "스트레스-20필드(한글키)",
        many_fields,
        "워크플로우 에이전트 플랫폼 구축 프로젝트. 작성자 신지용, 개발팀. 고객사 SK네트웍스. 배경: 수작업 업무 비효율. 목적: AI 자동화. 범위: 챗봇+문서생성+일정관리. 4월~6월, 예산 8000만원. 인력: 프론트1, 백엔드1, AI3, PM1. 기술: React, FastAPI, LangGraph, Qdrant. 리스크: sLLM 성능 부족 가능성. 대응: LoRA 파인튜닝. 기대효과: 업무시간 30% 절감. 산출물: 웹앱, API, 매뉴얼, 테스트 보고서. 검수: E2E 테스트 통과. 승인자: 김팀장.",
        "프로젝트 제안서",
    )
    results.append(r)

    # ── 결과 보고서 출력 ──
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("  한글 키 LoRA 테스트 결과 보고서")
    report_lines.append("=" * 70)
    report_lines.append("")
    report_lines.append(f"{'테스트':<30s} {'필드':>4s} {'채움':>8s} {'시간':>6s}")
    report_lines.append("-" * 55)
    for r in results:
        report_lines.append(f"{r['name']:<30s} {r['field_count']:>4d} {r['rate']:>8s} {r['elapsed']:>6s}")
    report_lines.append("-" * 55)
    report_lines.append(f"모델: {results[0]['model']}")
    report_lines.append("")

    for r in results:
        report_lines.append(f"\n### {r['name']}")
        report_lines.append(f"필드: {r['fields']}")
        data = r["data"]
        for key in r["fields"]:
            val = data.get(key, "")
            has = bool(val) and val not in ("", [], None, {})
            mark = "O" if has else "X"
            val_str = json.dumps(val, ensure_ascii=False)[:80] if has else "(empty)"
            report_lines.append(f"  [{mark}] {key:20s} = {val_str}")

    report_text = "\n".join(report_lines)
    with open("tests/results_korean_keys.txt", "w", encoding="utf-8") as f:
        f.write(report_text)
    print("결과 저장: tests/results_korean_keys.txt")


if __name__ == "__main__":
    asyncio.run(main())
