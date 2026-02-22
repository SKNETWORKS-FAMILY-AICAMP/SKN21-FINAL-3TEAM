"""
실험 1+2: 방법론 비교 (Random, Rule-based, BERT Base, BERT Fine-tuned)
         + 혼동행렬 생성

실행 (RunPod):
    pip install matplotlib seaborn
    python ai/experiments/run_method_comparison.py
"""

import json
import time
import random
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import (
    f1_score, accuracy_score, confusion_matrix,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "intent"
MODEL_DIR = BASE_DIR / "ai" / "models" / "intent_classifier"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate",
    "meeting_generate", "schedule_add", "schedule_view", "general",
]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ── 데이터 로드 ──

def load_adversarial():
    with open(DATA_DIR / "adversarial_test.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return [(d["text"], d["label"]) for d in data]


def load_eval():
    data = []
    with open(DATA_DIR / "eval.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line.strip())
            data.append((item["text"], item["label"]))
    return data


# ── Method 1: Random ──

def random_classify(text):
    return random.choice(INTENT_LABELS)


# ── Method 2: Rule-based ──
# 실무에서 처음 시도할 법한 합리적 수준의 키워드 규칙.
# 의도적으로 약하게 만들지 않음 — 카테고리별 핵심 키워드 + 우선순위.

RULES = [
    # (카테고리, 키워드 리스트) — 위에서부터 우선 매칭
    ("meeting_generate", ["회의록", "회의 내용", "회의 요약", "미팅 요약", "미팅 정리",
                          "회고 내용", "회고 정리", "스크럼 정리", "액션아이템 정리"]),
    ("schedule_add",     ["일정 추가", "일정추가", "회의 잡아", "미팅 잡아", "미팅 넣어",
                          "예약해", "등록해", "넣어줘", "일정 넣"]),
    ("schedule_view",    ["일정 알려", "일정 보여", "일정 확인", "뭐 있", "비어있",
                          "남은 일정", "뭐 있더라", "일정 있"]),
    ("doc_search",       ["찾아줘", "찾아봐", "검색", "보여줘", "어디 있", "어디서",
                          "양식", "템플릿", "자료 찾", "다운"]),
    ("doc_generate",     ["작성해", "만들어줘", "생성해", "초안", "써줘", "잡아줘"]),
    ("judgment",         ["규정", "규칙", "가능해", "되나", "허용", "위반", "불법",
                          "기준이", "의무", "강제", "징계", "돼?", "할 수 있"]),
]


def rule_based_classify(text):
    for label, keywords in RULES:
        if any(kw in text for kw in keywords):
            return label
    return "general"


# ── BERT 추론 공통 ──

def bert_predict(texts, tokenizer, model, id2label):
    preds = []
    for text in texts:
        inputs = tokenizer(
            text, return_tensors="pt", padding=True, truncation=True, max_length=64,
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
        pred_id = torch.argmax(outputs.logits, dim=-1).item()
        preds.append(id2label[pred_id])
    return preds


# ── 평가 ──

def evaluate(name, preds, labels):
    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, average="macro", labels=INTENT_LABELS, zero_division=0)
    return {"method": name, "accuracy": round(acc, 4), "f1_macro": round(f1, 4)}


# ── 혼동행렬 ──

def save_confusion_matrix(labels, preds, title, filename):
    cm = confusion_matrix(labels, preds, labels=INTENT_LABELS)
    plt.figure(figsize=(10, 8))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=INTENT_LABELS, yticklabels=INTENT_LABELS,
    )
    plt.title(title)
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close()
    print(f"    -> {filename}")


# ── 메인 ──

def main():
    print("=" * 60)
    print("  실험 1+2: 방법론 비교 + 혼동행렬")
    print(f"  Device: {device}")
    print("=" * 60)

    adv_data = load_adversarial()
    eval_data = load_eval()
    adv_texts, adv_labels = zip(*adv_data)
    eval_texts, eval_labels = zip(*eval_data)
    print(f"\n  Adversarial: {len(adv_data)}문장")
    print(f"  Eval:        {len(eval_data)}문장")

    results = []

    def save_results():
        """단계별로 중간 저장 — 이후 단계 실패해도 결과 보존"""
        with open(RESULTS_DIR / "method_comparison.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    # ---- 1. Random ----
    print("\n[1/4] Random baseline...")
    random.seed(42)
    t0 = time.time()
    preds = [random_classify(t) for t in adv_texts]
    elapsed = (time.time() - t0) * 1000
    r = evaluate("Random", preds, adv_labels)
    r["time_ms"] = round(elapsed / len(adv_texts), 2)
    r["cost"] = "$0"
    results.append(r)
    print(f"    F1={r['f1_macro']}  Acc={r['accuracy']}  {r['time_ms']}ms/문장")
    save_results()

    # ---- 2. Rule-based ----
    print("\n[2/4] Rule-based...")
    t0 = time.time()
    preds = [rule_based_classify(t) for t in adv_texts]
    elapsed = (time.time() - t0) * 1000
    r = evaluate("Rule-based", preds, adv_labels)
    r["time_ms"] = round(elapsed / len(adv_texts), 2)
    r["cost"] = "$0"
    results.append(r)
    print(f"    F1={r['f1_macro']}  Acc={r['accuracy']}  {r['time_ms']}ms/문장")
    save_results()

    # ---- 3. BERT Base (학습 전) ----
    print("\n[3/4] BERT Base (학습 전) — klue/bert-base 다운로드 중...")
    base_tok = AutoTokenizer.from_pretrained("klue/bert-base")
    base_model = AutoModelForSequenceClassification.from_pretrained(
        "klue/bert-base", num_labels=len(INTENT_LABELS),
    ).to(device)
    base_model.eval()
    id2label_base = {i: label for i, label in enumerate(INTENT_LABELS)}

    t0 = time.time()
    preds = bert_predict(adv_texts, base_tok, base_model, id2label_base)
    elapsed = (time.time() - t0) * 1000
    r = evaluate("BERT Base", preds, adv_labels)
    r["time_ms"] = round(elapsed / len(adv_texts), 2)
    r["cost"] = "$0"
    results.append(r)
    print(f"    F1={r['f1_macro']}  Acc={r['accuracy']}  {r['time_ms']}ms/문장")
    save_results()
    del base_model, base_tok

    # ---- 4. BERT Fine-tuned (v1.1) ----
    print("\n[4/4] BERT Fine-tuned (v1.1)...")
    ft_tok = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    ft_model = AutoModelForSequenceClassification.from_pretrained(
        str(MODEL_DIR),
    ).to(device)
    ft_model.eval()
    with open(MODEL_DIR / "label_map.json", "r", encoding="utf-8") as f:
        lm = json.load(f)
    id2label_ft = {int(k): v for k, v in lm["id2label"].items()}

    # adversarial
    t0 = time.time()
    ft_adv_preds = bert_predict(adv_texts, ft_tok, ft_model, id2label_ft)
    elapsed = (time.time() - t0) * 1000
    r = evaluate("BERT Fine-tuned", ft_adv_preds, adv_labels)
    r["time_ms"] = round(elapsed / len(adv_texts), 2)
    r["cost"] = "~$0.50 (1회 학습)"
    results.append(r)
    print(f"    F1={r['f1_macro']}  Acc={r['accuracy']}  {r['time_ms']}ms/문장")
    save_results()

    # eval set
    print("\n  Eval set 추론 중...")
    ft_eval_preds = bert_predict(eval_texts, ft_tok, ft_model, id2label_ft)
    er = evaluate("BERT Fine-tuned (eval)", ft_eval_preds, eval_labels)
    print(f"    Eval F1={er['f1_macro']}  Acc={er['accuracy']}")

    # ---- 혼동행렬 ----
    print("\n  혼동행렬 생성 중...")
    save_confusion_matrix(
        eval_labels, ft_eval_preds,
        f"Confusion Matrix — Eval Set ({len(eval_data)} samples)", "confusion_eval.png",
    )
    save_confusion_matrix(
        adv_labels, ft_adv_preds,
        f"Confusion Matrix — Adversarial Set ({len(adv_data)} samples)", "confusion_adv.png",
    )

    # ---- 요약 ----
    print(f"\n{'=' * 60}")
    print(f"  {'Method':<20} {'F1':>8} {'Acc':>8} {'Speed':>10}")
    print(f"  {'-' * 48}")
    for r in results:
        print(f"  {r['method']:<20} {r['f1_macro']:>8} {r['accuracy']:>8} {r['time_ms']:>8}ms")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
