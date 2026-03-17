# vLLM LoRA 서빙 버그 — 한글 깨짐 문제

> 2026-03-18 디버깅 기록. 해결 안 됨.

## 증상

v3_summary LoRA 어댑터를 vLLM serverless endpoint에서 서빙하면 **한글 출력이 깨짐** (replacement characters, 반복 루프).

```
입력: "2024년 1분기 마케팅팀 회의록..."
기대: "분류: 회의록\n태그: #마케팅팀 #신제품런칭...\n요약: ..."
실제: "�з�: ȸ�Ƿ�\n�±�: #5000 #2000...\n" (깨진 한글)
```

## 환경

- **vLLM**: v0.16.0 (RunPod Serverless)
- **이미지**: `registry.runpod.net/runpod-workers-worker-vllm-main-dockerfile:17efb0e7d`
- **Minimum CUDA version**: 12.9
- **베이스 모델**: `kakaocorp/kanana-1.5-8b-instruct-2505`
- **서빙 방식**: RunPod Serverless Endpoint
- **서빙 볼륨**: EU-RO-1 Network Volume

### Endpoint 환경 변수 전체

```
MODEL_NAME=kakaocorp/kanana-1.5-8b-instruct-2505
TOKENIZER_MODE=auto
SKIP_TOKENIZER_INIT=false
TRUST_REMOTE_CODE=true
LOAD_FORMAT=auto
DTYPE=bfloat16
KV_CACHE_DTYPE=auto
MAX_MODEL_LEN=4096
DISTRIBUTED_EXECUTOR_BACKEND=mp
RAY_WORKERS_USE_NSIGHT=false
PIPELINE_PARALLEL_SIZE=1
TENSOR_PARALLEL_SIZE=1
MAX_PARALLEL_LOADING_WORKERS=0
ENABLE_PREFIX_CACHING=false
DISABLE_SLIDING_WINDOW=false
SEED=0
MAX_NUM_BATCHED_TOKENS=0
MAX_NUM_SEQS=256
MAX_LOGPROBS=20
DISABLE_LOG_STATS=false
QUANTIZATION=None
ENABLE_LORA=true
MAX_LORAS=4
MAX_LORA_RANK=32
LORA_DTYPE=auto
MAX_CPU_LORAS=0
FULLY_SHARDED_LORAS=false
DEVICE=auto
SCHEDULER_DELAY_FACTOR=0
ENABLE_CHUNKED_PREFILL=false
NUM_SPECULATIVE_TOKENS=0
NGRAM_PROMPT_LOOKUP_MAX=0
ENABLE_LOG_REQUESTS=false
GPU_MEMORY_UTILIZATION=0.85
BLOCK_SIZE=16
SWAP_SPACE=4
ENFORCE_EAGER=false
DISABLE_CUSTOM_ALL_REDUCE=false
DEFAULT_BATCH_SIZE=50
DEFAULT_MIN_BATCH_SIZE=1
DEFAULT_BATCH_SIZE_GROWTH_FACTOR=3
RAW_OPENAI_OUTPUT=true
OPENAI_RESPONSE_ROLE=assistant
MAX_CONCURRENCY=30
ENABLE_EXPERT_PARALLEL=false
BASE_PATH=/runpod-volume
ENABLE_AUTO_TOOL_CHOICE=false
HF_TOKEN=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
LORA_MODULES=[{"name":"v2_generate","path":"/runpod-volume/outputs/v2_generate/kanana-1.5-8b-instruct-2505/final"},{"name":"v1_judgment","path":"/runpod-volume/adapters/v1_judgment"},{"name":"planner","path":"/runpod-volume/models/planner-v5-lora"},{"name":"v3_summary","path":"/runpod-volume/outputs/v3_summary/kanana-1.5-8b-instruct-2505/final"}]
```

## 어댑터별 서빙 결과

| 어댑터 | r | peft | modules | 한글 | 비고 |
|--------|---|------|---------|------|------|
| v1_judgment | 16 | 구버전 (없음) | 4개 (q,k,v,o) | ✅ OK | HF download |
| v2_generate | 32 | 0.18.1 | 6개 (q,k,v,o,gate,up) | ✅ OK | HF download |
| planner | 16 | 0.18.1 | 4개 (q,k,v,o) | ❌ 깨짐 | HF download |
| v3_summary (r=16) | 16 | 0.18.1 | 6개 (q,k,v,o,gate,up) | ❌ 깨짐 | direct upload |
| v3_summary (r=32 재학습) | 32 | 0.18.1 | 6개 (q,k,v,o,gate,up) | ❌ 깨짐 | direct upload |

**r=32로 재학습해도 안 됨 → r 문제 아님.**

## peft 직접 로드 (vLLM 아닌 환경) — 전부 정상

