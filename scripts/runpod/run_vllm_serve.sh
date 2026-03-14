#!/bin/bash
# ============================================================
# vLLM 서빙 실행 스크립트
#
# 파인튜닝 완료 후 실행:
#   bash scripts/run_vllm_serve.sh
#
# LoRA 어댑터 위치:
#   outputs/v1_judgment/final/  → 판단 특화
#   outputs/v2_document/final/  → 문서 특화 (추후)
# ============================================================

set -e

MODEL="kakaocorp/kanana-1.5-8b-instruct-2505"
PORT=8000

# LoRA 어댑터 경로 확인
V1_PATH="outputs/v1_judgment/final"
V2_PATH="outputs/v2_document/final"

LORA_MODULES=""

if [ -d "$V1_PATH" ]; then
    echo "  v1_judgment 어댑터 발견: $V1_PATH"
    LORA_MODULES="v1_judgment=$V1_PATH"
fi

if [ -d "$V2_PATH" ]; then
    echo "  v2_document 어댑터 발견: $V2_PATH"
    if [ -n "$LORA_MODULES" ]; then
        LORA_MODULES="$LORA_MODULES v2_document=$V2_PATH"
    else
        LORA_MODULES="v2_document=$V2_PATH"
    fi
fi

echo "============================================"
echo "  vLLM 서빙 시작"
echo "  모델: $MODEL"
echo "  포트: $PORT"
echo "  LoRA: $LORA_MODULES"
echo "============================================"

if [ -n "$LORA_MODULES" ]; then
    python -m vllm.entrypoints.openai.api_server \
        --model "$MODEL" \
        --enable-lora \
        --lora-modules $LORA_MODULES \
        --max-lora-rank 64 \
        --port $PORT \
        --trust-remote-code
else
    echo "  경고: LoRA 어댑터 없음. 베이스 모델만 서빙합니다."
    python -m vllm.entrypoints.openai.api_server \
        --model "$MODEL" \
        --port $PORT \
        --trust-remote-code
fi
