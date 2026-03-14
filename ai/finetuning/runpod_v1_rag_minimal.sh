#!/bin/bash
# RunPod 경량 실행 — 필요한 파일만 다운로드 (git clone 없이)
#
# 사용법:
#   curl -sL https://raw.githubusercontent.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM/feat/ai-yoon/ai/finetuning/runpod_v1_rag_minimal.sh | bash
#
#   또는 직접:
#   bash runpod_v1_rag_minimal.sh
#   bash runpod_v1_rag_minimal.sh eval   # 평가만

set -e
MODE=${1:-"all"}
BRANCH="feat/ai-yoon"
REPO="SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM"
RAW="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
WORK="/workspace/v1_rag"

echo "============================================"
echo " v1 Judgment RAG 경량 학습 (minimal)"
echo " Mode: ${MODE}"
echo "============================================"

# ── 1. 패키지 설치 (RunPod 기존 torch 유지, torchvision 건드리지 않음) ──
echo "[1/5] Installing dependencies..."
pip install -q --no-deps -U transformers
pip install -q -U \
    peft trl bitsandbytes \
    accelerate datasets pyyaml \
    sentencepiece protobuf

# ── 2. 작업 디렉토리 생성 ──
echo "[2/5] Setting up workspace..."
mkdir -p ${WORK}/ai/finetuning/configs
mkdir -p ${WORK}/data/training/v1_judgment
mkdir -p ${WORK}/outputs/v1_judgment_rag

# ── 3. 필요한 파일만 다운로드 (~30MB) ──
echo "[3/5] Downloading files..."

# 학습 스크립트
curl -sL "${RAW}/ai/finetuning/train_v1_judgment.py" \
    -o ${WORK}/ai/finetuning/train_v1_judgment.py
echo "  ✓ train_v1_judgment.py"

# config
curl -sL "${RAW}/ai/finetuning/configs/v1_judgment_rag.yaml" \
    -o ${WORK}/ai/finetuning/configs/v1_judgment_rag.yaml
echo "  ✓ v1_judgment_rag.yaml"

# 학습 데이터 (가장 큰 파일)
curl -sL "${RAW}/data/training/v1_judgment/train_rag.jsonl" \
    -o ${WORK}/data/training/v1_judgment/train_rag.jsonl
echo "  ✓ train_rag.jsonl ($(du -h ${WORK}/data/training/v1_judgment/train_rag.jsonl | cut -f1))"

# 평가 데이터
curl -sL "${RAW}/data/training/v1_judgment/eval_rag.jsonl" \
    -o ${WORK}/data/training/v1_judgment/eval_rag.jsonl
echo "  ✓ eval_rag.jsonl ($(du -h ${WORK}/data/training/v1_judgment/eval_rag.jsonl | cut -f1))"

# __init__.py (import용)
touch ${WORK}/ai/__init__.py
touch ${WORK}/ai/finetuning/__init__.py

# ── 4. 데이터 검증 ──
echo ""
echo "[4/5] Data check..."
echo "  train_rag: $(wc -l < ${WORK}/data/training/v1_judgment/train_rag.jsonl) lines"
echo "  eval_rag:  $(wc -l < ${WORK}/data/training/v1_judgment/eval_rag.jsonl) lines"

# GPU 확인
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
python -c "import torch; print(f'  PyTorch {torch.__version__}, CUDA {torch.version.cuda}, bf16={torch.cuda.is_bf16_supported()}')"

# ── 5. 학습 실행 ──
echo ""
echo "[5/5] Training start: $(date)"
cd ${WORK}
python ai/finetuning/train_v1_judgment.py \
    --mode "${MODE}" \
    --config ai/finetuning/configs/v1_judgment_rag.yaml

echo ""
echo "============================================"
echo " Done! $(date)"
echo " Adapter: ${WORK}/outputs/v1_judgment_rag/final/"
echo " Results: ${WORK}/outputs/v1_judgment_rag/eval_results.json"
echo "============================================"
echo ""
echo "어댑터 다운로드:"
echo "  scp runpod:${WORK}/outputs/v1_judgment_rag/final/* ./outputs/"
echo ""
echo "또는 HuggingFace에 업로드:"
echo "  cd ${WORK}/outputs/v1_judgment_rag/final"
echo "  huggingface-cli upload your-name/v1-judgment-rag ."
