#!/bin/bash
# RunPod Planner v6 실험 — 4단계 순차 실행
#
# 실험 A: Rule Guide 추가 (규칙 10, 11) → v5 어댑터로 holdout 재평가
# 실험 B: Few-shot 프롬프트 → v5 어댑터로 holdout 재평가
# 실험 C: 오답 타겟 보강 데이터 생성 (GPT-4o-mini, 60건)
# 실험 D: v6 학습 (lr=1e-4, epoch 4, MLP 포함) + holdout 평가
#
# 사용법:
#   bash ai/finetuning/runpod_planner_v6.sh              # 전체 실행 (A→B→C→D)
#   bash ai/finetuning/runpod_planner_v6.sh eval-only     # A+B만 (재학습 없이)
#   bash ai/finetuning/runpod_planner_v6.sh train-only    # C+D만 (데이터 생성 + 학습)
#
# 필요:
#   - OPENAI_API_KEY 환경변수 (실험 C용)
#   - GPU: A100 40GB 권장

set -e

MODE=${1:-"all"}

echo "========================================="
echo " Planner v6 실험 스위트"
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
    pyyaml \
    openai

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

# ── 결과 저장 디렉토리 ──
RESULTS_DIR="outputs/v6_planner/experiment_results"
mkdir -p ${RESULTS_DIR}

# ══════════════════════════════════════════════
# 실험 A: Rule Guide 추가 (v5 어댑터 + 새 규칙 10, 11)
# ══════════════════════════════════════════════
if [ "${MODE}" = "all" ] || [ "${MODE}" = "eval-only" ]; then
    echo ""
    echo "═══════════════════════════════════════"
    echo " 실험 A: Rule Guide 추가 (규칙 10, 11)"
    echo "═══════════════════════════════════════"
    echo ""

    # v5 어댑터가 있는지 확인
    V5_ADAPTER="outputs/v5_planner/final"
    if [ ! -d "${V5_ADAPTER}" ]; then
        # v4 어댑터로 fallback
        V5_ADAPTER="outputs/v4_planner/final"
    fi

    if [ -d "${V5_ADAPTER}" ]; then
        echo "Using adapter: ${V5_ADAPTER}"
        python3 ai/finetuning/scripts/eval_planner_holdout.py \
            --adapter ${V5_ADAPTER} \
            --output ${RESULTS_DIR}/exp_A_rule_guide.json \
            2>&1 | tee ${RESULTS_DIR}/exp_A_log.txt
    else
        echo "WARNING: No v5/v4 adapter found. Evaluating base model only."
        python3 ai/finetuning/scripts/eval_planner_holdout.py \
            --base-only \
            --output ${RESULTS_DIR}/exp_A_rule_guide_base.json \
            2>&1 | tee ${RESULTS_DIR}/exp_A_log.txt
    fi

    echo ""
    echo "✓ 실험 A 완료"
fi

# ══════════════════════════════════════════════
# 실험 B: Few-shot 프롬프트 (v5 어댑터 + 3-step 예시)
# ══════════════════════════════════════════════
if [ "${MODE}" = "all" ] || [ "${MODE}" = "eval-only" ]; then
    echo ""
    echo "═══════════════════════════════════════"
    echo " 실험 B: Few-shot 프롬프트"
    echo "═══════════════════════════════════════"
    echo ""

    V5_ADAPTER="outputs/v5_planner/final"
    if [ ! -d "${V5_ADAPTER}" ]; then
        V5_ADAPTER="outputs/v4_planner/final"
    fi

    if [ -d "${V5_ADAPTER}" ]; then
        python3 ai/finetuning/scripts/eval_planner_holdout.py \
            --adapter ${V5_ADAPTER} \
            --fewshot \
            --output ${RESULTS_DIR}/exp_B_fewshot.json \
            2>&1 | tee ${RESULTS_DIR}/exp_B_log.txt
    else
        python3 ai/finetuning/scripts/eval_planner_holdout.py \
            --base-only \
            --fewshot \
            --output ${RESULTS_DIR}/exp_B_fewshot_base.json \
            2>&1 | tee ${RESULTS_DIR}/exp_B_log.txt
    fi

    echo ""
    echo "✓ 실험 B 완료"
