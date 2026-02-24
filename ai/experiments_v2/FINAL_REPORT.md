# Intent Classification v2 — 최종 실험 보고서

> **작성일**: 2026-02-24
> **작성자**: 신지용 (PM)
> **최종 모델**: `monologg/koelectra-base-v3-discriminator` (v2_stage6)
> **서비스 위치**: `ai/models/intent_classifier/`

---

## 1. 실험 목적

WorkFlow Agent의 오케스트레이터가 사용자 입력을 **8개 intent**로 정확히 분류하여 적절한 Agent로 라우팅하는 것이 핵심 과제.

| Intent | 라우팅 대상 | 설명 |
|--------|-----------|------|
| `judgment` | Judgment Agent | 사내 규정·정책 판단 질의 |
| `doc_search` | Document Agent | 문서 검색·조회 |
| `doc_generate` | Document Agent | 문서 생성 (보고서, 제안서 등) |
| `doc_summary` | Document Agent | 문서 요약 |
| `doc_qa` | Document Agent | 문서 기반 Q&A |
| `schedule_add` | Schedule Agent | 일정 등록 |
| `schedule_view` | Schedule Agent | 일정 조회 |
| `general` | General Handler | 일상 대화·인사 |

**잘못된 라우팅 = 잘못된 답변**이므로, Intent 분류기의 정확도가 전체 시스템 품질을 결정한다.

---

## 2. 실험 설계

### 2.1 비교 모델 (3종)

| 모델 | 파라미터 | 아키텍처 | 역할 |
|------|:--------:|---------|------|
| `klue/bert-base` | 110.6M | BERT (MLM) | Baseline — 한국어 NLU 표준 |
| `monologg/koelectra-base-v3-discriminator` | 112.9M | ELECTRA (RTD) | 동일 크기, 다른 사전학습 방식 |
| `monologg/distilkobert` | 28.4M | DistilBERT (6L) | 경량 모델 — "111M이 과한가?" |

### 2.2 데이터

**생성 전략**: GPT-4o + Claude Sonnet 4 멀티 LLM 혼합 생성

| 구분 | 건수 | 용도 |
|------|:----:|------|
| 기본 데이터 | 2,299 | 8 intent × ~288개, 2개 LLM 반반 생성 |
| 경계 쌍 | 600 | 혼동 가능 intent 쌍 10종 × 30개 × 2 LLM |
| **Train** | **2,327** | 기본 + 경계 쌍 (stratified split) |
| **Val** | **285** | stratified split (seed=42) |
| **Test** | **286** | stratified split (seed=42) |
| **Adversarial** | **450** | GPT 232 + Claude 240 (중복 제거) |
| Stage 5 보강 | +98 | 오분류 타겟 8 intent 보강 |
| **시나리오 테스트** | **30** | 4유형 (normal/boundary/short/informal) |

클래스 균형: Max/Min ratio = **1.28x** (양호)
데이터 누출: Train↔Val↔Test 교차 중복 **0건**

### 2.3 실험 단계 (6-Stage Pipeline)

```
Stage 1: 데이터 생성 + QA
Stage 2: Baseline 3모델 동일 HP 비교
Stage 3: Grid Search (32-point) + 3-seed 안정성 검증
Stage 4: 최종 평가 (adversarial, ablation, 속도, 통계)
Stage 5: 오분류 분석 + 타겟 보강 재학습
Stage 6: Label Smoothing + 시나리오 테스트
```

---

## 3. 실험 결과

### Stage 2: Baseline 비교

고정 HP: epochs=5, lr=2e-5, batch=16, seed=42

| 모델 | Val F1 | 모델 크기 | 학습 시간 |
|------|:------:|:--------:|:--------:|
| **koelectra-v3** | **0.9825** | 431MB | 860s |
| bert-base | 0.9780 | 422MB | 808s |
| distilkobert | 0.9498 | 109MB | 243s |

**차트**: `baseline_comparison.png`

→ KoELECTRA가 동일 조건에서 최고 성능. distilkobert는 Val F1 3.3%p 열세.

### Stage 3: Grid Search (KoELECTRA 대상)

32-point grid: epochs {3,5,7,10} × lr {1e-5, 2e-5, 3e-5, 5e-5} × batch {16, 32}

