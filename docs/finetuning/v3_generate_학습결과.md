# 문서 생성 sLLM 파인튜닝 v3 — 학습 데이터 재설계

> GPU: RunPod H200 143GB | 태스크: 문서 생성 (회의록/보고서/제안서) | 모델: Kanana-1.5-8B
> v2 대비 변경: 학습 데이터 재설계 (필드 분포 + 입력 길이 다양화)

---

## 1. v2의 문제점

v2 LoRA 적용 후 QA 테스트에서 핵심 필드 60~86% 빈 배열 문제 발견:

| 문서 유형 | 문제 필드 | v2 채움률 | 원인 |
|----------|----------|:---------:|------|
| 회의록 | decisions | 34% | 학습 데이터에서 랜덤 선택으로 34%만 포함 |
| 회의록 | action_items | 34% | 동일 |
| 보고서 | tasks | 14% | 학습 데이터에서 극히 낮은 포함률 |
| 제안서 | schedule | 25% | 동일 |
| 제안서 | budget | 25% | 동일 |

**근본 원인**: `select_random_fields()`가 content/summary/decisions/action_items를 동일 확률(~34%)로 랜덤 선택 → 모델이 "빈 배열이 기본"으로 학습.

---

## 2. v3 데이터 재설계

### 2-1. 필드 계층 분리 (3계층)

v2는 core + meta + content(전부 랜덤)이었으나, v3는 **always + priority + content**로 분리:

```
always_content (100% 포함):
  회의록: content, summary
  보고서: overview, main_content
  제안서: content, expected_effect

priority_content (80% 포함):
  회의록: decisions, action_items
  보고서: tasks, next_plan, issues
  제안서: schedule, budget, background, current_situation

content (랜덤):
  나머지 (agenda, risks, notes, achievements 등)
```

### 2-2. 입력 길이 다양화

| 길이 | 비율 | 사용 패턴 |
|------|:----:|----------|
| short (50~200자) | 30% | 폼에서 제목+한줄 메모 |
| mid (200~800자) | 40% | 챗봇 일반 입력 |
| long (800~1500자) | 20% | 상세 기술 |
| xlong (1500~3000자) | 10% | 회의 전체 내용 붙여넣기 |

### 2-3. 할루시네이션 방지 설계

| 방지 수단 | 방법 |
|-----------|------|
| **길이별 sparse 비율** | short 60% / mid 30% / long 20% / xlong 10% |
| **content str 강제** | description에 "서술형 문자열로" 명시 |
| **budget 근거 기반** | "문서에 수치가 있을 때만" |
| **거부 감지** | GPT 거부 메시지 패턴 3회 재시도 |

---

## 3. 데이터 파이프라인

### 3-1. 처리 흐름 (7단계)

```
① Synthetic 802건 생성 (GPT-4o)
   회의록 402건 + 보고서 200건 + 제안서 200건
   → 혼입 10건 제거 + 10건 재생성

② AI Hub 700건 정제 (GPT-4o-mini)
   → 빈 priority 필드 보충 (557건) + 25% 입력 축약 (175건)

③ 필터링 — C급 제거: Syn 12건, AHub 144건 → 1346건

④ Priority 보완 — AI Hub만, 373건 boost

⑤ AI Hub 후처리
   → content str 변환 446건 + schedule/budget 신형식 변환 175건

⑥ 부족분 추가 생성 — 보고서 80건 + 제안서 80건 = 160건

⑦ 합치기 → 1500건 → train 1350 / eval 150
```

### 3-2. 최종 분포

| 유형 | train | eval | 합계 |
|------|:-----:|:----:|:----:|
| 회의록 | 419 | 42 | **461** |
| 보고서 | 425 | 59 | **484** |
| 제안서 | 506 | 49 | **555** |
| **합계** | **1350** | **150** | **1500** |

### 3-3. 학습 데이터 핵심 필드 채움률

