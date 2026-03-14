#!/bin/bash
# =============================================================
# RunPod — LoRA v1 모델 재평가 (RAG 개선 환경)
#
# 목적: RAG 개선(Reranker + HyDE)이 최종 판단 정확도에 미치는 효과 측정
#
# 실행:
#   bash scripts/runpod_eval_rag.sh              # 전체 비교 (A/B/C 3모드)
#   bash scripts/runpod_eval_rag.sh --setup-only  # 환경 설정만
#   bash scripts/runpod_eval_rag.sh --eval-only   # 평가만 (셋업 완료 후)
#   bash scripts/runpod_eval_rag.sh --quick        # 빠른 테스트 (30건만)
# =============================================================

set -e

MODE="${1:-all}"
PROJECT_DIR="/workspace/SKN21-FINAL-3TEAM"

# ── 셋업 ──
setup() {
    echo "============================================"
    echo "  RAG 개선 환경 재평가 — 환경 셋업"
    echo "============================================"

    # 시스템 패키지
    apt-get update -qq && apt-get install -y -qq git > /dev/null 2>&1

    # 프로젝트 확인
    if [ -d "$PROJECT_DIR" ]; then
        cd "$PROJECT_DIR"
        git pull origin develop 2>/dev/null || echo "  (git pull 스킵)"
    else
        echo "  ※ 프로젝트를 먼저 클론하세요: git clone <repo-url> $PROJECT_DIR"
        exit 1
    fi

    # Python 패키지
    pip install --quiet --upgrade pip

    # 기존 파인튜닝 패키지
    pip install --quiet \
        torch \
        "transformers>=4.44.0" \
        "accelerate>=0.33.0" \
        "bitsandbytes>=0.43.3" \
        "peft>=0.12.0" \
        "pyyaml>=6.0"

    # RAG 파이프라인 패키지
    pip install --quiet \
        "qdrant-client>=1.11.0" \
        "sentence-transformers>=3.0.0" \
        "rank-bm25>=0.2.2" \
        "kiwipiepy>=0.18.0" \
        "python-dotenv>=1.0.0"

    # 환경 확인
    cd "$PROJECT_DIR"
    python3 -c "
import torch
print(f'  PyTorch: {torch.__version__}')
print(f'  CUDA: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'  GPU: {torch.cuda.get_device_name(0)}')
    mem = torch.cuda.get_device_properties(0).total_mem / 1024**3
    print(f'  VRAM: {mem:.1f} GB')

# .env 확인
from pathlib import Path
from dotenv import load_dotenv
import os
load_dotenv(Path('$PROJECT_DIR') / '.env')
qdrant_url = os.getenv('QDRANT_URL', '')
has_qdrant = bool(qdrant_url)
print(f'  Qdrant URL: {\"설정됨\" if has_qdrant else \"미설정 ⚠\"}')
if not has_qdrant:
    print('    → .env에 QDRANT_URL, QDRANT_API_KEY를 설정하세요')

# 어댑터 확인
adapter_path = Path('$PROJECT_DIR/outputs/v1_judgment/final')
if adapter_path.exists():
    files = list(adapter_path.glob('*'))
    print(f'  LoRA 어댑터: {len(files)}개 파일 ✓')
else:
    print(f'  LoRA 어댑터: 없음 ⚠')
    print('    → 먼저 학습을 실행하거나 어댑터를 업로드하세요')

# eval 데이터 확인
eval_path = Path('$PROJECT_DIR/data/training/v1_judgment/eval.jsonl')
if eval_path.exists():
    count = sum(1 for line in open(eval_path) if line.strip())
    print(f'  Eval 데이터: {count}건 ✓')
else:
    print(f'  Eval 데이터: 없음 ⚠')
"

    echo ""
    echo "  셋업 완료!"
    echo ""
}

# ── 평가 실행 ──
run_eval() {
    echo "============================================"
    echo "  LoRA v1 재평가 — RAG 개선 환경"
    echo "============================================"
    echo ""
    echo "  Mode A: baseline (기존 컨텍스트)"
    echo "  Mode B: rag-improved (Reranker + HyDE)"
    echo "  Mode C: rag-baseline (RRF만)"
    echo ""

    cd "$PROJECT_DIR"

    EXTRA_ARGS=""
    if [ "$MODE" = "--quick" ]; then
        EXTRA_ARGS="--max_samples 30"
        echo "  ※ Quick 모드: 30건만 평가"
        echo ""
    fi

    python3 scripts/eval_lora_v1_rag_improved.py \
        --mode all \
        --adapter_path outputs/v1_judgment/final \
        --top_k 10 \
        --score_threshold -2.0 \
        $EXTRA_ARGS

    echo ""
    echo "  결과 파일:"
    echo "    outputs/v1_judgment/eval_rag_improved.json"
    echo "    outputs/v1_judgment/eval_detail_baseline.json"
    echo "    outputs/v1_judgment/eval_detail_rag_improved.json"
    echo "    outputs/v1_judgment/eval_detail_rag_baseline.json"
    echo ""
}

# ── 메인 ──
case "$MODE" in
    --setup-only)
        setup
        ;;
    --eval-only)
        cd "$PROJECT_DIR"
        run_eval
        ;;
    --quick)
        cd "$PROJECT_DIR"
        run_eval
        ;;
    all|*)
        setup
        run_eval
        echo "============================================"
        echo "  전체 완료!"
        echo "============================================"
        echo ""
        echo "  결과를 로컬로 다운로드:"
        echo "    scp runpod:/workspace/SKN21-FINAL-3TEAM/outputs/v1_judgment/eval_rag_improved.json ."
        echo ""
        ;;
esac
