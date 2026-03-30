# -*- coding: utf-8 -*-
"""리팩토링 검증: ONNX 6라벨 + override가 schedule_add로 정상 라우팅되는지"""
import sys, json
sys.path.insert(0, "/home/ubuntu/SKN21-FINAL-3TEAM")
import numpy as np
from ai.agents.intent_classifier import IntentClassifier, apply_known_overrides, INTENT_LABELS

clf = IntentClassifier()
clf.load_model()

print("=== INTENT_LABELS ===")
print(INTENT_LABELS)
print(f"count: {len(INTENT_LABELS)}")

print("\n=== ONNX id2label ===")
print(clf.id2label)
print(f"count: {len(clf.id2label)}")

# pipeline/approval 질문이 schedule_add로 분류되는지 확인
tests = [
    ("태스크 만들어줘", "schedule_add"),
    ("결재 올려줘", "schedule_add"),
    ("연차 신청해줘", "schedule_add"),
    ("파이프라인에 추가해줘", "schedule_add"),
    ("휴가 결재 올려줘", "schedule_add"),
    # 기존 기능이 깨지지 않는지 확인
    ("재택근무 규정 알려줘", "judgment"),
    ("보고서 찾아줘", "doc_retrieve"),
    ("회의록 작성해줘", "doc_generate"),
    ("내일 일정 알려줘", "schedule_view"),
    ("다음주 월요일 3시에 회의 잡아줘", "schedule_add"),
    ("안녕하세요", "general"),
    ("지각하면 어떻게 돼?", "judgment"),
    ("이 문서 요약해줘", "doc_retrieve"),
    ("출산휴가 규정 알려줘", "judgment"),
    ("연차 사용 시 며칠 전에 신청해야 하나요?", "judgment"),
]

print("\n=== 분류 테스트 ===")
ok = 0
fail = 0
for text, expected in tests:
    r = clf.predict(text, return_candidates=True)
    final = r["intent"]
    conf = r["confidence"]
    mark = "OK" if final == expected else "FAIL"
    if final == expected:
        ok += 1
    else:
        fail += 1
    cands = r.get("candidates", [])
    top2 = f"{cands[0]['intent']}({cands[0]['confidence']:.3f})" if cands else ""
    if len(cands) > 1:
        top2 += f" vs {cands[1]['intent']}({cands[1]['confidence']:.3f})"
    print(f"  [{mark:4s}] {text:35s} -> {final:15s} (conf={conf:.4f}) expected={expected:15s} | {top2}")

print(f"\n=== 결과: {ok}/{ok+fail} 정답 ({ok/(ok+fail)*100:.1f}%) ===")

# pipeline_create/approval_create가 INTENT_LABELS에 없는지 확인
assert "pipeline_create" not in INTENT_LABELS, "pipeline_create still in INTENT_LABELS!"
assert "approval_create" not in INTENT_LABELS, "approval_create still in INTENT_LABELS!"
print("\nASSERT PASS: pipeline_create/approval_create not in INTENT_LABELS")
