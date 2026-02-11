#!/bin/bash
# =============================================================
# 전체 모델 벤치마크 순차 실행
# 사용법: bash scripts/benchmark/runpod_run_all.sh
# =============================================================

set -e
cd /workspace/SKN21-FINAL-3TEAM

echo "============================================"
echo "  전체 모델 벤치마크 시작"
echo "  모델: Qwen3 → Kanana → EXAONE → Tri-7B"
echo "============================================"
echo ""

MODELS=("qwen3" "kanana" "exaone" "tri7b")
START_TIME=$(date +%s)

for model in "${MODELS[@]}"; do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  [$model] 벤치마크 시작: $(date '+%H:%M:%S')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    python scripts/benchmark/run.py --model "$model" 2>&1 | tee "data/evaluation/benchmark_results/${model}_log.txt"

    echo ""
    echo "  [$model] 완료: $(date '+%H:%M:%S')"
    echo ""

    # GPU 메모리 정리 대기
    sleep 5
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))

echo ""
echo "============================================"
echo "  전체 벤치마크 완료!"
echo "  총 소요시간: ${MINUTES}분 ${ELAPSED}초"
echo "============================================"
echo ""

# 비교 리포트 자동 생성
echo "비교 리포트 생성 중..."
python scripts/benchmark/run.py --report

echo ""
echo "결과 파일:"
ls -la data/evaluation/benchmark_results/
echo ""
echo "리포트: data/evaluation/benchmark_report.md"
