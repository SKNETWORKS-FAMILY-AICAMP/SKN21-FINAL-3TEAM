#!/bin/bash
# RunPod 원클릭 — v3 judgment 보강 데이터 학습
#
# 사용법:
#   curl -sL https://raw.githubusercontent.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM/feat/ai-yoon/ai/finetuning/runpod_v3_judgment.sh | bash

set -e
MODE=${1:-"all"}
BRANCH="feat/ai-yoon"
REPO="SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM"
RAW="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
WORK="/workspace/v3_judgment"

echo "============================================"
echo " v3 Judgment 보강 학습 (conditional 강화)"
echo " Mode: ${MODE}"
echo "============================================"

# ── 1. 패키지 설치 ──
echo "[1/5] Installing dependencies..."
pip uninstall torchvision torchaudio -y 2>/dev/null || true
pip install -q \
    transformers==4.46.3 bitsandbytes==0.45.0 \
    peft==0.13.2 trl==0.12.2 accelerate==1.1.1 \
    datasets pyyaml sentencepiece protobuf

# ── 2. 작업 디렉토리 생성 ──
echo "[2/5] Setting up workspace..."
mkdir -p ${WORK}/ai/finetuning/configs
mkdir -p ${WORK}/data/training/v1_judgment_v3
mkdir -p ${WORK}/outputs/v3_judgment

# ── 3. 파일 다운로드 ──
echo "[3/5] Downloading files..."

curl -sL "${RAW}/ai/finetuning/train_v1_judgment.py" \
    -o ${WORK}/ai/finetuning/train_v1_judgment.py
echo "  ✓ train_v1_judgment.py"

curl -sL "${RAW}/ai/finetuning/configs/v3_judgment.yaml" \
    -o ${WORK}/ai/finetuning/configs/v3_judgment.yaml
echo "  ✓ v3_judgment.yaml"

curl -sL "${RAW}/data/training/v1_judgment_v3/train.jsonl" \
    -o ${WORK}/data/training/v1_judgment_v3/train.jsonl
echo "  ✓ train.jsonl ($(du -h ${WORK}/data/training/v1_judgment_v3/train.jsonl | cut -f1))"

curl -sL "${RAW}/data/training/v1_judgment_v3/eval.jsonl" \
    -o ${WORK}/data/training/v1_judgment_v3/eval.jsonl
echo "  ✓ eval.jsonl ($(du -h ${WORK}/data/training/v1_judgment_v3/eval.jsonl | cut -f1))"

mkdir -p ${WORK}/ai/finetuning
touch ${WORK}/ai/__init__.py
touch ${WORK}/ai/finetuning/__init__.py

# ── 4. save_strategy 패치 (disk quota 방지) ──
echo "[4/5] Patching save_strategy..."
sed -i 's/save_strategy="steps"/save_strategy="no"/g' ${WORK}/ai/finetuning/train_v1_judgment.py 2>/dev/null || true
sed -i 's/save_steps=cfg_save_steps/save_steps=0/g' ${WORK}/ai/finetuning/train_v1_judgment.py 2>/dev/null || true

# HF 캐시 정리
rm -rf /root/.cache/huggingface/hub/models--* 2>/dev/null || true

# ── 5. 학습 + 평가 실행 ──
echo "[5/5] Starting training..."
cd ${WORK}

if [ "${MODE}" = "eval" ]; then
    python -m ai.finetuning.train_v1_judgment \
        --mode eval \
        --config ai/finetuning/configs/v3_judgment.yaml \
        --adapter_path outputs/v3_judgment/final
else
    nohup python -m ai.finetuning.train_v1_judgment \
        --mode all \
        --config ai/finetuning/configs/v3_judgment.yaml \
        > /workspace/train_v3_log.txt 2>&1 &
    echo ""
    echo "============================================"
    echo " 학습이 백그라운드에서 시작되었습니다!"
    echo " 로그: tail -f /workspace/train_v3_log.txt"
    echo " 예상 소요: ~2시간 (A100 기준)"
    echo "============================================"
fi
