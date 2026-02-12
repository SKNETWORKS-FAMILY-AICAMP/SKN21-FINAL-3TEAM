"""
판단 Agent 고도화 개선 효과 수치 평가

비교 항목:
  1. Confidence 보정 정확도 (기존 raw LLM vs 보정 후)
  2. 다중 규정 그룹핑 커버리지
  3. 판단 이력 추출 정확도
  4. 테스트 커버리지
"""
import json
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ai.agents.judgment_agent import (
    _calibrate_confidence,
    _group_regulations,
    _build_context_prompt,
    _extract_judgment_history,
)


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_table(headers: list[str], rows: list[list], col_widths: list[int] | None = None):
    if col_widths is None:
        col_widths = [max(len(str(r[i])) for r in [headers] + rows) + 2 for i in range(len(headers))]
    header_line = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, col_widths)) + " |"
    sep_line = "|-" + "-|-".join("-" * w for w in col_widths) + "-|"
    print(header_line)
    print(sep_line)
    for row in rows:
        print("| " + " | ".join(str(c).ljust(w) for c, w in zip(row, col_widths)) + " |")


# ── 1. Confidence 보정 평가 ──

def eval_confidence_calibration():
    print_header("1. Confidence 보정 정확도 비교")

    scenarios = [
        {
            "name": "높은 RAG + 다중 규정 (이상적)",
            "llm_conf": 0.9,
            "context": [
                {"content": "c", "source": "취업규칙 15조", "score": 0.95},
                {"content": "c", "source": "취업규칙 16조", "score": 0.90},
                {"content": "c", "source": "재택근무 규정 3조", "score": 0.85},
            ],
            "cross_refs": [],
            "expected_direction": "유지 (높음)",
        },
        {
            "name": "높은 LLM + 낮은 RAG (과신)",
            "llm_conf": 0.95,
            "context": [
                {"content": "c", "source": "취업규칙 1조", "score": 0.25},
            ],
            "cross_refs": [],
            "expected_direction": "하향 보정",
        },
        {
            "name": "규정 없음 (환각 방지)",
            "llm_conf": 0.8,
            "context": [],
            "cross_refs": [],
            "expected_direction": "대폭 하향",
        },
        {
            "name": "규정 충돌 (불확실)",
            "llm_conf": 0.85,
            "context": [
                {"content": "c", "source": "취업규칙 10조", "score": 0.80},
                {"content": "c", "source": "정보보안 규정 5조", "score": 0.75},
            ],
            "cross_refs": [{"relationship": "충돌"}, {"relationship": "충돌"}],
            "expected_direction": "하향 보정",
        },
        {
            "name": "낮은 LLM + 높은 RAG (보수적 LLM)",
            "llm_conf": 0.5,
            "context": [
                {"content": "c", "source": "취업규칙 20조", "score": 0.92},
                {"content": "c", "source": "인사 규정 3조", "score": 0.88},
            ],
            "cross_refs": [],
            "expected_direction": "상향 보정",
        },
    ]

    rows = []
    correct = 0
    total = len(scenarios)

    for s in scenarios:
        raw = s["llm_conf"]
        parsed = {"confidence": raw, "cross_references": s["cross_refs"]}
        calibrated = _calibrate_confidence(parsed, s["context"])
        diff = calibrated - raw
        diff_str = f"{diff:+.3f}"

        # 방향 정확성 판단
        direction = s["expected_direction"]
        if "하향" in direction and diff < 0:
            match = "O"
            correct += 1
        elif "상향" in direction and diff > 0:
            match = "O"
            correct += 1
        elif "유지" in direction and abs(diff) < 0.15:
            match = "O"
            correct += 1
        elif "대폭 하향" in direction and diff < -0.3:
            match = "O"
            correct += 1
        else:
            match = "X"

        rows.append([s["name"], f"{raw:.3f}", f"{calibrated:.3f}", diff_str, direction, match])

    print_table(
        ["시나리오", "기존(raw)", "보정후", "변화량", "기대 방향", "일치"],
        rows,
        [30, 10, 10, 10, 15, 6],
    )

    accuracy = correct / total * 100
    print(f"\n보정 방향 정확도: {correct}/{total} ({accuracy:.1f}%)")
    return accuracy


# ── 2. 다중 규정 그룹핑 평가 ──

def eval_regulation_grouping():
    print_header("2. 다중 규정 그룹핑 커버리지")

    test_cases = [
        {
            "name": "3개 규정 혼합",
            "context": [
                {"content": "c", "source": "취업규칙 15조", "score": 0.9},
                {"content": "c", "source": "취업규칙 16조", "score": 0.85},
                {"content": "c", "source": "재택근무 규정 3조", "score": 0.8},
                {"content": "c", "source": "재택근무 규정 5조", "score": 0.7},
                {"content": "c", "source": "정보보안 규정 10조", "score": 0.6},
            ],
            "expected_groups": 3,
        },
        {
            "name": "단일 규정",
            "context": [
                {"content": "c", "source": "취업규칙 22조", "score": 0.9},
                {"content": "c", "source": "취업규칙 23조", "score": 0.85},
            ],
            "expected_groups": 1,
        },
        {
            "name": "5개 규정 (복잡 시나리오)",
            "context": [
                {"content": "c", "source": "취업규칙 1조", "score": 0.9},
                {"content": "c", "source": "인사 규정 3조", "score": 0.8},
                {"content": "c", "source": "보안 규정 5조", "score": 0.7},
                {"content": "c", "source": "출장비 규정 2조", "score": 0.6},
                {"content": "c", "source": "복무 규정 10조", "score": 0.5},
            ],
            "expected_groups": 5,
        },
        {
            "name": "빈 context",
            "context": [],
            "expected_groups": 0,
        },
    ]

    rows = []
    correct = 0

    for tc in test_cases:
        groups = _group_regulations(tc["context"])
        actual = len(groups)
        expected = tc["expected_groups"]
        match = "O" if actual == expected else "X"
        if match == "O":
            correct += 1

        # 교차 분석 경고 포함 여부
        prompt = _build_context_prompt(tc["context"])
        has_warning = "다중 규정 교차 분석 필요" in prompt
        warning_str = "포함" if has_warning else "-"

        rows.append([tc["name"], str(expected), str(actual), match, warning_str])

    print_table(
        ["시나리오", "기대 그룹수", "실제 그룹수", "일치", "교차분석 경고"],
        rows,
        [25, 12, 12, 6, 15],
    )

    accuracy = correct / len(test_cases) * 100
    print(f"\n그룹핑 정확도: {correct}/{len(test_cases)} ({accuracy:.1f}%)")
    return accuracy


