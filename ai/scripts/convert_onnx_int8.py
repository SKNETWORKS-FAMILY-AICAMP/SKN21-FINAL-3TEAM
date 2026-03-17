"""
Intent 앙상블 모델 → ONNX + INT8 양자화 변환 스크립트

Usage:
    python -m ai.scripts.convert_onnx_int8

1) HuggingFace에서 5-seed 모델 다운로드
2) 각 seed를 ONNX로 변환
3) INT8 dynamic quantization 적용
4) 결과: ai/models/intent_ensemble_onnx/seed_{N}/model_int8.onnx
"""

import os
import json
import shutil
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from huggingface_hub import hf_hub_download, list_repo_tree
import onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType

HF_REPO = "jiyouxg/dudu-intent-ensemble"
HF_TOKEN = os.getenv("HUGGINGFACE_API_KEY", "")
SEEDS = [42, 123, 456, 789, 1337]
OUTPUT_DIR = Path("ai/models/intent_ensemble_onnx")


def download_seed(seed: int, cache_dir: Path) -> Path:
    """HuggingFace에서 단일 seed 모델 다운로드"""
    seed_dir = cache_dir / f"seed_{seed}"
    seed_dir.mkdir(parents=True, exist_ok=True)

    files = ["config.json", "model.safetensors", "tokenizer.json",
             "tokenizer_config.json", "model_info.json"]

    for fname in files:
        remote_path = f"seed_{seed}/{fname}"
        try:
            downloaded = hf_hub_download(
                repo_id=HF_REPO,
                filename=remote_path,
                token=HF_TOKEN,
                local_dir=cache_dir,
            )
            print(f"  ✓ {remote_path}")
        except Exception as e:
            if "model_info" in fname:
                continue  # optional file
            print(f"  ✗ {remote_path}: {e}")
            raise

    return seed_dir


def get_tokenizer(seed_dir: Path):
    """토크나이저 로드 (tokenizer_config 오류 우회)"""
    try:
        return AutoTokenizer.from_pretrained(str(seed_dir))
    except ValueError:
        # tokenizer_class가 잘못 저장된 경우 base 모델에서 로드
        return AutoTokenizer.from_pretrained("klue/roberta-large")


def convert_to_onnx(seed_dir: Path, onnx_path: Path):
    """PyTorch → ONNX 변환"""
    tokenizer = get_tokenizer(seed_dir)
    model = AutoModelForSequenceClassification.from_pretrained(str(seed_dir))
    model.eval()

    dummy_input = tokenizer(
        "테스트 입력입니다",
        return_tensors="pt",
        max_length=128,
        padding="max_length",
        truncation=True,
    )

    torch.onnx.export(
        model,
        (dummy_input["input_ids"], dummy_input["attention_mask"]),
        str(onnx_path),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "seq"},
            "attention_mask": {0: "batch", 1: "seq"},
            "logits": {0: "batch"},
        },
        opset_version=14,
        dynamo=False,
    )
    print(f"  ✓ ONNX 변환 완료: {onnx_path}")


def quantize_int8(onnx_path: Path, quant_path: Path):
    """ONNX → INT8 dynamic quantization"""
    quantize_dynamic(
        model_input=str(onnx_path),
        model_output=str(quant_path),
        weight_type=QuantType.QInt8,
    )
    print(f"  ✓ INT8 양자화 완료: {quant_path}")


def verify_model(quant_path: Path, tokenizer_dir: Path):
    """변환된 모델 검증"""
    tokenizer = get_tokenizer(tokenizer_dir)
    session = ort.InferenceSession(str(quant_path), providers=["CPUExecutionProvider"])

    inputs = tokenizer(
        "휴가 규정 찾아서 위반인지 판단해줘",
        return_tensors="np",
        max_length=128,
        padding="max_length",
        truncation=True,
    )

    outputs = session.run(None, {
        "input_ids": inputs["input_ids"],
        "attention_mask": inputs["attention_mask"],
    })

    import numpy as np
    probs = 1 / (1 + np.exp(-outputs[0][0]))  # sigmoid
    return probs


def main():
    cache_dir = Path("ai/models/_hf_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ensemble_meta 복사
    meta_path = cache_dir / "ensemble_meta.json"
    try:
        hf_hub_download(
            repo_id=HF_REPO, filename="ensemble_meta.json",
            token=HF_TOKEN, local_dir=cache_dir,
        )
    except Exception:
        pass

    # config.json에서 label 정보 추출 (첫 seed에서)
    label_info = None

    for seed in SEEDS:
        print(f"\n{'='*50}")
        print(f"[Seed {seed}] 처리 시작")
        print(f"{'='*50}")

        seed_out = OUTPUT_DIR / f"seed_{seed}"
        seed_out.mkdir(parents=True, exist_ok=True)

        # 1. 다운로드
        print("[1/3] HuggingFace 다운로드...")
        seed_dir = download_seed(seed, cache_dir)

        # label 정보 저장
        if label_info is None:
            config_path = seed_dir / "config.json"
            if config_path.exists():
                with open(config_path) as f:
                    cfg = json.load(f)
                label_info = {
                    "id2label": cfg.get("id2label", {}),
                    "label2id": cfg.get("label2id", {}),
                }

        # 2. ONNX 변환
        print("[2/3] ONNX 변환...")
        onnx_fp32 = seed_out / "model.onnx"
        convert_to_onnx(seed_dir, onnx_fp32)

        # 3. INT8 양자화
        print("[3/3] INT8 양자화...")
        onnx_int8 = seed_out / "model_int8.onnx"
        quantize_int8(onnx_fp32, onnx_int8)

        # FP32 ONNX 삭제 (INT8만 유지)
        onnx_fp32.unlink()

        # tokenizer 복사
        for f in ["tokenizer.json", "tokenizer_config.json", "config.json"]:
            src = seed_dir / f
            if src.exists():
                shutil.copy2(src, seed_out / f)

        # 크기 비교
        original_size = sum(
            f.stat().st_size for f in seed_dir.iterdir()
            if f.suffix == ".safetensors"
        )
        int8_size = onnx_int8.stat().st_size
        print(f"  원본: {original_size/1024/1024:.0f}MB → INT8: {int8_size/1024/1024:.0f}MB "
              f"({int8_size/original_size*100:.1f}%)")

        # 검증
        print("  검증 중...")
        probs = verify_model(onnx_int8, seed_dir)
        labels = label_info["id2label"] if label_info else {}
        top_labels = sorted(
            enumerate(probs), key=lambda x: x[1], reverse=True
        )[:3]
        for idx, prob in top_labels:
            name = labels.get(str(idx), f"label_{idx}")
            print(f"    {name}: {prob:.3f}")

    # 메타 정보 저장
    meta = {
        "model": "klue/roberta-large",
        "format": "onnx_int8",
        "seeds": SEEDS,
        "id2label": label_info["id2label"] if label_info else {},
        "label2id": label_info["label2id"] if label_info else {},
    }
    with open(OUTPUT_DIR / "ensemble_meta.json", "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # 최종 요약
    print(f"\n{'='*50}")
    print("변환 완료!")
    print(f"{'='*50}")
    total_size = sum(
        f.stat().st_size
        for f in OUTPUT_DIR.rglob("*.onnx")
    )
    print(f"총 크기: {total_size/1024/1024:.0f}MB (5 seeds)")
    print(f"출력: {OUTPUT_DIR}")

    # 캐시 정리
    print("\nHF 캐시 정리 중...")
    shutil.rmtree(cache_dir, ignore_errors=True)
    print("완료!")


if __name__ == "__main__":
    main()
