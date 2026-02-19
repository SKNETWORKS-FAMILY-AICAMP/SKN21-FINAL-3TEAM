"""
v2 회귀 테스트: Intent Classifier 확장 후 기존 성능 유지 확인

테스트 항목:
1. 기존 predict() 호환성 (return_candidates=False)
2. predict(return_candidates=True) 정상 동작
3. detect_complexity() 오탐/미감지 검증
4. is_context_dependent() 패턴 검증
5. apply_known_overrides() 동작 확인
6. adversarial 212문장 + blind 70문장 정확도 확인
"""

import json
import sys
import time
from pathlib import Path
from collections import Counter

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from ai.agents.intent_classifier import (
    IntentClassifier,
    detect_complexity,
    is_context_dependent,
    apply_known_overrides,
    INTENT_LABELS,
)


def load_test_data(name: str) -> list:
    path = ROOT / "data" / "training" / "intent" / f"{name}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_predict_compatibility():
    """기존 predict() 호환성 테스트"""
    print("\n=== 1. predict() 호환성 테스트 ===")
    clf = IntentClassifier()
    clf.load_model()

    # return_candidates=False (기존 동작)
    r1 = clf.predict("연차 규정 알려줘")
    assert "intent" in r1, f"intent 필드 없음: {r1}"
    assert "confidence" in r1, f"confidence 필드 없음: {r1}"
    assert "candidates" not in r1, f"candidates가 있으면 안 됨 (기본값): {r1}"
    print(f"  기본 모드: intent={r1['intent']}, confidence={r1['confidence']:.4f} ✓")

    # return_candidates=True (신규)
    r2 = clf.predict("연차 규정 알려줘", return_candidates=True)
    assert "intent" in r2, f"intent 필드 없음: {r2}"
    assert "candidates" in r2, f"candidates 필드 없음: {r2}"
    assert len(r2["candidates"]) >= 1, f"candidates가 비어있음: {r2}"
    assert r2["intent"] == r1["intent"], f"intent 불일치: {r1['intent']} vs {r2['intent']}"
    print(f"  후보 모드: candidates={r2['candidates'][:3]} ✓")

    print("  → 호환성 테스트 통과 ✓")


def test_detect_complexity():
    """복합 감지 테스트"""
    print("\n=== 2. detect_complexity() 테스트 ===")

    # 단순 쿼리 (복합 아님)
    simple_cases = [
        ("연차 규정 알려줘", [{"intent": "doc_search", "confidence": 0.9}, {"intent": "general", "confidence": 0.05}]),
        ("오늘 일정 보여줘", [{"intent": "schedule_view", "confidence": 0.95}, {"intent": "general", "confidence": 0.03}]),
        ("이거 규정 위반이야?", [{"intent": "judgment", "confidence": 0.88}, {"intent": "doc_search", "confidence": 0.08}]),
        ("규정 확인해서 알려줘", [{"intent": "doc_search", "confidence": 0.85}, {"intent": "general", "confidence": 0.05}]),  # 동사 1개 → 단순
    ]

    # 복합 쿼리
    complex_cases = [
        ("규정 찾아서 판단해줘", [{"intent": "judgment", "confidence": 0.6}, {"intent": "doc_search", "confidence": 0.35}]),
        ("일정 확인하고 보고서 작성해줘", [{"intent": "schedule_view", "confidence": 0.5}, {"intent": "doc_generate", "confidence": 0.4}]),
        ("문서 검색해줘 그리고 정리해줘", [{"intent": "doc_search", "confidence": 0.55}, {"intent": "doc_generate", "confidence": 0.35}]),
    ]

    errors = 0

    print("  [단순 쿼리 — 복합 아님이어야 함]")
    for text, cands in simple_cases:
        result = detect_complexity(text, cands)
        status = "✓" if not result["is_complex"] else "✗ (오탐!)"
        if result["is_complex"]:
            errors += 1
        print(f"    '{text}' → is_complex={result['is_complex']}, signals={result['signals']}, reasons={result['trigger_reasons']} {status}")

    print("  [복합 쿼리 — 복합이어야 함]")
    for text, cands in complex_cases:
        result = detect_complexity(text, cands)
        status = "✓" if result["is_complex"] else "✗ (미감지!)"
        if not result["is_complex"]:
            errors += 1
        print(f"    '{text}' → is_complex={result['is_complex']}, signals={result['signals']}, reasons={result['trigger_reasons']} {status}")

    if errors == 0:
        print(f"  → 복합 감지 테스트 전체 통과 ✓")
    else:
        print(f"  → 복합 감지 테스트 {errors}건 실패 ✗")


