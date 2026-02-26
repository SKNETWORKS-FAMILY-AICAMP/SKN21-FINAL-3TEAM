"""
Intent Classification 테스트 스크립트 (PM 지용)

학습된 모델로 직접 문장을 입력하여 intent 분류를 테스트합니다.

사용법:
    # 대화형 테스트 (문장 직접 입력)
    python ai/agents/test_intent.py

    # 단일 문장 테스트
    python ai/agents/test_intent.py --text "연차 사용 가능한가요?"

    # adversarial 테스트 (헷갈리는 문장들로 자동 테스트)
    python ai/agents/test_intent.py --adversarial
"""

import argparse
import json
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForSequenceClassification


BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = BASE_DIR / "ai" / "models" / "intent_classifier"


def load_model():
    """학습된 모델 로드"""
    print(f"모델 로드 중... ({MODEL_DIR})")
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR))
    model.eval()

    with open(MODEL_DIR / "label_map.json", "r", encoding="utf-8") as f:
        label_map = json.load(f)

    id2label = {int(k): v for k, v in label_map["id2label"].items()}
    print("모델 로드 완료!\n")
    return tokenizer, model, id2label


def predict(text: str, tokenizer, model, id2label) -> dict:
    """단일 문장 intent 분류"""
    inputs = tokenizer(
        text, return_tensors="pt", padding=True, truncation=True, max_length=64
    )
    with torch.no_grad():
        outputs = model(**inputs)

    probs = torch.softmax(outputs.logits, dim=-1)[0]
    pred_id = torch.argmax(probs).item()
    confidence = probs[pred_id].item()

    # Top-3
    top3_ids = torch.topk(probs, 3).indices.tolist()
    top3 = [(id2label[i], probs[i].item()) for i in top3_ids]

    return {
        "intent": id2label[pred_id],
        "confidence": confidence,
        "top3": top3,
    }


def print_result(text: str, result: dict):
    """결과 출력"""
    print(f"  입력: {text}")
    print(f"  결과: {result['intent']} ({result['confidence']:.4f})")
    print("  Top3: ", end="")
    for label, prob in result["top3"]:
        print(f"{label}({prob:.3f}) ", end="")
    print("\n")


def interactive_mode(tokenizer, model, id2label):
    """대화형 테스트"""
    print("=" * 50)
    print("  Intent 분류 테스트 (종료: q)")
    print("=" * 50)
    print()

    while True:
        text = input("문장 입력 > ").strip()
        if text.lower() in ("q", "quit", "exit", "종료"):
            print("테스트 종료!")
            break
        if not text:
            continue

        result = predict(text, tokenizer, model, id2label)
        print_result(text, result)


def load_adversarial_cases() -> list[tuple[str, str]]:
    """adversarial 테스트 케이스를 JSON 파일에서 로드"""
    adv_path = BASE_DIR / "data" / "training" / "intent" / "adversarial_test.json"
    with open(adv_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [(item["text"], item["label"]) for item in data]


def adversarial_test(tokenizer, model, id2label):
    """헷갈리는 문장들로 테스트"""
    print("=" * 50)
    print("  Adversarial 테스트 (경계가 모호한 문장)")
    print("=" * 50)
    print()

    test_cases = load_adversarial_cases()

    correct = 0
    wrong = []

    for text, expected in test_cases:
        result = predict(text, tokenizer, model, id2label)
        is_correct = result["intent"] == expected
        correct += is_correct
        status = "O" if is_correct else "X"

        if not is_correct:
            wrong.append((text, expected, result["intent"], result["confidence"]))

        print(f"  [{status}] \"{text}\"")
        print(f"       예상: {expected} → 결과: {result['intent']} ({result['confidence']:.3f})")

    print(f"\n{'=' * 50}")
    print(f"  결과: {correct}/{len(test_cases)} ({correct/len(test_cases)*100:.1f}%)")
    print(f"{'=' * 50}")

    if wrong:
        print(f"\n  오분류 {len(wrong)}건:")
        for text, expected, got, conf in wrong:
            print(f"    \"{text}\" → 예상:{expected} 실제:{got} ({conf:.3f})")


def main():
    parser = argparse.ArgumentParser(description="Intent Classification 테스트")
    parser.add_argument("--text", type=str, help="테스트할 문장")
    parser.add_argument("--adversarial", action="store_true", help="adversarial 테스트 실행")
    args = parser.parse_args()

    tokenizer, model, id2label = load_model()

    if args.text:
        result = predict(args.text, tokenizer, model, id2label)
        print_result(args.text, result)
    elif args.adversarial:
        adversarial_test(tokenizer, model, id2label)
    else:
        interactive_mode(tokenizer, model, id2label)


if __name__ == "__main__":
    main()