```python
# RunPod GPU Pod에서 peft로 직접 로드
model = PeftModel.from_pretrained(base_model, adapter_path)
# → 완벽한 한글 출력: "분류: 회의록\n태그: #마케팅팀...\n요약: ..."
```

**어댑터 자체는 100% 정상. vLLM 서빙에서만 깨짐.**

## 시도한 것들 (전부 효과 없음)

| # | 시도 | 결과 |
|---|------|------|
| 1 | adapter_config.json을 v1_judgment 호환 포맷으로 정리 (36→24 keys) | ❌ LoRA 로드 안 됨 (base 응답) |
| 2 | peft 0.13.2 (구버전)로 re-save | ❌ 동일 증상 |
| 3 | ENFORCE_EAGER=true (CUDA graph 비활성화) | ❌ 동일 증상 |
| 4 | tokenizer 파일 삭제 (adapter_config + safetensors만 남김) | ❌ 동일 증상 |
| 5 | r=32로 재학습 (v2_generate와 동일 조건) | ❌ 동일 증상 |
| 6 | adapter_config를 v2_generate 템플릿 기반으로 재생성 | ❌ LoRA 로드 안 됨 |
| 7 | safetensors를 metadata 없이 re-save | ❌ 동일 증상 |

## 확인된 사실

### 어댑터 무결성

- weight shape: 정상 (lora_A: [r, 4096], lora_B: [4096, r])
- weight dtype: float32
- NaN/Inf: 없음
- key naming: `base_model.model.model.layers.*.lora_A/B.weight` (표준)
- 32 layers 전부 존재
- safetensors metadata: `{"format": "pt"}`

### v1_judgment(OK) vs v3_summary(BAD) 차이

1. **adapter_config keys**: v1=24개 (구 peft), v3=36개 (peft 0.18.1)
2. **tokenizer_config 크기**: v1=66KB (풀), v2_generate=355B (미니멀), v3=66KB (풀)
3. **학습 환경**: v1은 다른 세션에서 학습, v3은 이번 세션에서 학습

### vLLM 로그

- `Loaded new LoRA adapter: name 'v3_summary'` → 로드 성공 로그 있음
- `WARNING: vLLM has deprecated support for different tokenizers for different LoRAs` → tokenizer 경고
- 에러 로그 없음 (크래시는 별개 이슈)

## 남은 가설

1. **vLLM 0.16.0의 LoRA weight 적용 버그** — 특정 조건에서 weight를 잘못 매핑
2. **학습 환경(transformers 4.57 + torch 2.4)이 vLLM 0.16.0과 호환 안 됨** — v1_judgment는 다른 환경에서 학습
3. **vLLM 이미지 버전 변경** 필요 — 다른 vLLM 버전에서는 동작할 수 있음
4. **v1_judgment가 HF Hub에서 다운로드된 것**과 관련 — Hub 다운로드 과정에서 뭔가 변환?

## 다음 시도할 것

1. **v1_judgment를 학습한 환경 확인** — 어떤 transformers/peft/torch 버전이었는지
2. **v3_summary를 HF Hub에 올린 후 다시 다운로드** — Hub 변환 효과 확인
3. **vLLM 이미지를 0.14~0.15로 다운그레이드** — endpoint 이미지 변경
4. **vLLM 소스 코드에서 LoRA 로딩 로직 디버깅** — `serving.py`, `lora_manager.py` 확인
5. **v1_judgment 학습 환경을 재현하여 v3_summary 재학습** — 동일 환경이면 동일 결과?

## 관련 파일 위치

### EU-RO 서빙 볼륨 (`/runpod-volume/`)

```
/runpod-volume/adapters/v1_judgment/          ← OK
/runpod-volume/outputs/v2_generate/.../final/ ← OK
/runpod-volume/models/planner-v5-lora/        ← BAD
/runpod-volume/outputs/v3_summary/.../final/  ← BAD (r=32 버전)
```

### Endpoint 설정

```
LORA_MODULES: [
  {"name":"v2_generate","path":"/runpod-volume/outputs/v2_generate/kanana-1.5-8b-instruct-2505/final"},
  {"name":"v1_judgment","path":"/runpod-volume/adapters/v1_judgment"},
  {"name":"planner","path":"/runpod-volume/models/planner-v5-lora"},
  {"name":"v3_summary","path":"/runpod-volume/outputs/v3_summary/kanana-1.5-8b-instruct-2505/final"}
]
```

### SSH 접속

- 학습용 (NC-1): `ssh root@103.196.86.177 -p 29297 -i ~/.ssh/id_ed25519`
- 서빙용 (EU-RO): `ssh root@213.173.110.21 -p 22209 -i ~/.ssh/id_ed25519`
- RunPod API: `https://api.runpod.ai/v2/0e5gus1dyiqj00/openai/v1`
- API Key: `rpa_YSD9TY64PUJAVEE62AVJFPQ58W06GBYLLE49077G1hwqpc`
