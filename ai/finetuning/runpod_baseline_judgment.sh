#!/bin/bash
# RunPod 원클릭 — 베이스라인 평가 (파인튜닝 전 베이스 모델)
#
# 사용법:
#   curl -sL https://raw.githubusercontent.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM/feat/ai-yoon/ai/finetuning/runpod_baseline_judgment.sh | bash

set -e
BRANCH="feat/ai-yoon"
REPO="SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM"
RAW="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
WORK="/workspace/baseline_judgment"

echo "============================================"
echo " Judgment 베이스라인 평가 (LoRA 없이)"
echo " 모델: kanana-1.5-8b-instruct-2505"
echo " 데이터: eval.jsonl (328건)"
echo "============================================"

# ── 1. 패키지 설치 ──
echo "[1/4] Installing dependencies..."
pip uninstall torchvision torchaudio -y 2>/dev/null || true
pip install -q \
    transformers==4.46.3 bitsandbytes==0.45.0 \
    accelerate==1.1.1 datasets pyyaml sentencepiece protobuf torch

# ── 2. 작업 디렉토리 생성 ──
echo "[2/4] Setting up workspace..."
mkdir -p ${WORK}/ai/finetuning
mkdir -p ${WORK}/data/training/v1_judgment
mkdir -p ${WORK}/outputs/v1_judgment

touch ${WORK}/ai/__init__.py
touch ${WORK}/ai/finetuning/__init__.py

# ── 3. 파일 다운로드 ──
echo "[3/4] Downloading files..."

curl -sL "${RAW}/ai/finetuning/eval_baseline.py" \
    -o ${WORK}/ai/finetuning/eval_baseline.py
echo "  ✓ eval_baseline.py"

curl -sL "${RAW}/data/training/v1_judgment/eval.jsonl" \
    -o ${WORK}/data/training/v1_judgment/eval.jsonl
echo "  ✓ eval.jsonl ($(du -h ${WORK}/data/training/v1_judgment/eval.jsonl | cut -f1))"

# HF 캐시 정리
rm -rf /root/.cache/huggingface/hub/models--* 2>/dev/null || true

# ── 4. 베이스라인 평가 실행 ──
echo "[4/4] Starting baseline evaluation..."
cd ${WORK}

python -m ai.finetuning.eval_baseline --device cuda 2>&1 | tee /workspace/baseline_eval_log.txt

echo ""
echo "============================================"
echo " 베이스라인 평가 완료!"
echo " 결과: ${WORK}/outputs/v1_judgment/eval_baseline_results.json"
echo " 로그: /workspace/baseline_eval_log.txt"
echo "============================================"

# 결과 출력
cat ${WORK}/outputs/v1_judgment/eval_baseline_results.json
