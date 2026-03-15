#!/bin/bash
# RunPod SSH에서 Planner LoRA 학습 실행
#
# 사용법:
#   bash ai/finetuning/runpod_planner_train.sh              # 학습 + 평가
#   bash ai/finetuning/runpod_planner_train.sh train         # 학습만
#   bash ai/finetuning/runpod_planner_train.sh eval          # 평가만

set -e

MODE=${1:-"all"}

echo "========================================="
echo " Planner LoRA Training (v3)"
echo " Mode: ${MODE}"
echo " Time: $(date)"
echo "========================================="

# ── 1. 패키지 설치 ──────────────────────────────
echo "[1/4] Installing dependencies..."
pip install -q -U \
    torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -q -U \
    transformers \
    peft \
    trl \
    bitsandbytes \
    accelerate \
    datasets \
    sentencepiece \
    protobuf \
    pyyaml

# ── 2. 프로젝트 클론/업데이트 ────────────────────
cd /workspace
if [ ! -d "SKN21-FINAL-3TEAM" ]; then
    echo "[2/4] Cloning repository..."
    git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM.git
    cd SKN21-FINAL-3TEAM
    git checkout FEAT/frontend
else
    echo "[2/4] Repository exists, pulling latest..."
    cd SKN21-FINAL-3TEAM
    git fetch origin && git reset --hard origin/FEAT/frontend
fi

# ── 3. GPU 확인 ──────────────────────────────────
echo "[3/4] GPU check..."
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
python3 -c "import torch; print(f'PyTorch {torch.__version__}, CUDA {torch.version.cuda}, GPU count: {torch.cuda.device_count()}')"
echo ""

# ── 4. 학습 실행 ─────────────────────────────────
echo "[4/4] Running planner LoRA training (mode=${MODE})..."
echo ""

python3 ai/finetuning/train_v3_planner.py --mode ${MODE}

echo ""
echo "========================================="
echo " Done! $(date)"
echo " Output: outputs/v3_planner/"
echo "========================================="
