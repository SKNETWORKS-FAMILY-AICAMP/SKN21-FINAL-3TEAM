#!/bin/bash
# RunPod SSH에서 Planner LoRA 학습 실행
#
# 사용법:
#   bash ai/finetuning/runpod_planner_train.sh              # v4 데이터 생성 + 학습 + 평가
#   bash ai/finetuning/runpod_planner_train.sh train         # 학습만
#   bash ai/finetuning/runpod_planner_train.sh eval          # 평가만
#   bash ai/finetuning/runpod_planner_train.sh v3            # v3 (기존) 모드
#
# v4 변경사항:
#   - 데이터 자동 생성 (1500건, complex 28% / no_connector 15% / anti_collapse 6%)
#   - configs/v4_planner.yaml 사용
#   - outputs/v4_planner/ 저장

set -e

MODE=${1:-"all"}
VERSION=${2:-"v4"}

# v3 호환 모드
if [ "${MODE}" = "v3" ]; then
    VERSION="v3"
    MODE="all"
fi

echo "========================================="
echo " Planner LoRA Training (${VERSION})"
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
if [ "${VERSION}" = "v4" ]; then
    # v4: 데이터 생성 후 학습
    if [ "${MODE}" != "eval" ]; then
        echo "[4a/5] Generating v4 training data (1500 cases)..."
        python3 ai/finetuning/scripts/synthesize_planner.py \
            --version v4 \
            --total 1500 \
            --seed 42
        echo ""
    fi

    CONFIG="ai/finetuning/configs/v4_planner.yaml"
    echo "[4b/5] Running planner LoRA training v4 (mode=${MODE})..."
    echo ""
    python3 ai/finetuning/train_v3_planner.py --mode ${MODE} --config ${CONFIG}

    echo ""
    echo "========================================="
    echo " Done! $(date)"
    echo " Output: outputs/v4_planner/"
    echo "========================================="
else
    # v3: 기존 방식 (데이터 생성 없이 바로 학습)
    echo "[4/4] Running planner LoRA training v3 (mode=${MODE})..."
    echo ""
    python3 ai/finetuning/train_v3_planner.py --mode ${MODE}

    echo ""
    echo "========================================="
    echo " Done! $(date)"
    echo " Output: outputs/v3_planner/"
    echo "========================================="
fi