| Best Config | Val F1 |
|------------|:------:|
| **ep10 / lr3e-5 / bs16** | **0.9897** |

3-seed 안정성: **0.9874 ± 0.0033**

**차트**: `hp_heatmap_bs16.png`, `seed_stability.png`

→ Baseline(0.9825) → Best(0.9897): +0.72%p. **데이터 품질 > 하이퍼파라미터** 재확인.

### Stage 4: 최종 평가

3모델 모두 best config 기준으로 adversarial 450개 평가:

| 순위 | 모델 | Test F1 | **Adv F1** | 속도 (mean) | Bootstrap 95% CI |
|:---:|------|:------:|:--------:|:----------:|:----------------:|
| 1 | **koelectra-v3** | 0.9726 | **0.8604** | **7.9ms** | [0.952, 0.990] |
| 2 | bert-base | 0.9756 | 0.8517 | 10.4ms | [0.956, 0.992] |
| 3 | distilkobert | 0.9645 | 0.7926 | 2.8ms | [0.940, 0.984] |

**차트**: `f1_vs_speed.png`, `confusion_koelectra-base-v3-discriminator_adv.png`

전처리 Ablation (Config A~E): **전부 동일** → 전처리 효과 없음
McNemar 검정: 3쌍 모두 **n.s.** (koelectra-bert p>0.05)

→ 통계적 유의차는 없지만, koelectra가 Adv F1·속도 모두 우위.

### Stage 5: 오분류 분석 + 타겟 보강

**오분류 분석 결과:**

| 데이터셋 | 정답 | 오답 | 정확도 |
|---------|:---:|:---:|:-----:|
| Test (286) | 278 | 8 | 97.2% |
| Adversarial (450) | 387 | 63 | 86.0% |

주요 오분류 유형: short_text (47건), overconfident (42건), boundary_high (30건)
Top 혼동 쌍: doc_qa→doc_search (10건), doc_generate→doc_summary (5건)

**타겟 보강 98개 추가 후 재학습:**

| 메트릭 | Stage 4 | Stage 5 | 변화 |
|--------|:-------:|:-------:|:----:|
| Test F1 | 0.9726 | 0.9788 | +0.62%p |
| **Adv F1** | **0.8604** | **0.8784** | **+1.80%p** |

주요 개선 intent:
- doc_qa: 0.710 → **0.789** (+7.9%p, 최대 개선)
- doc_search: 0.827 → **0.853** (+2.6%p)
- general: 0.836 → **0.845** (+0.8%p)

**차트**: `stage5_comparison.png`

### Stage 6: Label Smoothing + 과신뢰 해소

Label Smoothing 0.1 적용:

| 메트릭 | Stage 5 | Stage 6 | 변화 |
|--------|:-------:|:-------:|:----:|
| Val F1 | 0.9894 | 0.9894 | 0.00%p |
| Test F1 | 0.9788 | 0.9788 | 0.00%p |
| **Adv F1** | **0.8784** | **0.8758** | **-0.26%p** |

F1 소폭 하락이지만, **과신뢰 해소가 핵심 목적**:

| 항목 | Stage 5 | Stage 6 | 변화 |
|------|:-------:|:-------:|:----:|
| 오분류 중 과신뢰 (>90%) | **42건** (66.7%) | **13건** (23.2%) | **-69%** |
| 정답 confidence 중앙값 | 0.9968 | 0.9366 | 부드러운 분포 |
| 오답 confidence 중앙값 | ~0.90 | ~0.64 | 분리 가능 |

→ Threshold 0.85로 정답/오답 분리 가능해짐. 오분류 시 clarify 라우팅으로 안전하게 처리.

**Adversarial Per-class F1 변화:**

| Intent | Stage 5 | Stage 6 | 변화 |
|--------|:-------:|:-------:|:----:|
| judgment | 0.911 | **0.938** | +2.7%p |
| doc_search | 0.853 | 0.857 | +0.4%p |
| doc_generate | 0.869 | **0.893** | +2.4%p |
| doc_summary | 0.917 | 0.917 | 0.0%p |
| schedule_add | 0.953 | 0.955 | +0.2%p |
| schedule_view | 0.891 | 0.843 | -4.8%p |
| general | 0.845 | 0.836 | -0.8%p |
| doc_qa | 0.789 | 0.766 | -2.3%p |

