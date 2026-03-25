"""
대시보드 AI 추천 — GPT vs sLLM(Kanana) 성능 비교 스크립트

3개 함수를 동일한 입력으로 GPT-4o-mini / Kanana(vLLM) 각각 호출하여 비교:
  1. generate_checklist (체크리스트 생성)
  2. suggest_schedules (일정 추천)
  3. suggest_approvals (결재 추천)

실행:
  python scripts/compare_dashboard_ai.py
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

# 프로젝트 루트 설정
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from ai.llm.factory import create_llm
from ai.llm.prompts import (
    SCHEDULE_CHECKLIST_SYSTEM_PROMPT,
    SCHEDULE_SUGGEST_SYSTEM_PROMPT,
    APPROVAL_SUGGEST_SYSTEM_PROMPT,
)

# ── 테스트 입력 데이터 (실제 사용자 컨텍스트 시뮬레이션) ──
TEST_CONTEXT = """## 현재 사용자 정보
- 이름: 안혜빈
- 팀: 개발
- 오늘 날짜: 2026-03-17 Tuesday

## 파이프라인 태스크 현황
- 전체: 12개
- To Do: 3개, In Progress: 4개, Review: 2개, Done: 3개
- 완료율: 25%
- 태스크 상세 (진행 중 + 리뷰 + 할 일):
[
  {"title": "vLLM 백엔드 연동", "stage": "in_progress", "priority": "HIGH", "assignee": "안혜빈", "due_date": "2026-03-20", "project": "듀듀"},
  {"title": "sLLM 성능 평가", "stage": "in_progress", "priority": "HIGH", "assignee": "안혜빈", "due_date": "2026-03-22", "project": "듀듀"},
  {"title": "Google Calendar 버그 수정", "stage": "in_progress", "priority": "MEDIUM", "assignee": "안혜빈", "due_date": null, "project": "듀듀"},
  {"title": "EC2 서버 모니터링 설정", "stage": "in_progress", "priority": "LOW", "assignee": "안혜빈", "due_date": "2026-03-25", "project": "듀듀"},
  {"title": "API 문서 업데이트", "stage": "review", "priority": "MEDIUM", "assignee": "문지영", "due_date": "2026-03-18", "project": "듀듀"},
  {"title": "프론트엔드 UI 리뷰", "stage": "review", "priority": "HIGH", "assignee": "안혜빈", "due_date": "2026-03-17", "project": "듀듀"},
  {"title": "최종 발표 자료 준비", "stage": "todo", "priority": "HIGH", "assignee": "신지용", "due_date": "2026-03-28", "project": "듀듀"},
  {"title": "성능 테스트 시나리오 작성", "stage": "todo", "priority": "MEDIUM", "assignee": "안혜빈", "due_date": "2026-03-24", "project": "듀듀"},
  {"title": "Docker Compose 최적화", "stage": "todo", "priority": "LOW", "assignee": "안혜빈", "due_date": null, "project": "듀듀"}
]

