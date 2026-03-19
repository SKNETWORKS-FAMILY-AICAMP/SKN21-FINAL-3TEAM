"""
v3_generate 문서 생성 통합 테스트
=================================
LoRA v3_generate 어댑터를 통한 실제 문서 생성 파이프라인 검증.
백엔드 → document_agent → RunPod vLLM(v3_generate) → JSON → DOCX

테스트 목적:
  1. 전체 파이프라인 정상 동작
  2. 필드 채움률 (핵심 필드가 적절히 채워지는지)
  3. 할루시네이션 체크 (입력에 없는 내용을 지어내지 않는지)
  4. 기본 템플릿 3종 (회의록/보고서/제안서)

실행 방법:
  1. 백엔드 서버 기동: cd backend && uvicorn app.main:app --reload --port 8000
  2. python tests/test_v3_generate.py

환경 변수 (.env):
  DOC_AGENT_MODE=sllm
  VLLM_USE_LORA=true
  VLLM_BASE_URL=https://api.runpod.ai/v2/0e5gus1dyiqj00/openai/v1
  VLLM_API_KEY=...
"""

import sys
import os
import json
import time
import re
import argparse
import httpx
from pathlib import Path
from datetime import datetime

# ── 설정 ──
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
API = f"{BASE_URL}/api/v1"

TEST_USER = {
    "email": "test_v3gen@dudu.dev",
    "password": "testpass1234!",
    "name": "v3테스터",
    "team": "개발팀",
}

REQUEST_TIMEOUT = 120  # RunPod cold start 고려

# ── 7개 테스트 케이스 ──