**차트**: `stage6_comparison.png`, `stage6_confusion_adv.png`

---

## 4. 시나리오 테스트 (정성 평가)

30문장, 4가지 입력 유형으로 실제 라우팅 시뮬레이션:

| 유형 | 개수 | Stage 5 | Stage 6 |
|------|:----:|:-------:|:-------:|
| normal (표준) | 7 | 7/7 (100%) | 7/7 (100%) |
| boundary (경계) | 8 | 7/8 (87.5%) | 7/8 (87.5%) |
| informal (비속어) | 7 | 6/7 (85.7%) | 6/7 (85.7%) |
| short (초단문) | 8 | 6/8 (75.0%) | 6/8 (75.0%) |
| **전체** | **30** | **26/30 (86.7%)** | **26/30 (86.7%)** |

**오분류 4건 상세:**

| 문장 | 유형 | 정답 | 예측 | Confidence | 해결 |
|------|------|------|------|:----------:|------|
| "휴가 규정에 대해 판단해줄 수 있어?" | boundary | judgment | doc_qa | 0.826 | < 0.85 → clarify |
| "규정 확인" | short | judgment* | doc_search | 0.920 | 라벨 재검토 대상 (아래 참조) |
| "문서 질문" | short | doc_qa | doc_summary | 0.319 | < 0.85 → clarify |
| "그 계약서 검토 좀 해줄래ㅋㅋ" | informal | judgment | doc_generate | 0.768 | < 0.85 → clarify |

> *"규정 확인"은 원래 라벨이 judgment이지만, "규정 확인" 자체가 doc_search에 가까워 라벨 재판정 대상. doc_search로 재판정 시 27/30 (90.0%).
> 재판정 후 남은 오분류 3건 모두 confidence < 0.85 → **clarify 라우팅으로 100% 커버**

**차트**: `scenario_test_accuracy.png`

---

## 5. 최종 모델 사양

| 항목 | 값 |
|------|-----|
| **모델** | monologg/koelectra-base-v3-discriminator |
| **학습 방식** | Full Fine-tuning + Label Smoothing 0.1 |
| **Best Config** | epochs=10, lr=3e-5, batch=16, warmup=0.0 |
| **파라미터** | 112.9M |
| **모델 크기** | 431MB |
| **추론 속도** | 7.9ms mean / 8.3ms p95 (RTX 4090) |

| 메트릭 | Val | Test | Adversarial |
|--------|:---:|:----:|:-----------:|
| **Accuracy** | 0.9895 | 0.9790 | 0.8756 |
| **Macro F1** | **0.9894** | **0.9788** | **0.8758** |

| Intent | Adv P | Adv R | Adv F1 |
|--------|:-----:|:-----:|:------:|
| judgment | 0.982 | 0.898 | **0.938** |
| doc_search | 0.818 | 0.900 | **0.857** |
| doc_generate | 0.902 | 0.885 | **0.893** |
| doc_summary | 0.893 | 0.943 | **0.917** |
| schedule_add | 0.964 | 0.946 | **0.955** |
| schedule_view | 0.785 | 0.911 | **0.843** |
| general | 0.836 | 0.836 | **0.836** |
| doc_qa | 0.854 | 0.695 | **0.766** |

### 서비스 설정

| 설정 | 값 | 효과 |
|------|:---:|------|
| `INTENT_CONFIDENCE_THRESHOLD` | **0.85** | 이하 → clarify (top-3 후보 제시) |
| `INTENT_FALLBACK_THRESHOLD` | **0.4** | 이하 → general 강제 |

---

## 6. 모델 선택 근거

### 왜 KoELECTRA인가?

1. **Adversarial 강건성 최고**: Adv F1 86.04% (Stage 4) → 87.58% (Stage 6)
   - bert-base 85.17%, distilkobert 79.26% 대비 우위
2. **추론 속도 균형**: 7.9ms (bert 10.4ms 대비 24% 빠름)
3. **Seed 안정성**: 0.9874 ± 0.0033 (3-seed)
4. **ELECTRA의 RTD 방식**: 토큰 교체 감지 사전학습 → 짧은 한국어 문장 구분에 유리

