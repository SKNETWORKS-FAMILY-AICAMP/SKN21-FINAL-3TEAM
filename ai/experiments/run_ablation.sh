#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# roberta-large 멀티라벨 성능 최대화 — RunPod 실행 스크립트
#
# 실행 순서:
#   1. Focal Loss + Label Weight 단독
#   2. FGM 단독
#   3. Focal + FGM 조합
#   4. Winner config로 5-seed 앙상블 학습
#   5. 앙상블 평가 + threshold 재최적화
#
# 사용법 (RunPod):
#   cd /workspace/SKN21-FINAL-3TEAM
#   bash ai/experiments/run_ablation.sh
# ═══════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════════════════"
echo "  환경 세팅"
echo "═══════════════════════════════════════════════════════"
pip install transformers datasets accelerate scikit-learn matplotlib seaborn

# GPU 확인
python3 -c "import torch; print(f'GPU: {torch.cuda.get_device_name(0)}'); print(f'VRAM: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB')"

MODEL="klue/roberta-large"
RESULTS_DIR="ai/experiments/results"
mkdir -p $RESULTS_DIR

# ═══════════════════════════════════════════════════════════════
# Step 0: Baseline (BCE, seed=42) — 비교 기준
# ═══════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Step 0: Baseline (BCE only)"
echo "═══════════════════════════════════════════════════════"
python3 -m ai.experiments.train_multilabel \
    --model $MODEL \
    --seed 42

# Baseline held-out 평가
python3 -m ai.experiments.eval_holdout \
    --model-dir ai/models/intent_multilabel \
    --optimize-thresholds

cp $RESULTS_DIR/holdout_evaluation_results.json $RESULTS_DIR/holdout_step0_baseline.json
echo "Step 0 결과 저장: holdout_step0_baseline.json"

# ═══════════════════════════════════════════════════════════════
# Step 1: Focal Loss + Label Weight 단독
# ═══════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Step 1: Focal Loss (gamma=2.0) + Label Weight"
echo "═══════════════════════════════════════════════════════"
python3 -m ai.experiments.train_multilabel \
    --model $MODEL \
    --focal --focal-gamma 2.0 --label-weights \
    --seed 42

python3 -m ai.experiments.eval_holdout \
    --model-dir ai/models/intent_multilabel \
    --optimize-thresholds

cp $RESULTS_DIR/holdout_evaluation_results.json $RESULTS_DIR/holdout_step1_focal.json
echo "Step 1 결과 저장: holdout_step1_focal.json"

# ═══════════════════════════════════════════════════════════════
# Step 2: FGM 단독
# ═══════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Step 2: FGM (epsilon=1.0)"
echo "═══════════════════════════════════════════════════════"
python3 -m ai.experiments.train_multilabel \
    --model $MODEL \
    --fgm --fgm-epsilon 1.0 \
    --seed 42

python3 -m ai.experiments.eval_holdout \
    --model-dir ai/models/intent_multilabel \
    --optimize-thresholds

cp $RESULTS_DIR/holdout_evaluation_results.json $RESULTS_DIR/holdout_step2_fgm.json
echo "Step 2 결과 저장: holdout_step2_fgm.json"

# ═══════════════════════════════════════════════════════════════
# Step 3: Focal + FGM 조합
# ═══════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Step 3: Focal + FGM 조합"
echo "═══════════════════════════════════════════════════════"
python3 -m ai.experiments.train_multilabel \
    --model $MODEL \
    --focal --focal-gamma 2.0 --label-weights \
    --fgm --fgm-epsilon 1.0 \
    --seed 42

python3 -m ai.experiments.eval_holdout \
    --model-dir ai/models/intent_multilabel \
    --optimize-thresholds

cp $RESULTS_DIR/holdout_evaluation_results.json $RESULTS_DIR/holdout_step3_focal_fgm.json
echo "Step 3 결과 저장: holdout_step3_focal_fgm.json"

# ═══════════════════════════════════════════════════════════════
# Step 4: 5-Seed 앙상블 학습 (Focal + FGM)
# ═══════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Step 4: 5-Seed 앙상블 (Focal + FGM)"
echo "═══════════════════════════════════════════════════════"
python3 -m ai.experiments.train_multilabel \
    --model $MODEL \
    --focal --focal-gamma 2.0 --label-weights \
    --fgm --fgm-epsilon 1.0 \
    --ensemble-seeds 42,123,456,789,1337

# ═══════════════════════════════════════════════════════════════
# Step 5: 앙상블 평가 + Threshold 재최적화
# ═══════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Step 5: 앙상블 평가 + Threshold 재최적화"
echo "═══════════════════════════════════════════════════════"
python3 -m ai.experiments.eval_holdout \
    --ensemble-dir ai/models/intent_multilabel_ensemble \
    --optimize-thresholds

# ═══════════════════════════════════════════════════════════════
# 최종 요약
# ═══════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  전체 실험 완료!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "결과 파일:"
echo "  $RESULTS_DIR/holdout_step0_baseline.json"
echo "  $RESULTS_DIR/holdout_step1_focal.json"
echo "  $RESULTS_DIR/holdout_step2_fgm.json"
echo "  $RESULTS_DIR/holdout_step3_focal_fgm.json"
echo "  $RESULTS_DIR/holdout_ensemble_results.json"
echo ""
echo "요약 비교:"
python3 -c "
import json
from pathlib import Path

results_dir = Path('ai/experiments/results')
steps = [
    ('Step 0: Baseline',       'holdout_step0_baseline.json'),
    ('Step 1: Focal+LW',       'holdout_step1_focal.json'),
    ('Step 2: FGM',            'holdout_step2_fgm.json'),
    ('Step 3: Focal+FGM',      'holdout_step3_focal_fgm.json'),
    ('Step 5: 5-Seed Ensemble', 'holdout_ensemble_results.json'),
]

print(f'  {\"단계\":<26} {\"Held-out ACC\":>12} {\"Threshold ACC\":>14} {\"추론(ms)\":>10}')
print(f'  {\"─\"*26} {\"─\"*12} {\"─\"*14} {\"─\"*10}')

for name, fname in steps:
    path = results_dir / fname
    if not path.exists():
        print(f'  {name:<26} (파일 없음)')
        continue
    with open(path) as f:
        r = json.load(f)
    baseline_acc = r['holdout_adversarial']['subset_accuracy']
    th_acc = r.get('holdout_adversarial_threshold', {}).get('subset_accuracy', '-')
    infer = r.get('inference_time_ms', '-')
    th_str = f'{th_acc*100:.1f}%' if isinstance(th_acc, float) else th_acc
    print(f'  {name:<26} {baseline_acc*100:>11.1f}% {th_str:>14} {infer:>10}')
"