CASES = [
    # ── 회의록 (meeting_minutes) ──
    {
        "id": "M1",
        "template_type": "meeting_minutes",
        "input_length": "short",
        "fields_data": {
            "title": "주간 팀 미팅",
            "date": "2026-03-19",
        },
        "content": "주간 팀 미팅, API 스키마 확정 논의",
        "description": "짧은 입력 (~50자) — 확장 억제 검증",
        "expected_facts": ["API 스키마"],
        "key_fields": ["decisions", "action_items"],
    },
    {
        "id": "M2",
        "template_type": "meeting_minutes",
        "input_length": "medium",
        "fields_data": {
            "title": "Q1 스프린트 리뷰",
            "date": "2026-03-19",
            "attendees": ["김철수", "이영희", "박지민"],
        },
        "content": (
            "Q1 스프린트 리뷰 회의. 참석자: 김철수(PM), 이영희(백엔드), 박지민(프론트). "
            "안건 1: API 스키마 v2 검토 — RESTful 규칙 준수 확인. "
            "안건 2: DB 마이그레이션 일정 — 3월 25일까지 완료 목표. "
            "안건 3: 프론트엔드 디자인 시안 검토. "
            "결정사항: API 스키마 v2 확정, DB 마이그레이션 담당 이영희."
        ),
        "description": "중간 입력 (~200자) — 참석자 3명 + 안건 3개 + 결정사항",
        "expected_facts": ["김철수", "이영희", "박지민", "API 스키마 v2", "3월 25일", "DB 마이그레이션"],
        "key_fields": ["decisions", "action_items"],
    },
    {
        "id": "M3",
        "template_type": "meeting_minutes",
        "input_length": "long",
        "fields_data": {
            "title": "2026 Q1 개발팀 정기 회의",
            "date": "2026-03-19",
            "attendees": ["김철수", "이영희", "박지민", "최수진"],
        },
        "content": (
            "2026년 Q1 개발팀 정기 회의. 참석자: 김철수(PM), 이영희(백엔드), 박지민(프론트), 최수진(QA). "
            "안건 1: 인증 모듈 리팩토링 — JWT 토큰 갱신 로직에 보안 취약점 발견. "
            "이영희가 3월 22일까지 패치 완료 예정. 코드 리뷰는 김철수 담당. "
            "안건 2: 프론트엔드 성능 개선 — Lighthouse 점수 72점에서 85점 목표. "
            "박지민이 이미지 최적화 + 코드 스플리팅 적용 예정, 기한 3월 28일. "
            "안건 3: QA 자동화 — E2E 테스트 커버리지 현재 45%에서 70%로 확대. "
            "최수진이 Playwright 도입 검토 후 4월 5일까지 PoC 완료. "
            "결정사항: (1) JWT 패치 우선 진행, (2) Lighthouse 85점 달성 시 배포, "
            "(3) Playwright PoC 결과에 따라 도입 결정. "
            "다음 회의: 2026-03-26 14:00."
        ),
        "description": "긴 입력 (~500자) — 안건 3개 상세 + 결정사항 + 담당자 + 기한",
        "expected_facts": [
            "김철수", "이영희", "박지민", "최수진",
            "JWT", "3월 22일", "Lighthouse", "72", "85",
            "3월 28일", "Playwright", "4월 5일", "45%", "70%",
        ],
        "key_fields": ["decisions", "action_items"],
    },
    # ── 보고서 (report) ──
    {
        "id": "R2",
        "template_type": "report",
        "input_length": "medium",
        "fields_data": {
            "title": "3월 개발 진행 현황 보고",
            "date": "2026-03-19",
            "author": "김철수",
            "department": "개발팀",
        },
        "content": (
            "3월 개발 진행 현황 보고. 담당자: 김철수(백엔드 60% 완료), 이영희(프론트 40% 완료). "
            "주요 이슈: API 응답 지연 문제 발생 (평균 2.3초 → 목표 1초 이내). "
            "원인 분석 중이며 DB 인덱싱 최적화 예정."
        ),
        "description": "중간 입력 (~200자) — 담당자 2명 + 진행률 + 이슈",
        "expected_facts": ["김철수", "이영희", "60%", "40%", "2.3초", "1초"],
        "key_fields": ["tasks", "next_plan"],
    },
    {
        "id": "R3",
        "template_type": "report",
        "input_length": "long",
        "fields_data": {
            "title": "Q1 프로젝트 중간 보고서",
            "date": "2026-03-19",
            "author": "김철수",
            "department": "개발팀",
        },
        "content": (
            "Q1 프로젝트 중간 보고서. "
            "담당자별 진행 현황: "
            "김철수(PM) — 일정 관리 및 코드 리뷰, 전체 진행률 55%. "
            "이영희(백엔드) — API 개발 70% 완료, 인증 모듈 완료, DB 마이그레이션 진행 중. "
            "박지민(프론트) — UI 개발 50% 완료, 대시보드 페이지 완료, 문서 관리 페이지 작업 중. "
            "주요 이슈: (1) API 응답 시간 평균 2.3초로 목표(1초) 미달, "
            "(2) 프론트엔드 번들 사이즈 3.2MB로 최적화 필요. "
            "향후 계획: 3월 25일까지 DB 인덱싱 최적화, 3월 28일까지 코드 스플리팅 적용, "
            "4월 1일 E2E 테스트 시작."
        ),
        "description": "긴 입력 (~500자) — 담당자 3명 + 진행률 + 이슈 + 향후 계획",
        "expected_facts": [
            "김철수", "이영희", "박지민", "55%", "70%", "50%",
            "2.3초", "1초", "3.2MB", "3월 25일", "3월 28일", "4월 1일",
        ],
        "key_fields": ["tasks", "next_plan"],
    },
    # ── 제안서 (proposal) ──
    {
        "id": "P2",
        "template_type": "proposal",
        "input_length": "medium",
        "fields_data": {
            "title": "사내 업무 자동화 시스템 도입 제안",
            "date": "2026-03-19",
            "company": "듀듀 주식회사",
            "manager": "김철수",
        },
        "content": (
            "사내 업무 자동화 시스템 도입 제안. "
            "현황: 수동 문서 작성에 월 평균 40시간 소요. "
            "예산: 초기 도입비 5000만원, 월 운영비 200만원. "
            "일정: 2026년 4월 PoC 시작, 6월 파일럿 운영, 8월 전사 도입."
        ),
        "description": "중간 입력 (~200자) — 현황 + 예산 + 일정 언급",
        "expected_facts": ["40시간", "5000만원", "200만원", "4월", "6월", "8월"],
        "key_fields": ["schedule", "budget"],
    },
    {
        "id": "P3",
        "template_type": "proposal",
        "input_length": "long",
        "fields_data": {
            "title": "AI 기반 문서 자동화 플랫폼 구축 제안서",
            "date": "2026-03-19",
            "company": "듀듀 주식회사",
            "manager": "김철수",
        },
        "content": (
            "AI 기반 문서 자동화 플랫폼 구축 제안서. "
            "배경: 현재 사내 문서 작성은 수동으로 이루어지며, 팀당 월 평균 40시간 소요. "
            "반복 업무(회의록, 보고서)가 전체 문서의 70%를 차지하여 자동화 효과가 높음. "
            "현황 분석: 직원 설문 결과, 문서 작성 업무에 대한 불만족도 65%. "
            "기존 솔루션 검토: A사 제품(월 500만원, 한국어 미지원), B사 제품(월 300만원, 커스텀 불가). "
            "예산 항목: 인프라 구축 3000만원, LLM API 비용 월 150만원, 인건비 2000만원, "
            "총 예산 5150만원 + 월 운영비 200만원. "
            "추진 일정: 4월 요구사항 분석 및 설계(2주), 5~6월 개발(8주), "
            "7월 내부 테스트(2주), 8월 파일럿(2주), 9월 전사 도입. "
            "기대 효과: 문서 작성 시간 60% 절감, 연간 인건비 1억원 절약 예상."
        ),
        "description": "긴 입력 (~500자) — 배경 + 현황 + 예산 항목 + 추진 일정 상세",
        "expected_facts": [
            "40시간", "70%", "65%", "500만원", "300만원",
            "3000만원", "150만원", "2000만원", "5150만원", "200만원",
            "4월", "5", "6월", "7월", "8월", "9월",
            "60%", "1억원",
        ],
        "key_fields": ["schedule", "budget"],
    },
]

