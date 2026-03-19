# -*- coding: utf-8 -*-
"""보고서(R2,R3) + 제안서(P2,P3) 생성 테스트 — 결과를 유형별 폴더에 제목+시간으로 복사"""
import httpx, json, shutil, sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

API = "http://localhost:8000/api/v1"
GENERATED = Path("backend/generated_docs")
RESULTS = Path("tests/results")

r = httpx.post(f"{API}/auth/login", json={"email": "v3test2@dudu.dev", "password": "test1234"}, timeout=15)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

cases = [
    # ── 보고서 ──
    ("R2", "report", "보고서", "200자 중간", {
        "template_type": "report",
        "fields_data": {
            "title": "3월 개발 진행 현황 보고",
            "date": "2026-03-19",
            "author": "김철수",
            "department": "개발팀",
        },
        "content": "3월 개발 진행 현황 보고. 담당자: 김철수(백엔드 60% 완료), 이영희(프론트 40% 완료). 주요 이슈: API 응답 지연 문제 발생 (평균 2.3초 → 목표 1초 이내). 원인 분석 중이며 DB 인덱싱 최적화 예정.",
    }),
    ("R3", "report", "보고서", "500자 긴 입력", {
        "template_type": "report",
        "fields_data": {
            "title": "Q1 프로젝트 중간 보고서",
            "date": "2026-03-19",
            "author": "김철수",
            "department": "개발팀",
        },
        "content": "Q1 프로젝트 중간 보고서. 담당자별 진행 현황: 김철수(PM) — 일정 관리 및 코드 리뷰, 전체 진행률 55%. 이영희(백엔드) — API 개발 70% 완료, 인증 모듈 완료, DB 마이그레이션 진행 중. 박지민(프론트) — UI 개발 50% 완료, 대시보드 페이지 완료, 문서 관리 페이지 작업 중. 주요 이슈: (1) API 응답 시간 평균 2.3초로 목표(1초) 미달, (2) 프론트엔드 번들 사이즈 3.2MB로 최적화 필요. 향후 계획: 3월 25일까지 DB 인덱싱 최적화, 3월 28일까지 코드 스플리팅 적용, 4월 1일 E2E 테스트 시작.",
    }),
    # ── 제안서 ──
    ("P2", "proposal", "제안서", "200자 중간", {
        "template_type": "proposal",
        "fields_data": {
            "title": "사내 업무 자동화 시스템 도입 제안",
            "date": "2026-03-19",
            "company": "듀듀 주식회사",
            "manager": "김철수",
        },
        "content": "사내 업무 자동화 시스템 도입 제안. 현황: 수동 문서 작성에 월 평균 40시간 소요. 예산: 초기 도입비 5000만원, 월 운영비 200만원. 일정: 2026년 4월 PoC 시작, 6월 파일럿 운영, 8월 전사 도입.",
    }),
    ("P3", "proposal", "제안서", "500자 긴 입력", {
        "template_type": "proposal",
        "fields_data": {
            "title": "AI 기반 문서 자동화 플랫폼 구축 제안서",
            "date": "2026-03-19",
            "company": "듀듀 주식회사",
            "manager": "김철수",
        },
        "content": "AI 기반 문서 자동화 플랫폼 구축 제안서. 배경: 현재 사내 문서 작성은 수동으로 이루어지며, 팀당 월 평균 40시간 소요. 반복 업무(회의록, 보고서)가 전체 문서의 70%를 차지하여 자동화 효과가 높음. 현황 분석: 직원 설문 결과, 문서 작성 업무에 대한 불만족도 65%. 기존 솔루션 검토: A사 제품(월 500만원, 한국어 미지원), B사 제품(월 300만원, 커스텀 불가). 예산 항목: 인프라 구축 3000만원, LLM API 비용 월 150만원, 인건비 2000만원, 총 예산 5150만원 + 월 운영비 200만원. 추진 일정: 4월 요구사항 분석 및 설계(2주), 5~6월 개발(8주), 7월 내부 테스트(2주), 8월 파일럿(2주), 9월 전사 도입. 기대 효과: 문서 작성 시간 60% 절감, 연간 인건비 1억원 절약 예상.",
    }),
]

now_str = datetime.now().strftime("%H%M%S")

for cid, ttype, folder_name, desc, payload in cases:
    print()
    print("=" * 50)
    print(f"[{cid}] {folder_name} — {desc}")
    print("=" * 50)

    r = httpx.post(f"{API}/documents/generate", json=payload, headers=headers, timeout=120)

    if r.status_code != 200:
        print(f"FAIL: HTTP {r.status_code}")
        print(r.text[:300])
        continue

    body = r.json()
    doc_id = body["document_id"]
    data = body["data"]
    title = data.get("title", cid)
    model = body.get("model_name", "?")
    print(f"OK — model: {model}")

    # JSON 저장
    with open(f"tests/{cid.lower()}_result.json", "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)

    # 유형별 폴더에 제목+시간으로 복사
    dest_dir = RESULTS / folder_name
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "_")[:30]
    dest_name = f"{safe_title}_{now_str}.docx"
    src = GENERATED / f"{doc_id}.docx"
    dest = dest_dir / dest_name
    if src.exists():
        shutil.copy2(src, dest)
        print(f"DOCX: {dest}")
    else:
        print(f"DOCX 원본 없음: {src}")

    print(f"[content] {str(data.get('content',''))[:150]}...")

print("\n완료!")
