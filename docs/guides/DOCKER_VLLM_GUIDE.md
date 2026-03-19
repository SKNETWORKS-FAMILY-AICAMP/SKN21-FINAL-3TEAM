# vLLM Docker 이미지 빌드 & RunPod 서빙 가이드

> 2026-03-18 작성. Network Volume 없이 전 지역 GPU를 사용하기 위한 커스텀 Docker 이미지 방식.

## 왜 이 방식을 쓰는가

| 방식 | 장점 | 단점 |
|------|------|------|
| Network Volume | Cold Start 빠름 | **지역 묶임**, GPU 할당 어려움 |
| HF Hub 다운로드 | 지역 자유 | 매번 16GB 다운, 타임아웃 위험 |
| **Docker 이미지 (현재)** | **지역 자유 + 다운로드 없음** | 이미지 재빌드 필요 (캐시로 빠름) |

## 구조

```
Docker 이미지 (jiyong1110/vllm-kanana:v2)
├─ runpod/worker-v1-vllm:v2.14.0  (vLLM 엔진)
├─ /models/kanana-1.5-8b-instruct-2505/  (베이스 모델 16GB)
└─ /adapters/
    ├─ v1_judgment/   (HF: jiyong1110/v1_judgment)
    ├─ v2_generate/   (HF: jiyong1110/v2_generate)
    ├─ v3_summary/    (HF: jiyong1110/v3_summary)
    └─ planner/       (HF: jiyong1110/planner)
```

## 관련 계정/주소

| 서비스 | 계정 | 용도 |
|--------|------|------|
| Docker Hub | jiyong1110 | 이미지 저장소 (`jiyong1110/vllm-kanana`) |
| HuggingFace | jiyong1110 | LoRA 어댑터 저장소 (4개 repo, public) |
| RunPod | - | Serverless endpoint |

## Dockerfile 위치

`docker/Dockerfile` (프로젝트 루트)

## RunPod Serverless Endpoint 설정

| 항목 | 값 |
|------|---|
| Container Image | `jiyong1110/vllm-kanana:v2` |
| Model | `kakaocorp/kanana-1.5-8b-instruct-2505` |
| GPU | A40, L40S, A6000, RTX 4090 등 다수 체크 |
| Max Workers | 1~2 |
| Active Workers | 0 (발표 시 1) |
| Idle Timeout | 120-300초 |
| Network Volume | **없음** (이미지에 포함) |
| Base Path | `/` |
| Enable LoRA | ✅ |
| Max LoRAs | 4 |
| Max LoRA Rank | 32 |
| GPU Memory Utilization | 0.90 |
| Max Model Length | 4096 |
| Data Type | auto |

### LORA_MODULES 환경변수 (JSON 형식)

```json
[{"name":"v1_judgment","path":"/adapters/v1_judgment"},{"name":"v2_generate","path":"/adapters/v2_generate"},{"name":"v3_summary","path":"/adapters/v3_summary"},{"name":"planner","path":"/adapters/planner"}]
```

**주의: 문자열 형식 (`name=path,name=path`)이 아닌 JSON 배열 형식으로 넣어야 함**

## LoRA 추가/수정 시 절차

### 1. HF Hub에 어댑터 업로드

```bash
# RunPod Pod 또는 학습 서버에서
pip install huggingface_hub
python3 -c "from huggingface_hub import login; login(token='HF_TOKEN')"

python3 -c "
from huggingface_hub import HfApi
api = HfApi()
api.create_repo('jiyong1110/새어댑터이름', exist_ok=True)
api.upload_folder(folder_path='/경로/새어댑터', repo_id='jiyong1110/새어댑터이름')
"
```

### 2. Dockerfile 수정

```dockerfile
# LoRA 다운로드 부분에 한 줄 추가
RUN hf download jiyong1110/v1_judgment --local-dir /adapters/v1_judgment && \
    hf download jiyong1110/v2_generate --local-dir /adapters/v2_generate && \
    hf download jiyong1110/v3_summary  --local-dir /adapters/v3_summary && \
    hf download jiyong1110/planner     --local-dir /adapters/planner && \
    hf download jiyong1110/새어댑터이름 --local-dir /adapters/새어댑터이름

# ENV에도 추가
ENV MAX_LORAS=5  # 개수 증가
```

### 3. 이미지 빌드 + push

```bash
# 빌드 전 디스크 정리 (필수!)
docker rmi jiyong1110/vllm-kanana:이전태그
docker builder prune -af

# 빌드 + push
cd docker/
docker build --platform linux/amd64 -t jiyong1110/vllm-kanana:v3 .
docker push jiyong1110/vllm-kanana:v3
```

- 베이스 모델은 캐시되어 있어서 LoRA 다운로드만 다시 실행 (~1-2분)
- push도 변경 레이어만 업로드

### 4. RunPod endpoint 설정 변경

- RunPod Dashboard → Serverless → Endpoint → Edit
- Container Image: `jiyong1110/vllm-kanana:v3` (새 태그)
- LORA_MODULES 환경변수에 새 어댑터 추가

## 빌드 시 주의사항

### Docker 디스크 부족 → 캐시 무한 반복 방지

이미지가 ~60GB라서 Docker Desktop 가상 디스크에 여유가 없으면 캐시가 자동 삭제되어 매번 베이스 이미지를 다시 pull합니다.

```bash
# 빌드 전 반드시 확인
docker system df

# 이전 이미지 삭제 + 캐시 정리
docker rmi jiyong1110/vllm-kanana:이전태그
docker builder prune -af
```

### 어댑터 rank 현황

```
v1_judgment:  r=16
v2_generate:  r=32  ← 최대
v3_summary:   r=16
planner:      r=16
```

Max LoRA Rank는 최대 rank 이상으로 설정 (현재 32).

## 트러블슈팅

### Worker 시작 시 gpu_memory_utilization 에러
- `GPU Memory Utilization` UI 필드와 환경변수 둘 다 0.90으로 설정
- UI 필드가 ENV보다 우선 적용됨

### LoRA adapter json load error
- `LORA_MODULES` 환경변수를 **JSON 배열 형식**으로 넣어야 함

### EngineCore died unexpectedly
- vLLM 버전 불일치 가능성
- worker-v1-vllm 태그별 vLLM 버전: v2.11.3→0.11.0, v2.14.0→0.14.0(추정)

### initializing에서 멈춤
- RunPod endpoint env에 만료된 `HF_TOKEN`이 있으면 제거
- GPU 타입을 더 많이 체크

### 이미지 빌드 시 huggingface-cli not found
- `hf download` 명령어 사용 (`huggingface-cli`는 PATH에 없을 수 있음)
- `pip install -U huggingface_hub[cli]` 후 `hf download` 사용

## Network Volume 어댑터 위치 (백업용)

```
/workspace/adapters/
├─ v1_judgment/        (원본)
├─ v2_generate/        (outputs에서 복사)
├─ v3_summary/         (outputs에서 복사)
└─ planner/            (models에서 복사)

원본 위치:
/workspace/outputs/v2_generate/kanana-1.5-8b-instruct-2505/final/
/workspace/outputs/v3_summary/kanana-1.5-8b-instruct-2505/final/
/workspace/models/planner-v5-lora/
```