fi

# ══════════════════════════════════════════════
# 실험 C: 오답 타겟 보강 데이터 생성
# ══════════════════════════════════════════════
if [ "${MODE}" = "all" ] || [ "${MODE}" = "train-only" ]; then
    echo ""
    echo "═══════════════════════════════════════"
    echo " 실험 C: 오답 타겟 보강 (GPT-4o-mini)"
    echo "═══════════════════════════════════════"
    echo ""

    if [ -z "${OPENAI_API_KEY}" ]; then
        echo "WARNING: OPENAI_API_KEY 미설정 — 쿼리만 생성합니다."
        python3 ai/finetuning/scripts/augment_v6_planner.py --count 60 --no-gpt \
            2>&1 | tee ${RESULTS_DIR}/exp_C_log.txt
    else
        python3 ai/finetuning/scripts/augment_v6_planner.py --count 60 \
            2>&1 | tee ${RESULTS_DIR}/exp_C_log.txt
    fi

    echo ""
    echo "✓ 실험 C 완료"
fi

# ══════════════════════════════════════════════
# 실험 D: v6 학습 (lr=1e-4, epoch 4, MLP 포함)
# ══════════════════════════════════════════════
if [ "${MODE}" = "all" ] || [ "${MODE}" = "train-only" ]; then
    echo ""
    echo "═══════════════════════════════════════"
    echo " 실험 D: v6 LoRA 학습 + Holdout 평가"
    echo "═══════════════════════════════════════"
    echo ""

    # v6 데이터가 있는지 확인
    if [ ! -f "data/training/v6_planner/train.jsonl" ]; then
        echo "ERROR: v6 학습 데이터 없음 (실험 C를 먼저 실행하세요)"
        echo "  data/training/v6_planner/train.jsonl 필요"
    else
        echo "v6 학습 시작..."
        echo "  Config: ai/finetuning/configs/v6_planner.yaml"
        echo "  lr=1e-4, epoch=4, LoRA r=16, MLP 포함"
        echo ""

        # 학습
        python3 ai/finetuning/train_v3_planner.py \
            --mode train \
            --config ai/finetuning/configs/v6_planner.yaml \
            2>&1 | tee ${RESULTS_DIR}/exp_D_train_log.txt

        echo ""
        echo "v6 Holdout 평가..."

        # Holdout 평가 (새 Rule + 기본 프롬프트)
        python3 ai/finetuning/scripts/eval_planner_holdout.py \
            --adapter outputs/v6_planner/final \
            --output ${RESULTS_DIR}/exp_D_holdout.json \
            2>&1 | tee ${RESULTS_DIR}/exp_D_eval_log.txt

        # Holdout 평가 (새 Rule + Few-shot 프롬프트)
        python3 ai/finetuning/scripts/eval_planner_holdout.py \
            --adapter outputs/v6_planner/final \
            --fewshot \
            --output ${RESULTS_DIR}/exp_D_holdout_fewshot.json \
            2>&1 | tee ${RESULTS_DIR}/exp_D_eval_fewshot_log.txt

        echo ""
        echo "✓ 실험 D 완료"
    fi
fi

# ══════════════════════════════════════════════
# 결과 요약
# ══════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════"
echo " 실험 결과 요약"
echo "═══════════════════════════════════════"
echo ""
echo "결과 파일:"
ls -la ${RESULTS_DIR}/ 2>/dev/null || echo "  (결과 없음)"

# JSON 결과에서 Perfect Match 추출
echo ""
echo "Perfect Match 비교:"
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
echo " 전체 완료! $(date)"
echo "========================================="