# ── 핵심 필드 기대치 (type → {field: {medium: target, long: target}}) ──
FIELD_TARGETS = {
    "meeting_minutes": {"decisions": {"medium": 0.5, "long": 0.8}, "action_items": {"medium": 0.5, "long": 0.8}},
    "report": {"tasks": {"medium": 0.5, "long": 0.8}, "next_plan": {"medium": 0.5, "long": 0.8}},
    "proposal": {"schedule": {"medium": 0.4, "long": 0.6}, "budget": {"medium": 0.4, "long": 0.6}},
}


# ════════════════════════════════════════════════
# 유틸리티
# ════════════════════════════════════════════════

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def ok(msg): print(f"  {Colors.GREEN}[PASS]{Colors.RESET} {msg}")
def fail(msg): print(f"  {Colors.RED}[FAIL]{Colors.RESET} {msg}")
def warn(msg): print(f"  {Colors.YELLOW}[WARN]{Colors.RESET} {msg}")
def info(msg): print(f"  {Colors.CYAN}[INFO]{Colors.RESET} {msg}")
def header(msg): print(f"\n{Colors.BOLD}{'=' * 60}\n{msg}\n{'=' * 60}{Colors.RESET}")


def is_filled(value) -> bool:
    """필드가 채워졌는지 판별"""
    if value is None:
        return False
    if isinstance(value, str):
        return len(value.strip()) > 0
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    return True


