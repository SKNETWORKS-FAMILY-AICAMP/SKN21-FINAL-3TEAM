# RunPod Serverless LoRA 서빙 설정 가이드

> 작성일: 2026-03-15
> 작성자: 신지용 (PM)

## 개요

파인튜닝한 LoRA 어댑터(`v2_generate`)를 RunPod Serverless + vLLM으로 서빙하는 과정에서 겪은 문제와 해결 방법을 정리한 문서.

---

## 현재 운영 설정

| 항목 | 값 |
|---|---|
| 엔드포인트 ID | `0e5gus1dyiqj00` |
| 리전 | EU-RO-1 |
| GPU | RTX 4090 (24GB) |
| Base 모델 | `kakaocorp/kanana-1.5-8b-instruct-2505` |
| LoRA 어댑터 | `v2_generate` |
| Network Volume | EU-RO-1, 20GB |
| Container Image | `runpod/worker-v1-vllm:stable-cuda12.1.0` (기본 latest) |

### .env 설정

```env
VLLM_BASE_URL=https://api.runpod.ai/v2/0e5gus1dyiqj00/openai/v1
VLLM_MODEL=kakaocorp/kanana-1.5-8b-instruct-2505
VLLM_API_KEY=<RunPod API Key - .env 참고>
VLLM_USE_LORA=true
```

### RunPod Serverless 환경변수

| 환경변수 | 값 | 설명 |
|---|---|---|
| `MODEL_NAME` | `kakaocorp/kanana-1.5-8b-instruct-2505` | base 모델 |
| `ENABLE_LORA` | `1` | LoRA 활성화 |
| `LORA_MODULES` | (아래 참고) | LoRA 어댑터 경로 (JSON 형식) |
| `MAX_LORA_RANK` | `32` | LoRA rank 상한 |
| `MAX_MODEL_LEN` | `4096` | 최대 시퀀스 길이 |
| `GPU_MEMORY_UTILIZATION` | `0.85` | GPU 메모리 사용률 |
| `DTYPE` | `bfloat16` | 모델 데이터 타입 |
| `TRUST_REMOTE_CODE` | `1` | 커스텀 tokenizer 로드 허용 |

#### LORA_MODULES 값 (JSON 형식)

```json
[{"name": "v2_generate", "path": "/runpod-volume/outputs/v2_generate/kanana-1.5-8b-instruct-2505/final"}]
```

> **주의**: 최신 vLLM worker 이미지는 JSON 형식만 지원. 과거 `name=path` 형식은 동작하지 않음.

---

## 마이그레이션 과정 요약

### 배경

- 기존 Network Volume: US-NC-1 (GPU throttled → 서버 배정 불가)
- LoRA 어댑터가 해당 볼륨에 있어서 Serverless 엔드포인트가 base 모델로만 동작

### 이전 경로

```
US-NC-1 (기존 Pod)
  → HuggingFace Hub (jiyong1110/kanana-lora-v2-generate)
    → EU-RO-1 (새 Pod → Network Volume에 저장)
```

- 로컬 PC 경유 대신 **HuggingFace Hub** 활용 → 데이터센터 간 전송 속도 최적화
- 학습 결과/평가 로그는 로컬(`runpod_backup/`)에 별도 다운로드

### 파일 구조 (Network Volume)

```
/runpod-volume/
└── outputs/
    └── v2_generate/
        └── kanana-1.5-8b-instruct-2505/
            └── final/
                ├── adapter_model.safetensors  (260MB, LoRA 가중치)
                ├── adapter_config.json
                ├── tokenizer.json
                ├── tokenizer_config.json
                └── chat_template.jinja
```

> Pod에서는 `/workspace/`, Serverless에서는 `/runpod-volume/`로 마운트됨

---

## 겪은 문제와 해결

### 1. CUDA 버전 호환성 (RTX 5090)

**증상**: `CUDA error: the provided PTX was compiled with an unsupported toolchain`