def test_context_dependent():
    """맥락 의존 감지 테스트"""
    print("\n=== 3. is_context_dependent() 테스트 ===")

    positive = ["그거 정리해줘", "아까 말한 내용 보여줘", "그 문서 찾아줘", "다시 해줘", "이전에 논의한 것 알려줘"]
    negative = ["연차 규정 알려줘", "보고서 작성해줘", "오늘 일정 확인해줘"]

    errors = 0
    for text in positive:
        result = is_context_dependent(text)
        status = "✓" if result else "✗"
        if not result:
            errors += 1
        print(f"    '{text}' → {result} {status}")
    for text in negative:
        result = is_context_dependent(text)
        status = "✓" if not result else "✗ (오탐)"
        if result:
            errors += 1
        print(f"    '{text}' → {result} {status}")

    if errors == 0:
        print(f"  → 맥락 감지 테스트 전체 통과 ✓")
    else:
        print(f"  → 맥락 감지 테스트 {errors}건 실패 ✗")


def test_known_overrides():
    """알려진 오분류 보정 테스트"""
    print("\n=== 4. apply_known_overrides() 테스트 ===")

    cases = [
        ("인센티브 지급 기준 알려줘", "doc_search", "judgment"),
        ("성과급 조건이 뭐야?", "doc_search", "judgment"),
        ("남은 공휴일 알려줘", "general", "schedule_view"),
        ("다음 휴일 언제야?", "general", "schedule_view"),
        ("연차 규정 알려줘", "doc_search", "doc_search"),  # 매칭 안 되는 경우 → 원본 유지
    ]

    errors = 0
    for text, bert_intent, expected in cases:
        result = apply_known_overrides(text, bert_intent)
        status = "✓" if result == expected else f"✗ (expected={expected})"
        if result != expected:
            errors += 1
        print(f"    '{text}' ({bert_intent}) → {result} {status}")

    if errors == 0:
        print(f"  → 오분류 보정 테스트 전체 통과 ✓")
    else:
        print(f"  → 오분류 보정 테스트 {errors}건 실패 ✗")


def test_regression(dataset_name: str):
    """데이터셋 기반 회귀 테스트"""
    print(f"\n=== 5. 회귀 테스트: {dataset_name} ===")

    data = load_test_data(dataset_name)
    clf = IntentClassifier()
    clf.load_model()

    correct = 0
    total = len(data)
    errors_by_intent = Counter()
    times = []

    for item in data:
        text = item["text"]
        expected = item["label"]

        t0 = time.time()
        result = clf.predict(text, return_candidates=True)
        elapsed = (time.time() - t0) * 1000
        times.append(elapsed)

        predicted = result["intent"]

        if predicted == expected:
            correct += 1
        else:
            errors_by_intent[f"{expected}→{predicted}"] += 1

    accuracy = correct / total * 100
    avg_time = sum(times) / len(times)
    p95_time = sorted(times)[int(len(times) * 0.95)]

    print(f"  정확도: {correct}/{total} ({accuracy:.2f}%)")
    print(f"  평균 시간: {avg_time:.2f}ms (P95: {p95_time:.2f}ms)")

    if errors_by_intent:
        print(f"  오분류 패턴 (상위 10):")
        for pattern, count in errors_by_intent.most_common(10):
            print(f"    {pattern}: {count}건")

    return accuracy


if __name__ == "__main__":
    print("=" * 60)
    print("Intent Classifier v2 회귀 테스트")
    print("=" * 60)

    # 기능 테스트
    test_predict_compatibility()
    test_detect_complexity()
    test_context_dependent()
    test_known_overrides()

    # 성능 회귀 테스트
    adv_acc = test_regression("adversarial_test")
    blind_acc = test_regression("blind_test")

    # 요약
    print("\n" + "=" * 60)
    print("요약")
    print("=" * 60)
    print(f"  adversarial: {adv_acc:.2f}%")
    print(f"  blind:       {blind_acc:.2f}%")

    # 기존 기준: adversarial F1 90.07%, blind F1 92.84%
    # accuracy와 F1은 다르지만 큰 하락이 없으면 OK
    if adv_acc >= 85 and blind_acc >= 85:
        print("  → 회귀 테스트 통과 ✓ (기존 성능 유지)")
    else:
        print("  → ⚠️ 성능 하락 감지! 기존 대비 확인 필요")