## 현재 캘린더 일정 (향후 7일)
[
  {"title": "팀 스탠드업", "start": "2026-03-17 10:00", "end": "2026-03-17 10:30", "type": "meeting"},
  {"title": "멘토 피드백 미팅", "start": "2026-03-18 14:00", "end": "2026-03-18 15:00", "type": "meeting"},
  {"title": "sLLM 성능 비교 테스트", "start": "2026-03-19 09:00", "end": "2026-03-19 12:00", "type": "task"},
  {"title": "최종 발표 리허설", "start": "2026-03-21 15:00", "end": "2026-03-21 17:00", "type": "meeting"}
]
"""

# ── 평가 기준 ──
FUNCTIONS = [
    {
        "name": "generate_checklist",
        "system_prompt": SCHEDULE_CHECKLIST_SYSTEM_PROMPT,
        "temperature": 0.3,
        "expected_key": "checklist",
        "required_fields": ["title", "category", "priority"],
        "valid_categories": {"meeting", "task", "review", "prepare", "report"},
        "valid_priorities": {"high", "medium", "low"},
    },
    {
        "name": "suggest_schedules",
        "system_prompt": SCHEDULE_SUGGEST_SYSTEM_PROMPT,
        "temperature": 0.4,
        "expected_key": "suggestions",
        "required_fields": ["title", "schedule_type", "priority"],
        "valid_categories": {"meeting", "task", "deadline", "review", "milestone"},
        "valid_priorities": {"high", "medium", "low"},
    },
    {
        "name": "suggest_approvals",
        "system_prompt": APPROVAL_SUGGEST_SYSTEM_PROMPT,
        "temperature": 0.4,
        "expected_key": "suggestions",
        "required_fields": ["type", "title", "priority"],
        "valid_categories": {"leave", "remote", "room", "design", "certificate", "budget", "review", "deploy", "infra", "security"},
        "valid_priorities": {"high", "medium", "low"},
    },
]


def evaluate_response(func_config: dict, raw_content: str) -> dict:
    """응답 품질 평가"""
    result = {
        "json_valid": False,
        "has_expected_key": False,
        "item_count": 0,
        "fields_complete": 0,
        "fields_total": 0,
        "category_valid": 0,
        "priority_valid": 0,
        "avg_title_len": 0,
        "avg_reason_len": 0,
        "score": 0,
    }

    # 1. JSON 파싱
    try:
        # 코드블록 제거
        content = raw_content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        parsed = json.loads(content)
        result["json_valid"] = True
    except (json.JSONDecodeError, Exception):
        result["score"] = 0
        return result

    # 2. 키 확인
    key = func_config["expected_key"]
    items = parsed.get(key, [])
    if not isinstance(items, list):
        return result
    result["has_expected_key"] = True
    result["item_count"] = len(items)

    if not items:
        result["score"] = 10
        return result

    # 3. 필드 완성도
    req_fields = func_config["required_fields"]
    total_fields = 0
    complete_fields = 0
    cat_valid = 0
    pri_valid = 0
    title_lens = []
    reason_lens = []

    cat_field = "category" if "category" in req_fields else "type" if "type" in req_fields else "schedule_type"

    for item in items:
        for f in req_fields:
            total_fields += 1
            if item.get(f):
                complete_fields += 1

        # 카테고리 유효성
        cat_val = item.get(cat_field, "")
        if cat_val and cat_val.lower() in func_config["valid_categories"]:
            cat_valid += 1

        # 우선순위 유효성
        pri_val = item.get("priority", "")
        if pri_val and pri_val.lower() in func_config["valid_priorities"]:
            pri_valid += 1

        # 텍스트 길이
        title = item.get("title", "")
        title_lens.append(len(title))
        reason = item.get("reason", item.get("related", ""))
        reason_lens.append(len(reason))

    result["fields_complete"] = complete_fields
    result["fields_total"] = total_fields
    result["category_valid"] = cat_valid
    result["priority_valid"] = pri_valid
    result["avg_title_len"] = sum(title_lens) / len(title_lens) if title_lens else 0
    result["avg_reason_len"] = sum(reason_lens) / len(reason_lens) if reason_lens else 0

    # 4. 종합 점수 (100점 만점)
    n = len(items)
    score = 0
    score += 20 if result["json_valid"] else 0                       # JSON 파싱 성공
    score += 10 if result["has_expected_key"] else 0                  # 키 존재
    score += min(15, n * 5) if 1 <= n <= 10 else 5                   # 적절한 개수 (3~5개가 이상적)
    score += 25 * (complete_fields / total_fields) if total_fields else 0  # 필드 완성도
    score += 15 * (cat_valid / n) if n else 0                        # 카테고리 유효성
    score += 15 * (pri_valid / n) if n else 0                        # 우선순위 유효성
    result["score"] = round(score, 1)

    return result


async def call_llm(provider_name: str, func_config: dict) -> dict:
    """LLM 호출 + 평가"""
    try:
        llm = create_llm(provider=provider_name)
    except Exception as e:
        return {"error": f"Provider 생성 실패: {e}", "score": 0, "latency": 0}

    start = time.time()
    try:
        response = await llm.generate(
            prompt=TEST_CONTEXT,
            system_prompt=func_config["system_prompt"],
            json_mode=True,
            temperature=func_config["temperature"],
            max_tokens=1500,
        )
        latency = time.time() - start
        raw = response.content
    except Exception as e:
        latency = time.time() - start
        return {"error": str(e), "score": 0, "latency": round(latency, 2), "raw": ""}

    evaluation = evaluate_response(func_config, raw)
    evaluation["latency"] = round(latency, 2)
    evaluation["raw"] = raw[:500]  # 처음 500자만
    evaluation["model"] = getattr(response, "model", provider_name)
    evaluation["tokens"] = getattr(response, "usage", {})

    return evaluation


async def main():
    print("=" * 80)
    print("  대시보드 AI 추천 — GPT-4o-mini vs Kanana(vLLM) 성능 비교")
    print(f"  실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    providers = ["openai", "vllm"]
    all_results = {}

    for func in FUNCTIONS:
        print(f"\n{'─' * 60}")
        print(f"  [{func['name']}]")
        print(f"{'─' * 60}")

        func_results = {}
        for prov in providers:
            print(f"\n  >> {prov.upper()} 호출 중...", end=" ", flush=True)
            result = await call_llm(prov, func)
            func_results[prov] = result

            if "error" in result:
                print(f"ERROR: {result['error']}")
            else:
                print(f"완료 ({result['latency']}s, 점수: {result['score']}/100)")

        all_results[func["name"]] = func_results

        # 비교 출력
        print(f"\n  {'항목':<20} {'GPT-4o-mini':<20} {'Kanana(vLLM)':<20}")
        print(f"  {'─'*60}")

        metrics = [
            ("JSON 파싱", "json_valid"),
            ("키 존재", "has_expected_key"),
            ("항목 수", "item_count"),
            ("필드 완성도", None),
            ("카테고리 유효", "category_valid"),
            ("우선순위 유효", "priority_valid"),
            ("평균 제목 길이", "avg_title_len"),
            ("응답 시간(초)", "latency"),
            ("종합 점수", "score"),
        ]

        for label, key in metrics:
            gpt = func_results.get("openai", {})
            sllm = func_results.get("vllm", {})

            if "error" in gpt:
                gpt_val = "ERROR"
            elif key is None:
                gpt_val = f"{gpt.get('fields_complete', 0)}/{gpt.get('fields_total', 0)}"
            elif key == "json_valid" or key == "has_expected_key":
                gpt_val = "O" if gpt.get(key) else "X"
            elif key == "avg_title_len":
                gpt_val = f"{gpt.get(key, 0):.0f}자"
            elif key == "score":
                gpt_val = f"{gpt.get(key, 0)}/100"
            else:
                gpt_val = str(gpt.get(key, "-"))

            if "error" in sllm:
                sllm_val = "ERROR"
            elif key is None:
                sllm_val = f"{sllm.get('fields_complete', 0)}/{sllm.get('fields_total', 0)}"
            elif key == "json_valid" or key == "has_expected_key":
                sllm_val = "O" if sllm.get(key) else "X"
            elif key == "avg_title_len":
                sllm_val = f"{sllm.get(key, 0):.0f}자"
            elif key == "score":
                sllm_val = f"{sllm.get(key, 0)}/100"
            else:
                sllm_val = str(sllm.get(key, "-"))

            print(f"  {label:<20} {gpt_val:<20} {sllm_val:<20}")

    # ── 최종 요약 ──
    print(f"\n{'=' * 80}")
    print("  최종 요약")
    print(f"{'=' * 80}")
    print(f"\n  {'함수':<25} {'GPT 점수':<15} {'sLLM 점수':<15} {'차이':<10}")
    print(f"  {'─'*65}")

    total_gpt = 0
    total_sllm = 0

    for func_name, results in all_results.items():
        gpt_score = results.get("openai", {}).get("score", 0)
        sllm_score = results.get("vllm", {}).get("score", 0)
        diff = sllm_score - gpt_score
        total_gpt += gpt_score
        total_sllm += sllm_score
        sign = "+" if diff >= 0 else ""
        print(f"  {func_name:<25} {gpt_score:<15} {sllm_score:<15} {sign}{diff:<10}")

    avg_gpt = total_gpt / len(all_results) if all_results else 0
    avg_sllm = total_sllm / len(all_results) if all_results else 0
    diff = avg_sllm - avg_gpt
    sign = "+" if diff >= 0 else ""
    print(f"  {'─'*65}")
    print(f"  {'평균':<25} {avg_gpt:<15.1f} {avg_sllm:<15.1f} {sign}{diff:<10.1f}")

    # ── 원본 응답 출력 ──
    print(f"\n{'=' * 80}")
    print("  원본 응답 (처음 500자)")
    print(f"{'=' * 80}")
    for func_name, results in all_results.items():
        print(f"\n  --- {func_name} ---")
        for prov in providers:
            r = results.get(prov, {})
            raw = r.get("raw", r.get("error", "N/A"))
            print(f"\n  [{prov.upper()}]:")
            print(f"  {raw[:500]}")

    # ── 결과 JSON 저장 ──
    out_dir = os.path.join(ROOT, "outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"dashboard_ai_compare_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

    save_data = {}
    for func_name, results in all_results.items():
        save_data[func_name] = {}
        for prov, r in results.items():
            save_data[func_name][prov] = {k: v for k, v in r.items() if k != "raw"}
            save_data[func_name][prov]["raw_response"] = r.get("raw", "")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
