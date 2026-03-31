# -*- coding: utf-8 -*-
"""Intent classifier 6라벨 기준 confidence 분석"""
import sys, json
sys.path.insert(0, "/home/ubuntu/SKN21-FINAL-3TEAM")
import numpy as np
from ai.agents.intent_classifier import IntentClassifier, apply_known_overrides

clf = IntentClassifier()
clf.load_model()

tests = [
    # 규정 판단 (judgment)
    ("재택근무 규정 알려줘", "judgment"),
    ("연차 사용 시 며칠 전에 신청해야 하나요?", "judgment"),
    ("출장 시 숙박비 한도가 얼마인가요?", "judgment"),
    ("지각하면 어떻게 돼?", "judgment"),
    ("복리후생 뭐 있어?", "judgment"),
    ("인센티브 지급 기준이 뭐야", "judgment"),
    ("퇴직금 계산해줘", "judgment"),
    ("야근 수당 규정 설명해줘", "judgment"),
    ("휴일근무 수당 얼마야?", "judgment"),
    ("경조사 휴가 며칠이야?", "judgment"),
    ("출산휴가 규정 알려줘", "judgment"),
    ("해외출장 일비 기준 알려줘", "judgment"),
    ("연봉 인상 기준이 뭐야?", "judgment"),
    ("보안 규정 위반하면 어떻게 돼?", "judgment"),
    ("USB 반입 가능한가요?", "judgment"),
    ("재택근무 가능한가요?", "judgment"),
    ("병가 쓰려면 어떻게 해야 해?", "judgment"),
    # 문서 검색 (doc_retrieve)
    ("보고서 찾아줘", "doc_retrieve"),
    ("이 문서 요약해줘", "doc_retrieve"),
    ("지난달 회의록 보여줘", "doc_retrieve"),
    ("마케팅 관련 문서 검색", "doc_retrieve"),
    ("프로젝트 현황 보고서 있어?", "doc_retrieve"),
    # 문서 생성 (doc_generate)
    ("회의록 작성해줘", "doc_generate"),
    ("보고서 만들어줘", "doc_generate"),
    ("제안서 작성해줘", "doc_generate"),
    # 일정 (schedule) — pipeline/approval도 schedule_add
    ("내일 일정 알려줘", "schedule_view"),
    ("다음주 월요일 3시에 회의 잡아줘", "schedule_add"),
    ("이번주 일정 뭐 있어?", "schedule_view"),
    ("태스크 만들어줘", "schedule_add"),
    ("결재 올려줘", "schedule_add"),
    ("연차 신청해줘", "schedule_add"),
    # 일반 (general)
    ("안녕하세요", "general"),
    ("오늘 날씨 어때", "general"),
    ("고마워", "general"),
]

results = []
for text, expected in tests:
    r = clf.predict(text, return_candidates=True)
    cands = r.get("candidates", [])

    # ONNX raw (before override)
    probs_np = clf._onnx_predict_probs(text)
    raw_id = int(np.argmax(probs_np))
    raw_intent = clf.id2label.get(raw_id, "general")

    # after override
    final_intent = r["intent"]
    final_conf = r["confidence"]

    gap = cands[0]["confidence"] - cands[1]["confidence"] if len(cands) >= 2 else 999

    # verdict
    if raw_intent != final_intent:
        if final_intent == expected and raw_intent != expected:
            verdict = "override_fix"
        elif raw_intent == expected and final_intent != expected:
            verdict = "override_break"
        else:
            verdict = "both_wrong"
    elif final_intent == expected:
        verdict = "ok"
    else:
        verdict = "onnx_wrong"

    results.append({
        "text": text,
        "expected": expected,
        "raw_intent": raw_intent,
        "raw_conf": round(float(probs_np[raw_id]), 4),
        "final_intent": final_intent,
        "final_conf": round(final_conf, 4),
        "gap": round(gap, 4),
        "top3": [{"i": c["intent"], "c": round(c["confidence"], 4)} for c in cands[:3]],
        "verdict": verdict,
    })

print(json.dumps(results, ensure_ascii=False, indent=2))
