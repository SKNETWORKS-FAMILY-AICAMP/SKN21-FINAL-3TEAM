#!/bin/bash
# =============================================================
# RunPod LoRA v1 (판단 Agent) 파인튜닝 셋업 + 실행 스크립트
#
# RunPod A100 40GB 터미널에서 실행:
#   bash scripts/runpod_finetune.sh
#
# 또는 셋업만:
#   bash scripts/runpod_finetune.sh --setup-only
#
# 또는 학습만 (셋업 완료 후):
#   bash scripts/runpod_finetune.sh --train-only
#
# 평가만:
#   bash scripts/runpod_finetune.sh --eval-only
# =============================================================

set -e

MODE="${1:-all}"  # all, --setup-only, --train-only, --eval-only

PROJECT_DIR="/workspace/SKN21-FINAL-3TEAM"

# ── 셋업 ──
setup() {
    echo "============================================"
    echo "  LoRA v1 파인튜닝 환경 셋업"
    echo "============================================"

    # 1. 시스템 패키지
    echo ""
    echo "[1/4] 시스템 패키지 업데이트..."
    apt-get update -qq && apt-get install -y -qq git > /dev/null 2>&1
    echo "  완료"

    # 2. 프로젝트 확인
    echo ""
    echo "[2/4] 프로젝트 확인..."
    if [ -d "$PROJECT_DIR" ]; then
        echo "  프로젝트 폴더 이미 존재: $PROJECT_DIR"
        cd "$PROJECT_DIR"
        git pull origin develop 2>/dev/null || echo "  (git pull 스킵)"
    else
        echo "  ※ 프로젝트를 먼저 /workspace에 클론하거나 업로드하세요:"
        echo "    git clone <repo-url> $PROJECT_DIR"
        exit 1
    fi

    # 3. Python 패키지 설치
    echo ""
    echo "[3/4] Python 패키지 설치..."
    pip install --quiet --upgrade pip

    pip install --quiet \
        torch \
        "transformers>=4.44.0" \
        "accelerate>=0.33.0" \
        "bitsandbytes>=0.43.3" \
        "peft>=0.12.0" \
        "trl>=0.9.0" \
        "datasets>=3.0.0" \
        "pyyaml>=6.0" \
        "scikit-learn>=1.5.0"

    echo "  완료"

    # 4. GPU + 데이터 확인
    echo ""
    echo "[4/4] 환경 확인..."
    cd "$PROJECT_DIR"
    python3 -c "
import torch
print(f'  PyTorch: {torch.__version__}')
print(f'  CUDA: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'  GPU: {torch.cuda.get_device_name(0)}')
    mem = torch.cuda.get_device_properties(0).total_mem / 1024**3
    print(f'  VRAM: {mem:.1f} GB')
else:
    print('  ⚠ GPU가 없습니다! A100 40GB Pod을 사용하세요.')

import json
from pathlib import Path

base = Path('$PROJECT_DIR')
train_path = base / 'data/training/v1_judgment/train.jsonl'
eval_path = base / 'data/training/v1_judgment/eval.jsonl'

for name, path in [('Train', train_path), ('Eval', eval_path)]:
    if path.exists():
        count = sum(1 for line in open(path) if line.strip())
        print(f'  {name} 데이터: {count}건 ✓')
    else:
        print(f'  {name} 데이터: 없음 ✗')

# 패키지 버전 확인
import transformers, peft, trl, bitsandbytes, accelerate
print(f'  transformers={transformers.__version__}, peft={peft.__version__}')
print(f'  trl={trl.__version__}, bitsandbytes={bitsandbytes.__version__}')
print(f'  accelerate={accelerate.__version__}')
"

    echo ""
    echo "  셋업 완료!"
    echo ""
}

# ── 학습 ──
run_train() {
    echo "============================================"
    echo "  LoRA v1 학습 시작 (Kanana-1.5-8B)"
    echo "============================================"
    echo ""
    echo "  모델: kakaocorp/kanana-1.5-8b-instruct-2505"
    echo "  QLoRA: r=16, alpha=32, 4-bit NF4"
    echo "  학습: 3 epochs, batch=4, grad_accum=4, lr=2e-4"
    echo ""

    cd "$PROJECT_DIR"
    python3 ai/finetuning/train_v1_judgment.py --mode train

    echo ""
    echo "  학습 완료! 어댑터: outputs/v1_judgment/final/"
    echo ""
}

# ── 평가 ──
run_eval() {
    echo "============================================"
    echo "  LoRA v1 평가"
    echo "============================================"
    echo ""

    cd "$PROJECT_DIR"
    python3 ai/finetuning/train_v1_judgment.py --mode eval \
        --adapter_path outputs/v1_judgment/final

    echo ""
}

# ── 메인 ──
case "$MODE" in
    --setup-only)
        setup
        ;;
    --train-only)
        cd "$PROJECT_DIR"
        run_train
        ;;
    --eval-only)
        cd "$PROJECT_DIR"
        run_eval
        ;;
    all|*)
        setup
        run_train
        run_eval
        echo "============================================"
        echo "  전체 완료! (셋업 → 학습 → 평가)"
        echo "============================================"
        echo ""
        echo "  어댑터 경로: outputs/v1_judgment/final/"
        echo "  평가 결과: outputs/v1_judgment/eval_results.json"
        echo ""
        echo "  어댑터 다운로드:"
        echo "    scp -r runpod:/workspace/SKN21-FINAL-3TEAM/outputs/v1_judgment/final/ ./outputs/v1_judgment/"
        echo ""
        ;;
esac
