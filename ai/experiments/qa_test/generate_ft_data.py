"""
파인튜닝용 합성 QA 데이터 생성 스크립트 (Upstage Solar 사용)

베이스라인 실험에서 발견된 3가지 약점 유형과 일반 QA를 생성한다.

  multi_entity  : 지문에 날짜/수치가 여러 개 혼재 → 엉뚱한 값 선택 오류 보강
  enumeration   : 여러 항목 중 일부만 나열하는 조기 종료 오류 보강
  detail_missing: 핵심 답은 맞지만 세부 정보 누락 오류 보강
  general_qa    : 기존 성능 유지용 일반 QA (망각 방지)

사용법:
    # 전체 생성 (기본 목표량: 총 500건)
    python ai/experiments/qa_test/generate_ft_data.py

    # 유형별 개수 지정
    python ai/experiments/qa_test/generate_ft_data.py --type multi_entity --count 50
    python ai/experiments/qa_test/generate_ft_data.py --type enumeration --count 30
    python ai/experiments/qa_test/generate_ft_data.py --type detail_missing --count 30
    python ai/experiments/qa_test/generate_ft_data.py --type general_qa --count 50

    # 기존 파일에 이어서 생성 (중단 후 재개)
    python ai/experiments/qa_test/generate_ft_data.py --resume

환경:
    pip install openai python-dotenv
    .env에 SOLAR_API_KEY 설정 필요
"""

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(BASE_DIR / ".env")

OUTPUT_PATH = BASE_DIR / "ai" / "data" / "ft_train_data.json"

client = OpenAI(
    api_key=os.getenv("SOLAR_API_KEY"),
    base_url="https://api.upstage.ai/v1",
)

# ── 유형별 기본 생성 목표량 ──
DEFAULT_COUNTS = {
    "multi_entity": 150,
    "enumeration": 100,
    "detail_missing": 100,
    "general_qa": 150,
}

BATCH_SIZE = 5  # 한 번의 API 호출에서 생성할 샘플 수


# ── 유형별 프롬프트 ──

SYSTEM_PROMPT = (
    "당신은 한국어 QA 데이터셋 생성 전문가입니다. "
    "요청한 형식에 맞게 최상위에 'samples'라는 키를 가진 JSON 객체(Object)만 출력하세요."
)


def make_user_prompt(qa_type: str, batch_size: int) -> str:
    if qa_type == "multi_entity":
        return f"""
한국어 업무 문서 기반 QA 샘플 {batch_size}개를 생성하세요.

[조건]
- 지문(context): 실제 업무 현장에서 쓰이는 문서 (회의록, 이메일, 보고서, 공지사항 등)
- 지문(context)에 날짜, 시간, 수치, 금액, 기간이 반드시 3개 이상 등장해야 함
- 반드시 같은 종류의 값이 2개 이상 포함될 것 (날짜끼리, 금액끼리 등)
  예) 요청 SLA 8시간 vs 현행 SLA 24시간, 계약금액 1억 vs 선급금 3천만 원,
      계약 만료일 3/31 vs 검토 후 회신일 4/4 vs 착수일 4/10 등
- 각 값은 서로 다른 맥락(요청값/현행값/예정일/조건 등)에 속해 혼동을 유발하는 구조
- 질문(question): 같은 종류 값 중 특정 하나를 정확히 묻는 질문
- 정답(answer): 질문이 묻는 값만 간결하게 (오답 후보가 지문에 명시적으로 존재해야 함)

[출력 형식 - JSON 객체]
{{
  "samples": [
    {{
      "domain": "business",
      "type": "multi_entity",
      "context": "...",
      "question": "...",
      "answer": "..."
    }}
  ]
}}
"""

    if qa_type == "enumeration":
        return f"""
한국어 QA 샘플 {batch_size}개를 생성하세요.

[조건]
- 도메인: general(일반 상식)과 business(업무)를 섞어서 생성
- 지문(context): 4가지 이상의 항목(종류, 방법, 원인, 특징 등)이 나열된 내용
- 질문(question): "~을 모두 나열하시오", "~의 종류는?", "~에는 어떤 것들이 있는가?" 형태
- 정답(answer): 지문에 등장한 모든 항목을 빠짐없이 나열 (쉼표 구분, 4개 이상)

[출력 형식 - JSON 객체]
{{
  "samples": [
    {{
      "domain": "general 또는 business",
      "type": "enumeration",
      "context": "...",
      "question": "...",
      "answer": "A, B, C, D (모든 항목 포함)"
    }}
  ]
}}
"""

    if qa_type == "detail_missing":
        return f"""
한국어 QA 샘플 {batch_size}개를 생성하세요.

[조건]
- 도메인: general(일반 상식)과 business(업무)를 섞어서 생성
- 지문(context): 핵심 사실 + 그 근거/기간/조건이 함께 서술된 내용
- 질문(question): 핵심 사실과 그 세부 내용을 함께 묻는 질문
  예) "~의 기간과 그 이유는?", "~은 얼마이며, 언제부터 적용되는가?"
- 정답(answer): 핵심 답 + 세부 정보를 함께 포함한 완전한 답변
  예) "3개월 (4월부터 7월 재평가까지)", "9,860원 (2024년 1월 1일부터 적용)"

[출력 형식 - JSON 객체]
{{
  "samples": [
    {{
      "domain": "general 또는 business",
      "type": "detail_missing",
      "context": "...",
      "question": "...",
      "answer": "핵심답 (세부정보 포함)"
    }}
  ]
}}
"""

    if qa_type == "general_qa":
        return f"""
한국어 일반 상식 QA 샘플 {batch_size}개를 생성하세요.

[조건]
- 과학, 역사, 지리, 경제, 문화 등 다양한 분야
- 지문(context): 100~200자 분량의 짧은 설명 단락
- 질문(question): 지문에서 단 하나의 사실을 묻는 단답형 질문
- 정답(answer): 1~5단어의 간결한 단답 (연도, 이름, 수치, 단어 등)

[출력 형식 - JSON 객체]
{{
  "samples": [
    {{
      "domain": "general",
      "type": "general_qa",
      "context": "...",
      "question": "...",
      "answer": "..."
    }}
  ]
}}
"""

    raise ValueError(f"알 수 없는 유형: {qa_type}")


