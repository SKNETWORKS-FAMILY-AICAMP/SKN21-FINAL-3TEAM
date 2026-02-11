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
import numpy as np
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
    print(f"  Top3: ", end="")
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


def adversarial_test(tokenizer, model, id2label):
    """헷갈리는 문장들로 테스트"""
    print("=" * 50)
    print("  Adversarial 테스트 (경계가 모호한 문장)")
    print("=" * 50)
    print()

    test_cases = [
        # ===== doc_search vs doc_generate 경계 (10개) =====
        ("출장 보고서 양식 찾아줘", "doc_search"),
        ("출장 보고서 작성해줘", "doc_generate"),
        ("제안서 템플릿 있어?", "doc_search"),
        ("제안서 만들어줘", "doc_generate"),
        ("이전에 작성한 보고서 찾아줘", "doc_search"),
        ("이전 보고서 참고해서 새로 써줘", "doc_generate"),
        ("NDA 양식 어디서 다운받아?", "doc_search"),
        ("NDA 초안 작성해줘", "doc_generate"),
        ("지난달 매출 보고서 보여줘", "doc_search"),
        ("이번 달 매출 보고서 만들어줘", "doc_generate"),

        # ===== doc_generate vs meeting_generate 경계 (8개) =====
        ("회의 내용 정리해줘", "meeting_generate"),
        ("보고서 정리해줘", "doc_generate"),
        ("오늘 미팅 요약해줘", "meeting_generate"),
        ("이 문서 요약해줘", "doc_generate"),
        ("스프린트 회고 내용 정리해줘", "meeting_generate"),
        ("프로젝트 현황 보고서 작성해줘", "doc_generate"),
        ("킥오프 미팅 회의록 만들어줘", "meeting_generate"),
        ("신입사원 온보딩 가이드 만들어줘", "doc_generate"),

        # ===== schedule_add vs schedule_view 경계 (10개) =====
        ("내일 회의 있어?", "schedule_view"),
        ("내일 회의 잡아줘", "schedule_add"),
        ("다음 주 일정 알려줘", "schedule_view"),
        ("다음 주에 일정 추가해줘", "schedule_add"),
        ("금요일 비어있어?", "schedule_view"),
        ("금요일 3시에 미팅 넣어줘", "schedule_add"),
        ("이번 달 마감일 뭐 있지?", "schedule_view"),
        ("프로젝트 마감일 등록해줘", "schedule_add"),
        ("오후에 일정 있나?", "schedule_view"),
        ("오후 4시에 팀 회의 예약해줘", "schedule_add"),

        # ===== judgment vs general 경계 (10개) =====
        ("연차 규정이 뭐야?", "judgment"),
        ("연차 몇 개 남았어?", "general"),
        ("야근 수당 기준이 어떻게 돼?", "judgment"),
        ("야근하기 싫다", "general"),
        ("육아휴직 남자도 쓸 수 있어?", "judgment"),
        ("육아 힘들다", "general"),
        ("겸직 가능해?", "judgment"),
        ("이직 생각 중이야", "general"),
        ("회사가 이렇게 해도 되는 거야?", "judgment"),
        ("회사 밥이 맛없어", "general"),

        # ===== judgment vs doc_search 경계 (8개) =====
        ("퇴직금 규정 찾아줘", "doc_search"),
        ("퇴직금 받을 수 있어?", "judgment"),
        ("인사 규정 보여줘", "doc_search"),
        ("이 경우 징계 대상이야?", "judgment"),
        ("보안 정책 문서 어디 있어?", "doc_search"),
        ("USB 반입해도 돼?", "judgment"),
        ("근로기준법 자료 찾아줘", "doc_search"),
        ("주 52시간 넘기면 어떻게 돼?", "judgment"),

        # ===== 비정형/구어체 입력 (10개) =====
        ("ㅋㅋㅋ", "general"),
        ("뭐해", "general"),
        ("아 그거 뭐냐 연차 쓸 수 있냐 없냐", "judgment"),
        ("보고서 그거 아까 말한거 해줘", "doc_generate"),
        ("일정 좀", "schedule_view"),
        ("아까 그 규정 다시 찾아봐", "doc_search"),
        ("ㅇㅇ 그거 회의록 정리해줘", "meeting_generate"),
        ("내일 뭐 있더라", "schedule_view"),
        ("수고", "general"),
        ("고마워", "general"),

        # ===== 복합/긴 문장 (8개) =====
        ("지난주 회의에서 나온 액션아이템 정리해서 회의록 만들어줘", "meeting_generate"),
        ("마케팅팀이랑 수요일 오후에 미팅 잡아줘", "schedule_add"),
        ("작년 4분기 실적 보고서 찾아서 보여줘", "doc_search"),
        ("신규 프로젝트 제안서를 지난 제안서 참고해서 작성해줘", "doc_generate"),
        ("계약직 2년 넘었는데 정규직 전환 안 해주면 불법이야?", "judgment"),
        ("이번 주 남은 일정이랑 내주 일정 같이 보여줘", "schedule_view"),
        ("팀장님이 주말 출근하라는데 이거 강제할 수 있는 거야?", "judgment"),
        ("다음 분기 사업 계획서 초안 좀 잡아줘", "doc_generate"),

        # ===== 오타/축약어 (6개) =====
        ("연차 ㅆㄹ수있어?", "judgment"),
        ("회의록 ㄱㄱ", "meeting_generate"),
        ("내일 ㅇㅈ 뭐야", "schedule_view"),
        ("ㅂㄱㅅ 써줘", "doc_generate"),
        ("안녕하세여", "general"),
        ("일정추가", "schedule_add"),
    ]

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