# ── 3. 판단 이력 추출 평가 ──

def eval_history_extraction():
    print_header("3. 판단 이력 추출 정확도")

    judgment_responses = [
        json.dumps({"type": "judgment", "result": "yes", "confidence": 0.9, "reasoning": "가능합니다"}, ensure_ascii=False),
        json.dumps({"type": "judgment", "result": "no", "confidence": 0.85, "reasoning": "불가합니다"}, ensure_ascii=False),
        json.dumps({"type": "judgment", "result": "conditional", "confidence": 0.7, "reasoning": "조건부 가능"}, ensure_ascii=False),
    ]

    test_cases = [
        {
            "name": "판단 3건 포함 대화",
            "history": [
                {"role": "user", "content": "질문1"},
                {"role": "assistant", "content": judgment_responses[0]},
                {"role": "user", "content": "질문2"},
                {"role": "assistant", "content": judgment_responses[1]},
                {"role": "user", "content": "질문3"},
                {"role": "assistant", "content": judgment_responses[2]},
            ],
            "expected_count": 3,
        },
        {
            "name": "판단 + 일반 응답 혼합",
            "history": [
                {"role": "user", "content": "안녕"},
                {"role": "assistant", "content": "안녕하세요!"},
                {"role": "user", "content": "규정 질문"},
                {"role": "assistant", "content": judgment_responses[0]},
                {"role": "user", "content": "감사"},
                {"role": "assistant", "content": "도움이 되었으면 좋겠습니다."},
            ],
            "expected_count": 1,
        },
        {
            "name": "판단 없는 대화",
            "history": [
                {"role": "user", "content": "안녕"},
                {"role": "assistant", "content": "안녕하세요!"},
            ],
            "expected_count": 0,
        },
        {
            "name": "빈 대화",
            "history": [],
            "expected_count": 0,
        },
        {
            "name": "깨진 JSON 포함",
            "history": [
                {"role": "assistant", "content": '{"type": "judgment", broken'},
                {"role": "assistant", "content": judgment_responses[0]},
            ],
            "expected_count": 1,
        },
    ]

    rows = []
    correct = 0

    for tc in test_cases:
        extracted = _extract_judgment_history(tc["history"])
        actual = len(extracted)
        expected = tc["expected_count"]
        match = "O" if actual == expected else "X"
        if match == "O":
            correct += 1
        rows.append([tc["name"], str(expected), str(actual), match])

    print_table(
        ["시나리오", "기대 추출 수", "실제 추출 수", "일치"],
        rows,
        [25, 14, 14, 6],
    )

    accuracy = correct / len(test_cases) * 100
    print(f"\n이력 추출 정확도: {correct}/{len(test_cases)} ({accuracy:.1f}%)")
    return accuracy


# ── 4. 종합 비교 ──

def eval_overall():
    print_header("4. 기존 vs 고도화 기능 비교")

    rows = [
        ["규정 교차 분석", "X (단일 패스)", "O (그룹핑 + cross_references)", "신규"],
        ["confidence 보정", "X (LLM raw 값)", "O (RAG+커버리지+충돌 가중)", "신규"],
        ["판단 이력 참조", "X", "O (최근 3건 자동 추출)", "신규"],
        ["SSE 스트리밍", "X", "O (judgment_agent_stream)", "신규"],
        ["RAG top_k", "5", "7 (커버리지 확대)", "개선"],
        ["규정별 프롬프트", "번호만 표시", "규정명 그룹 + 관련도 점수", "개선"],
        ["응답 필드", "6개", "8개 (+cross_references, regulation_groups)", "확장"],
        ["테스트 케이스", "5개 (헬퍼 함수)", "27개 (6개 카테고리)", "5.4배"],
    ]

    print_table(
        ["항목", "기존 (2단계)", "고도화 (3단계)", "변화"],
        rows,
        [20, 22, 40, 8],
    )


# ── 메인 ──

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  판단 Agent 고도화 (#12) 개선 효과 평가 리포트")
    print("=" * 60)

    acc1 = eval_confidence_calibration()
    acc2 = eval_regulation_grouping()
    acc3 = eval_history_extraction()
    eval_overall()

    print_header("종합 결과")
    avg = (acc1 + acc2 + acc3) / 3
    rows = [
        ["confidence 보정 방향", f"{acc1:.1f}%"],
        ["규정 그룹핑 정확도", f"{acc2:.1f}%"],
        ["이력 추출 정확도", f"{acc3:.1f}%"],
        ["평균", f"{avg:.1f}%"],
    ]
    print_table(["평가 항목", "정확도"], rows, [25, 10])
    print()