# ── API 호출 ──

def generate_batch(qa_type: str, batch_size: int, retry: int = 3) -> list[dict]:
    """Solar로 batch_size개 샘플 생성. 실패 시 retry 횟수만큼 재시도."""
    for attempt in range(1, retry + 1):
        try:
            response = client.chat.completions.create(
                model="solar-pro",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": make_user_prompt(qa_type, batch_size)},
                ],
                response_format={"type": "json_object"},
                temperature=0.9,
            )
            raw = response.choices[0].message.content.strip()

            # JSON 파싱 — 배열이 최상위 키 아래 있을 수 있으므로 탐색
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                samples = parsed
            else:
                # {"samples": [...]} 또는 첫 번째 list 값 사용
                samples = next(
                    (v for v in parsed.values() if isinstance(v, list)),
                    []
                )

            # 필드 검증
            valid = []
            for s in samples:
                if all(k in s for k in ("domain", "type", "context", "question", "answer")):
                    valid.append(s)

            if valid:
                return valid

            print(f"  [경고] 유효 샘플 0건 (시도 {attempt}/{retry}), 재시도...")

        except Exception as e:
            print(f"  [오류] {e} (시도 {attempt}/{retry}), 재시도...")
            time.sleep(2)

    return []


# ── ID 부여 ──

def assign_ids(samples: list[dict], existing_count: int) -> list[dict]:
    """기존 데이터 개수 기준으로 순번 ID 부여"""
    prefix_map = {
        "multi_entity": "ft_biz",
        "enumeration": "ft_enum",
        "detail_missing": "ft_det",
        "general_qa": "ft_gen",
    }
    for i, s in enumerate(samples):
        prefix = prefix_map.get(s.get("type", ""), "ft")
        s["id"] = f"{prefix}_{existing_count + i + 1:04d}"
    return samples


# ── 저장 ──

def load_existing() -> list[dict]:
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def save(data: list[dict]) -> None:
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 메인 ──

def run(qa_type: str, target_count: int, resume: bool) -> None:
    existing = load_existing() if resume else []
    already = sum(1 for s in existing if s.get("type") == qa_type)
    remaining = max(0, target_count - already)

    if remaining == 0:
        print(f"  [{qa_type}] 이미 {already}건 존재 → 스킵")
        return

    print(f"\n  [{qa_type}] 목표 {target_count}건 중 {already}건 존재 → {remaining}건 추가 생성")

    generated_this_run = 0
    fail_count = 0
    while generated_this_run < remaining:
        need = min(BATCH_SIZE, remaining - generated_this_run)
        batch = generate_batch(qa_type, need)

        if not batch:
            print("  [경고] 배치 생성 실패, 건너뜀")
            fail_count += 1
            if fail_count >= 3:
                print("  [오류] 연속 3회 생성 실패. 프로그램을 중단합니다.")
                break
            continue
        fail_count = 0

        batch = assign_ids(batch, len(existing))
        existing.extend(batch)
        generated_this_run += len(batch)
        save(existing)

        print(f"    +{len(batch)}건 저장 (누적 {len(existing)}건)")
        time.sleep(0.5)  # Rate limit 방지

    print(f"  [{qa_type}] 완료: {generated_this_run}건 생성")


def main():
    parser = argparse.ArgumentParser(description="파인튜닝용 합성 QA 데이터 생성")
    parser.add_argument(
        "--type",
        choices=["multi_entity", "enumeration", "detail_missing", "general_qa", "all"],
        default="all",
    )
    parser.add_argument("--count", type=int, default=None, help="생성할 샘플 수 (기본: 유형별 기본값)")
    parser.add_argument("--resume", action="store_true", help="기존 파일에 이어서 생성")
    args = parser.parse_args()

    types = list(DEFAULT_COUNTS.keys()) if args.type == "all" else [args.type]

    print(f"출력 경로: {OUTPUT_PATH}")
    print(f"생성 유형: {types}")
    print(f"이어서 생성: {args.resume}")

    for t in types:
        count = args.count if args.count else DEFAULT_COUNTS[t]
        run(t, count, resume=args.resume)

    # 최종 통계
    data = load_existing()
    print("\n" + "=" * 50)
    print("  생성 완료 - 유형별 통계")
    print("=" * 50)
    for t in DEFAULT_COUNTS:
        n = sum(1 for s in data if s.get("type") == t)
        print(f"  {t:<20}: {n}건")
    print(f"  {'합계':<20}: {len(data)}건")
    print(f"  저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
