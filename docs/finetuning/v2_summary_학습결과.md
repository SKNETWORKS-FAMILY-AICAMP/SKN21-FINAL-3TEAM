# LoRA v2 문서 요약 (v2_summary) 파인튜닝 결과

## 1. 개요

| 항목 | 내용 |
|------|------|
| **태스크** | 문서 요약 (Document Summary) |
| **목적** | 입력 문서를 마크다운 형식으로 요약 (핵심요약 + 주요포인트 + 키워드) |
| **베이스 모델** | `kakaocorp/kanana-1.5-8b-instruct-2505` |
| **학습 방식** | QLoRA 4-bit (NF4) |
| **학습 일시** | 2026-03-10 |
| **학습 환경** | RunPod H200 143GB |

## 2. 학습 설정

| 하이퍼파라미터 | 값 |
|----------------|-----|
| LoRA rank (r) | 16 |
| LoRA alpha | 32 |
| LoRA dropout | 0.05 |
| Target modules | q_proj, v_proj, k_proj, o_proj, gate_proj, up_proj |
| Epochs | 5 |
| Batch size | 4 |
| Gradient accumulation | 4 (effective batch = 16) |
| Learning rate | 1e-4 (cosine schedule) |
| Warmup ratio | 0.1 |
| Max sequence length | 2,560 tokens |
| Early stopping patience | 3 |

## 3. 데이터 구성

| 구분 | 건수 | 비율 |
|------|------|------|
| **Train** | 900 | 90% |
| **Eval** | 100 | 10% |
| **합계** | 1,000 | 100% |

**데이터 소스 구성:**
- AI Hub 공공 문서 요약 데이터: 700건 (70%)
- GPT-4o 합성 데이터: 200건 (20%)
- 엣지케이스 변형 데이터: 100건 (10%)

**카테고리:** 회의록, 보고서, 간행물, 뉴스, 사설, 이메일, 공지, 계약서 등 8종

## 4. 학습 결과

### 4-1. Epoch별 지표 추이

| Epoch | Train Loss | Eval Loss | Token Accuracy | 비고 |
|-------|-----------|-----------|----------------|------|
| 1 | 1.072 | **1.056** | 73.8% | 초기 수렴 |
| 2 | 0.952 | 1.017 | 74.5% | Best eval_loss 근접 |
| 3 | 0.893 | **1.016** | 74.6% | **Best eval_loss** |
| 4 | 0.872 | 1.023 | 74.4% | 소폭 상승 |
| 5 | 0.848 | 1.027 | 74.4% | 학습 종료 |

> Best checkpoint: **Epoch 3** (eval_loss = 1.016)

### 4-2. Loss 변화 상세

```
Epoch 1    ████████████████████░░░░░  Train: 1.072 → Eval: 1.056
Epoch 2    ███████████████████░░░░░░  Train: 0.952 → Eval: 1.017
Epoch 3    ██████████████████░░░░░░░  Train: 0.893 → Eval: 1.016 ← Best
Epoch 4    █████████████████░░░░░░░░  Train: 0.872 → Eval: 1.023
Epoch 5    ████████████████░░░░░░░░░  Train: 0.848 → Eval: 1.027
```

### 4-3. Token Accuracy 추이

| Step | Epoch | Accuracy | 변화 |
|------|-------|----------|------|
| 10 | 0.18 | 64.0% | 초기값 |
| 50 | 0.89 | 73.2% | +9.2%p 급상승 |
| 100 | 1.76 | 74.9% | 안정화 |
| 180 | 3.16 | 77.1% | 최고 구간 |
| 260 | 4.57 | **78.6%** | **최고치** |
| 285 | 5.00 | 77.6% | 학습 종료 |

## 5. 3-Way 모델 비교 (Eval 100건)

동일 평가 데이터 100건에 대해 Base 모델, Fine-tuned 모델, GPT-4o-mini를 비교 평가하였다.

### 5-1. 비교 결과 요약

