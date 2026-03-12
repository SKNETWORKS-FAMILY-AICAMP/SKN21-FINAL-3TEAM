#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 크로스 모델 실험 — 후보 모델 학습 + 크로스 앙상블
#
# 목적: roberta-large 외 다른 아키텍처를 학습하고
#       크로스 모델 앙상블로 93.3% → 95%+ 가능한지 확인
#
# 사용법 (RunPod):
#   cd /workspace/SKN21-FINAL-3TEAM
#   bash ai/experiments/run_cross_model.sh
# ═══════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════════════════"
echo "  크로스 모델 실험 시작"
echo "═══════════════════════════════════════════════════════"

RESULTS_DIR="ai/experiments/results"
mkdir -p $RESULTS_DIR

# 후보 모델 리스트
MODELS=(
    "klue/roberta-base"
    "beomi/KcELECTRA-base-v2022"
    "lighthouse/mdeberta-v3-base-kor-further"
)

# ═══════════════════════════════════════════════════════════════
# 각 모델 학습 (Focal + FGM + Label Weight, seed=42)
# ═══════════════════════════════════════════════════════════════
for MODEL in "${MODELS[@]}"; do
    SHORT_NAME=$(echo $MODEL | tr '/' '_')
    echo ""
    echo "═══════════════════════════════════════════════════════"
    echo "  학습: $MODEL"
    echo "═══════════════════════════════════════════════════════"

    python3 -m ai.experiments.train_multilabel \
        --model "$MODEL" \
        --focal --focal-gamma 2.0 --label-weights \
        --fgm --fgm-epsilon 1.0 \
        --seed 42 \
    || { echo "⚠️  $MODEL 학습 실패, 건너뜀"; continue; }

    # 모델 백업 (다음 모델이 덮어쓰기 전에)
    BACKUP_DIR="ai/models/intent_multilabel_${SHORT_NAME}"
    mkdir -p "$BACKUP_DIR"
    cp ai/models/intent_multilabel/* "$BACKUP_DIR/"
    echo "모델 백업: $BACKUP_DIR"

    # 중간 체크포인트 정리 (디스크 절약)
    rm -rf "$RESULTS_DIR/multilabel_"*"_seed"*/
    rm -rf "$RESULTS_DIR/multilabel_${MODEL##*/}"/

    # 개별 held-out 평가
    python3 -m ai.experiments.eval_holdout \
        --model-dir "$BACKUP_DIR" \
        --optimize-thresholds \
    || echo "⚠️  $MODEL 평가 실패"

    cp "$RESULTS_DIR/holdout_evaluation_results.json" \
       "$RESULTS_DIR/holdout_${SHORT_NAME}.json" 2>/dev/null || true

    echo "완료: $MODEL"
done

# ═══════════════════════════════════════════════════════════════
# 결과 요약
# ═══════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  개별 모델 결과 요약"
echo "═══════════════════════════════════════════════════════"

python3 -c "
import json
from pathlib import Path

results_dir = Path('ai/experiments/results')
models = [
    ('roberta-large (5-seed 앙상블)', 'holdout_ensemble_results.json'),
    ('klue_roberta-base', 'holdout_klue_roberta-base.json'),
    ('beomi_KcELECTRA-base-v2022', 'holdout_beomi_KcELECTRA-base-v2022.json'),
    ('lighthouse_mdeberta-v3', 'holdout_lighthouse_mdeberta-v3-base-kor-further.json'),
]

print(f'  {\"모델\":<35} {\"Held-out ACC\":>12} {\"Threshold ACC\":>14}')
print(f'  {\"─\"*35} {\"─\"*12} {\"─\"*14}')

for name, fname in models:
    path = results_dir / fname
    if not path.exists():
        print(f'  {name:<35} (파일 없음)')
        continue
    with open(path) as f:
        r = json.load(f)
    baseline = r.get('holdout_adversarial', {}).get('subset_accuracy', 0)
    th = r.get('holdout_adversarial_threshold', {}).get('subset_accuracy', '-')
    th_str = f'{th*100:.1f}%' if isinstance(th, float) else str(th)
    print(f'  {name:<35} {baseline*100:>11.1f}% {th_str:>14}')
"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  크로스 모델 실험 완료!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "다음 단계:"
echo "  1. 결과 보고 가장 좋은 모델 확인"
echo "  2. roberta-large 앙상블 + 최고 모델로 크로스 앙상블 구성"
