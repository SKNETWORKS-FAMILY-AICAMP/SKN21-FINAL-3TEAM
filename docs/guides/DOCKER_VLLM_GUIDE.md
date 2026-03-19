# vLLM Docker 이미지 빌드 & RunPod 서빙 가이드

> 2026-03-18 작성. Network Volume 없이 전 지역 GPU를 사용하기 위한 커스텀 Docker 이미지 방식.

## 구조

```
Docker 이미지 (jiyong1110/vllm-kanana)
├─ runpod/worker-v1-vllm:v2.11.3  (vLLM 엔진)
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
| Docker Hub | jiyong1110 | 이미지 저장소 |
| HuggingFace | jiyong1110 | LoRA 어댑터 저장소 |
| RunPod | - | Serverless endpoint |

- Docker Hub 이미지: `jiyong1110/vllm-kanana:v1`
- HF 어댑터: `jiyong1110/v1_judgment`, `jiyong1110/v2_generate`, `jiyong1110/v3_summary`, `jiyong1110/planner`

## Dockerfile 위치

`docker/Dockerfile` (프로젝트 루트)

## LoRA 추가/수정 시 절차

### 1. HF Hub에 어댑터 업로드

```bash
# RunPod Pod 또는 학습 서버에서
pip install huggingface_hub
python -c "from huggingface_hub import login; login(token='HF_TOKEN')"

python -c "
from huggingface_hub import HfApi
api = HfApi()
api.create_repo('jiyong1110/새어댑터이름', exist_ok=True)
api.upload_folder(folder_path='/경로/새어댑터', repo_id='jiyong1110/새어댑터이름')
"
```

### 2. Dockerfile 수정

```dockerfile
# LoRA 다운로드 부분에 한 줄 추가
RUN huggingface-cli download jiyong1110/v1_judgment --local-dir /adapters/v1_judgment && \
    huggingface-cli download jiyong1110/v2_generate --local-dir /adapters/v2_generate && \
    huggingface-cli download jiyong1110/v3_summary  --local-dir /adapters/v3_summary && \
    huggingface-cli download jiyong1110/planner     --local-dir /adapters/planner && \
    huggingface-cli download jiyong1110/새어댑터이름 --local-dir /adapters/새어댑터이름

# ENV에도 추가
ENV LORA_MODULES="...,새어댑터이름=/adapters/새어댑터이름"
ENV MAX_LORAS=5  # 개수 증가
```

### 3. 이미지 빌드 + push

```bash
# 로컬에서 (Docker Desktop 필요)
cd docker/
docker build --platform linux/amd64 -t jiyong1110/vllm-kanana:v2 .
docker push jiyong1110/vllm-kanana:v2
```

- 베이스 모델은 캐시되어 있어서 **LoRA 다운로드만 다시 실행** (~1-2분)
- push도 변경 레이어만 업로드

### 4. RunPod endpoint 설정 변경

- RunPod Dashboard → Serverless → Endpoint → Edit
- Container Image: `jiyong1110/vllm-kanana:v2` (새 태그)

## RunPod Serverless Endpoint 설정

| 항목 | 추천 값 |
|------|--------|
| Container Image | `jiyong1110/vllm-kanana:v1` |
| GPU | A40, L40S, A6000, RTX 4090 등 다수 체크 |
| Max Workers | 2 |
| Active Workers | 0 (발표 시 1) |
| Idle Timeout | 120-300초 |
| Network Volume | 없음 (이미지에 포함) |

## 왜 이 방식을 쓰는가

| 방식 | 장점 | 단점 |
|------|------|------|
| Network Volume | Cold Start 빠름 | 지역 묶임, GPU 할당 어려움 |
| HF Hub 다운로드 | 지역 자유 | 매번 16GB 다운, 타임아웃 위험 |
| **Docker 이미지 (현재)** | **지역 자유 + 다운로드 없음** | 이미지 재빌드 필요 (캐시로 빠름) |

## 트러블슈팅

### initializing에서 멈춤
- RunPod endpoint env에 만료된 `HF_TOKEN`이 있으면 제거
- GPU 타입을 더 많이 체크

### 이미지 빌드 실패
- Docker Desktop 실행 확인
- `runpod/worker-v1-vllm` 태그 확인: https://hub.docker.com/r/runpod/worker-v1-vllm/tags

### LoRA 어댑터 변경 후 반영 안 됨
- 이미지 태그를 변경했는지 확인 (v1 → v2)
- RunPod endpoint에서 새 태그로 업데이트했는지 확인
