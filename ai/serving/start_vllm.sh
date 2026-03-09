#!/bin/bash
# vLLM 서버 시작 스크립트 (RunPod GPU Pod용)
# 사용법: bash start_vllm.sh

set -e

echo "=== vLLM 서빙 환경 설정 ==="

# 패키지 설치
pip install -U vllm torch torchvision --index-url https://download.pytorch.org/whl/cu124 -q 2>/dev/null
pip install peft bitsandbytes -q 2>/dev/null

echo "=== 패키지 설치 완료 ==="

# 모델 및 어댑터 경로
BASE_MODEL="kakaocorp/kanana-1.5-8b-instruct-2505"
ADAPTER_PATH="/workspace/SKN21-FINAL-3TEAM/outputs/v2_generate/kanana-1.5-8b-instruct-2505/final"
PORT=8000

# 어댑터 존재 확인
if [ ! -f "${ADAPTER_PATH}/adapter_model.safetensors" ]; then
    echo "ERROR: adapter weights not found at ${ADAPTER_PATH}"
    exit 1
fi

echo "=== vLLM 서버 시작 ==="
echo "  Base model: ${BASE_MODEL}"
echo "  LoRA adapter: ${ADAPTER_PATH}"
echo "  Port: ${PORT}"
echo ""
echo "  백엔드 .env에서 아래 설정:"
echo "    DOC_AGENT_MODE=sllm"
echo "    VLLM_BASE_URL=http://<이 서버 IP>:${PORT}/v1"
echo ""

python -m vllm.entrypoints.openai.api_server \
    --model ${BASE_MODEL} \
    --port ${PORT} \
    --host 0.0.0.0 \
    --trust-remote-code \
    --enable-lora \
    --lora-modules v2_generate=${ADAPTER_PATH} \
    --max-lora-rank 32 \
    --max-model-len 2560 \
    --gpu-memory-utilization 0.85 \
    --dtype bfloat16