| 필드 | v2 | v3 | 변화 |
|------|:--:|:--:|:----:|
| content/main_content | 32~34% | **100%** | +66pp |
| decisions | 34% | **91%** | +57pp |
| action_items | 34% | **94%** | +60pp |
| tasks | 14% | **63%** | +49pp |
| next_plan | 34% | **98%** | +64pp |
| schedule | 25% | **74%** | +49pp |
| budget | 25% | **47%** | +22pp |

> budget 47%: AI Hub 원본에 예산 수치 자체가 없는 문서가 대다수. Synthetic만 보면 69%.

---

## 4. 학습 설정

| 항목 | 값 |
|------|-----|
| Base Model | kakaocorp/kanana-1.5-8b-instruct-2505 |
| 양자화 | 4-bit (NF4) QLoRA |
| LoRA r / alpha | 32 / 64 |
| Target Modules | q, k, v, o, gate, up_proj |
| Epochs | 5 (eval loss로 best 선택) |
| Batch size | 4 (grad accum 4 = effective 16) |
| Learning rate | 1e-4 (cosine schedule) |
| max_length | 2560 |

v2와 동일 설정. 데이터만 개선하여 효과를 순수 측정.

---

## 5. 학습 결과

### 5-1. Epoch별 지표 추이

| Epoch | Train Loss | Eval Loss | Token Accuracy | 비고 |
|-------|-----------|-----------|----------------|------|
| 1 | 0.543 | 0.520 | 85.6% | |
| 2 | 0.479 | **0.508** | 85.8% | **Best** |
| 3 | 0.422 | 0.511 | 85.8% | overfitting 시작 |
| 4 | 0.395 | 0.525 | 85.7% | |
| 5 | 0.383 | 0.536 | 85.6% | |

> Best checkpoint: **Epoch 2** (step 170, eval_loss = 0.508)

### 5-2. 학습 효율

| 항목 | 수치 |
|------|------|
| 총 학습 시간 | **51분 46초** |
| 처리 속도 | 2.17 samples/sec |
| 총 스텝 수 | 425 steps |
| VRAM 사용량 | 5.7 GB (학습) / 8.2 GB (추론) |
| 학습 환경 | RunPod H200 143GB |

---

## 6. 평가 결과

> eval 150건 (회의록 42 + 보고서 59 + 제안서 49), checkpoint-170 (epoch 2) 사용
> 서빙 어댑터: `/workspace/adapters/v3_generate/` = checkpoint-170과 MD5 일치 확인

### 6-1. 구조 지표

| 지표 | Base | Fine-tuned | 변화 |
|------|:----:|:----------:|:----:|
| JSON 유효율 | 77.3% | **87.3%** | +10.0% |
| 필드 완전성 | 77.3% | 87.3% | +10.0% |
| 필드명 정확도 | 100% | 100% | 동일 |

### 6-2. 내용 품질

| 지표 | Base | Fine-tuned | 변화 |
|------|:----:|:----------:|:----:|
| ROUGE-L | 0.4653 | **0.6649** | **+43%** |
| BERTScore F1 | 0.8959 | **0.926** | +3.4% |
| 평균 출력 길이 | 1593 | 1395 | -12.4% |

### 6-3. 할루시네이션

| 지표 | Base | Fine-tuned | 변화 |
|------|:----:|:----------:|:----:|
| 빈 필드 정확도 | 55.7% | **82.1%** | +26.4% |
| False Fill율 | 44.3% | **17.9%** | **-59%** |

### 6-4. 핵심 필드 채움률

