#!/bin/bash
# ============================================================
# LoRA v1 파인튜닝 실행 스크립트 (RunPod A100 40GB)
#
# 사용법:
#   1. RunPod에서 A100 40GB Pod 생성
#   2. 이 repo를 clone
#   3. bash scripts/run_finetune_v1.sh
#
# 예상 시간: ~30-40분 (A100 40GB 기준)
# 예상 비용: ~$1-2 (RunPod A100 시간당 $1.64)
# ============================================================

set -e

echo "============================================"
echo "  LoRA v1: 판단 특화 파인튜닝 시작"
echo "  모델: kakaocorp/kanana-1.5-8b-instruct-2505"
echo "  데이터: 1,500건 (판단 1,000 + Q&A 500)"
echo "============================================"

# 1. 패키지 설치
echo ""
echo "[1/5] 패키지 설치 중..."
pip install -q transformers peft trl bitsandbytes accelerate datasets torch pyyaml

# 2. GPU 확인
echo ""
echo "[2/5] GPU 확인..."
python -c "
import torch
print(f'  CUDA: {torch.cuda.is_available()}')
print(f'  GPU: {torch.cuda.get_device_name(0)}')
print(f'  VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB')
"

# 3. 데이터 확인
echo ""
echo "[3/5] 데이터 확인..."
python -c "
import json
train_count = sum(1 for _ in open('data/training/v1_judgment/train.jsonl', encoding='utf-8'))
eval_count = sum(1 for _ in open('data/training/v1_judgment/eval.jsonl', encoding='utf-8'))
print(f'  Train: {train_count}건')
print(f'  Eval:  {eval_count}건')
print(f'  Total: {train_count + eval_count}건')
"

# 4. 학습 실행
echo ""
echo "[4/5] 학습 시작... (약 30-40분 소요)"
python ai/finetuning/train_v1_judgment.py --mode train

# 5. 평가 실행
echo ""
echo "[5/5] 평가 시작..."
python ai/finetuning/train_v1_judgment.py --mode eval --adapter_path outputs/v1_judgment/final

echo ""
echo "============================================"
echo "  완료!"
echo "  어댑터 위치: outputs/v1_judgment/final/"
echo "  평가 결과: outputs/v1_judgment/eval_results.json"
echo "============================================"