| 모델 | 포맷 준수율 | ROUGE-L | 추론 시간 |
|------|-----------|---------|----------|
| **Base Kanana** (LoRA 없음) | 88.0% | 0.3815 | 569초 |
| **Fine-tuned Kanana** (LoRA 적용) | **100.0%** | **0.4194** | 928초 |
| **GPT-4o-mini** (API) | **100.0%** | **0.4779** | 546초 |

### 5-2. 파인튜닝 효과 분석

**Base → Fine-tuned 개선폭:**

| 지표 | Base | Fine-tuned | 개선 |
|------|------|-----------|------|
| 포맷 준수율 | 88.0% | **100.0%** | **+12.0%p** |
| ROUGE-L | 0.3815 | **0.4194** | **+0.038 (+9.9%)** |

- **포맷 준수율**: 88% → 100%로 완전 해결. LoRA 학습으로 마크다운 출력 형식을 완벽히 학습
- **ROUGE-L**: 0.38 → 0.42로 약 10% 개선. 요약 품질이 유의미하게 향상됨

**Fine-tuned vs GPT-4o-mini:**

| 지표 | Fine-tuned | GPT-4o-mini | 차이 |
|------|-----------|-------------|------|
| 포맷 준수율 | 100.0% | 100.0% | 동일 |
| ROUGE-L | 0.4194 | 0.4779 | -0.059 (87.8%) |

- GPT-4o-mini 대비 ROUGE-L **87.8%** 수준 도달
- 포맷 준수율은 동일 (100%)
- 8B 파라미터 sLLM으로 GPT급 포맷 안정성 확보

### 5-3. 핵심 인사이트

1. **파인튜닝의 가장 큰 효과는 포맷 준수율** — Base 모델은 12%가 형식 미준수였으나 LoRA로 100% 해결
2. **ROUGE-L은 GPT 대비 88% 수준** — 8B 모델로 상용 LLM에 근접한 요약 품질
3. **비용 효율성** — GPT API 호출 비용 없이 자체 서빙 가능 (vLLM)

## 6. 학습 효율

| 항목 | 수치 |
|------|------|
| 총 학습 시간 | **15분 29초** |
| 처리 속도 | 4.84 samples/sec |
| 총 스텝 수 | 285 steps |
| VRAM 사용량 | 5.7 GB (학습) / 11.6 GB (추론) |
| 어댑터 크기 | 125 MB |

## 7. 산출물

| 파일 | 경로 |
|------|------|
| LoRA 어댑터 | `outputs/v2_summary/kanana-1.5-8b-instruct-2505/final/` |
| 평가 결과 | `outputs/v2_summary/kanana-1.5-8b-instruct-2505/eval_results.json` |
| 3-Way 비교 | `outputs/v2_summary/kanana-1.5-8b-instruct-2505/comparison_results.json` |
| 학습 로그 | `outputs/v2_summary/kanana-1.5-8b-instruct-2505/train_log.json` |
| 학습 설정 | `ai/finetuning/configs/v2_summary.yaml` |

## 8. 결론 및 향후 계획

### 성과
- Kanana-1.5-8B 기반 문서 요약 LoRA 어댑터 학습 완료
- **포맷 준수율 88% → 100%** — 파인튜닝으로 출력 형식 완전 안정화
- **ROUGE-L 0.38 → 0.42** — Base 대비 약 10% 요약 품질 향상
- **GPT-4o-mini 대비 ROUGE-L 88% 수준** 달성 (8B 모델 기준 우수)
- 15분 만에 학습 완료 — H200 GPU 활용 효율적 학습

### 개선 방향
1. **ROUGE-L 향상**: 학습 데이터 증강 (variants 비중 확대) 또는 epoch/rank 조정
2. **다른 모델과 비교**: Qwen3-8B, EXAONE-3.5-7.8B 동일 조건 학습 후 비교 (`--mode compare`)
3. **vLLM 서빙 연동**: 학습된 어댑터를 vLLM에 로드하여 실서비스 적용 (API 비용 절감)
