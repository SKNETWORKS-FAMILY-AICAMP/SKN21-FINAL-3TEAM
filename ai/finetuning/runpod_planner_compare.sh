#!/bin/bash
# RunPod SSH에서 Planner 베이스 모델 비교
#
# 사용법:
#   bash ai/finetuning/runpod_planner_compare.sh              # Qwen + Kanana 비교
#   bash ai/finetuning/runpod_planner_compare.sh all           # 3개 모델 전부
#   bash ai/finetuning/runpod_planner_compare.sh qwen          # Qwen만
#   bash ai/finetuning/runpod_planner_compare.sh kanana        # Kanana만

set -e

TARGET=${1:-"default"}

echo "========================================="
echo " Planner Base Model Comparison"
echo " Target: ${TARGET}"
echo " Time: $(date)"
echo "========================================="

# ── 1. 패키지 설치 ──────────────────────────────

echo "[1/4] Installing dependencies..."
pip install -q -U \
    torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -q -U \
    transformers \
    peft \
    bitsandbytes \
    accelerate \
    sentencepiece \
    protobuf \
    openai

# ── 2. 프로젝트 클론/업데이트 ────────────────────

cd /workspace
if [ ! -d "SKN21-FINAL-3TEAM" ]; then
    echo "[2/4] Cloning repository..."
    git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM.git
    cd SKN21-FINAL-3TEAM
    git checkout develop
else
    echo "[2/4] Repository exists, pulling latest..."
    cd SKN21-FINAL-3TEAM
    git pull --rebase origin develop || true
fi

# ── 3. GPU 확인 ──────────────────────────────────

echo "[3/4] GPU check..."
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
python3 -c "import torch; print(f'PyTorch {torch.__version__}, CUDA {torch.version.cuda}, GPU count: {torch.cuda.device_count()}')"
echo ""

# ── 4. 비교 실행 ─────────────────────────────────

echo "[4/4] Running comparison..."
echo ""

case "$TARGET" in
    all)
        python3 ai/finetuning/scripts/compare_planner_models.py \
            --models qwen kanana exaone
        ;;
    qwen)
        python3 ai/finetuning/scripts/compare_planner_models.py \
            --models qwen
        ;;
    kanana)
        python3 ai/finetuning/scripts/compare_planner_models.py \
            --models kanana
        ;;
    exaone)
        python3 ai/finetuning/scripts/compare_planner_models.py \
            --models exaone
        ;;
    *)
        # 기본: Qwen + Kanana
        python3 ai/finetuning/scripts/compare_planner_models.py \
            --models qwen kanana
        ;;
esac

echo ""
echo "========================================="
echo " Done! $(date)"
echo " Results: outputs/planner_comparison/"
echo "========================================="
