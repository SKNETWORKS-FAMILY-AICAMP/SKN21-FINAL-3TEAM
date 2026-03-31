FROM runpod/worker-v1-vllm:v2.14.0

# 베이스 모델 다운로드 (빌드 시 1회만)
RUN pip install -U huggingface_hub[cli] && \
    hf download kakaocorp/kanana-1.5-8b-instruct-2505 \
    --local-dir /models/kanana-1.5-8b-instruct-2505

# LoRA 어댑터 다운로드 (HF Hub에서)
RUN hf download jiyong1110/v1_judgment --local-dir /adapters/v1_judgment && \
    hf download jiyong1110/v2_generate --local-dir /adapters/v2_generate && \
    hf download jiyong1110/v3_summary  --local-dir /adapters/v3_summary && \
    hf download jiyong1110/planner     --local-dir /adapters/planner

# vLLM 환경변수 설정
ENV MODEL_NAME="/models/kanana-1.5-8b-instruct-2505"
ENV ENABLE_LORA=true
ENV MAX_LORAS=4
ENV MAX_LORA_RANK=32
ENV LORA_MODULES="v1_judgment=/adapters/v1_judgment,v2_generate=/adapters/v2_generate,v3_summary=/adapters/v3_summary,planner=/adapters/planner"
ENV MAX_MODEL_LEN=4096
ENV GPU_MEMORY_UTILIZATION=0.90
ENV DTYPE="auto"
ENV TOKENIZER_MODE="auto"
