# -*- coding: utf-8 -*-
"""M1/M2/M3 회의록 생성 테스트 — Base sLLM (LoRA 없음)"""
import httpx, json, time, sys
sys.stdout.reconfigure(encoding="utf-8")

API = "http://localhost:8000/api/v1"
r = httpx.post(f"{API}/auth/login", json={"email": "v3test2@dudu.dev", "password": "test1234"}, timeout=15)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

cases = [
    ("M1", "30자 짧은 입력", {
        "template_type": "meeting_minutes",
        "fields_data": {"title": "주간 팀 미팅", "date": "2026-03-19"},
        "content": "주간 팀 미팅, API 스키마 확정 논의",
    }),
    ("M2", "200자 중간 입력", {
        "template_type": "meeting_minutes",
        "fields_data": {"title": "Q1 스프린트 리뷰", "date": "2026-03-19", "attendees": ["김철수", "이영희", "박지민"]},
        "content": "Q1 스프린트 리뷰 회의. 참석자: 김철수(PM), 이영희(백엔드), 박지민(프론트). 안건 1: API 스키마 v2 검토 - RESTful 규칙 준수 확인. 안건 2: DB 마이그레이션 일정 - 3월 25일까지 완료 목표. 안건 3: 프론트엔드 디자인 시안 검토. 결정사항: API 스키마 v2 확정, DB 마이그레이션 담당 이영희.",
    }),
    ("M3", "500자 긴 입력", {
        "template_type": "meeting_minutes",
        "fields_data": {"title": "2026 Q1 개발팀 정기 회의", "date": "2026-03-19", "attendees": ["김철수", "이영희", "박지민", "최수진"]},
        "content": "2026년 Q1 개발팀 정기 회의. 참석자: 김철수(PM), 이영희(백엔드), 박지민(프론트), 최수진(QA). 안건 1: 인증 모듈 리팩토링 - JWT 토큰 갱신 로직에 보안 취약점 발견. 이영희가 3월 22일까지 패치 완료 예정. 코드 리뷰는 김철수 담당. 안건 2: 프론트엔드 성능 개선 - Lighthouse 점수 72점에서 85점 목표. 박지민이 이미지 최적화 + 코드 스플리팅 적용 예정, 기한 3월 28일. 안건 3: QA 자동화 - E2E 테스트 커버리지 현재 45%에서 70%로 확대. 최수진이 Playwright 도입 검토 후 4월 5일까지 PoC 완료. 결정사항: (1) JWT 패치 우선 진행, (2) Lighthouse 85점 달성 시 배포, (3) Playwright PoC 결과에 따라 도입 결정. 다음 회의: 2026-03-26 14:00.",
    }),
]

for cid, desc, payload in cases:
    print()
    print("=" * 50)
    print(f"[{cid}-BASE] {desc}")
    print("=" * 50)

    start = time.time()
    r = httpx.post(f"{API}/documents/generate", json=payload, headers=headers, timeout=120)
    elapsed = time.time() - start

    if r.status_code != 200:
        print(f"FAIL: HTTP {r.status_code} ({elapsed:.1f}s)")
        print(r.text[:300])
        continue

    body = r.json()
    doc_id = body.get("document_id", "")
    model = body.get("model_name", "?")
    print(f"OK ({elapsed:.1f}s) model: {model}")
    print(f"document_id: {doc_id}")
    docx_path = f"C:\\SKN21-FINAL-3TEAM\\backend\\generated_docs\\{doc_id}.docx"
    print(f"DOCX: {docx_path}")

    with open(f"tests/{cid.lower()}_base_result.json", "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)

print("\n완료!")
