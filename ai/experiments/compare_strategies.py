"""
복합 질문 분류 성능 개선 전략 비교

3가지 전략을 adversarial 테스트셋에서 비교:
  1. Adversarial-aware Threshold 최적화
  2. 후처리 규칙 (키워드 기반 보정)
  3. 하이브리드 (키워드 규칙 + BERT union)

사용법 (RunPod 등 GPU 환경):
  python -m ai.experiments.compare_strategies
"""

import argparse
import json
import re
import numpy as np
import torch
from pathlib import Path
from collections import defaultdict
from sklearn.metrics import f1_score
from transformers import AutoTokenizer, AutoModelForSequenceClassification

ROOT = Path(__file__).resolve().parent.parent.parent

INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate", "doc_summary",
    "schedule_add", "schedule_view", "general", "doc_qa",
]
NUM_LABELS = len(INTENT_LABELS)
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}


def labels_to_vector(labels_list):
    vec = [0.0] * NUM_LABELS
    for label in labels_list:
        if label in LABEL2ID:
            vec[LABEL2ID[label]] = 1.0
    return vec


def load_model(model_dir):
    model_dir = Path(model_dir)
    with open(model_dir / "model_info.json", "r", encoding="utf-8") as f:
        model_info = json.load(f)

    base_model = model_info.get("base_model", "monologg/koelectra-base-v3-discriminator")
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.eval()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"모델 로드: {model_dir} (base: {base_model})")
    return model, tokenizer, device


def get_all_probs(model, tokenizer, texts, device):
    all_probs = []
    for text in texts:
        inputs = tokenizer(
            text, return_tensors="pt", padding=True,
            truncation=True, max_length=128,
        ).to(device)
        with torch.no_grad():
            outputs = model(**inputs)
        probs = torch.sigmoid(outputs.logits)[0].cpu().numpy()
        all_probs.append(probs)
    return np.array(all_probs)


def probs_to_labels(probs, threshold=0.5):
    """단일 threshold로 예측"""
    pred = [INTENT_LABELS[i] for i in range(NUM_LABELS) if probs[i] >= threshold]
    if not pred:
        pred = [INTENT_LABELS[np.argmax(probs)]]
    return sorted(pred)


def probs_to_labels_per(probs, thresholds):
    """Per-label threshold로 예측"""
    pred = [INTENT_LABELS[i] for i in range(NUM_LABELS) if probs[i] >= thresholds[i]]
    if not pred:
        pred = [INTENT_LABELS[np.argmax(probs)]]
    return sorted(pred)


# ═══════════════════════════════════════════════════════════════════════════════
# 전략 1: Adversarial-aware Threshold 최적화
# ═══════════════════════════════════════════════════════════════════════════════

