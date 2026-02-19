"""
복합 질문 감지 정확도 검증 (Phase 3)

detect_complexity() + is_context_dependent() 함수를 30문장 테스트셋으로 평가.
결과를 콘솔에 출력하고 JSON으로 저장.

사용법:
    python ai/experiments/run_complex_test.py
"""

import json
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from ai.agents.intent_classifier import detect_complexity, is_context_dependent


def load_test_data():
    """테스트 데이터 로드"""
    test_file = ROOT / "data" / "training" / "intent" / "complex_test.json"
    with open(test_file, "r", encoding="utf-8") as f:
        return json.load(f)


def make_dummy_candidates(is_complex_expected: bool):
    """
    테스트용 더미 candidates 생성.

    detect_complexity는 candidates의 top-2 gap을 사용하므로,
    복합으로 판정되어야 하는 경우 gap을 좁게,
    단순으로 판정되어야 하는 경우 gap을 넓게 설정.

    실제 서비스에서는 BERT predict(return_candidates=True)가 제공.
    여기서는 순수하게 규칙(키워드+동사)만 테스트하기 위해
    confidence gap은 중립적으로 설정 (gap=0.25 → 경계 부근).
    """
    # 중립적 gap: 키워드와 동사 패턴만으로 판정되도록
    return [
        {"intent": "doc_search", "confidence": 0.55},
        {"intent": "judgment", "confidence": 0.30},
        {"intent": "general", "confidence": 0.15},
    ]


def run_test():
    """복합 질문 감지 테스트 실행"""
    test_data = load_test_data()
    items = test_data["data"]

    results = {
        "total": len(items),
        "complexity_correct": 0,
        "complexity_wrong": 0,
        "context_correct": 0,
        "context_wrong": 0,
        "details": [],
    }

    # 카테고리별 집계
    category_stats = {}

    print("=" * 70)
    print("  복합 질문 감지 테스트 (Phase 3)")
    print("=" * 70)
    print()

    for item in items:
        text = item["text"]
        expected = item["expected"]
        category = item["category"]

        # 더미 candidates 생성
        candidates = make_dummy_candidates(expected.get("is_complex", False))

        # detect_complexity 실행
        complexity = detect_complexity(text, candidates)
        predicted_complex = complexity["is_complex"]
        expected_complex = expected.get("is_complex", False)

        # is_context_dependent 실행
        predicted_context = is_context_dependent(text)
        expected_context = expected.get("is_context_dependent", False)

        # 정답 판정
        complex_correct = predicted_complex == expected_complex
        context_correct = predicted_context == expected_context

        if complex_correct:
            results["complexity_correct"] += 1
        else:
            results["complexity_wrong"] += 1

        if context_correct:
            results["context_correct"] += 1
        else:
            results["context_wrong"] += 1

        # 카테고리별 집계
        if category not in category_stats:
            category_stats[category] = {"total": 0, "complex_ok": 0, "context_ok": 0}
        category_stats[category]["total"] += 1
        if complex_correct:
            category_stats[category]["complex_ok"] += 1
        if context_correct:
            category_stats[category]["context_ok"] += 1

        # 상세 결과
        status = "PASS" if (complex_correct and context_correct) else "FAIL"
        detail = {
            "id": item["id"],
            "text": text,
            "category": category,
            "expected_complex": expected_complex,
            "predicted_complex": predicted_complex,
            "complexity_signals": complexity["signals"],
            "trigger_reasons": complexity["trigger_reasons"],
            "expected_context": expected_context,
            "predicted_context": predicted_context,
            "complex_correct": complex_correct,
            "context_correct": context_correct,
            "status": status,
        }
        results["details"].append(detail)

        # 출력
        icon = "PASS" if status == "PASS" else "FAIL"
        print(f"  [{icon}] #{item['id']:2d} | {text}")
        if not complex_correct:
            print(f"         복합: expected={expected_complex}, got={predicted_complex} "
                  f"(signals={complexity['signals']}, reasons={complexity['trigger_reasons']})")
        if not context_correct:
            print(f"         맥락: expected={expected_context}, got={predicted_context}")

    # 요약
    total = results["total"]
    complex_acc = results["complexity_correct"] / total * 100
    context_acc = results["context_correct"] / total * 100

    results["complexity_accuracy"] = round(complex_acc, 2)
    results["context_accuracy"] = round(context_acc, 2)
    results["category_stats"] = category_stats

    print()
    print("=" * 70)
    print(f"  복합 감지 정확도: {results['complexity_correct']}/{total} ({complex_acc:.1f}%)")
    print(f"  맥락 감지 정확도: {results['context_correct']}/{total} ({context_acc:.1f}%)")
    print()

    # 카테고리별 결과
    print("  카테고리별 결과:")
    for cat, stats in category_stats.items():
        cat_total = stats["total"]
        print(f"    {cat:25s}: 복합 {stats['complex_ok']}/{cat_total}, "
              f"맥락 {stats['context_ok']}/{cat_total}")

    print()

    # 오분류 상세
    errors = [d for d in results["details"] if d["status"] == "FAIL"]
    if errors:
        print(f"  오분류 {len(errors)}건:")
        for e in errors:
            print(f"    #{e['id']:2d} \"{e['text']}\"")
            if not e["complex_correct"]:
                print(f"        복합: expected={e['expected_complex']} → got={e['predicted_complex']} "
                      f"(reasons={e['trigger_reasons']})")
            if not e["context_correct"]:
                print(f"        맥락: expected={e['expected_context']} → got={e['predicted_context']}")
    else:
        print("  오분류 0건!")

    print("=" * 70)

    # 결과 저장
    output_file = Path(__file__).parent / "results" / "complex_test.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {output_file}")

    return results


if __name__ == "__main__":
    run_test()
