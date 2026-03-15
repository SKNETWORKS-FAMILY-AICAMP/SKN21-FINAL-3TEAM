"""
SKN_3TEAM 프로젝트에 실제 파이프라인 태스크를 생성하는 스크립트
각 팀원의 작업 로그 기반으로 태스크를 구성
"""
import requests
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://3.37.118.197:8000/api/v1"

# 로그인
login_resp = requests.post(f"{BASE}/auth/login", json={
    "email": "yoon@dudu.com",
    "password": "test1234"
})
if login_resp.status_code != 200:
    print(f"로그인 실패: {login_resp.text}")
    sys.exit(1)

TOKEN = login_resp.json()["access_token"]
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

PROJECT = "SKN_3TEAM"

# 프로젝트 생성 (이미 있으면 409 — 무시)
proj_resp = requests.post(f"{BASE}/pipeline/projects", headers=HEADERS, json={
    "name": PROJECT,
    "description": "SKN21 3팀 최종 프로젝트 - 듀듀 WorkFlow Agent",
    "members": ["신지용", "윤경은", "안혜빈", "문지영", "진승언"]
})
print(f"프로젝트 생성: {proj_resp.status_code} {proj_resp.text}")

# 이미 존재하면 members 업데이트
if proj_resp.status_code == 409:
    # 프로젝트 ID 조회 후 멤버 업데이트
    list_resp = requests.get(f"{BASE}/pipeline/projects", headers=HEADERS)
    if list_resp.status_code == 200:
        for p in list_resp.json():
            if p["name"] == PROJECT:
                upd_resp = requests.put(f"{BASE}/pipeline/projects/{p['id']}", headers=HEADERS, json={
                    "members": ["신지용", "윤경은", "안혜빈", "문지영", "진승언"]
                })
                print(f"멤버 업데이트: {upd_resp.status_code} {upd_resp.text}")
                break

