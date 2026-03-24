#!/bin/bash
# RunPod Planner v5 — 4-step / 5-step 일반화 테스트
#
# 최종 모델(v5, 88% PM)이 3-step까지만 학습했는데
# 4-step, 5-step도 제대로 계획하는지 일반화 능력 평가
#
# 사전 조건: 네트워크 볼륨에 v5 어댑터 존재 (/workspace/models/planner-v5-lora/)
#
# 사용법:
#   bash ai/finetuning/runpod_eval_4step_5step.sh          # 전체 (sanity + 4step + 5step)
#   bash ai/finetuning/runpod_eval_4step_5step.sh 4step    # 4step만
#   bash ai/finetuning/runpod_eval_4step_5step.sh 5step    # 5step만

set -e

MODE=${1:-"all"}

echo "========================================="
echo " Planner v5 — 4-step / 5-step 일반화 테스트"
echo " Mode: ${MODE}"
echo " Time: $(date)"
echo "========================================="

# ── 1. 패키지 설치 ──
echo "[1/4] Installing dependencies..."
pip install -q -U \
    torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -q -U \
    transformers peft bitsandbytes accelerate \
    sentencepiece protobuf pyyaml

# ── 2. 프로젝트 업데이트 ──
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

# ── 3. GPU + 어댑터 확인 ──
echo ""
echo "[3/4] GPU check..."
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
python3 -c "import torch; print(f'PyTorch {torch.__version__}, CUDA {torch.version.cuda}, GPU: {torch.cuda.device_count()}')"

export HF_HOME=/workspace/hf_cache
mkdir -p ${HF_HOME}

V5_ADAPTER="/workspace/models/planner-v5-lora"
if [ ! -f "${V5_ADAPTER}/adapter_model.safetensors" ]; then
    echo "ERROR: v5 어댑터 없음: ${V5_ADAPTER}"
    echo "  네트워크 볼륨 마운트 확인 필요"
    exit 1
fi
echo "✓ v5 어댑터: ${V5_ADAPTER}"
ls -lh ${V5_ADAPTER}/adapter_model.safetensors
echo ""

RESULTS_DIR="outputs/v5_planner/step_test_results"
mkdir -p ${RESULTS_DIR}

# ══════════════════════════════════════════════
# Holdout 100건 sanity check (88% 기대)
# ══════════════════════════════════════════════
if [ "${MODE}" = "all" ]; then
    echo "═══════════════════════════════════════"
    echo " [Sanity] Holdout 100건 재현 확인"
    echo "═══════════════════════════════════════"
    python3 ai/finetuning/scripts/eval_planner_holdout.py \
        --adapter ${V5_ADAPTER} \
        --output ${RESULTS_DIR}/eval_holdout_sanity.json \
        2>&1 | tee ${RESULTS_DIR}/eval_holdout_sanity_log.txt
    echo ""
fi

# ══════════════════════════════════════════════
# 4-step 평가 (30건)
# ══════════════════════════════════════════════
if [ "${MODE}" = "all" ] || [ "${MODE}" = "4step" ]; then
    echo "═══════════════════════════════════════"
    echo " 4-step 일반화 테스트 (30건)"
    echo "═══════════════════════════════════════"

    echo "[4step-1] 기본 프롬프트..."
    python3 ai/finetuning/scripts/eval_planner_holdout.py \
        --adapter ${V5_ADAPTER} \
        --test-cases data/evaluation/planner_test_4step.json \
        --max-steps 4 \
        --output ${RESULTS_DIR}/eval_4step_basic.json \
        2>&1 | tee ${RESULTS_DIR}/eval_4step_basic_log.txt

    echo ""
    echo "[4step-2] 하이브리드 프롬프트..."
    python3 ai/finetuning/scripts/eval_planner_holdout.py \
        --adapter ${V5_ADAPTER} \
        --test-cases data/evaluation/planner_test_4step.json \
        --max-steps 4 \
        --hybrid \
        --output ${RESULTS_DIR}/eval_4step_hybrid.json \
        2>&1 | tee ${RESULTS_DIR}/eval_4step_hybrid_log.txt

    echo "✓ 4-step 완료"
fi

# ══════════════════════════════════════════════
# 5-step 평가 (30건)
# ══════════════════════════════════════════════
if [ "${MODE}" = "all" ] || [ "${MODE}" = "5step" ]; then
    echo ""
    echo "═══════════════════════════════════════"
    echo " 5-step 일반화 테스트 (30건)"
    echo " --max-steps 5 (프롬프트: '최대 5단계')"
    echo "═══════════════════════════════════════"

    echo "[5step-1] 기본 프롬프트..."
    python3 ai/finetuning/scripts/eval_planner_holdout.py \
        --adapter ${V5_ADAPTER} \
        --test-cases data/evaluation/planner_test_5step.json \
        --max-steps 5 \
        --output ${RESULTS_DIR}/eval_5step_basic.json \
        2>&1 | tee ${RESULTS_DIR}/eval_5step_basic_log.txt

    echo ""
    echo "[5step-2] 하이브리드 프롬프트..."
    python3 ai/finetuning/scripts/eval_planner_holdout.py \
        --adapter ${V5_ADAPTER} \
        --test-cases data/evaluation/planner_test_5step.json \
        --max-steps 5 \
        --hybrid \
        --output ${RESULTS_DIR}/eval_5step_hybrid.json \
        2>&1 | tee ${RESULTS_DIR}/eval_5step_hybrid_log.txt

    echo "✓ 5-step 완료"
fi

# ══════════════════════════════════════════════
# [4/4] 결과 요약
# ══════════════════════════════════════════════
echo ""
echo "[4/4] 결과 요약"
echo "═══════════════════════════════════════"

for f in ${RESULTS_DIR}/eval_*.json; do
    if [ -f "$f" ]; then
        name=$(basename "$f" .json)
        result=$(python3 -c "
import json
with open('$f') as f:
    d = json.load(f)
pm = d.get('perfect_rate', 0)
total = d.get('total', 0)
perfect = int(pm * total)
ws = d.get('weighted_score', 0)
ir = d.get('intent_recall', 0)
print(f'{perfect}/{total} ({pm*100:.1f}%) | WS={ws*100:.1f}% IR={ir*100:.1f}%')
" 2>/dev/null || echo "parse error")
        printf "  %-30s %s\n" "$name" "$result"
    fi
done

echo ""
echo "═══════════════════════════════════════"
echo " Step별 Perfect Match"
echo "═══════════════════════════════════════"

for f in ${RESULTS_DIR}/eval_*.json; do
    if [ -f "$f" ]; then
        name=$(basename "$f" .json)
        echo "  [${name}]"
        python3 -c "
import json
from collections import defaultdict
with open('$f') as f:
    d = json.load(f)
results = d.get('results', [])
by_step = defaultdict(lambda: [0,0])
for r in results:
    ns = r.get('expected_steps', r.get('expected', {}).get('num_steps', 0))
    by_step[ns][1] += 1
    if r.get('perfect_match', False):
        by_step[ns][0] += 1
for ns in sorted(by_step):
    c, t = by_step[ns]
    print(f'    {ns}-step: {c}/{t} ({c/t*100:.1f}%)')
" 2>/dev/null || echo "    parse error"
    fi
done

echo ""
echo "========================================="
echo " 완료! $(date)"
echo " 결과: ${RESULTS_DIR}/"
echo "========================================="
