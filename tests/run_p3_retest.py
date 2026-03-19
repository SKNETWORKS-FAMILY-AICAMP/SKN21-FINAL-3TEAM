# -*- coding: utf-8 -*-
"""P3 제안서 재테스트"""
import httpx, json, shutil, sys
from pathlib import Path
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8")

API = "http://localhost:8000/api/v1"
r = httpx.post(f"{API}/auth/login", json={"email": "v3test2@dudu.dev", "password": "test1234"}, timeout=30)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

r = httpx.post(f"{API}/documents/generate", json={
    "template_type": "proposal",
    "fields_data": {
        "title": "AI 기반 문서 자동화 플랫폼 구축 제안서",
        "date": "2026-03-19",
        "company": "듀듀 주식회사",
        "manager": "김철수",
    },
    "content": "AI 기반 문서 자동화 플랫폼 구축 제안서. 배경: 현재 사내 문서 작성은 수동으로 이루어지며, 팀당 월 평균 40시간 소요. 반복 업무(회의록, 보고서)가 전체 문서의 70%를 차지하여 자동화 효과가 높음. 현황 분석: 직원 설문 결과, 문서 작성 업무에 대한 불만족도 65%. 기존 솔루션 검토: A사 제품(월 500만원, 한국어 미지원), B사 제품(월 300만원, 커스텀 불가). 예산 항목: 인프라 구축 3000만원, LLM API 비용 월 150만원, 인건비 2000만원, 총 예산 5150만원 + 월 운영비 200만원. 추진 일정: 4월 요구사항 분석 및 설계(2주), 5~6월 개발(8주), 7월 내부 테스트(2주), 8월 파일럿(2주), 9월 전사 도입. 기대 효과: 문서 작성 시간 60% 절감, 연간 인건비 1억원 절약 예상."
}, headers=headers, timeout=180)

body = r.json()
data = body["data"]
doc_id = body["document_id"]

print(f"model: {body.get('model_name', '?')}")
print(f"purpose: {data.get('purpose', '')[:100]}")
print(f"background: {data.get('background', '')[:100]}")
print(f"schedule: {len(data.get('schedule', []))}개")
print(f"budget: {len(data.get('budget', []))}개")
print(f"expected_effect: {data.get('expected_effect', '')[:100]}")
print(f"content type: {type(data.get('content', '')).__name__}, len: {len(str(data.get('content', '')))}")

dest = Path("tests/results/제안서")
dest.mkdir(parents=True, exist_ok=True)
src = Path(f"backend/generated_docs/{doc_id}.docx")
if src.exists():
    ts = datetime.now().strftime("%H%M%S")
    shutil.copy2(src, dest / f"P3_재테스트_{ts}.docx")
    print(f"DOCX: tests/results/제안서/P3_재테스트_{ts}.docx")

with open("tests/p3_result.json", "w", encoding="utf-8") as f:
    json.dump(body, f, ensure_ascii=False, indent=2)
