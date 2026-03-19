# -*- coding: utf-8 -*-
"""P1/P2/P3 제안서 생성 테스트"""
import httpx, json, shutil, sys
from pathlib import Path
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8")

API = "http://localhost:8000/api/v1"
GENERATED = Path("backend/generated_docs")
RESULTS = Path("tests/results/제안서")
RESULTS.mkdir(parents=True, exist_ok=True)

r = httpx.post(f"{API}/auth/login", json={"email": "v3test2@dudu.dev", "password": "test1234"}, timeout=30)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

cases = [
    ("P1", "100자 짧은 입력", {
        "template_type": "proposal",
        "fields_data": {"title": "재택근무 제도 도입 제안", "date": "2026-03-19", "company": "듀듀 주식회사", "manager": "김철수"},
        "content": "재택근무 제도 도입 제안. 주 2회 재택근무로 출퇴근 시간 절약 및 업무 만족도 향상 기대.",
    }),
    ("P2", "200자 중간 입력", {
        "template_type": "proposal",
        "fields_data": {"title": "사내 업무 자동화 시스템 도입 제안", "date": "2026-03-19", "company": "듀듀 주식회사", "manager": "김철수"},
        "content": "사내 업무 자동화 시스템 도입 제안. 현황: 수동 문서 작성에 월 평균 40시간 소요. 예산: 초기 도입비 5000만원, 월 운영비 200만원. 일정: 2026년 4월 PoC 시작, 6월 파일럿 운영, 8월 전사 도입.",
    }),
    ("P3", "500자 긴 입력", {
        "template_type": "proposal",
        "fields_data": {"title": "AI 기반 문서 자동화 플랫폼 구축 제안서", "date": "2026-03-19", "company": "듀듀 주식회사", "manager": "김철수"},
        "content": "AI 기반 문서 자동화 플랫폼 구축 제안서. 배경: 현재 사내 문서 작성은 수동으로 이루어지며, 팀당 월 평균 40시간 소요. 반복 업무(회의록, 보고서)가 전체 문서의 70%를 차지하여 자동화 효과가 높음. 현황 분석: 직원 설문 결과, 문서 작성 업무에 대한 불만족도 65%. 기존 솔루션 검토: A사 제품(월 500만원, 한국어 미지원), B사 제품(월 300만원, 커스텀 불가). 예산 항목: 인프라 구축 3000만원, LLM API 비용 월 150만원, 인건비 2000만원, 총 예산 5150만원 + 월 운영비 200만원. 추진 일정: 4월 요구사항 분석 및 설계(2주), 5~6월 개발(8주), 7월 내부 테스트(2주), 8월 파일럿(2주), 9월 전사 도입. 기대 효과: 문서 작성 시간 60% 절감, 연간 인건비 1억원 절약 예상.",
    }),
]

now_str = datetime.now().strftime("%H%M%S")

for cid, desc, payload in cases:
    print()
    print("=" * 50)
    print(f"[{cid}] {desc}")
    print("=" * 50)

    r = httpx.post(f"{API}/documents/generate", json=payload, headers=headers, timeout=180)

    if r.status_code != 200:
        print(f"FAIL: HTTP {r.status_code}")
        print(r.text[:300])
        continue

    body = r.json()
    data = body["data"]
    doc_id = body["document_id"]
    title = data.get("title", cid)
    model = body.get("model_name", "?")
    print(f"OK - model: {model}")
    print(f"  title: {data.get('title', '')}")
    print(f"  submit_date: {data.get('submit_date', '')}")
    print(f"  company: {data.get('company', '')}")
    print(f"  manager: {data.get('manager', '')}")
    print(f"  purpose: {str(data.get('purpose', ''))[:80]}")
    print(f"  current_situation: {str(data.get('current_situation', ''))[:80]}")
    print(f"  schedule: {len(data.get('schedule', []))}개")
    print(f"  budget: {len(data.get('budget', []))}개")
    print(f"  expected_effect: {str(data.get('expected_effect', ''))[:80]}")

    safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "_")[:30]
    src = GENERATED / f"{doc_id}.docx"
    dest = RESULTS / f"{cid}_{safe_title}_{now_str}.docx"
    if src.exists():
        shutil.copy2(src, dest)
        print(f"  DOCX: {dest}")

    with open(f"tests/{cid.lower()}_result.json", "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)

print("\n완료!")
