# vLLM LoRA 서빙 버그 — 한글 깨짐 문제

> 2026-03-18 디버깅 기록. **해결됨 ✅**
>
> **원인**: `LORA_DTYPE=bfloat16` (명시적 설정)이 float32 weight를 강제 bfloat16 변환하면서 한글 깨짐 발생
> **해결**: `LORA_DTYPE=auto`로 변경 → vLLM이 자동 판단 → v3_summary, planner 모두 한글 정상 출력

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

## 원인 확정 (2026-03-18)

**`LORA_DTYPE=bfloat16` 명시 설정이 원인.**

- 어댑터 weight는 float32로 저장됨
- `LORA_DTYPE=bfloat16`이면 vLLM이 float32→bfloat16 강제 변환
- 이 변환 과정에서 vLLM 0.16.0의 LoRA CUDA kernel(bgmv/sgmv)이 특정 weight 분포에서 수치 오류 발생
- `LORA_DTYPE=auto`로 변경하면 vLLM이 자동 판단하여 안전한 경로로 처리 → 정상

**v1_judgment, v2_generate가 동작했던 이유:**
- v1_judgment: 구 peft 포맷(24키)이라 다른 로딩 경로 사용
- v2_generate: weight 분포가 우연히 bfloat16 변환에 안전했거나, HF Hub clone 과정에서 정규화

## 이전 가설 (참고)

1. ~~vLLM 0.16.0의 LoRA weight 적용 버그~~ → dtype 강제 변환이 원인
2. ~~학습 환경 호환성~~ → dtype 설정 문제
3. ~~vLLM 이미지 버전~~ → 설정만 변경으로 해결
4. ~~HF Hub 다운로드 관련~~ → 무관

## 해결 플랜 (5단계)

스크립트 위치: `ai/serving/fix_lora_hangul.sh`, `ai/serving/fix_lora_dtype.py`, `ai/serving/test_lora_endpoint.sh`

### Step 1: LORA_DTYPE 명시 (가장 빠름, 비파괴)
- RunPod 콘솔에서 `LORA_DTYPE=float16` (또는 `float32`) 변경
- `auto` 대신 명시적 dtype으로 vLLM의 자동 변환 우회
- OK → float32→bfloat16 자동 변환이 원인 (가설 1 확정)

### Step 2: weight를 bfloat16으로 re-save
- `bash fix_lora_hangul.sh 2` (서빙 볼륨 GPU Pod에서)
- v3_summary + planner의 float32 weight를 bfloat16으로 변환
- 원본은 `.bak`으로 백업

### Step 3: HF Hub에 올린 후 다시 clone
- `bash fix_lora_hangul.sh 3`
- v2_generate(OK)가 HF Hub clone으로 가져온 점에 착안
- Hub의 파일 정규화 효과 확인

### Step 4: v1_judgment_resaved 서빙 테스트
- `/workspace/adapters/v1_judgment_resaved/` (peft 0.18.1로 재저장)
- BAD → peft 0.18.1 포맷 자체가 문제 (가설 2 확정)
- OK → weight 자체의 문제 (가설 1 or 3)

### Step 5: vLLM 버전 다운그레이드
- Docker 이미지를 vLLM 0.14~0.15로 변경
- 다른 버전에서 OK → vLLM 0.16.0 버그 확정

### 검증 명령어
```bash
bash test_lora_endpoint.sh all    # 전체 어댑터 테스트
bash test_lora_endpoint.sh v3_summary  # 개별 테스트
```

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
