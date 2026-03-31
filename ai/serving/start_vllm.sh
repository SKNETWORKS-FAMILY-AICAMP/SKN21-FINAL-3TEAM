#!/bin/bash
# vLLM 서버 시작 스크립트 (RunPod GPU Pod용)
# 사용법: bash start_vllm.sh
#
# 지원 LoRA 어댑터:
#   - v1_judgment: 규정 판단 (yoongyeongeun/v1-judgment-hardcoded)
#   - v3_generate: 문서 생성 (v3)
#   - v3_summary: 문서 요약 (v3)

set -e

echo "=== vLLM 서빙 환경 설정 ==="

# 패키지 설치
pip install -U vllm torch torchvision --index-url https://download.pytorch.org/whl/cu124 -q 2>/dev/null
pip install peft bitsandbytes huggingface_hub -q 2>/dev/null

echo "=== 패키지 설치 완료 ==="

# 모델 및 어댑터 경로
BASE_MODEL="kakaocorp/kanana-1.5-8b-instruct-2505"
PORT=8000

# v1_judgment 어댑터: HuggingFace에서 다운로드
ADAPTER_JUDGMENT_DIR="/workspace/adapters/v1_judgment"
if [ ! -f "${ADAPTER_JUDGMENT_DIR}/adapter_model.safetensors" ]; then
    echo "=== v1_judgment 어댑터 다운로드 (HuggingFace) ==="
    mkdir -p "${ADAPTER_JUDGMENT_DIR}"
    huggingface-cli download yoongyeongeun/v1-judgment-hardcoded \
        --local-dir "${ADAPTER_JUDGMENT_DIR}" \
        --local-dir-use-symlinks False
fi

# v3 어댑터 경로
ADAPTER_GENERATE="/workspace/adapters/v3_generate"
ADAPTER_SUMMARY="/workspace/adapters/v3_summary"

# planner (복합질문 순서 처리)
ADAPTER_PLANNER="/workspace/models/planner-v5-lora"

# 어댑터 존재 확인 + LoRA 모듈 목록 구성
LORA_MODULES="v1_judgment=${ADAPTER_JUDGMENT_DIR}"

for name_path in "v3_generate:${ADAPTER_GENERATE}" "v3_summary:${ADAPTER_SUMMARY}" "planner:${ADAPTER_PLANNER}"; do
    name="${name_path%%:*}"
    path="${name_path#*:}"
    if [ -f "${path}/adapter_model.safetensors" ]; then
        LORA_MODULES="${LORA_MODULES} ${name}=${path}"
        echo "  LoRA 어댑터 발견: ${name}"
    else
        echo "  WARNING: ${name} adapter weights not found at ${path} (건너뜀)"
    fi
done

echo ""
echo "=== vLLM 서버 시작 ==="
echo "  Base model: ${BASE_MODEL}"
echo "  LoRA modules: ${LORA_MODULES}"
echo "  Port: ${PORT}"
echo ""
echo "  백엔드 .env에서 아래 설정:"
echo "    JUDGMENT_AGENT_MODE=sllm"
echo "    DOC_AGENT_MODE=sllm"
echo "    VLLM_BASE_URL=http://<이 서버 IP>:${PORT}/v1"
echo "    VLLM_USE_LORA=true"
echo ""

python -m vllm.entrypoints.openai.api_server \
    --model ${BASE_MODEL} \
    --port ${PORT} \
    --host 0.0.0.0 \
    --trust-remote-code \
    --enable-lora \
    --lora-modules ${LORA_MODULES} \
    --max-lora-rank 32 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.85 \
    --dtype bfloat16
