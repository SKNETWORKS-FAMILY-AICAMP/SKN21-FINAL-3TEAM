#!/bin/bash
# RunPod Planner v7 — Rule Guide 타겟 보강 학습 + 평가
#
# v7 변경: Rule 의존 패턴 90건 보강 (GPT 불필요, 확정 라벨 직접 생성)
#
# 사용법:
#   bash ai/finetuning/runpod_planner_v7.sh              # 전체 (학습 + 평가)
#   bash ai/finetuning/runpod_planner_v7.sh train-only    # 학습만
#   bash ai/finetuning/runpod_planner_v7.sh eval-only     # 평가만 (기존 어댑터 사용)
#
# 필요: GPU A100 40GB 권장

set -e

MODE=${1:-"all"}

echo "========================================="
echo " Planner v7 — Rule Target 보강 학습"
echo " Mode: ${MODE}"
echo " Time: $(date)"
echo "========================================="

# ── 1. 패키지 설치 ──
echo "[1/5] Installing dependencies..."
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

# ── 2. 프로젝트 업데이트 ──
cd /workspace
if [ ! -d "SKN21-FINAL-3TEAM" ]; then
    echo "[2/5] Cloning repository..."
    git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM.git
    cd SKN21-FINAL-3TEAM
    git checkout FEAT/frontend
else
    echo "[2/5] Repository exists, pulling latest..."
    cd SKN21-FINAL-3TEAM
    git fetch origin && git reset --hard origin/FEAT/frontend
fi

# ── 3. GPU 확인 ──
echo ""
echo "[3/5] GPU check..."
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
python3 -c "import torch; print(f'PyTorch {torch.__version__}, CUDA {torch.version.cuda}, GPU: {torch.cuda.device_count()}')"
echo ""

RESULTS_DIR="outputs/v7_planner/experiment_results"
mkdir -p ${RESULTS_DIR}

# ══════════════════════════════════════════════
# Step A: v7 데이터 확인 (이미 repo에 포함)
# ══════════════════════════════════════════════
if [ "${MODE}" = "all" ] || [ "${MODE}" = "train-only" ]; then
    echo "═══════════════════════════════════════"
    echo " Step A: 학습 데이터 확인"
    echo "═══════════════════════════════════════"

    if [ ! -f "data/training/v7_planner/train.jsonl" ]; then
        echo "v7 데이터 없음 — 생성합니다..."
        python3 ai/finetuning/scripts/augment_v7_rule_targets.py --merge
    fi

    TRAIN_COUNT=$(wc -l < data/training/v7_planner/train.jsonl)
    EVAL_COUNT=$(wc -l < data/training/v7_planner/eval.jsonl)
    echo "  train: ${TRAIN_COUNT}건"
    echo "  eval:  ${EVAL_COUNT}건"
    echo ""
fi

# ══════════════════════════════════════════════
# Step B: v7 LoRA 학습
# ══════════════════════════════════════════════
if [ "${MODE}" = "all" ] || [ "${MODE}" = "train-only" ]; then
    echo "═══════════════════════════════════════"
    echo " Step B: v7 LoRA 학습"
    echo "═══════════════════════════════════════"
    echo "  Config: ai/finetuning/configs/v7_planner.yaml"
    echo "  lr=1e-4, epoch=4, LoRA r=16, MLP 포함"
    echo ""

    python3 ai/finetuning/train_v3_planner.py \
        --mode train \
        --config ai/finetuning/configs/v7_planner.yaml \
        2>&1 | tee ${RESULTS_DIR}/train_log.txt

    echo ""
    echo "✓ 학습 완료"
fi

# ══════════════════════════════════════════════
# Step C: Holdout 평가 (Rule 있음 vs 없음 비교)
# ══════════════════════════════════════════════
if [ "${MODE}" = "all" ] || [ "${MODE}" = "eval-only" ]; then
    echo ""
    echo "═══════════════════════════════════════"
    echo " Step C: Holdout 평가"
    echo "═══════════════════════════════════════"

    V7_ADAPTER="outputs/v7_planner/final"
    if [ ! -d "${V7_ADAPTER}" ]; then
        echo "WARNING: v7 어댑터 없음 — v5로 fallback"
        V7_ADAPTER="outputs/v5_planner/final"
    fi

    if [ -d "${V7_ADAPTER}" ]; then
        echo "Using adapter: ${V7_ADAPTER}"
        echo ""

        # 평가 1: 기본 프롬프트
        echo "[C-1] 기본 프롬프트 평가..."
        python3 ai/finetuning/scripts/eval_planner_holdout.py \
            --adapter ${V7_ADAPTER} \
            --output ${RESULTS_DIR}/eval_basic.json \
            2>&1 | tee ${RESULTS_DIR}/eval_basic_log.txt

        # 평가 2: Few-shot 프롬프트
        echo ""
        echo "[C-2] Few-shot 프롬프트 평가..."
        python3 ai/finetuning/scripts/eval_planner_holdout.py \
            --adapter ${V7_ADAPTER} \
            --fewshot \
            --output ${RESULTS_DIR}/eval_fewshot.json \
            2>&1 | tee ${RESULTS_DIR}/eval_fewshot_log.txt

        # 평가 3: 하이브리드 프롬프트
        echo ""
        echo "[C-3] 하이브리드 프롬프트 평가..."
        python3 ai/finetuning/scripts/eval_planner_holdout.py \
            --adapter ${V7_ADAPTER} \
            --hybrid \
            --output ${RESULTS_DIR}/eval_hybrid.json \
            2>&1 | tee ${RESULTS_DIR}/eval_hybrid_log.txt
    else
        echo "ERROR: 어댑터를 찾을 수 없습니다."
    fi

    echo ""
    echo "✓ 평가 완료"
fi

# ══════════════════════════════════════════════
# 결과 요약
# ══════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════"
echo " Perfect Match 비교"
echo "═══════════════════════════════════════"
for f in ${RESULTS_DIR}/eval_*.json; do
    if [ -f "$f" ]; then
        name=$(basename "$f" .json)
        pm=$(python3 -c "
import json
with open('$f') as f:
    d = json.load(f)
pm = d.get('perfect_rate', 0)
total = d.get('total', 0)
perfect = int(pm * total)
print(f'{perfect}/{total} ({pm*100:.1f}%)')
" 2>/dev/null || echo "parse error")
        printf "  %-30s %s\n" "$name" "$pm"
    fi
done

echo ""
echo "========================================="
echo " 완료! $(date)"
echo " Output: outputs/v7_planner/"
echo "========================================="