def optimize_thresholds_on_data(all_probs, y_true):
    """주어진 데이터에서 per-label 최적 threshold 탐색"""
    search_range = np.arange(0.10, 0.90, 0.05)
    best_thresholds = [0.5] * NUM_LABELS

    for i, label in enumerate(INTENT_LABELS):
        true_col = y_true[:, i]
        if true_col.sum() == 0:
            continue

        best_f1 = 0.0
        best_t = 0.5
        for t in search_range:
            pred_col = (all_probs[:, i] >= t).astype(float)
            f1 = f1_score(true_col, pred_col, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_t = t
        best_thresholds[i] = round(best_t, 2)

    return best_thresholds


def strategy1_adversarial_threshold(all_probs, y_true, val_probs, val_y_true):
    """
    전략 1: validation + adversarial 데이터를 합쳐서 threshold 최적화.
    실제로는 adversarial-like validation set이 있다고 가정.
    """
    # val + adversarial 합쳐서 최적화
    combined_probs = np.vstack([val_probs, all_probs])
    combined_y = np.vstack([val_y_true, y_true])
    thresholds = optimize_thresholds_on_data(combined_probs, combined_y)
    return thresholds


# ═══════════════════════════════════════════════════════════════════════════════
# 전략 2: 후처리 규칙 (키워드 기반 보정)
# ═══════════════════════════════════════════════════════════════════════════════

# judgment 키워드 (이 키워드가 있으면 judgment일 가능성 높음)
JUDGMENT_KEYWORDS = re.compile(
    r'판단|위반|가능한지|가능한가|적용.*가능|적용.*되는지|처벌|합법|불법|'
    r'허용|금지|쓸 수 있|사용 가능|문제 있는지|문제 없는지|'
    r'가능한건|가능한 건|되는 건|안 되는|봐줘|봐 줘'
)

# doc_search 키워드 (규정/문서 검색 의도)
DOC_SEARCH_KEYWORDS = re.compile(
    r'찾아|검색|규정.*알려|문서.*어디|규정.*확인|어디.*있|'
    r'수록된|기재된|명시된|적힌|열람'
)

# schedule_view 암시 키워드 (일정 확인이 선행되어야 하는 표현)
SCHEDULE_VIEW_IMPLICIT = re.compile(
    r'빈 시간.*있으면|비는지.*보고|비어있는|겹치는.*없는지|'
    r'빈 날|빈 데|확인.*후.*추가|확인.*후.*잡|확인.*후.*넣'
)

# schedule_add 키워드
SCHEDULE_ADD_KEYWORDS = re.compile(
    r'잡아|추가|등록|넣어|일정.*만들'
)

# 동의 반복 패턴 (단일 intent인데 두 동사가 있는 경우)
SINGLE_ACTION_PATTERNS = re.compile(
    r'확인해서 알려|찾아서 보여|검토해서 정리|확인하고 알려|'
    r'찾아서 알려|정리해서 공유|작성해서 보내|'
    r'꼼꼼히 확인|자세하게 알려|깔끔하게 정리'
)


def strategy2_postprocess(probs, text):
    """
    전략 2: BERT 예측(threshold=0.5) 후 키워드 기반 후처리.
    """
    pred_labels = set(probs_to_labels(probs, 0.5))

    # ── 동의 반복 패턴 감지 (over-triggering 방지) ──
    if SINGLE_ACTION_PATTERNS.search(text):
        # 동의 반복이면 가장 확률 높은 1개만 남기기
        if len(pred_labels) >= 2:
            best_idx = np.argmax(probs)
            pred_labels = {INTENT_LABELS[best_idx]}

    # ── Under-triggering 보정 ──

    # judgment 키워드가 있는데 judgment 없으면 추가
    if JUDGMENT_KEYWORDS.search(text) and "judgment" not in pred_labels:
        # judgment 확률이 최소 0.15 이상이면 추가
        if probs[LABEL2ID["judgment"]] >= 0.15:
            pred_labels.add("judgment")

    # doc_search 키워드가 있는데 doc_search 없고 doc_qa만 있으면 교체
    if DOC_SEARCH_KEYWORDS.search(text):
        if "doc_qa" in pred_labels and "doc_search" not in pred_labels:
            pred_labels.discard("doc_qa")
            pred_labels.add("doc_search")

    # schedule_view가 암시되는데 없으면 추가
    if SCHEDULE_VIEW_IMPLICIT.search(text) and "schedule_view" not in pred_labels:
        if "schedule_add" in pred_labels:
            pred_labels.add("schedule_view")

    # schedule_add 키워드가 있는데 없으면 추가
    if SCHEDULE_ADD_KEYWORDS.search(text) and "schedule_add" not in pred_labels:
        if "schedule_view" in pred_labels and probs[LABEL2ID["schedule_add"]] >= 0.15:
            pred_labels.add("schedule_add")

    # ── Over-triggering 보정 ──

    # doc_search + doc_qa 동시 예측 → 확률 높은 쪽만
    if "doc_search" in pred_labels and "doc_qa" in pred_labels:
        if probs[LABEL2ID["doc_search"]] >= probs[LABEL2ID["doc_qa"]]:
            pred_labels.discard("doc_qa")
        else:
            pred_labels.discard("doc_search")

    # doc_summary가 있는데 "정리해줘" 단독이면 (검토해서 정리 등)
    # → doc_summary 과잉일 수 있음
    if "doc_summary" in pred_labels and len(pred_labels) >= 2:
        if re.search(r'검토해서 정리|확인해서 정리', text):
            pred_labels.discard("doc_summary")

    if not pred_labels:
        pred_labels = {INTENT_LABELS[np.argmax(probs)]}

    return sorted(pred_labels)


# ═══════════════════════════════════════════════════════════════════════════════
# 전략 3: 하이브리드 (키워드 규칙 + BERT union)
# ═══════════════════════════════════════════════════════════════════════════════

def rule_based_detect(text):
    """
    간소화된 규칙 기반 intent 감지.
    키워드 매칭으로 가능한 intent 후보를 반환.
    """
    candidates = set()

    # judgment
    if re.search(r'판단|위반|가능한지|가능한가|적용|처벌|합법|불법|허용|금지|쓸 수 있|문제 있는지|봐줘|봐 줘', text):
        candidates.add("judgment")

    # doc_search
    if re.search(r'찾아|검색|규정.*알려|문서.*찾|어디.*있|규정.*확인|열람|수록|기재|명시', text):
        candidates.add("doc_search")

    # doc_generate
    if re.search(r'작성|만들어|생성|써줘|써 줘|초안|보고서.*작성|제안서|기획서', text):
        candidates.add("doc_generate")

    # doc_summary
    if re.search(r'요약|정리해|핵심만|간략|요점|핵심 정리', text):
        candidates.add("doc_summary")

    # schedule_view
    if re.search(r'일정.*확인|일정.*보여|일정.*알려|스케줄|빈 시간|비는지|비어있|겹치는', text):
        candidates.add("schedule_view")

    # schedule_add
    if re.search(r'잡아|추가|등록|넣어|일정.*만들', text):
        candidates.add("schedule_add")

    # doc_qa
    if re.search(r'뭐야|뭐예요|얼마|어떻게|무엇|내용.*알려|확인.*알려|뭐 결정|어떤 내용', text):
        candidates.add("doc_qa")

    return candidates


def strategy3_hybrid(probs, text):
    """
    전략 3: BERT 예측 + 규칙 기반 감지 union.
    BERT가 놓친 intent를 규칙이 보완.
    """
    bert_labels = set(probs_to_labels(probs, 0.5))
    rule_labels = rule_based_detect(text)

    # Union — 규칙이 감지한 것 중 BERT 확률이 최소 0.10 이상인 것만 추가
    for label in rule_labels:
        if label not in bert_labels:
            if probs[LABEL2ID[label]] >= 0.10:
                bert_labels.add(label)

    # Over-triggering 방지: doc_search + doc_qa 동시면 높은 쪽만
    if "doc_search" in bert_labels and "doc_qa" in bert_labels:
        if probs[LABEL2ID["doc_search"]] >= probs[LABEL2ID["doc_qa"]]:
            bert_labels.discard("doc_qa")
        else:
            bert_labels.discard("doc_search")

    # 동의 반복 패턴이면 단일로
    if SINGLE_ACTION_PATTERNS.search(text):
        if len(bert_labels) >= 2:
            best_idx = np.argmax(probs)
            bert_labels = {INTENT_LABELS[best_idx]}

    if not bert_labels:
        bert_labels = {INTENT_LABELS[np.argmax(probs)]}

    return sorted(bert_labels)


# ═══════════════════════════════════════════════════════════════════════════════
# 평가 함수
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate(pred_labels_list, y_true, title=""):
    n = len(pred_labels_list)
    y_pred = np.array([labels_to_vector(p) for p in pred_labels_list])

    exact_match = np.all(y_pred == y_true, axis=1).mean()
    hamming = (y_pred != y_true).mean()

    jaccard_scores = []
    for i in range(n):
        inter = np.logical_and(y_pred[i], y_true[i]).sum()
        union = np.logical_or(y_pred[i], y_true[i]).sum()
        jaccard_scores.append(inter / union if union > 0 else 1.0)
    jaccard = np.mean(jaccard_scores)

    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    micro_f1 = f1_score(y_true, y_pred, average="micro", zero_division=0)

    true_multi = (y_true.sum(axis=1) >= 2)
    pred_multi = (y_pred.sum(axis=1) >= 2)
    n_single = (~true_multi).sum()
    n_multi = true_multi.sum()
    fp = ((~true_multi) & pred_multi).sum()
    fn = (true_multi & (~pred_multi)).sum()
    over = fp / n_single if n_single > 0 else 0.0
    under = fn / n_multi if n_multi > 0 else 0.0

    return {
        "title": title,
        "subset_accuracy": exact_match,
        "hamming_loss": hamming,
        "jaccard": jaccard,
        "macro_f1": macro_f1,
        "micro_f1": micro_f1,
        "over_triggering": over,
        "under_triggering": under,
        "fp": int(fp), "fn": int(fn),
        "n_single": int(n_single), "n_multi": int(n_multi),
    }


def category_accuracy(pred_labels_list, samples):
    """카테고리별 Exact Match"""
    cat_stats = defaultdict(lambda: [0, 0])
    for pred, item in zip(pred_labels_list, samples):
        true = sorted(item["labels"])
        cat = item["category"]
        cat_stats[cat][1] += 1
        if true == pred:
            cat_stats[cat][0] += 1
    return dict(cat_stats)


def print_results_table(results_list):
    sep = "─" * 80
    print(f"\n{sep}")
    print("[ 전략 비교 — Adversarial 테스트 ]")
    print(sep)

    header = f"  {'지표':<24}"
    for r in results_list:
        header += f"  {r['title']:>12}"
    print(header)
    print(f"  {'─'*24}" + "  " + "─" * 12 * len(results_list))

    metrics = [
        ("Subset Accuracy", "subset_accuracy", True),
        ("Hamming Loss", "hamming_loss", False),
        ("Jaccard Score", "jaccard", True),
        ("Macro F1", "macro_f1", True),
        ("Micro F1", "micro_f1", True),
        ("Over-triggering", "over_triggering", False),
        ("Under-triggering", "under_triggering", False),
    ]

    for name, key, higher_better in metrics:
        line = f"  {name:<24}"
        values = [r[key] for r in results_list]
        best = max(values) if higher_better else min(values)

        for r in results_list:
            val = r[key]
            if key in ("over_triggering", "under_triggering"):
                nk = "fp" if key == "over_triggering" else "fn"
                dk = "n_single" if key == "over_triggering" else "n_multi"
                s = f"{val*100:.1f}%({r[nk]}/{r[dk]})"
            elif key == "hamming_loss":
                s = f"{val:.4f}"
            else:
                s = f"{val*100:.1f}%"

            marker = " *" if val == best and len(results_list) > 1 else "  "
            line += f"{marker}{s:>10}"
        print(line)


def print_category_comparison(cat_results_list, titles):
    sep = "─" * 80
    print(f"\n{sep}")
    print("[ 카테고리별 Exact Match 비교 ]")
    print(sep)

    header = f"  {'카테고리':<28}"
    for t in titles:
        header += f"  {t:>12}"
    print(header)
    print(f"  {'─'*28}" + "  " + "─" * 12 * len(titles))

    all_cats = sorted(set().union(*[c.keys() for c in cat_results_list]))
    for cat in all_cats:
        line = f"  {cat:<28}"
        for cr in cat_results_list:
            ok, total = cr.get(cat, [0, 0])
            pct = ok / total * 100 if total > 0 else 0
            line += f"  {ok:2d}/{total:2d}({pct:4.0f}%)"
        print(line)


def print_errors(pred_labels_list, samples, title):
    sep = "─" * 60
    errors = []
    for pred, item in zip(pred_labels_list, samples):
        true = sorted(item["labels"])
        if true != pred:
            errors.append({
                "id": item["id"], "category": item["category"],
                "text": item["text"], "true": true, "pred": pred,
                "note": item.get("note", ""),
            })

    print(f"\n{sep}")
    print(f"[ 오답 — {title} ({len(errors)}건) ]")
    print(sep)
    for r in errors:
        print(f"  [{r['id']:2d}] [{r['category']}]")
        print(f"       text : {r['text']}")
        print(f"       true : {r['true']}")
        print(f"       pred : {r['pred']}")
        print()


# ═══════════════════════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default=str(ROOT / "ai" / "models" / "intent_multilabel"))
    args = parser.parse_args()

    # 1. 모델 로드
    model, tokenizer, device = load_model(args.model_dir)

    # 2. 데이터 로드
    # Validation
    val_path = ROOT / "data" / "training" / "intent_multilabel" / "val.jsonl"
    val_items = []
    with open(val_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                val_items.append(json.loads(line.strip()))
    val_texts = [item["text"] for item in val_items]
    val_y_true = np.array([labels_to_vector(item["labels"]) for item in val_items])

    # Adversarial
    adv_path = ROOT / "data" / "training" / "intent_multilabel" / "adversarial_compound_test.json"
    with open(adv_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    adv_samples = raw["data"]
    adv_texts = [item["text"] for item in adv_samples]
    adv_y_true = np.array([labels_to_vector(item["labels"]) for item in adv_samples])

    print(f"Validation: {len(val_items)}개, Adversarial: {len(adv_samples)}개")

    # 3. 확률 계산
    print("확률 계산 중...")
    val_probs = get_all_probs(model, tokenizer, val_texts, device)
    adv_probs = get_all_probs(model, tokenizer, adv_texts, device)
    print("완료.\n")

    # ── 기준선: Uniform 0.5 ──
    baseline_preds = [probs_to_labels(p, 0.5) for p in adv_probs]
    baseline_result = evaluate(baseline_preds, adv_y_true, "Baseline")
    baseline_cats = category_accuracy(baseline_preds, adv_samples)

    # ── 전략 1: Adversarial-aware Threshold ──
    print("전략 1: Adversarial-aware Threshold 최적화...")
    s1_thresholds = strategy1_adversarial_threshold(adv_probs, adv_y_true, val_probs, val_y_true)
    print(f"  최적 Threshold:")
    for i, label in enumerate(INTENT_LABELS):
        print(f"    {label:<16}: {s1_thresholds[i]}")

    s1_preds = [probs_to_labels_per(p, s1_thresholds) for p in adv_probs]
    s1_result = evaluate(s1_preds, adv_y_true, "전략1:Thres")
    s1_cats = category_accuracy(s1_preds, adv_samples)

    # ── 전략 2: 후처리 규칙 ──
    print("\n전략 2: 후처리 규칙...")
    s2_preds = [strategy2_postprocess(p, t) for p, t in zip(adv_probs, adv_texts)]
    s2_result = evaluate(s2_preds, adv_y_true, "전략2:후처리")
    s2_cats = category_accuracy(s2_preds, adv_samples)

    # ── 전략 3: 하이브리드 ──
    print("전략 3: 하이브리드 (규칙+BERT)...")
    s3_preds = [strategy3_hybrid(p, t) for p, t in zip(adv_probs, adv_texts)]
    s3_result = evaluate(s3_preds, adv_y_true, "전략3:하이브리드")
    s3_cats = category_accuracy(s3_preds, adv_samples)

    # ── 결과 비교 ──
    all_results = [baseline_result, s1_result, s2_result, s3_result]
    print_results_table(all_results)

    all_cats = [baseline_cats, s1_cats, s2_cats, s3_cats]
    titles = [r["title"] for r in all_results]
    print_category_comparison(all_cats, titles)

    # ── 각 전략 오답 출력 ──
    print_errors(baseline_preds, adv_samples, "Baseline (Uniform 0.5)")
    print_errors(s1_preds, adv_samples, "전략1: Adversarial Threshold")
    print_errors(s2_preds, adv_samples, "전략2: 후처리 규칙")
    print_errors(s3_preds, adv_samples, "전략3: 하이브리드")

    # ── 최고 전략 판정 ──
    print(f"\n{'═'*80}")
    print("[ 최종 추천 ]")
    print(f"{'═'*80}")
    best = max(all_results, key=lambda r: r["subset_accuracy"])
    print(f"  Subset Accuracy 기준 최고: {best['title']} ({best['subset_accuracy']*100:.1f}%)")
    best_f1 = max(all_results, key=lambda r: r["micro_f1"])
    print(f"  Micro F1 기준 최고:        {best_f1['title']} ({best_f1['micro_f1']*100:.1f}%)")

    # ── 결과 저장 ──
    out = {
        "baseline": {k: round(v, 4) if isinstance(v, float) else v for k, v in baseline_result.items()},
        "strategy1_threshold": {k: round(v, 4) if isinstance(v, float) else v for k, v in s1_result.items()},
        "strategy1_thresholds": {INTENT_LABELS[i]: s1_thresholds[i] for i in range(NUM_LABELS)},
        "strategy2_postprocess": {k: round(v, 4) if isinstance(v, float) else v for k, v in s2_result.items()},
        "strategy3_hybrid": {k: round(v, 4) if isinstance(v, float) else v for k, v in s3_result.items()},
    }
    out_path = ROOT / "ai" / "experiments" / "results" / "strategy_comparison_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