| 필드 | 해당 유형 | 학습데이터 채움률 | Base | FT (ep2) | 목표 | 판정 |
|------|----------|:--------------:|:----:|:--------:|:----:|------|
| decisions | 회의록 | 77.3% | 66.7% | **87.5%** | 80%+ | **달성** |
| action_items | 회의록 | 77.6% | 92.6% | **92.0%** | 80%+ | **달성** |
| tasks | 보고서 | 55.8% | 94.0% | **52.7%** | 70%+ | 미달 |
| next_plan | 보고서 | 85.9% | 100% | **100%** | 70%+ | **달성** |
| schedule | 제안서 | 67.8% | 100% | **70.7%** | 70%+ | **달성** |
| budget | 제안서 | 43.1% | 96.6% | **46.3%** | 50%+ | 미달 |

### 6-5. 핵심 필드 채움률 분석

tasks/schedule/budget의 FT 채움률이 Base 대비 크게 하락한 것처럼 보이지만, **학습데이터의 채움률과 비교하면 모델이 데이터 분포를 정확히 재현**한 결과:

| 필드 | 학습데이터 채움률 | FT 채움률 | 차이 |
|------|:--------------:|:--------:|:----:|
| tasks | 55.8% | 52.7% | -3.1pp |
| schedule | 67.8% | 70.7% | +2.9pp |
| budget | 43.1% | 46.3% | +3.2pp |

Base 모델이 94~100% 채웠던 것은 근거 없이 아무 값이나 채우는 행동이었음 (False Fill 44.3%).
FT 모델은 "근거 없으면 비운다"를 학습하여 False Fill을 17.9%로 줄인 대신, 채움률도 학습데이터 수준으로 수렴.

**결론: 모델은 정상 동작 중. 채움률을 올리려면 학습데이터에서 빈 배열 `[]` 비율을 줄여야 함.**

학습데이터 빈 배열 상세:

| 필드 | 해당 유형 | 키 존재 | 채워짐 | 빈 배열 `[]` |
|------|----------|:------:|:------:|:----------:|
| tasks | 보고서(425) | 89.2% | 55.8% | **33.4%** |
| schedule | 제안서(506) | 91.9% | 67.8% | **24.1%** |
| budget | 제안서(506) | 91.1% | 43.1% | **48.0%** |

boost 스크립트가 priority 필드 키를 추가했으나, 입력에 근거가 없는 경우 빈 배열로 남겨둔 샘플이 상당수 존재.

---

## 7. 향후 계획

1. vLLM 서빙 연동 (v3 어댑터 로드)
2. summary/qa LoRA 추가 학습 → 멀티 어댑터 서빙
3. GPT-4o 대비 정량 비교 후 sLLM 전환 최종 판단

---

## 8. 산출물

| 파일 | 경로 |
|------|------|
| LoRA 어댑터 (best) | `outputs/v3_generate/kanana-1.5-8b-instruct-2505/checkpoints/checkpoint-170/` |
| LoRA 어댑터 (final) | `outputs/v3_generate/kanana-1.5-8b-instruct-2505/final/` |
| 평가 결과 | `outputs/v3_generate/eval_results/` |
| 학습 로그 | `outputs/v3_generate/kanana-1.5-8b-instruct-2505/train_log.json` |
| 학습 설정 | `ai/finetuning/configs/v3_generate.yaml` |
| 평가 스크립트 | `ai/finetuning/scripts/eval_v3_generate.py` |
| 학습 데이터 | `data/training/v2_generate/train.jsonl` (1350건) |
| 평가 데이터 | `data/training/v2_generate/eval.jsonl` (150건) |

## 9. 실행 명령어

```bash
# 학습
python ai/finetuning/train_v2_document.py --task generate --mode train

# 평가 (Fine-tuned + Base 비교)
python ai/finetuning/scripts/eval_v3_generate.py \
    --adapter outputs/v3_generate/kanana-1.5-8b-instruct-2505/checkpoints/checkpoint-170 \
    --base

# Fine-tuned만 평가
python ai/finetuning/scripts/eval_v3_generate.py \
    --adapter outputs/v3_generate/kanana-1.5-8b-instruct-2505/checkpoints/checkpoint-170

# Base만 평가
python ai/finetuning/scripts/eval_v3_generate.py --base
```
