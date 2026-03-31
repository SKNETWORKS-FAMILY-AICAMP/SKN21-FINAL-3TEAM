#!/bin/bash
# RunPod에서 Planner LoRA held-out 평가 실행
#
# 사용법:
#   bash ai/finetuning/runpod_planner_holdout.sh                        # v4 LoRA 모델 평가 (기본)
#   bash ai/finetuning/runpod_planner_holdout.sh --adapter outputs/v3_planner/final  # v3 평가
#   bash ai/finetuning/runpod_planner_holdout.sh --base-only            # base 모델만 평가

set -e

echo "========================================="
echo " Planner LoRA Held-out Evaluation"
echo " Time: $(date)"
echo "========================================="

# ── 1. 패키지 설치 ──
echo "[1/3] Installing dependencies..."
pip install -q -U \
    torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -q -U \
    transformers peft bitsandbytes accelerate sentencepiece protobuf

# ── 2. 프로젝트 업데이트 ──
cd /workspace
if [ ! -d "SKN21-FINAL-3TEAM" ]; then
    echo "[2/3] Cloning repository..."
    git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM.git
    cd SKN21-FINAL-3TEAM
    git checkout FEAT/frontend
else
    echo "[2/3] Repository exists, pulling latest..."
    cd SKN21-FINAL-3TEAM
    git fetch origin && git reset --hard origin/FEAT/frontend
fi

# ── 3. GPU 확인 ──
echo "[3/3] GPU check..."
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
echo ""

# ── 4. 평가 실행 ──
echo "Running held-out evaluation..."
echo ""

# 기본값: v4 어댑터 사용 (명시적으로 다른 경로 지정 시 그 경로 사용)
if [ "$#" -eq 0 ]; then
    python3 ai/finetuning/scripts/eval_planner_holdout.py --adapter outputs/v4_planner/final
else
    python3 ai/finetuning/scripts/eval_planner_holdout.py "$@"
fi

echo ""
echo "========================================="
echo " Done! $(date)"
echo "========================================="
