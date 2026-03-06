#!/bin/bash
# RunPod H100 환경 세팅 + 학습 실행 스크립트
# 사용법: bash runpod_setup.sh <task> [model_index]
#   task: generate | qa | summary
#   model_index: 0=Qwen3-8B, 1=EXAONE, 2=Kanana (기본: 전체 3개 순차)
#
# 예시:
#   GPU 1: bash runpod_setup.sh generate
#   GPU 2: bash runpod_setup.sh qa
#   GPU 3: bash runpod_setup.sh summary

set -e

TASK=${1:?'Usage: bash runpod_setup.sh <generate|qa|summary> [model_index]'}
MODEL_INDEX=${2:-"all"}

echo "========================================="
echo " RunPod H100 Fine-tuning Setup"
echo " Task: ${TASK}"
echo " Model: ${MODEL_INDEX}"
echo "========================================="

# 1. 패키지 설치
echo "[1/4] Installing dependencies..."
pip install -q \
    transformers>=4.46.0 \
    peft>=0.13.0 \
    trl>=0.12.0 \
    bitsandbytes>=0.44.0 \
    accelerate>=1.0.0 \
    datasets>=3.0.0 \
    torch \
    pyyaml \
    rouge-score \
    bert-score \
    sentencepiece \
    protobuf

# 2. 프로젝트 루트로 이동
cd /workspace
if [ ! -d "SKN21-FINAL-3TEAM" ]; then
    echo "[2/4] Cloning repository..."
    git clone https://github.com/sjy361872/SKN21-FINAL-3TEAM.git
    cd SKN21-FINAL-3TEAM
    git checkout feat/jiyong
else
    echo "[2/4] Repository exists, pulling latest..."
    cd SKN21-FINAL-3TEAM
    git checkout feat/jiyong
    git pull origin feat/jiyong
fi

# 3. GPU 확인
echo "[3/4] GPU check..."
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo ""

# 4. 학습 실행
echo "[4/4] Starting training..."
echo "Task: ${TASK}"
echo "Start time: $(date)"
echo ""

MODELS=("Qwen/Qwen3-8B" "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct" "kakaocorp/kanana-1.5-8b-instruct-2505")
MODEL_NAMES=("Qwen3-8B" "EXAONE-3.5-7.8B" "Kanana-1.5-8B")

if [ "$MODEL_INDEX" = "all" ]; then
    # 3개 모델 순차 학습 (compare 모드)
    for i in 0 1 2; do
        echo ""
        echo "===== [${MODEL_NAMES[$i]}] Training start: $(date) ====="
        python ai/finetuning/train_v2_document.py \
            --task "$TASK" \
            --mode all \
            --base_model "${MODELS[$i]}"
        echo "===== [${MODEL_NAMES[$i]}] Training done: $(date) ====="
    done
else
    # 특정 모델만
    echo "===== [${MODEL_NAMES[$MODEL_INDEX]}] Training start: $(date) ====="
    python ai/finetuning/train_v2_document.py \
        --task "$TASK" \
        --mode all \
        --base_model "${MODELS[$MODEL_INDEX]}"
    echo "===== [${MODEL_NAMES[$MODEL_INDEX]}] Training done: $(date) ====="
fi

echo ""
echo "========================================="
echo " All done! $(date)"
echo "========================================="
echo " Results in: outputs/v2_${TASK}/"
echo "========================================="