# ── 태스크 목록 (로그 기반) ──
TASKS = [
    # ── 신지용 (PM) ──
    {"title": "Intent 분류 모델 파인튜닝 (v1.0~v1.4)", "assignee": "신지용", "stage": "done", "priority": "high", "due_date": "2026-02-11", "tags": ["AI", "Intent", "파인튜닝"], "description": "klue/bert-base 기반 7개 카테고리 분류 모델 학습. v1.3 최종 모델 (Eval F1 98.63%, Adversarial 91.67%)"},
    {"title": "LangGraph 오케스트레이터 구현", "assignee": "신지용", "stage": "done", "priority": "high", "due_date": "2026-02-12", "tags": ["AI", "LangGraph", "오케스트레이터"], "description": "Agent 라우팅 + SSE 스트리밍 + Intent 기반 분기 처리"},
    {"title": "복합질문(Compound Query) 처리 시스템", "assignee": "신지용", "stage": "done", "priority": "high", "due_date": "2026-03-06", "tags": ["AI", "Intent", "멀티라벨"], "description": "멀티라벨 분류 + 복합질문 분해 + 병렬 Agent 실행"},
    {"title": "Intent 6-label 앙상블 학습", "assignee": "신지용", "stage": "in_progress", "priority": "high", "due_date": "2026-03-14", "tags": ["AI", "Intent", "앙상블", "RunPod"], "description": "klue/roberta-large 5-seed 앙상블 + Focal Loss + FGM. 6-label 재학습 진행중"},
    {"title": "Intent 8→7→6개 축소 리팩토링", "assignee": "신지용", "stage": "done", "priority": "medium", "due_date": "2026-03-13", "tags": ["AI", "리팩토링"], "description": "doc_qa+doc_search+doc_summary → doc_retrieve 통합. 전체 스택 27개 파일 수정"},
    {"title": "ML 비교 실험 (발표용)", "assignee": "신지용", "stage": "done", "priority": "medium", "due_date": "2026-02-11", "tags": ["AI", "실험", "발표"], "description": "6가지 방법론 비교 + GPT Few-shot vs BERT Fine-tuned 성능 분석"},

    # ── 윤경은 (AI서브) ──
    {"title": "RAG 파이프라인 구현 (Qdrant + BM25 하이브리드)", "assignee": "윤경은", "stage": "done", "priority": "high", "due_date": "2026-02-12", "tags": ["AI", "RAG", "Qdrant", "BM25"], "description": "BM25+Vector 하이브리드 검색, RRF 합산, CrossEncoder 리랭커, scope 필터링"},
    {"title": "판단 Agent 고도화 (다중 규정 교차 판단)", "assignee": "윤경은", "stage": "done", "priority": "high", "due_date": "2026-02-12", "tags": ["AI", "Agent", "판단"], "description": "규정 교차 분석, confidence 보정, 판단 이력 참조, SSE 스트리밍"},
    {"title": "Sheets 미리보기 + 인라인 편집", "assignee": "윤경은", "stage": "done", "priority": "medium", "due_date": "2026-03-10", "tags": ["Backend", "Frontend", "Sheets"], "description": "시트 데이터 읽기/쓰기 API + 프론트 테이블 렌더링 + 셀 편집"},
    {"title": "Sheets 확장 탭 (Gantt/Dashboard/Risk/Report)", "assignee": "윤경은", "stage": "done", "priority": "high", "due_date": "2026-03-12", "tags": ["Backend", "AI", "Sheets"], "description": "간트 차트 + 통합 대시보드 + AI 리스크 분석 + AI 주간 보고서 탭 자동 생성"},
    {"title": "sLLM 전환 테스트 (schedule agent)", "assignee": "윤경은", "stage": "in_progress", "priority": "medium", "due_date": "2026-03-15", "tags": ["AI", "sLLM", "vLLM"], "description": "Kanana-8B/Qwen3-8B 기반 schedule 파싱 sLLM 전환 테스트"},
    {"title": "모델 벤치마크 (3개 모델 비교)", "assignee": "윤경은", "stage": "done", "priority": "high", "due_date": "2026-02-11", "tags": ["AI", "벤치마크", "RunPod"], "description": "EXAONE/Kanana/Qwen3 벤치마크 → Kanana-1.5-8B 최종 선정"},

    # ── 안혜빈 (Backend) ──
    {"title": "DB 스키마 확정 + Alembic 마이그레이션", "assignee": "안혜빈", "stage": "done", "priority": "high", "due_date": "2026-02-11", "tags": ["Backend", "DB", "PostgreSQL"], "description": "11개 테이블 ORM 모델 + Alembic 초기/변경 마이그레이션 + ERD 작성"},
    {"title": "JWT 인증 + Google OAuth 구현", "assignee": "안혜빈", "stage": "done", "priority": "high", "due_date": "2026-02-11", "tags": ["Backend", "인증", "OAuth"], "description": "JWT 생성/검증, bcrypt, AES-256, Google OAuth 소셜 로그인"},
    {"title": "Google Services 4종 구현", "assignee": "안혜빈", "stage": "done", "priority": "high", "due_date": "2026-02-11", "tags": ["Backend", "Google", "Calendar", "Tasks", "Gmail", "Sheets"], "description": "Calendar/Tasks/Gmail/Sheets 양방향 동기화 + API 라우터"},
    {"title": "문서 업로드 API + 텍스트 추출", "assignee": "안혜빈", "stage": "done", "priority": "high", "due_date": "2026-02-12", "tags": ["Backend", "문서", "API"], "description": "PDF/DOCX/TXT 업로드 + PyMuPDF 추출 + 11개 엔드포인트"},
    {"title": "Pipeline→Sheets 내보내기", "assignee": "안혜빈", "stage": "done", "priority": "medium", "due_date": "2026-03-11", "tags": ["Backend", "Sheets", "Pipeline"], "description": "프로젝트 태스크를 Google Sheets로 내보내기 + D-day 계산 + 서식 적용"},
    {"title": "EC2 서버 안정화 (OOM/커넥션풀)", "assignee": "안혜빈", "stage": "done", "priority": "high", "due_date": "2026-03-12", "tags": ["Backend", "인프라", "EC2"], "description": "DB 커넥션풀 최적화 + startup 백그라운드 전환 + OOM 해결"},
    {"title": "화면설계서 PDF 완성 (35페이지)", "assignee": "안혜빈", "stage": "done", "priority": "medium", "due_date": "2026-03-11", "tags": ["문서", "설계서"], "description": "다크모드 포함 35페이지 화면설계서"},

    # ── 문지영 (Frontend) ──
    {"title": "프로젝트 초기 세팅 + 디자인 시스템", "assignee": "문지영", "stage": "done", "priority": "high", "due_date": "2026-02-09", "tags": ["Frontend", "React", "Tailwind"], "description": "React+Vite+Tailwind 구성, 컬러 토큰, 디렉토리 구조"},
    {"title": "로그인/회원가입 + 대시보드 + 챗봇 UI", "assignee": "문지영", "stage": "done", "priority": "high", "due_date": "2026-02-10", "tags": ["Frontend", "UI", "대시보드", "챗봇"], "description": "대시보드 11개 컴포넌트 + 챗봇 UI 13개 컴포넌트 + Zustand 4개 스토어"},
    {"title": "Google Services 통합 UI", "assignee": "문지영", "stage": "done", "priority": "high", "due_date": "2026-02-11", "tags": ["Frontend", "Google", "UI"], "description": "Calendar/Tasks/Gmail/Sheets/Meet 5개 서비스 통합 UI"},
    {"title": "다크모드 + 글씨 크기 조절", "assignee": "문지영", "stage": "done", "priority": "medium", "due_date": "2026-02-14", "tags": ["Frontend", "UI", "다크모드"], "description": "CSS 변수 방식 다크모드 + 가-/가+ 글씨 크기 5단계 조절"},
    {"title": "문서 생성 시스템 UI", "assignee": "문지영", "stage": "done", "priority": "high", "due_date": "2026-02-10", "tags": ["Frontend", "문서", "UI"], "description": "회의록 생성 + 문서 생성 페이지 (템플릿 선택/업로드 + AI 생성)"},
    {"title": "Intent 6-label 프론트 리팩토링", "assignee": "문지영", "stage": "done", "priority": "medium", "due_date": "2026-03-13", "tags": ["Frontend", "Intent", "리팩토링"], "description": "doc_qa+doc_search+doc_summary → doc_retrieve 통합 UI 반영"},
    {"title": "백엔드 실제 연동 (Mock 교체)", "assignee": "문지영", "stage": "in_progress", "priority": "high", "due_date": "2026-03-18", "tags": ["Frontend", "API", "연동"], "description": "대시보드/문서 생성 등 Mock 데이터를 실제 API로 교체"},

    # ── 진승언 (AI리드) ──
    {"title": "Document Agent 구현 + 테스트", "assignee": "진승언", "stage": "done", "priority": "high", "due_date": "2026-02-12", "tags": ["AI", "Agent", "문서"], "description": "doc_search/doc_generate/meeting_generate intent 분기 + LLM 호출 + State 전달 검증"},
    {"title": "CI/CD GitHub Actions 구축", "assignee": "진승언", "stage": "done", "priority": "high", "due_date": "2026-02-19", "tags": ["인프라", "CI/CD", "EC2"], "description": "develop push → EC2 자동 배포 + systemd 서비스 + SSH 인증"},
    {"title": "문서 요약 환각 수정 + doc_pick", "assignee": "진승언", "stage": "done", "priority": "high", "due_date": "2026-02-24", "tags": ["AI", "Agent", "버그수정"], "description": "DOCX 테이블 추출 누락 + user_input fallback 제거 + 문서 선택 UI"},
    {"title": "vLLM RunPod Serverless 연결", "assignee": "진승언", "stage": "in_progress", "priority": "high", "due_date": "2026-03-14", "tags": ["AI", "vLLM", "RunPod", "인프라"], "description": "Kanana-1.5-8B base model 연결 + cold start 해결 + LoRA 어댑터 연결 진행중"},
    {"title": "문서 생성 form 플래그 + DB 경로 통합", "assignee": "진승언", "stage": "done", "priority": "medium", "due_date": "2026-03-12", "tags": ["AI", "Backend", "문서생성"], "description": "시스템 템플릿 form:true/false 분리 + DB 경로 우선 + 하드코딩 fallback"},
]

print(f"\n총 {len(TASKS)}개 태스크 생성 시작...\n")

success = 0
fail = 0
for t in TASKS:
    t["project"] = PROJECT
    resp = requests.post(f"{BASE}/pipeline/", headers=HEADERS, json=t)
    if resp.status_code in (200, 201):
        data = resp.json()
        print(f"  OK [{t['stage']:12s}] {t['assignee']}: {t['title']}")
        success += 1
    else:
        print(f"  FAIL [{resp.status_code}] {t['assignee']}: {t['title']} — {resp.text[:100]}")
        fail += 1

print(f"\n완료: {success}개 성공, {fail}개 실패")
