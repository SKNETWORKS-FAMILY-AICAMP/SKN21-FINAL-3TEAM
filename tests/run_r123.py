# -*- coding: utf-8 -*-
"""R1/R2/R3 보고서 생성 테스트"""
import httpx, json, shutil, sys
from pathlib import Path
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8")

API = "http://localhost:8000/api/v1"
GENERATED = Path("backend/generated_docs")
RESULTS = Path("tests/results/보고서")
RESULTS.mkdir(parents=True, exist_ok=True)

r = httpx.post(f"{API}/auth/login", json={"email": "v3test2@dudu.dev", "password": "test1234"}, timeout=30)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

cases = [
    ("R1", "100자 짧은 입력", {
        "template_type": "report",
        "fields_data": {"title": "3월 주간 업무 보고", "date": "2026-03-19", "author": "김철수", "department": "개발팀"},
        "content": "이번 주 API 개발 완료. 다음 주 테스트 예정.",
    }),
    ("R2", "200자 중간 입력", {
        "template_type": "report",
        "fields_data": {"title": "3월 개발 진행 현황 보고", "date": "2026-03-19", "author": "김철수", "department": "개발팀"},
        "content": "3월 개발 진행 현황 보고. 담당자: 김철수(백엔드 60% 완료), 이영희(프론트 40% 완료). 주요 이슈: API 응답 지연 문제 발생 (평균 2.3초 → 목표 1초 이내). 원인 분석 중이며 DB 인덱싱 최적화 예정.",
    }),
    ("R3", "500자 긴 입력", {
        "template_type": "report",
        "fields_data": {"title": "Q1 프로젝트 중간 보고서", "date": "2026-03-19", "author": "김철수", "department": "개발팀"},
        "content": "Q1 프로젝트 중간 보고서. 담당자별 진행 현황: 김철수(PM) — 일정 관리 및 코드 리뷰, 전체 진행률 55%. 이영희(백엔드) — API 개발 70% 완료, 인증 모듈 완료, DB 마이그레이션 진행 중. 박지민(프론트) — UI 개발 50% 완료, 대시보드 페이지 완료, 문서 관리 페이지 작업 중. 주요 이슈: (1) API 응답 시간 평균 2.3초로 목표(1초) 미달, (2) 프론트엔드 번들 사이즈 3.2MB로 최적화 필요. 향후 계획: 3월 25일까지 DB 인덱싱 최적화, 3월 28일까지 코드 스플리팅 적용, 4월 1일 E2E 테스트 시작.",
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
    print(f"  date: {data.get('date', '')}")
    print(f"  author: {data.get('author', '')}")
    print(f"  department: {data.get('department', '')}")
    print(f"  overview: {str(data.get('overview', ''))[:80]}")
    print(f"  main_content: {str(data.get('main_content', ''))[:80]}")
    print(f"  tasks: {len(data.get('tasks', []))}개")
    print(f"  issues: {str(data.get('issues', ''))[:80]}")
    print(f"  next_plan: {str(data.get('next_plan', ''))[:80]}")

    safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "_")[:30]
    src = GENERATED / f"{doc_id}.docx"
    dest = RESULTS / f"{cid}_{safe_title}_{now_str}.docx"
    if src.exists():
        shutil.copy2(src, dest)
        print(f"  DOCX: {dest}")

    with open(f"tests/{cid.lower()}_result.json", "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)

print("\n완료!")
