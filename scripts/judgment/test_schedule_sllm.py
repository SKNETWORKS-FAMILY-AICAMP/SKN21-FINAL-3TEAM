"""
Schedule Agent sLLM vs GPT 비교 테스트

사용법:
  # GPT-4o-mini (기본)
  python scripts/test_schedule_sllm.py

  # vLLM (sLLM)
  python scripts/test_schedule_sllm.py --provider vllm

  # vLLM URL 직접 지정
  python scripts/test_schedule_sllm.py --provider vllm --vllm-url https://api.runpod.ai/v2/xxx/openai/v1
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


TEST_CASES = [
    # (카테고리, 입력, 검증할 키, 기대값)
    ("일정", "내일 오후 3시 팀 회의 잡아줘", ["title", "start_time"], {"schedule_type": "meeting"}),
    ("일정", "모레 점심에 김과장이랑 미팅", ["title", "start_time"], {}),
    ("일정", "금요일 오전 10시 스탠드업", ["title", "start_time"], {"schedule_type": "meeting"}),
    ("태스크", "코드 리뷰 태스크 만들어줘 긴급", ["title", "priority"], {"priority": "high"}),
    ("태스크", "프론트엔드 버그 수정 태스크 추가 내일까지", ["title", "due_date"], {}),
    ("태스크", "디자인 시안 검토 task 등록", ["title"], {}),
    ("결재", "내일 연차 쓸게요", ["type", "title"], {"type": "leave"}),
    ("결재", "출장 신청해줘 부산 3일", ["type", "title"], {"type": "business_trip"}),
    ("결재", "코드 리뷰 결재 올려줘", ["type", "title"], {"type": "review"}),
    ("결재", "노트북 구매 품의서 올려줘", ["type", "title"], {"type": "budget"}),
]


async def run_test(provider_name: str):
    from ai.agents.schedule_agent import (
        _parse_schedule_input,
        _parse_pipeline_input,
        _parse_approval_input,
    )

    print(f"\n{'='*60}")
    print(f"Schedule Agent 파싱 테스트 — Provider: {provider_name}")
    print(f"{'='*60}\n")

    results = []

    for category, user_input, check_keys, expected_vals in TEST_CASES:
        _t = time.time()
        try:
            if category == "일정":
                parsed = await _parse_schedule_input(user_input)
            elif category == "태스크":
                parsed = await _parse_pipeline_input(user_input)
            else:
                parsed = await _parse_approval_input(user_input)

            elapsed = time.time() - _t

            # 필수 필드 채워짐 확인
            filled = all(parsed.get(k) for k in check_keys)

            # 기대값 일치 확인
            val_match = all(parsed.get(k) == v for k, v in expected_vals.items())

            ok = filled and val_match
            status = "✓" if ok else ("△" if filled else "✗")

            print(f"  {status} [{category}] \"{user_input}\" ({elapsed:.1f}s)")
            print(f"    → {json.dumps(parsed, ensure_ascii=False)}")

            if not filled:
                missing = [k for k in check_keys if not parsed.get(k)]
                print(f"    ⚠ 누락: {missing}")
            if not val_match:
                for k, v in expected_vals.items():
                    if parsed.get(k) != v:
                        print(f"    ⚠ {k}: 기대={v}, 실제={parsed.get(k)}")
            print()

            results.append({"ok": ok, "filled": filled, "elapsed": elapsed})

        except Exception as e:
            elapsed = time.time() - _t
            print(f"  ✗ [{category}] \"{user_input}\" ({elapsed:.1f}s)")
            print(f"    에러: {e}\n")
            results.append({"ok": False, "filled": False, "elapsed": elapsed})

    # 요약
    passed = sum(1 for r in results if r["ok"])
    filled = sum(1 for r in results if r["filled"])
    avg_time = sum(r["elapsed"] for r in results) / len(results)

    print(f"{'='*60}")
    print(f"결과: {passed}/{len(results)} 완전 통과 | {filled}/{len(results)} 필드 채움 | 평균 {avg_time:.1f}s")
    print(f"{'='*60}")

    return {"passed": passed, "filled": filled, "total": len(results), "avg_time": avg_time}


def main():
    parser = argparse.ArgumentParser(description="Schedule Agent sLLM 비교 테스트")
    parser.add_argument("--provider", default=None, choices=["openai", "vllm", "anthropic"],
                        help="LLM Provider (기본: .env의 LLM_PROVIDER)")
    parser.add_argument("--vllm-url", default=None,
                        help="vLLM URL 직접 지정 (예: https://api.runpod.ai/v2/xxx/openai/v1)")
    args = parser.parse_args()

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    if args.vllm_url:
        os.environ["VLLM_BASE_URL"] = args.vllm_url

    # LLM 싱글턴 리셋 (provider 변경 반영)
    from ai.llm import reset_llm
    reset_llm()

    provider = os.getenv("LLM_PROVIDER", "openai")

    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_test(provider))


if __name__ == "__main__":
    main()
