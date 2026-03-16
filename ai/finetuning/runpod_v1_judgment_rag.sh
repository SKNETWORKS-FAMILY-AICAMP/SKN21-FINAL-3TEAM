#!/bin/bash
# RunPod v1 Judgment RAG 학습 + 평가 스크립트
#
# 사용법:
#   1. RunPod에서 A100 40GB 인스턴스 실행
#   2. 터미널에서:
#      export HF_TOKEN=hf_xxxxx
#      bash ai/finetuning/runpod_v1_judgment_rag.sh
#
#   평가만 실행:
#      bash ai/finetuning/runpod_v1_judgment_rag.sh eval

set -e

MODE=${1:-"all"}  # all | train | eval

echo "============================================"
echo " v1 Judgment RAG 학습"
echo " Mode: ${MODE}"
echo " Start: $(date)"
echo "============================================"

# ── 1. 패키지 설치 ──
echo "[1/4] Installing dependencies..."
pip install -q -U \
    transformers \
    peft \
    trl \
    bitsandbytes \
    accelerate \
    datasets \
    torch \
    pyyaml \
    sentencepiece \
    protobuf

# ── 2. 레포 클론/업데이트 ──
cd /workspace
if [ ! -d "SKN21-FINAL-3TEAM" ]; then
    echo "[2/4] Cloning repository..."
    git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM.git
    cd SKN21-FINAL-3TEAM
else
    echo "[2/4] Repository exists, pulling latest..."
    cd SKN21-FINAL-3TEAM
    git pull || true
fi

# 브랜치 (본인 브랜치로 변경)
git checkout feat/ai-경은 2>/dev/null || git checkout develop 2>/dev/null || git checkout main

# ── 3. GPU 확인 ──
echo "[3/4] GPU check..."
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
python -c "import torch; print(f'PyTorch {torch.__version__}, CUDA {torch.version.cuda}, bf16={torch.cuda.is_bf16_supported()}')"
echo ""

# ── 4. 데이터 확인 ──
echo "Data check..."
echo "  train_rag.jsonl: $(wc -l < data/training/v1_judgment/train_rag.jsonl) lines ($(du -h data/training/v1_judgment/train_rag.jsonl | cut -f1))"
echo "  eval_rag.jsonl:  $(wc -l < data/training/v1_judgment/eval_rag.jsonl) lines ($(du -h data/training/v1_judgment/eval_rag.jsonl | cut -f1))"
echo ""

# ── 5. 학습/평가 실행 ──
echo "[4/4] Running train_v1_judgment.py --mode ${MODE} --config v1_judgment_rag.yaml"
echo "Start time: $(date)"
echo ""

python ai/finetuning/train_v1_judgment.py \
    --mode "${MODE}" \
    --config ai/finetuning/configs/v1_judgment_rag.yaml

echo ""
echo "============================================"
echo " Done! $(date)"
echo " Results: outputs/v1_judgment_rag/"
echo "============================================"
echo ""
echo "다음 단계:"
echo "  1. outputs/v1_judgment_rag/eval_results.json 확인"
echo "  2. 어댑터: outputs/v1_judgment_rag/final/"
echo "  3. vLLM 서빙 시: --lora-modules v1_rag=outputs/v1_judgment_rag/final"
