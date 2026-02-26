"""
버전별 Intent Classification 학습 + 평가 + 결과 저장 파이프라인

사용법:
    # v1.2 학습 (augment 데이터 포함)
    python ai/experiments/run_train_versioned.py --version v1.2

    # v1.3 학습
    python ai/experiments/run_train_versioned.py --version v1.3

    # v1.4 하이퍼파라미터 그리드 서치
    python ai/experiments/run_train_versioned.py --version v1.4 --grid-search

실행 환경: RunPod GPU
사전: pip install transformers datasets accelerate matplotlib seaborn scikit-learn
"""

import argparse
import json
import random
import shutil
import torch
import numpy as np
from pathlib import Path
from collections import Counter
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
from sklearn.metrics import (
    accuracy_score, f1_score, classification_report, confusion_matrix,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "intent"
MODEL_BASE = BASE_DIR / "ai" / "models"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

MODEL_NAME = "klue/bert-base"
INTENT_LABELS = [
    "judgment", "doc_search", "doc_generate",
    "meeting_generate", "schedule_add", "schedule_view", "general",
]
LABEL2ID = {label: i for i, label in enumerate(INTENT_LABELS)}
ID2LABEL = {i: label for i, label in enumerate(INTENT_LABELS)}

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

SEED = 42

def set_seed(seed=SEED):
    """재현성을 위한 시드 고정"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ── 데이터 로드 ──

def load_jsonl(path):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def load_all_category_data():
    """카테고리별 JSONL 파일 로드 (원본)"""
    all_data = []
    for label in INTENT_LABELS:
        path = DATA_DIR / f"{label}.jsonl"
        if path.exists():
            items = load_jsonl(path)
            all_data.extend(items)
    return all_data


def load_augment_data(version):
    """버전별 augment 데이터 로드"""
    aug_data = []
    pattern = f"augment_{version}_*.jsonl"
    for path in sorted(DATA_DIR.glob(pattern)):
        items = load_jsonl(path)
        aug_data.extend(items)
        print(f"    {path.name}: {len(items)}개")
    return aug_data


def build_dataset(version):
    """버전에 따라 학습 데이터 구성"""
    # 기본 데이터 (v1.1 기준: 원본 카테고리 파일들)
    base_data = load_all_category_data()
    print(f"  Base data: {len(base_data)}개")

    # 버전별 augment 누적 적용
    all_aug = []
    versions_to_load = []
    if version >= "v1.2":
        versions_to_load.append("v12")
    if version >= "v1.3":
        versions_to_load.append("v13")

    for v in versions_to_load:
        aug = load_augment_data(v)
        all_aug.extend(aug)
        print(f"  Augment {v}: +{len(aug)}개")

    combined = base_data + all_aug
    print(f"  Total: {len(combined)}개")

    # 카테고리별 분포
    dist = Counter(d["label"] for d in combined)
    for label in INTENT_LABELS:
        print(f"    {label}: {dist.get(label, 0)}")

    return combined


def split_train_eval(data, eval_ratio=0.15, seed=42):
    """카테고리별 층화 분할"""
    random.seed(seed)
    by_label = {}
    for item in data:
        by_label.setdefault(item["label"], []).append(item)

    train, eval_ = [], []
    for label, items in by_label.items():
        random.shuffle(items)
        n_eval = max(1, int(len(items) * eval_ratio))
        eval_.extend(items[:n_eval])
        train.extend(items[n_eval:])

    random.shuffle(train)
    random.shuffle(eval_)
    return train, eval_


# ── 학습 ──

def tokenize(examples, tokenizer, max_length=64):
    return tokenizer(
        examples["text"], padding="max_length", truncation=True, max_length=max_length,
    )


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
        "f1_weighted": f1_score(labels, preds, average="weighted"),
    }


def train_model(train_data, eval_data, output_dir, epochs=5, lr=2e-5, batch_size=16, max_length=64):
    """모델 학습"""
    train_ds = Dataset.from_list(
        [{"text": d["text"], "label": LABEL2ID[d["label"]]} for d in train_data]
    )
    eval_ds = Dataset.from_list(
        [{"text": d["text"], "label": LABEL2ID[d["label"]]} for d in eval_data]
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=len(INTENT_LABELS), id2label=ID2LABEL, label2id=LABEL2ID,
    )

    train_tok = train_ds.map(lambda x: tokenize(x, tokenizer, max_length), batched=True)
    eval_tok = eval_ds.map(lambda x: tokenize(x, tokenizer, max_length), batched=True)

    args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=lr,
        weight_decay=0.01,
        seed=SEED,
        data_seed=SEED,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        logging_steps=50,
        save_total_limit=2,
        report_to="none",
    )

    trainer = Trainer(
        model=model, args=args,
        train_dataset=train_tok, eval_dataset=eval_tok,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    results = trainer.evaluate()

    # 상세 리포트
    predictions = trainer.predict(eval_tok)
    preds = np.argmax(predictions.predictions, axis=-1)
    report = classification_report(
        predictions.label_ids, preds, target_names=INTENT_LABELS, digits=4,
    )

    # 저장
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    label_map = {"id2label": ID2LABEL, "label2id": LABEL2ID}
    with open(output_dir / "label_map.json", "w", encoding="utf-8") as f:
        json.dump(label_map, f, ensure_ascii=False, indent=2)

    return results, report, tokenizer, trainer.model


# ── 평가 ──

def predict_all(texts, tokenizer, model):
    """배치 추론"""
    model.eval()
    model.to(device)
    preds = []
    confs = []
    for text in texts:
        inputs = tokenizer(
            text, return_tensors="pt", padding=True, truncation=True, max_length=64,
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)[0]
        pred_id = torch.argmax(probs).item()
        preds.append(ID2LABEL[pred_id])
        confs.append(probs[pred_id].item())
    return preds, confs


def evaluate_adversarial(tokenizer, model, version):
    """adversarial 테스트"""
    adv_path = DATA_DIR / "adversarial_test.json"
    with open(adv_path, "r", encoding="utf-8") as f:
        adv_data = json.load(f)

    texts = [d["text"] for d in adv_data]
    labels = [d["label"] for d in adv_data]
    preds, confs = predict_all(texts, tokenizer, model)

    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, average="macro", labels=INTENT_LABELS, zero_division=0)

    # 오분류 목록
    wrong = []
    for i, (text, label, pred, conf) in enumerate(zip(texts, labels, preds, confs)):
        if label != pred:
            wrong.append({"text": text, "expected": label, "predicted": pred, "confidence": round(conf, 3)})

    # 혼동행렬
    cm = confusion_matrix(labels, preds, labels=INTENT_LABELS)
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=INTENT_LABELS, yticklabels=INTENT_LABELS)
    plt.title(f"Confusion Matrix — {version} Adversarial ({len(adv_data)} samples)")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / f"confusion_adv_{version}.png", dpi=150)
    plt.close()

    return {
        "version": version,
        "adversarial_count": len(adv_data),
        "accuracy": round(acc, 4),
        "f1_macro": round(f1, 4),
        "errors": len(wrong),
        "error_details": wrong,
    }


# ── 그리드 서치 (v1.4) ──

def grid_search(train_data, eval_data, version):
    """하이퍼파라미터 그리드 서치"""
    grid = [
        {"epochs": 3, "lr": 2e-5},
        {"epochs": 5, "lr": 1e-5},
        {"epochs": 5, "lr": 2e-5},
        {"epochs": 5, "lr": 5e-5},
        {"epochs": 7, "lr": 2e-5},
        {"epochs": 10, "lr": 2e-5},
    ]

    best_f1 = 0
    best_config = None
    all_results = []

    for i, cfg in enumerate(grid):
        print(f"\n  --- Grid {i+1}/{len(grid)}: epochs={cfg['epochs']}, lr={cfg['lr']} ---")
        output_dir = MODEL_BASE / f"intent_{version}_grid_{i}"
        output_dir.mkdir(parents=True, exist_ok=True)

        results, report, tok, model = train_model(
            train_data, eval_data, output_dir,
            epochs=cfg["epochs"], lr=cfg["lr"],
        )

        f1 = results["eval_f1_macro"]
        all_results.append({
            "config": cfg,
            "eval_f1": round(f1, 4),
            "eval_acc": round(results["eval_accuracy"], 4),
        })
        print(f"  F1={f1:.4f}")

        if f1 > best_f1:
            best_f1 = f1
            best_config = cfg
            best_tok = tok
            best_model = model
            best_report = report
            best_results = results

        # cleanup
        if output_dir.exists():
            shutil.rmtree(output_dir)

    print(f"\n  Best: epochs={best_config['epochs']}, lr={best_config['lr']}, F1={best_f1:.4f}")

    # 최종 모델 저장
    final_dir = MODEL_BASE / "intent_classifier"
    best_tok.save_pretrained(str(final_dir))
    best_model.save_pretrained(str(final_dir))
    label_map = {"id2label": ID2LABEL, "label2id": LABEL2ID}
    with open(final_dir / "label_map.json", "w", encoding="utf-8") as f:
        json.dump(label_map, f, ensure_ascii=False, indent=2)

    # 그리드 결과 저장
    with open(RESULTS_DIR / f"grid_search_{version}.json", "w", encoding="utf-8") as f:
        json.dump({"grid_results": all_results, "best_config": best_config}, f,
                  ensure_ascii=False, indent=2)

    return best_results, best_report, best_tok, best_model, all_results


# ── 메인 ──

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="모델 버전 (v1.2, v1.3, v1.4)")
    parser.add_argument("--grid-search", action="store_true", help="v1.4 그리드 서치")
    args = parser.parse_args()

    version = args.version
    set_seed(SEED)
    print("=" * 60)
    print(f"  Intent Classification {version} 학습")
    print(f"  Device: {device}")
    print(f"  Seed: {SEED}")
    print("=" * 60)

    # 1. 데이터 구성
    print("\n[1/4] 데이터 구성...")
    combined = build_dataset(version)
    train_data, eval_data = split_train_eval(combined)
    print(f"\n  Train: {len(train_data)}개, Eval: {len(eval_data)}개")

    # 2. 학습
    model_dir = MODEL_BASE / "intent_classifier"
    model_dir.mkdir(parents=True, exist_ok=True)

    if args.grid_search:
        print(f"\n[2/4] 그리드 서치 ({version})...")
        results, report, tokenizer, model, grid_results = grid_search(
            train_data, eval_data, version,
        )
        print("\n  Grid 결과:")
        for gr in grid_results:
            print(f"    epochs={gr['config']['epochs']}, lr={gr['config']['lr']}"
                  f" → F1={gr['eval_f1']}")
    else:
        print(f"\n[2/4] 학습 ({version})...")
        results, report, tokenizer, model = train_model(
            train_data, eval_data, model_dir,
        )

    print("\n[3/4] Eval 결과:")
    print(f"  Accuracy:    {results['eval_accuracy']:.4f}")
    print(f"  F1 (macro):  {results['eval_f1_macro']:.4f}")
    print(f"  F1 (weighted): {results['eval_f1_weighted']:.4f}")
    print(f"\n{report}")

    # 3. Adversarial 평가
    print("\n[4/4] Adversarial 평가...")
    adv_result = evaluate_adversarial(tokenizer, model, version)
    print(f"  Adversarial F1: {adv_result['f1_macro']}")
    print(f"  Adversarial Acc: {adv_result['accuracy']}")
    print(f"  오분류: {adv_result['errors']}건")

    if adv_result["error_details"]:
        print("\n  오분류 상세:")
        for e in adv_result["error_details"]:
            print(f"    \"{e['text']}\" → 예상:{e['expected']} 실제:{e['predicted']} ({e['confidence']})")

    # 4. 결과 저장
    version_result = {
        "version": version,
        "train_count": len(train_data),
        "eval_count": len(eval_data),
        "eval_accuracy": round(results["eval_accuracy"], 4),
        "eval_f1_macro": round(results["eval_f1_macro"], 4),
        "eval_f1_weighted": round(results["eval_f1_weighted"], 4),
        "adversarial": adv_result,
    }

    result_path = RESULTS_DIR / f"version_{version}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(version_result, f, ensure_ascii=False, indent=2)
    print(f"\n  -> {result_path.name}")
    print(f"  -> confusion_adv_{version}.png")

    print(f"\n{'=' * 60}")
    print(f"  {version} 완료!")
    print(f"  Eval F1: {results['eval_f1_macro']:.4f}")
    print(f"  Adversarial F1: {adv_result['f1_macro']}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
