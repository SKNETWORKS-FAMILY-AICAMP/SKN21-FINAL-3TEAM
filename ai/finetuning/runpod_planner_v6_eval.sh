#!/bin/bash
# v5 어댑터 + Few-shot + 정교한 KNOWN_OVERRIDES 평가
#
# 실행:
#   bash ai/finetuning/runpod_planner_v6_eval.sh

set -e

echo "========================================="
echo " v5 + Few-shot + KNOWN_OVERRIDES 평가"
echo " Time: $(date)"
echo "========================================="

# ── 1. 패키지 설치 ──
pip install -q -U \
    torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -q -U \
    transformers peft bitsandbytes accelerate sentencepiece protobuf

# ── 2. 프로젝트 업데이트 ──
cd /workspace
if [ ! -d "SKN21-FINAL-3TEAM" ]; then
    git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM.git
    cd SKN21-FINAL-3TEAM
    git checkout FEAT/frontend
else
    cd SKN21-FINAL-3TEAM
    git fetch origin && git reset --hard origin/FEAT/frontend
fi

# ── 3. GPU 확인 ──
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
echo ""

RESULTS_DIR="outputs/v6_planner/experiment_results"
mkdir -p ${RESULTS_DIR}

V5_ADAPTER="outputs/v5_planner/final"
if [ ! -d "${V5_ADAPTER}" ]; then
    V5_ADAPTER="outputs/v4_planner/final"
fi

# ── 실험 G: v5 + 기본 + 후처리 매핑 (knowledge_query) ──
echo ""
echo "═══════════════════════════════════════"
echo " 실험 G: v5 + 기본 + 후처리 매핑"
echo "═══════════════════════════════════════"
python3 ai/finetuning/scripts/eval_planner_holdout.py \
    --adapter ${V5_ADAPTER} \
    --output ${RESULTS_DIR}/exp_G_mapping.json \
    2>&1 | tee ${RESULTS_DIR}/exp_G_log.txt
echo "✓ 실험 G 완료"

# ── 실험 H: v5 + Few-shot + 후처리 매핑 ──
echo ""
echo "═══════════════════════════════════════"
echo " 실험 H: v5 + Few-shot + 후처리 매핑"
echo "═══════════════════════════════════════"
python3 ai/finetuning/scripts/eval_planner_holdout.py \
    --adapter ${V5_ADAPTER} \
    --fewshot \
    --output ${RESULTS_DIR}/exp_H_fewshot_mapping.json \
    2>&1 | tee ${RESULTS_DIR}/exp_H_log.txt
echo "✓ 실험 H 완료"

# ── 결과 비교 ──
echo ""
echo "═══════════════════════════════════════"
echo " Perfect Match 비교"
echo "═══════════════════════════════════════"
for f in ${RESULTS_DIR}/exp_*.json; do
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
        printf "  %-35s %s\n" "$name" "$pm"
    fi
done

echo ""
echo "========================================="
echo " 완료! $(date)"
echo "========================================="