def extract_facts(text: str) -> list[str]:
    """텍스트에서 구체적 사실(수치, 날짜, 고유명사) 추출 — 이름은 expected_facts로만 판별"""
    facts = []
    # 숫자 + 단위 (핵심: 수치 할루시네이션이 가장 위험)
    facts.extend(re.findall(r'\d+[\d,.]*\s*(?:만원|억원|원|%|시간|초|MB|GB|점|주|개월|명)', text))
    # 날짜 패턴
    facts.extend(re.findall(r'\d{1,2}월\s*\d{0,2}일?', text))
    facts.extend(re.findall(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}', text))
    # 영문 고유명사 (Playwright, JWT 등)
    facts.extend(re.findall(r'[A-Z][a-zA-Z]{2,}', text))
    return list(set(facts))


def check_hallucination(input_text: str, fields_data: dict, output_data: dict, expected_facts: list[str]) -> dict:
    """출력 데이터에서 할루시네이션 검사 — fields_data도 입력으로 포함"""
    # 입력 전체 = content + fields_data 값 모두
    all_input = input_text
    for v in fields_data.values():
        if isinstance(v, list):
            all_input += " " + " ".join(str(x) for x in v)
        else:
            all_input += " " + str(v)

    output_str = json.dumps(output_data, ensure_ascii=False)
    output_facts = extract_facts(output_str)

    results = {"grounded": [], "inferred": [], "hallucinated": [], "output_facts": output_facts}

    for fact in output_facts:
        if fact in all_input:
            results["grounded"].append(fact)
        elif any(ef in fact or fact in ef for ef in expected_facts):
            results["grounded"].append(fact)
        else:
            results["hallucinated"].append(fact)

    return results


# ════════════════════════════════════════════════
# 메인 테스트 로직
# ════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="v3_generate 통합 테스트")
    parser.add_argument("--case", type=str, default=None,
                        help="특정 케이스만 실행 (예: M1, R2, P3). 콤마로 복수 지정 가능: M1,M2")
    parser.add_argument("--pause", action="store_true",
                        help="각 케이스 실행 후 Enter 대기 (1개씩 안전하게)")
    args = parser.parse_args()

    # 케이스 필터링
    if args.case:
        selected = [c.strip().upper() for c in args.case.split(",")]
        run_cases = [c for c in CASES if c["id"] in selected]
        if not run_cases:
            print(f"  유효한 케이스 없음: {selected}")
            print(f"  가능한 값: {[c['id'] for c in CASES]}")
            return
    else:
        run_cases = CASES

    header("v3_generate 통합 테스트 시작")
    print(f"  대상: {API}")
    print(f"  시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  케이스: {len(run_cases)}개 / 전체 {len(CASES)}개")
    if args.pause:
        print(f"  모드: 1개씩 실행 (--pause)")

    client = httpx.Client(timeout=REQUEST_TIMEOUT)
    results = []  # (case_id, status, response_time, data, hallucination_report)
    total_pass = 0
    total_fail = 0
    total_warn = 0

    # ── Phase 1: 인증 ──
    header("Phase 1: 인증 토큰 발급")

    # 회원가입 (이미 있으면 409 — 무시)
    try:
        resp = client.post(f"{API}/auth/register", json=TEST_USER, timeout=15)
        if resp.status_code == 201:
            info(f"회원가입 성공: {TEST_USER['email']}")
        elif resp.status_code == 409:
            info(f"기존 계정 사용: {TEST_USER['email']}")
        else:
            fail(f"회원가입 실패: {resp.status_code} — {resp.text}")
    except Exception as e:
        fail(f"회원가입 요청 실패: {e}")
        print("\n  백엔드 서버가 실행 중인지 확인하세요:")
        print("    cd backend && uvicorn app.main:app --reload --port 8000")
        return

    # 로그인
    try:
        resp = client.post(
            f"{API}/auth/login",
            json={"email": TEST_USER["email"], "password": TEST_USER["password"]},
            timeout=15,
        )
        if resp.status_code != 200:
            fail(f"로그인 실패: {resp.status_code} — {resp.text}")
            return
        token = resp.json()["access_token"]
        ok(f"로그인 성공, 토큰 발급 완료")
    except Exception as e:
        fail(f"로그인 요청 실패: {e}")
        return

    auth_headers = {"Authorization": f"Bearer {token}"}

    # ── Phase 2: 문서 생성 테스트 ──
    header(f"Phase 2: 문서 생성 테스트 ({len(run_cases)}개 케이스)")

    for case in run_cases:
        case_id = case["id"]
        print(f"\n  {'─' * 50}")
        print(f"  {Colors.BOLD}[{case_id}] {case['template_type']} — {case['description']}{Colors.RESET}")
        print(f"  입력 길이: {len(case['content'])}자")

        payload = {
            "template_type": case["template_type"],
            "fields_data": case["fields_data"],
            "content": case["content"],
        }

        start = time.time()
        try:
            resp = client.post(
                f"{API}/documents/generate",
                json=payload,
                headers=auth_headers,
                timeout=REQUEST_TIMEOUT,
            )
            elapsed = time.time() - start
        except httpx.TimeoutException:
            elapsed = time.time() - start
            fail(f"타임아웃 ({elapsed:.1f}s > {REQUEST_TIMEOUT}s)")
            results.append((case_id, "FAIL", elapsed, None, None))
            total_fail += 1
            continue
        except Exception as e:
            elapsed = time.time() - start
            fail(f"요청 실패: {e}")
            results.append((case_id, "FAIL", elapsed, None, None))
            total_fail += 1
            continue

        # A. 기본 동작 검증
        if resp.status_code != 200:
            fail(f"HTTP {resp.status_code} ({elapsed:.1f}s)")
            try:
                detail = resp.json().get("detail", resp.text[:200])
            except Exception:
                detail = resp.text[:200]
            print(f"    → {detail}")
            results.append((case_id, "FAIL", elapsed, None, None))
            total_fail += 1
            continue

        try:
            body = resp.json()
        except Exception:
            fail(f"JSON 파싱 실패 ({elapsed:.1f}s)")
            results.append((case_id, "FAIL", elapsed, None, None))
            total_fail += 1
            continue

        data = body.get("data", {})
        doc_id = body.get("document_id", "")
        model_name = body.get("model_name", "unknown")
        download_url = body.get("download_url", "")

        ok(f"200 OK ({elapsed:.1f}s) — model: {model_name}")
        info(f"document_id: {doc_id}")
        info(f"download_url: {download_url}")

        # B. 필드 채움률
        all_keys = list(data.keys())
        filled_keys = [k for k in all_keys if is_filled(data[k])]
        fill_rate = len(filled_keys) / len(all_keys) if all_keys else 0

        info(f"전체 필드: {len(all_keys)}개, 채움: {len(filled_keys)}개 ({fill_rate:.0%})")
        info(f"  채워진 필드: {filled_keys}")
        empty_keys = [k for k in all_keys if not is_filled(data[k])]
        if empty_keys:
            info(f"  빈 필드: {empty_keys}")

        # 핵심 필드 목표 달성 여부
        case_status = "PASS"
        for kf in case["key_fields"]:
            val = data.get(kf)
            filled = is_filled(val)
            length = case["input_length"]
            target = FIELD_TARGETS.get(case["template_type"], {}).get(kf, {}).get(length, 0)

            if filled:
                ok(f"핵심필드 [{kf}]: 채워짐")
                # 배열/문자열 내용 미리보기
                if isinstance(val, list):
                    for i, item in enumerate(val[:3]):
                        preview = json.dumps(item, ensure_ascii=False)[:80] if isinstance(item, dict) else str(item)[:80]
                        info(f"    [{i}] {preview}")
                elif isinstance(val, str):
                    info(f"    → {val[:100]}...")
            else:
                if target > 0:
                    warn(f"핵심필드 [{kf}]: 비어있음 (목표: {target:.0%})")
                    if case_status == "PASS":
                        case_status = "WARN"
                else:
                    info(f"핵심필드 [{kf}]: 비어있음 (short 입력 — 허용)")

        # content/summary 필수 확인
        for must_field in ["content", "summary"]:
            if must_field in data and not is_filled(data[must_field]):
                fail(f"필수필드 [{must_field}] 비어있음")
                case_status = "FAIL"

        # C. 할루시네이션 체크
        hall = check_hallucination(case["content"], case["fields_data"], data, case["expected_facts"])
        h_count = len(hall["hallucinated"])
        g_count = len(hall["grounded"])
        i_count = len(hall["inferred"])

        if h_count == 0:
            ok(f"할루시네이션: 없음 (grounded: {g_count}, inferred: {i_count})")
        elif h_count <= 2:
            warn(f"할루시네이션: {h_count}개 — {hall['hallucinated']}")
            if case_status == "PASS":
                case_status = "WARN"
        else:
            fail(f"할루시네이션: {h_count}개 — {hall['hallucinated']}")
            case_status = "FAIL"

        # M1 특별 검증: 짧은 입력 확장 억제
        if case_id == "M1":
            content_val = data.get("content", "")
            input_len = len(case["content"])
            output_len = len(content_val) if isinstance(content_val, str) else 0
            ratio = output_len / input_len if input_len > 0 else 0
            if ratio > 5:
                warn(f"M1 확장 비율: {ratio:.1f}x (입력 {input_len}자 → 출력 {output_len}자)")
                if case_status == "PASS":
                    case_status = "WARN"
            else:
                ok(f"M1 확장 비율: {ratio:.1f}x (적절)")

        # D. DOCX 다운로드 확인
        if download_url:
            try:
                dl_resp = client.get(f"{BASE_URL}{download_url}", headers=auth_headers, timeout=10)
                if dl_resp.status_code == 200:
                    ok(f"DOCX 다운로드: {len(dl_resp.content)} bytes")
                else:
                    warn(f"DOCX 다운로드 실패: HTTP {dl_resp.status_code}")
                    if case_status == "PASS":
                        case_status = "WARN"
            except Exception as e:
                warn(f"DOCX 다운로드 실패: {e}")

        # 결과 집계
        if case_status == "PASS":
            total_pass += 1
        elif case_status == "WARN":
            total_warn += 1
        else:
            total_fail += 1

        results.append((case_id, case_status, elapsed, data, hall))

        # --pause 모드: 다음 케이스 전에 사용자 확인
        if args.pause and case != run_cases[-1]:
            try:
                input(f"\n  [Enter] 다음 케이스 진행 / [Ctrl+C] 중단 → ")
            except KeyboardInterrupt:
                print("\n  중단됨.")
                break

    # ── Phase 3: 종합 리포트 ──
    header("Phase 3: 종합 리포트")

    print(f"\n  {'케이스':<8} {'상태':<8} {'응답시간':<10} {'할루':<6} {'비고'}")
    print(f"  {'─' * 55}")

    for case_id, status, elapsed, data, hall in results:
        icon = {"PASS": Colors.GREEN + "PASS", "WARN": Colors.YELLOW + "WARN", "FAIL": Colors.RED + "FAIL"}.get(status, status)
        h_count = len(hall["hallucinated"]) if hall else "-"
        note = ""
        if data:
            filled = sum(1 for v in data.values() if is_filled(v))
            total = len(data)
            note = f"{filled}/{total} fields"
        print(f"  {case_id:<8} {icon}{Colors.RESET}  {elapsed:>7.1f}s   {str(h_count):<6} {note}")

    print(f"\n  {Colors.BOLD}결과: {Colors.GREEN}PASS {total_pass}{Colors.RESET} / "
          f"{Colors.YELLOW}WARN {total_warn}{Colors.RESET} / "
          f"{Colors.RED}FAIL {total_fail}{Colors.RESET}")

    # ── 결과 파일 저장 ──
    report_dir = Path(__file__).parent / "qa_results"
    report_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"v3_generate_{timestamp}.json"

    report_data = {
        "timestamp": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "summary": {"pass": total_pass, "warn": total_warn, "fail": total_fail, "total": len(run_cases)},
        "cases": [],
    }

    for (case_id, status, elapsed, data, hall), case in zip(results, run_cases):
        entry = {
            "case_id": case_id,
            "template_type": case["template_type"],
            "input_length": case["input_length"],
            "status": status,
            "response_time_s": round(elapsed, 2),
            "hallucination": {
                "grounded": hall["grounded"] if hall else [],
                "inferred": hall["inferred"] if hall else [],
                "hallucinated": hall["hallucinated"] if hall else [],
            } if hall else None,
            "data": data,
        }
        report_data["cases"].append(entry)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    ok(f"리포트 저장: {report_path}")

    # 종료 코드
    if total_fail > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