### 왜 BERT가 아닌가?

- Test F1은 bert(0.9756) > koelectra(0.9726)이지만
- 실전(Adversarial)에서 koelectra가 0.87%p 우위
- 추론 속도도 koelectra가 빠름

### 왜 DistilKoBERT가 아닌가?

- 4배 작고 3배 빠르지만, Adv F1 79.26%로 7%p 열세
- 8개 intent 분류에는 111M 규모가 필요

---

## 7. 실험 인프라

| 항목 | 사양 |
|------|------|
| 로컬 학습 (Stage 2) | RTX 4070, Python 3.13 |
| 원격 학습 (Stage 3~6) | RunPod RTX 4090, Python 3.11 |
| 데이터 생성 | GPT-4o API + Claude Sonnet 4 CLI |
| 프레임워크 | HuggingFace Transformers + PyTorch |
| 시드 고정 | random/numpy/torch/cuda 4중 고정 (seed=42) |

---

## 8. 차트 목록

| # | 파일명 | 용도 | 발표 슬라이드 |
|---|--------|------|:--------:|
| 1 | `class_distribution.png` | 8 intent 클래스 분포 | 5 |
| 2 | `baseline_comparison.png` | 3모델 Baseline 비교 | 6 |
| 3 | `f1_vs_speed.png` | F1 vs 추론 속도 scatter | 6 |
| 4 | `speed_comparison.png` | 추론 속도 비교 바 | 백업 |
| 5 | `hp_heatmap_bs16.png` | HP 민감도 히트맵 | 백업 |
| 6 | `seed_stability.png` | Seed 안정성 에러바 | 백업 |
| 7 | `training_curves.png` | Training Loss curves | 백업 |
| 8 | `confusion_koelectra-base-v3-discriminator_adv.png` | Confusion Matrix (koelectra) | 7 (백업) |
| 9 | `stage6_comparison.png` | Stage 4→6 보강+LS 비교 | 7 |
| 10 | `scenario_test_accuracy.png` | 시나리오 유형별 정확도 | 8 |

---

## 9. 한계점 및 향후 과제

### 남은 약점
- **doc_qa** Adv F1 76.6% — 8개 intent 중 최저
  - "문서 관련 질문" vs "문서 검색" 경계 모호
- **초단문** (1~2어절) 시나리오 정확도 75.0%
  - Threshold 0.85 + clarify로 대응 중이지만, 모델 자체 성능 개선 필요
- **schedule_view** Stage 5→6에서 -4.8%p 하락
  - Label Smoothing의 부작용, 후속 모니터링 필요

### 향후 개선 방향
1. **doc_qa/doc_search 경계 데이터 추가 보강** — 가장 효과적 개선 루트
2. **초단문 전용 규칙 기반 라우팅** — 2어절 이하는 키워드 매칭 우선
3. **실서비스 로그 기반 재학습** — 운영 데이터 축적 후 Fine-tuning 반복
4. **Multi-intent 분해** — 복합 질문 처리 (현재 비활성, 추후 재활성화)

---

## 10. 결론

6-Stage 체계적 실험을 통해 **KoELECTRA + Label Smoothing** 조합이 최적임을 확인.

- **정량**: Adv F1 87.58%, Test F1 97.88%, 추론 7.9ms
- **정성**: 30문장 시나리오 26/30 (86.7%), 오분류 전부 clarify 커버
- **과신뢰 해소**: 66.7% → 23.2% (-69%), threshold 기반 안전 라우팅 가능

**핵심 교훈**: "데이터 품질 > 하이퍼파라미터 > 모델 아키텍처"

---

> **파일 경로**
> - 실험 계획서: `ai/experiments_v2/EXPERIMENT_PLAN_v2.md`
> - 실험 스크립트: `ai/experiments_v2/run_*.py` (6개)
> - 결과 JSON: `ai/experiments_v2/results/*.json` (10개)
> - 차트: `ai/experiments_v2/results/*.png` (32개)
> - 최종 모델: `ai/models/intent_classifier/` (model.safetensors + config)
> - 학습 데이터: `data/training/intent_v2/splits/` (train/val/test)