**원인**: RTX 5090 (Blackwell)은 CUDA >= 12.9 필요. vLLM latest 이미지가 CUDA 12.1 기반이라 호환 불가.

**해결**: GPU를 **RTX 4090**으로 변경. RTX 5090은 아직 vLLM 공식 이미지에서 미지원.

---

### 2. GPU Memory Utilization 1.0 오류

**증상**: `Free memory on device cuda:0 (23.07/23.52 GiB) is less than desired GPU memory utilization (1.0)`

**원인**: RunPod UI에서 기본값이 `0.95`로 표시되지만 실제 기본값은 `1.0`. 시스템 프로세스가 ~0.45GB 사용하므로 100%는 불가.

**해결**: `GPU_MEMORY_UTILIZATION=0.85`로 설정.

---

### 3. LORA_MODULES 형식 오류

**증상**: `adapter json load error: Expecting value: line 1 column 1`

**원인**: 구버전 vLLM은 `name=path` 형식이었으나, 최신 이미지는 **JSON 배열** 형식만 지원.

**해결**:
```
# 잘못된 형식 (구버전)
LORA_MODULES=v2_generate=/runpod-volume/outputs/.../final

# 올바른 형식 (최신)
LORA_MODULES=[{"name":"v2_generate","path":"/runpod-volume/outputs/v2_generate/kanana-1.5-8b-instruct-2505/final"}]
```

---

### 4. 한국어 인코딩 깨짐 (mojibake)

**증상**: 응답에서 한국어가 `ȸ��` 같은 깨진 문자로 출력

**원인**: vLLM 문제가 아니라 **Windows curl의 UTF-8 전송 문제**. Windows 터미널에서 curl로 한국어를 직접 보내면 인코딩이 깨짐.

**해결**:
- curl 테스트 시 유니코드 이스케이프(`\uXXXX`) 사용
- **실제 백엔드(Python httpx/openai 클라이언트)에서는 UTF-8 정상 처리되므로 E2E에 영향 없음**

---

### 5. RunPod `/run` API 라우트 오류

**증상**: `/run` 엔드포인트에 OpenAI 형식 요청 시 `Invalid route`

**원인**: `/run`은 RunPod 네이티브 비동기 API. OpenAI 호환 요청은 `/openai/v1/chat/completions`로 직접 호출해야 함.

**해결**: `VLLM_BASE_URL`에 `/openai/v1` 경로 포함하여 OpenAI 호환 엔드포인트 직접 사용.

---

## 롤백 방법

| 상황 | 조치 |
|---|---|
| LoRA 품질 불량 | `.env`에서 `VLLM_USE_LORA=false` → 재시작 (base 모델 사용) |
| 엔드포인트 문제 | RunPod 콘솔에서 LORA 환경변수 제거 → 재시작 |
| vLLM 전체 포기 | `DOC_AGENT_MODE=api` → GPT-4o로 전환 |

## LoRA 어댑터 현황

| 어댑터 | 상태 | 비고 |
|---|---|---|
| `v2_generate` | ✅ 서빙 중 | 문서 생성 (회의록, 보고서 등) |
| `v2_summary` | ❌ 미학습 | 학습 데이터/설정만 존재, 모델 없음 |
| `v1_judgment` | ⏸️ 대기 | 경은이 2026-03-10 학습 완료, 별도 서빙 필요 시 추가 |

## HuggingFace 백업

- 리포: `jiyong1110/kanana-lora-v2-generate`
- 내용: adapter_model.safetensors, tokenizer, adapter_config
- 용도: Network Volume 유실 시 복구용

## 로컬 백업 (runpod_backup/)

- 경로: `C:\SKN21-FINAL-3TEAM\runpod_backup\`
- 내용: 학습 로그, 평가 결과, 체크포인트 메타 (모델 가중치 제외, 164파일)
- 용도: 발표 시 학습 과정/성능 평가 자료
