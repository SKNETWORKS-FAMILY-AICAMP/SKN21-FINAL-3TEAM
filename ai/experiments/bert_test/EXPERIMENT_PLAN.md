# ML 비교 실험 기획서

> Intent Classification 모델의 성능을 다각도로 검증하고, 중간발표용 시각 자료를 생성하기 위한 실험 계획.
> **최종 업데이트: 2026-02-16 (실험 1~6 전체 완료)**

---

## 실험 목적

발표에서 답해야 할 6가지 질문:

1. **"왜 이 방법을 선택했나?"** → 실험 1 (방법론 비교) ✅
2. **"어디가 약하고 어떻게 대응하나?"** → 실험 2 (혼동행렬) ✅
3. **"개선할 줄 아나?"** → 실험 3 (v1.0→v1.1 개선 차트) ✅
4. **"체계적으로 개선했나?"** → 실험 4 (v1.2~v1.4 버전별 학습) ✅
5. **"다른 모델도 해봤나? 충분히 탐색했나?"** → 실험 5 (다중 모델 × 하이퍼파라미터 전탐색) ✅
6. **"실서비스에서도 되나? 최대한 끌어올렸나?"** → 실험 6 (전처리 파이프라인 + 최종 성능) ✅

---

## 데이터 현황

### 기본 데이터
| 용도 | 파일 | 크기 |
|------|------|:----:|
| 학습 (원본) | `data/training/intent/{category}.jsonl` × 7 | 1,453문장 |
| 정규 평가 | 학습 데이터에서 15% 층화 분할 | 버전별 상이 |
| Adversarial 평가 | `data/training/intent/adversarial_test.json` | **212문장** (기존 120 + 신규 92 확장 완료) |

> ⚠️ **Adversarial 테스트셋 변천**: 실험 1~3은 25~70문장, 실험 4는 120문장으로 진행 완료. 실험 5~6에서는 **212문장으로 확장**하여 통계적 신뢰성을 높입니다. (1건당 0.47%p 변동 → 기존 120개 0.83%p 대비 안정적)

### 증강 데이터
| 버전 | 파일 패턴 | 건수 | 내용 |
|------|----------|:----:|------|
| v1.2 | `augment_v12_*.jsonl` × 6 | 300 | 비정형/인터넷 슬랭/초성 (카테고리별 50) |
| v1.3 | `augment_v13_*.jsonl` × 7 | 163 | boundary 타겟 (혼동 패턴별 20~30) |
| **합계** | | **463** | |

### 버전별 총 데이터
| 버전 | Base | +Augment | 총계 | Train | Eval |
|------|:----:|:--------:|:----:|:-----:|:----:|
| v1.0 | 1,405 | - | 1,405 | 1,194 | 211 |
| v1.1 | 1,455 | - | 1,455 | 1,236 | 219 |
| v1.2 | 1,455 | +300 | 1,755 | 1,495 | 260 |
| v1.3/v1.4 | 1,453 | +463 | 1,916 | ~1,629 | ~287 |

---

## 실험 1: 방법론 비교 ✅

**질문**: 파인튜닝이 다른 방법보다 나은가?

### 비교 대상 (6가지)

| # | 방법 | 설명 |
|---|------|------|
| 1 | **Random** | 7개 중 무작위 선택 (이론값 14.3%) |
| 2 | **Rule-based** | 키워드 매칭 (회의→meeting, 규정→judgment 등) |
| 3 | **BERT Base (학습 전)** | klue/bert-base에 classification head만 붙인 상태 |
| 4 | **GPT Zero-shot** | GPT-4o-mini + 시스템 프롬프트만 |
| 5 | **GPT Few-shot** | GPT-4o-mini + 카테고리별 3개 예시 (21문장) |
| 6 | **BERT Fine-tuned** | 우리 모델 (v1.1) |

### 결과

| 방법 | F1 (macro) | Accuracy | 속도 (ms) | 비용 |
|------|:----------:|:--------:|:---------:|:----:|
| GPT Few-shot | **97.53%** | 97.14% | 456.6 | ~$0.03/70문장 |
| GPT Zero-shot | 96.02% | 95.71% | 519.7 | ~$0.01/70문장 |
| **BERT Fine-tuned** | **89.97%** | 88.57% | **6.7** | **$0** |
| Rule-based | 86.81% | 84.29% | 0.0 | $0 |
| Random | 13.48% | 12.86% | 0.0 | $0 |
| BERT Base | 7.22% | 12.86% | 10.4 | $0 |

### 핵심 인사이트
- GPT가 accuracy 7.5%p 우위, 하지만 BERT가 **68배 빠르고 비용 $0 + 데이터 보안**
- **sLLM 선택 정당성**: 정확도 7.5%p를 속도 68배 + 비용 $0 + 로컬 추론으로 교환

![방법론 비교 차트](results/method_comparison.png)

---

## 실험 2: 혼동행렬 ✅

**질문**: 어떤 카테고리끼리 헷갈리는가?

| 항목 | 내용 |
|------|------|
| 방법 | eval + adversarial 각각 혼동행렬 |
| 출력 | 히트맵 이미지 — v1.1(2장) + v1.2(1장) + v1.3(1장) = **4장** |

### 결과 요약
- **v1.1 Eval (219문장)**: 오분류 3건, 거의 완벽한 대각선
- **v1.1 Adversarial (70문장)**: 오분류 8건, **전부 general로 폴백** (안전한 실패 방향)
- **v1.3 Adversarial (120문장)**: 오분류 10건, 주로 multi-intent와 ultra-short

| v1.1 Eval 혼동행렬 | v1.1 Adversarial 혼동행렬 |
|:---:|:---:|
| ![Eval CM](results/confusion_eval.png) | ![Adv CM](results/confusion_adv.png) |

| v1.2 Adversarial 혼동행렬 | v1.3 Adversarial 혼동행렬 (최종) |
|:---:|:---:|
| ![v1.2 CM](results/confusion_adv_v1.2.png) | ![v1.3 CM](results/confusion_adv_v1.3.png) |

---

## 실험 3: v1.0 → v1.1 개선 차트 ✅

**질문**: 문제를 발견하고 개선할 수 있는가?

| 지표 | v1.0 | v1.1 | 변화 |
|------|:----:|:----:|:----:|
| Eval F1 | 99.08% | 98.80% | -0.3%p (트레이드오프) |
| Adversarial (25문장) | 72% (18/25) | 88% (22/25) | **+16%p** |
| judgment→general 오분류 | 5건 | 0건 | **완전 해결** |

> ⚠️ 이 실험의 adversarial은 **25문장 기준**입니다. 실험 4의 120문장 셋과 난이도·크기가 다르므로 직접 비교 불가.

### 핵심 인사이트
- 원인 분석 → 타겟 증강 → 문제 해결의 체계적 프로세스 입증

![v1.0→v1.1 개선 차트](results/improvement_v1.png)

---

## 실험 4: v1.2 ~ v1.4 버전별 학습 ✅

**질문**: 체계적으로 모델을 개선할 수 있는가?

### 전략 (Strategy C: 약점 기반 점진적 개선)

```
v1.2  비정형 데이터 증강 (+300)
  ↓   오분류 패턴 분석 (18건)
v1.3  Boundary 타겟 증강 (+163) + 라벨 QA (3건 수정)
  ↓   "데이터 품질 vs 하이퍼파라미터" 검증
v1.4  하이퍼파라미터 그리드 서치 (6가지 조합)
```

### 결과

| 버전 | Eval F1 | Adv Acc (120개) | Adv F1 | 오분류 | 핵심 |
|------|:-------:|:---------------:|:------:|:------:|------|
| v1.2 | 98.07% | 85.0% | 85.57% | 18 | 비정형 증강, 더 어려운 셋 기준 |
| **v1.3** | **98.63%** | **91.67%** | **91.54%** | **10** | **boundary 증강 + 라벨 QA** |
| v1.4 | 98.26% | 89.2% | 89.02% | 13 | 그리드 서치 (과적합 발생) |

### v1.4 그리드 서치 상세

| epochs | lr | Eval F1 |
|:------:|:-----:|:-------:|
| 3 | 2e-5 | 0.9754 |
| 5 | 1e-5 | 0.9653 |
| 5 | 2e-5 | 0.9754 |
| 5 | 5e-5 | 0.9791 |
| 7 | 2e-5 | 0.9754 |
| **10** | **2e-5** | **0.9826** |

Best config(epochs=10)는 Eval 최고지만 Adversarial 하락 → **과적합 확인**

![전체 버전 비교 차트](results/improvement_all_versions.png)

### 핵심 인사이트
1. **데이터 품질 > 하이퍼파라미터**: boundary 증강(+6%p) >> 그리드 서치(효과 없음)
2. **라벨 QA의 중요성**: 모호한 라벨 3건 수정만으로 오분류 3건 감소
3. **klue/bert-base 기준 최적 데이터 = v1.3**: epochs=5, lr=2e-5, 1,916 데이터
4. → 이 데이터를 다른 모델에도 적용하여 최종 모델을 확정하는 것이 실험 5의 목적

---

## 실험 5~6 사전 작업: Adversarial 테스트셋 확장 (120 → 212)

### 확장 목적
- 120개에서 1건 = 0.83%p 변동 → 212개에서 1건 = 0.47%p 변동 → **통계적 안정성 향상**
- 실험 5에서 모델 3개 비교 시, 작은 차이가 의미 있는지 판단 가능

### 추가된 92문장 유형 분배 (완료)

| 유형 | 추가 건수 | 설명 |
|------|:--------:|------|
| multi-intent (복합 의도) | 15 | "규정 검색해서 판단해줘" 류 — 기존 약점 보강 |
| ultra-short (극단적 짧은 입력) | 15 | 1~2어절 ("규정", "일정", "문서 줘") |
| 오타/비정형 입력 | 15 | "연챠 귝정", "ㅎㅇㄹ 만듦" — 전처리 효과 측정용 |
| formal (격식체/존칭) | 10 | "~해주실 수 있으신지요", "검토 부탁드립니다" |
| context-dependent (맥락 의존) | 10 | "아까 그거", "위에 말한 거" |
| category boundary (경계) | 15 | doc_search↔doc_generate, judgment↔general 등 |

### 제작 규칙
- 기존 120문장과 중복 없음
- 카테고리별 최소 2문장 이상 포함
- 정답 라벨은 "최종 의도" 기준 (multi-intent 규칙 동일)
- 제작 후 라벨 QA 필수 (2인 교차 검증 또는 Claude 검증)

---

## 실험 5: 다중 모델 × 하이퍼파라미터 전탐색 ✅

**질문**: 다른 모델도 해봤나? 파라미터를 충분히 탐색했나?

> **실행 환경**: RunPod RTX 4090 (2026-02-12~13)
> **총 학습 횟수**: 153번 (모델당 51번 = Step1 48 + Step2 3)

### 실험 목적
1. klue/bert-base 외 다른 한국어 사전학습 모델과의 성능 비교
2. 모델별 최적 하이퍼파라미터 탐색 → 최종 모델 선택의 정당성 강화
3. "충분히 다양하게 실험했다"는 근거 확보

### 비교 모델 (3종)

| # | 모델 | 파라미터 수 | 특징 |
|---|------|:---------:|------|
| 1 | **klue/bert-base** | 111M | 현재 사용 중, KLUE 벤치마크 학습 |
| 2 | **klue/roberta-base** | 111M | BERT 변형, 동적 마스킹 + 더 많은 데이터로 학습 |
| 3 | **monologg/koelectra-base-v3-discriminator** | 111M | 한국어 특화, replaced token detection 방식 |

### 하이퍼파라미터 탐색 범위

| 파라미터 | 값 | 개수 | 근거 |
|---------|-----|:---:|------|
| epochs | [3, 5, 7, 10] | 4 | 부족~과적합 범위 커버 |
| learning_rate | [1e-5, 2e-5, 3e-5, 5e-5] | 4 | BERT 원논문 권장 범위 포함 |
| batch_size | [8, 16, 32] | 3 | 소형 데이터셋 표준 범위 |
| warmup_ratio | [0.0, 0.06, 0.1] | 3 | 학습 안정성 영향 확인 |
| weight_decay | 0.01 (고정) | - | BERT 표준값 |
| max_length | 64 (고정) | - | 평균 입력 길이 대비 충분 |
| seed | 42 (고정) | - | 재현성 보장 |

### 실험 진행 방식 (2단계)

**Step 1: 모델별 주요 파라미터 탐색 (warmup 고정 0.06)**
```
epochs × lr × batch_size = 4 × 4 × 3 = 48 조합
× 3모델 = 144번 학습
예상 시간: ~3~5시간 (RunPod A100)
```

**Step 2: best config 근처 warmup 미세 조정**
```
모델별 best config에서 warmup [0.0, 0.06, 0.1] 변경
3모델 × 3 = 9번 학습
예상 시간: ~15분
```

**총 153번 학습, 약 3~5시간**

### 고정 조건

| 항목 | 값 |
|------|-----|
| 학습 데이터 | v1.3 (1,916개) — 모든 모델 동일 |
| Train/Eval 분할 | 85:15 층화 분할 — 동일 seed로 동일 분할 |
| Eval 테스트셋 | ~287문장 (학습 데이터에서 분할) |
| Adversarial 테스트셋 | **212문장** (기존 120 + 신규 92 확장 완료) |
| 평가 지표 | Eval F1 (macro), Adversarial Accuracy, Adversarial F1 (macro) |
| GPU | RunPod RTX 4090 / A100 |

### 예상 결과물

| 출력 | 설명 |
|------|------|
| `results/model_comparison.json` | 3모델 × best config 수치 |
| `results/grid_search_full.json` | 153번 전체 결과 |
| `results/model_comparison.png` | 모델별 성능 비교 차트 |
| `results/heatmap_*.png` | 모델별 lr×epochs 히트맵 (3장) |
| `results/confusion_adv_*.png` | 모델별 best config 혼동행렬 (3장) |
| `results/inference_speed.png` | 모델별 추론 속도 비교 차트 |

### 실험 결과

| 모델 | Best Config | Eval F1 | Adv Acc | Adv F1 | 추론 속도 |
|------|------------|:-------:|:-------:|:------:|:---------:|
| **klue/bert-base** | epochs=5, lr=2e-5, batch=16, warmup=0.0 | 0.9823 | 0.9009 | **0.9015** | 7.48ms |
| klue/roberta-base | epochs=3, lr=5e-5, batch=32, warmup=0.1 | 0.9822 | 0.8962 | 0.8990 | 8.09ms |
| koelectra-base-v3 | epochs=10, lr=1e-5, batch=16, warmup=0.06 | 0.9825 | 0.8868 | 0.8856 | 7.32ms |

### 최종 모델 선정

```
1순위: Adversarial F1 (실전 성능) → BERT 0.9015 > RoBERTa 0.899 > KoELECTRA 0.886
2순위: Eval F1 (기본 성능) → 3모델 거의 동일 (~0.982)
3순위: 추론 속도 (서비스 응답성) → 3모델 거의 동일 (7~8ms)
→ 최종 선택: klue/bert-base (epochs=5, lr=2e-5, batch=16, warmup=0.0)
```

### 주요 발견
- **Eval F1은 3모델 거의 동일** (0.982~0.983) → 일반 입력에서는 차이 없음
- **Adversarial F1에서 BERT가 우위** → 비정형/경계 입력 처리 능력이 결정적 차이
- KoELECTRA는 수렴에 epochs=10 필요 → 학습 비용 대비 효과 낮음
- 최종 모델(`ai/models/intent_classifier/`)에 BERT best config로 배포 완료

### 차트

| 3모델 성능 비교 | 추론 속도 + 학습 시간 |
|:---:|:---:|
| ![Model Comparison](results/model_comparison.png) | ![Speed Comparison](results/inference_speed.png) |

| 그리드 서치 Adv F1 분포 (51 runs each) | 종합 레이더 |
|:---:|:---:|
| ![Grid Distribution](results/grid_distribution.png) | ![Radar](results/model_radar.png) |

| BERT 히트맵 | RoBERTa 히트맵 | KoELECTRA 히트맵 |
|:---:|:---:|:---:|
| ![BERT](results/heatmap_bert-base.png) | ![RoBERTa](results/heatmap_roberta-base.png) | ![KoELECTRA](results/heatmap_koelectra-base-v3-discriminator.png) |

| BERT 혼동행렬 | RoBERTa 혼동행렬 |
|:---:|:---:|
| ![BERT CM](results/confusion_adv_bert-base_exp5.png) | ![RoBERTa CM](results/confusion_adv_roberta-base_exp5.png) |

### 스크립트

| 파일 | 역할 |
|------|------|
| `run_model_comparison.py` | Step 1~2 전체 그리드 서치 + 평가 자동화 |
| `run_visualize.py` (업데이트) | 실험 5 차트 추가 생성 |

---

## 실험 6: 전처리 파이프라인 + 최종 성능 검증 ✅

**질문**: 실서비스에서도 되나? 최대한 끌어올렸나?

> **실행 환경**: 로컬 데스크탑 RTX 4070 12GB (2026-02-16)
> **총 학습 횟수**: 3번 (seed 42, 123, 456) × 5 ablation config = 15회 평가

### 실험 목적
1. 실험 5에서 확정된 최적 모델에 전처리를 추가하여 **최종 성능 상한선** 확인
2. 전처리 단계별 기여도를 개별 측정 → "어떤 전처리가 얼마나 효과 있는지" 정량화
3. seed 3개 반복 실행 → 결과 신뢰성(안정성) 검증

### 전제 조건
- 실험 5 완료 후 확정된 **최적 모델 + best config** 사용
- 모델 자체는 재학습하지 않음 — **추론 시 입력만 전처리**

### 전처리 파이프라인 (4단계)

| 단계 | 처리 | 예시 |
|:---:|------|------|
| P1 | **맞춤법 교정** | "연챠 규정" → "연차 규정" |
| P2 | **초성 복원** | "ㅎㅇㄹ 만들어줘" → "회의록 만들어줘" |
| P3 | **슬랭/축약어 정규화** | "걍 그거 해주셈" → "그냥 그거 해주세요" |
| P4 | **공백/특수문자 정리** | "회의록 ㅋㅋ   만들어줘!!" → "회의록 만들어줘" |

### 실험 설계: Ablation Study (제거 실험)

각 전처리를 하나씩 켜면서 **어떤 단계가 얼마나 기여하는지** 측정:

| # | 조합 | 설명 |
|---|------|------|
| A | 없음 (baseline) | 전처리 없이 모델만 (실험 5 best 그대로) |
| B | P4만 | 공백/특수문자 정리만 |
| C | P4 + P1 | + 맞춤법 교정 |
| D | P4 + P1 + P2 | + 초성 복원 |
| E | P4 + P1 + P2 + P3 | 전체 파이프라인 (풀 전처리) |

### 신뢰성 검증: seed 3개 반복

```
실험 5 best config를 seed 3개(42, 123, 456)로 재학습
→ 각각 전처리 조합 A~E 평가
→ 평균 ± 표준편차 보고
```

| 조합 | seed=42 | seed=123 | seed=456 | 평균±std |
|------|:-------:|:--------:|:--------:|:--------:|
| A (baseline) | 0.8996 | 0.8689 | 0.8510 | 0.8732±0.0246 |
| B (P4) | 0.8996 | 0.8735 | 0.8510 | 0.8747±0.0243 |
| C (P4+P1) | 0.9039 | 0.8770 | 0.8538 | 0.8782±0.0251 |
| D (P4+P1+P2) | 0.9041 | 0.8818 | 0.8587 | 0.8815±0.0227 |
| **E (전체)** | **0.9082** | **0.8859** | **0.8627** | **0.8856±0.0228** |

> **위 수치는 Adversarial F1 (macro) 기준**

### 고정 조건

| 항목 | 값 |
|------|-----|
| 모델 | 실험 5 최적 모델 |
| 하이퍼파라미터 | 실험 5 best config |
| 학습 데이터 | v1.3 (1,916개) — 전처리 적용하지 않음 (원본 학습) |
| 테스트 데이터 | Eval ~287문장 + Adversarial **212문장** — **추론 시에만 전처리 적용** |
| 평가 지표 | Eval F1, Adversarial Acc, Adversarial F1 |

> **중요**: 학습 데이터는 그대로 두고, **테스트 입력에만 전처리를 적용**합니다. 실서비스에서 사용자 입력이 들어올 때 전처리하는 것과 동일한 상황을 재현합니다.

### 예상 결과물

| 출력 | 설명 |
|------|------|
| `results/preprocessing_ablation.json` | 조합 A~E × seed 3개 전체 결과 |
| `results/preprocessing_ablation.png` | 전처리 단계별 성능 변화 차트 |
| `results/seed_stability.png` | seed별 결과 분포 (에러 바 차트) |
| `results/final_confusion_adv.png` | 최종(풀 전처리) 혼동행렬 |

### 실험 결과 요약

```
A (전처리 없음):  Adversarial F1 = 0.873 ± 0.025 (212문장, 3 seed 평균)
E (풀 전처리):    Adversarial F1 = 0.886 ± 0.023 (212문장, 3 seed 평균)
→ 전처리로 +1.3%p 개선, 단계별 누적 효과 확인
```

### 실험 5 → 6 수치 비교 해석

> **Q: 실험 5에서 90.15%였는데 실험 6에서 88.56%로 떨어진 것 아닌가?**
> **A: 아닙니다.** 비교 기준이 다릅니다.

| 비교 | Adv F1 | 조건 |
|------|:------:|------|
| 실험 5 보고값 | 90.15% | seed=42 **단일** |
| 실험 6 최종 보고값 | 88.56% | seed 3개 **평균** |

**같은 seed=42 기준으로 비교하면:**

| 항목 | 실험 5 (seed=42) | 실험 6 baseline A (seed=42) | 실험 6 풀전처리 E (seed=42) |
|------|:----------------:|:---------------------------:|:---------------------------:|
| Adv F1 | 90.15% | 89.96% | **90.82% (+0.67%p)** |

seed=42 기준, 전처리 적용 후 오히려 **+0.67%p 상승**. 3-seed 평균이 낮아 보이는 것은 seed=123(86.89%), seed=456(85.10%)이 원래 낮기 때문이며, 이것이 **seed 1개로 보고할 때의 한계**를 실험 6에서 밝혀낸 것.

### 주요 발견
- **전처리 효과**: A→E로 단계 추가될수록 Adversarial F1 꾸준히 상승, **모든 seed에서 일관되게 개선** (+0.86~1.70%p)
- **단계별 기여도**: P1(맞춤법) > P2(초성복원) > P3(슬랭) > P4(공백정리) 순
- **seed 편차 발견 (실험 6의 핵심 기여)**:
  - seed=42(0.908) vs seed=456(0.863) → ~4.5%p 차이 존재
  - 소규모 데이터셋(1,916개) 특성상 초기화에 따른 편차가 불가피
  - 실험 5의 단일 seed 보고(90.15%)가 **낙관적 수치**였음을 밝힘
  - 3 seed 평균±std로 보고하여 **정직하고 신뢰성 있는 성능 보고** 달성
- **Eval F1**: 전처리 적용 시 미세 하락 (0.970→0.967) — 정규 입력을 불필요하게 변환하는 부작용
  - 실서비스에서는 adversarial 입력이 주요 대상이므로 전처리 적용이 유리
- **혼동행렬**: general↔다른 카테고리 혼동이 주요 오분류 패턴 (general에서 7건 오분류)

### 스크립트

| 파일 | 역할 |
|------|------|
| `preprocessing.py` | 전처리 파이프라인 모듈 (P1~P4 각각 on/off 가능) |
| `run_preprocessing_ablation.py` | 조합 A~E × seed 3개 자동 평가 |
| `run_visualize.py` (업데이트) | 실험 6 차트 추가 생성 |

---

## 실험 7: 최종 비교 — BERT(실험6) vs GPT-4o-mini (동일 212문장) ✅

**질문**: 개선을 거친 최종 BERT가 GPT와 비교해도 통하는가?

> **실행 환경**: 로컬 RTX 4070 + OpenAI API (2026-02-16)
> **테스트셋**: Adversarial 212문장 (실험 5~6과 동일)

### 실험 목적
1. 실험 1(70문장)에서 GPT가 우세했던 비교를, **확장된 212문장 + 최종 모델**로 재검증
2. 전처리 파이프라인(실험 6) 적용 상태의 BERT와 GPT의 공정 비교
3. sLLM 선택의 최종 정당성 확보

### 비교 대상 (4가지)

| # | 방법 | 모델 | 설명 |
|---|------|------|------|
| 1 | BERT Fine-tuned (전처리 없음) | klue/bert-base | 실험 5 best config (seed=42) |
| 2 | **BERT Fine-tuned + 풀 전처리** | klue/bert-base | 실험 6 Config E 적용 |
| 3 | GPT Zero-shot | gpt-4o-mini | 시스템 프롬프트만 |
| 4 | GPT Few-shot | gpt-4o-mini | 시스템 프롬프트 + 카테고리별 3개 예시 (21문장) |

### 결과

| 방법 | F1 (macro) | Accuracy | 속도 | 오분류 | 비용 |
|------|:----------:|:--------:|:----:|:------:|:----:|
| **BERT + 전처리 (실험6)** | **90.07%** | **90.09%** | **13.1ms** | **21건** | **$0** |
| BERT (전처리 없음) | 89.20% | 89.15% | 12.8ms | 23건 | $0 |
| GPT-4o-mini Few-shot | 86.30% | 85.38% | 583.7ms | 31건 | ~$0.09 |
| GPT-4o-mini Zero-shot | 85.11% | 84.91% | 435.9ms | 32건 | ~$0.03 |

### 실험 1 → 실험 7 비교 (환경 변화)

| 항목 | 실험 1 | 실험 7 |
|------|:------:|:------:|
| Adversarial 셋 | 70문장 | **212문장** (난이도 상승) |
| BERT 버전 | v1.1 | v1.3 + 전처리 (실험 5 best + 실험 6) |
| BERT F1 | 89.97% | **90.07%** |
| GPT Few-shot F1 | 97.53% | **86.30%** (↓11.2%p) |
| 결론 | GPT > BERT (7.5%p) | **BERT > GPT (3.8%p) — 역전** |

### 오분류 패턴 분석

| 구분 | 건수 | 특징 |
|------|:----:|------|
| BERT만 틀림 | 11건 | 맥락 의존("아까 그거"), 복합 질문 |
| **GPT만 틀림** | **21건** | **1어절 입력("일정","규정","보고서","회의록")을 general로 오분류** |
| 둘 다 틀림 | 10건 | 진짜 어려운 문장 (복합 의도, 맥락 의존) |

### 핵심 인사이트
- **BERT가 GPT를 역전**: 70문장에서는 GPT가 7.5%p 우세 → 212문장에서는 BERT가 **3.8%p 우세**
- **GPT의 약점 발견**: 짧은 입력(1~2어절)에서 의도 추론 실패 → general로 폴백. BERT는 학습 데이터로 단어-의도 매핑을 확실히 학습함
- **전처리의 기여**: 전처리 없는 BERT(89.20%)도 GPT(86.30%)를 이기지만, 전처리 적용 시 격차 확대 (90.07% vs 86.30%)
- **sLLM 정당성 강화**: 정확도에서도 BERT가 우세 + 속도 45배 + 비용 $0 → 모든 지표에서 BERT 우위

### 스크립트

| 파일 | 역할 |
|------|------|
| `run_final_comparison.py` | 4가지 방법 비교 + 오분류 상세 분석 |

---

## 실험 전체 요약

| 실험 | 질문 | 상태 | 소요 시간 |
|:---:|------|:---:|:---------:|
| 1 | 왜 이 방법? (6가지 비교) | ✅ 완료 | - |
| 2 | 어디서 틀리나? (혼동행렬) | ✅ 완료 | - |
| 3 | 고칠 줄 아나? (v1.0→v1.1) | ✅ 완료 | - |
| 4 | 체계적 개선? (v1.2~v1.4) | ✅ 완료 | - |
| 5 | 다른 모델도? 충분히 탐색? | ✅ 완료 | ~4시간 (RunPod RTX 4090) |
| 6 | 최대한 끌어올렸나? 실서비스? | ✅ 완료 | ~5분 (로컬 RTX 4070) |
| 7 | 최종 BERT가 GPT를 이기나? | ✅ 완료 | ~5분 (로컬 + API) |
| 8 | 결론이 통계적으로 유의미한가? | ✅ 완료 | ~2분 (로컬) |
| 9 | 독립 셋에서도 되나? 폴백이 실제로 작동하나? | ✅ 완료 | ~2분 (로컬) |

**전체 실험 완료 (2026-02-16)**

---

## 최종 모델 성능 (실험 5~9 완료 후 확정)

### 배포 모델: klue/bert-base (v1.3 데이터, 실험 5 best config)

| 지표 | 값 | 비고 |
|------|-----|------|
| Eval F1 (macro) | **98.23%** | 정규 입력 성능 |
| Adversarial F1 (seed=42, 전처리) | **90.07%** | 실험 7 기준 (212문장) |
| Adversarial F1 (3 seed 평균, 전처리) | **88.56% ± 2.28%** | 실험 6, 3-seed 평균 |
| Adversarial F1 95% CI (bootstrap) | **[85.52%, 93.84%]** | 실험 8, 10,000회 bootstrap |
| **Blind F1 (독립 테스트셋)** | **92.84%** | **실험 9, 70문장 (모델 비의존적 제작)** |
| 추론 속도 | **7.48ms/문장** | RTX 4090 기준 |
| 운영 비용 | **$0** | 로컬 모델 |
| 최적 confidence threshold | **0.70** | 실험 9, Precision 93.0% / Recall 98.0% |

> **참고 1**: Adversarial 테스트셋이 120→212문장으로 확장되면서 이전 기록(91.67%)과 직접 비교 불가. 212문장 기준이 더 엄격한 평가임.
> **참고 2**: 실험 5(90.15%)와 실험 6 평균(88.56%)의 차이는 성능 하락이 아님. seed=42 단일 보고 vs 3-seed 평균의 차이이며, **같은 seed=42 기준으로는 전처리 적용 후 90.15% → 90.82%로 상승**. 실험 6은 단일 seed의 낙관적 보고를 보정하고, 전처리의 일관된 효과(+1.3%p)를 검증한 실험.
> **참고 3 (실험 8)**: BERT vs GPT McNemar p=0.1116 → 통계적으로 유의미한 차이 없음. sLLM 정당성은 "동급 정확도 + 속도/비용/보안 우위"로 결론.
> **참고 4 (실험 9)**: Overconfident error(conf≥0.9인데 틀림)가 오분류의 57.7% → confidence만으로 폴백하기엔 한계. 오케스트레이터에서 대화 맥락 기반 추가 검증 필요.

---

## 실험 8: 통계적 유의성 검증 ✅

**질문**: 지금까지의 결론이 통계적으로 유의미한가?

> **실행 환경**: 로컬 (2026-02-16)
> **방법**: McNemar's Test, Bootstrap CI, Seed Variance 비교

### Seed 분산 분석

| 항목 | 값 |
|------|-----|
| Adv F1 (seed 42/123/456) | 0.9082 / 0.8859 / 0.8627 |
| 평균 ± std | **0.8856 ± 0.0186** |
| Range | **0.0455 (4.55%p)** |

### Bootstrap CI (BERT 단일 모델, 10,000회)

| 항목 | 값 |
|------|-----|
| F1 mean | 0.8987 |
| **95% CI** | **[0.8552, 0.9384]** |

### McNemar's Test (BERT vs GPT)

| 항목 | 값 |
|------|-----|
| BERT 맞고 GPT 틀림 | 21건 |
| BERT 틀리고 GPT 맞음 | 11건 |
| chi² | 2.5312 |
| **p-value** | **0.1116 (유의미하지 않음)** |

### 모델 간 차이 vs Seed 편차

| 비교 | F1 차이 | seed std 대비 | 결론 |
|------|:-------:|:------------:|------|
| BERT vs RoBERTa | 0.0025 | 0.1배 | 노이즈 수준 |
| BERT vs KoELECTRA | 0.0159 | 0.9배 | 노이즈 수준 |

### 핵심 결론
1. **BERT vs GPT**: 통계적으로 유의미한 차이 없음 (p=0.1116). sLLM 정당성 = "동급 정확도 + 속도/비용/보안"
2. **3모델 동급**: seed 편차 > 모델 간 차이. BERT 선택은 합리적이지만 "최고"는 과장
3. **정직한 보고**: 단일 수치 90.15%가 아닌 95% CI [85.5%, 93.8%] 범위로 보고

### 스크립트

| 파일 | 역할 |
|------|------|
| `run_statistical_tests.py` | McNemar, Bootstrap CI, Seed Variance 전체 분석 |

---

## 실험 9: 독립 테스트셋 Blind 평가 + Confidence 분석 ✅

**질문**: 모델 개발에 관여하지 않은 독립 셋에서도 잘 되는가? 폴백 전략이 실제로 작동하는가?

> **실행 환경**: 로컬 RTX 4070 (2026-02-16)

### Part A: 독립 테스트셋

- **70문장** (7개 카테고리 × 10문장)
- 기존 adversarial과 중복 0건, adversarial 패턴 의도적 미포함
- 순수 업무 시나리오 기반

| 테스트셋 | F1 (macro) | Accuracy | 오분류 |
|---------|:----------:|:--------:|:-----:|
| Adversarial (212) | 90.07% | 90.09% | 21건 |
| **Blind (70)** | **92.84%** | **92.86%** | **5건** |

오분류 5건 중 4건이 confidence > 0.97 (overconfident error).

### Part B: Confidence Threshold 분석

282문장(adversarial 212 + blind 70) 통합 분석.

| Threshold | Coverage | Precision | Recall | Overconfident | False Rej |
|:---------:|:--------:|:---------:|:------:|:------------:|:---------:|
| 0.50 | 99.3% | 91.1% | 99.6% | 25건 | 1건 |
| **0.70** | **95.7%** | **93.0%** | **98.0%** | **19건** | **5건** |
| 0.90 | 91.1% | 94.2% | 94.5% | 15건 | 14건 |

- **추천 threshold: 0.70** (기존 설정과 일치)
- **Overconfident error 15건** (conf≥0.9인데 틀림) -- 오분류의 57.7%
- **False rejection 5건** (conf<0.7인데 맞음) -- 정답의 2.0%

### 핵심 결론
1. **독립 셋에서 F1 92.84%**: 일반 업무 시나리오에서 충분한 성능
2. **Threshold 0.7 적정**: Precision 93.0%, Recall 98.0%
3. **Overconfident error가 핵심 한계**: confidence만으로 폴백 판단 불가. 오케스트레이터에서 대화 맥락 기반 추가 검증 필요

### 스크립트

| 파일 | 역할 |
|------|------|
| `run_blind_evaluation.py` | 독립 테스트셋 평가 + 혼동행렬 |
| `run_confidence_analysis.py` | Threshold 분석 + confidence 분포 |

---

## 결과 파일 위치

```
ai/experiments/
├── EXPERIMENT_PLAN.md              ← 이 문서
├── run_method_comparison.py        ← 실험1 (Rule+BERT) + 실험2 (혼동행렬)
├── run_gpt_comparison.py           ← 실험1 (GPT zero/few-shot)
├── run_visualize.py                ← 차트 생성 (전체 실험 통합)
├── run_train_versioned.py          ← 실험4 (버전별 학습 파이프라인)
├── run_model_comparison.py         ← 실험5 (다중 모델 그리드 서치)
├── preprocessing.py                ← 실험6 (전처리 파이프라인 모듈)
├── run_preprocessing_ablation.py   ← 실험6 (ablation + seed 반복)
├── run_final_comparison.py         ← 실험7 (BERT vs GPT 최종 비교)
├── run_statistical_tests.py        ← 실험8 (통계적 유의성 검증)
├── run_blind_evaluation.py         ← 실험9 (독립 테스트셋 blind 평가)
├── run_confidence_analysis.py      ← 실험9 (confidence threshold 분석)
├── run_gpt_fair_comparison.py      ← (준비) GPT adversarial few-shot 공정 비교
└── results/
    ├── method_comparison.json      ← 실험1 수치
    ├── gpt_comparison.json         ← 실험1 GPT 수치
    ├── method_comparison.png       ← 실험1 막대 그래프
    ├── confusion_eval.png          ← 실험2 혼동행렬 (v1.1 eval)
    ├── confusion_adv.png           ← 실험2 혼동행렬 (v1.1 adversarial)
    ├── confusion_adv_v1.2.png      ← 실험4 혼동행렬 (v1.2)
    ├── confusion_adv_v1.3.png      ← 실험4 혼동행렬 (v1.3)
    ├── improvement_v1.png          ← 실험3 v1.0→v1.1 개선 차트
    ├── improvement_all_versions.png← 실험4 전체 버전 비교 (4패널)
    ├── version_v1.2.json           ← 실험4 v1.2 결과
    ├── version_v1.3.json           ← 실험4 v1.3 결과
    ├── grid_search_v1.3.json       ← 실험4 그리드 서치 결과
    ├── model_comparison.json       ← 실험5 roberta best config
    ├── model_comparison_bert.json  ← 실험5 bert best config
    ├── model_comparison_koelectra.json ← 실험5 koelectra best config
    ├── grid_search_bert.json       ← 실험5 bert 51번 결과
    ├── grid_search_full.json       ← 실험5 roberta 51번 결과
    ├── grid_search_koelectra.json  ← 실험5 koelectra 51번 결과
    ├── heatmap_bert-base.png       ← 실험5 BERT lr×epochs 히트맵
    ├── heatmap_roberta-base.png    ← 실험5 RoBERTa lr×epochs 히트맵
    ├── heatmap_koelectra-base-v3-discriminator.png ← 실험5 KoELECTRA 히트맵
    ├── confusion_adv_bert-base_exp5.png    ← 실험5 BERT 혼동행렬
    ├── confusion_adv_roberta-base_exp5.png ← 실험5 RoBERTa 혼동행렬
    ├── model_comparison.png        ← 실험5 3모델 성능 비교 차트
    ├── inference_speed.png         ← 실험5 추론 속도 + 학습 시간 비교
    ├── grid_distribution.png       ← 실험5 그리드 서치 Adv F1 분포 (boxplot)
    ├── model_radar.png             ← 실험5 종합 레이더 차트
    ├── preprocessing_ablation.json ← 실험6 전처리 조합별 결과
    ├── preprocessing_ablation.png  ← 실험6 단계별 성능 차트
    ├── seed_stability.png          ← 실험6 seed별 안정성 차트
    ├── final_confusion_adv.png     ← 실험6 최종 혼동행렬
    ├── final_comparison.json       ← 실험7 BERT vs GPT 최종 비교 결과
    ├── statistical_tests.json      ← 실험8 통계적 유의성 테스트 결과
    ├── blind_evaluation.json       ← 실험9 독립 테스트셋 평가 결과
    ├── confusion_blind_test.png    ← 실험9 Blind 테스트 혼동행렬
    ├── confidence_analysis.json    ← 실험9 confidence threshold 분석
    ├── confidence_threshold.png    ← 실험9 threshold별 P/R/Coverage 차트
    └── confidence_distribution.png ← 실험9 confidence 분포 차트

data/training/intent/
├── adversarial_test.json           ← 공용 테스트셋 (212문장, 확장 완료)
├── blind_test.json                 ← 독립 테스트셋 (70문장, 실험9)
├── augment_v12_*.jsonl             ← v1.2 증강 데이터 (6파일, 300건)
└── augment_v13_*.jsonl             ← v1.3 증강 데이터 (7파일, 163건)
```

---

## 결과 기록

모든 결과는 `ai/models/TRAINING_LOG.md`에 기록:
- v1.0 ~ v1.4 버전별 상세 (데이터, 하이퍼파라미터, 성능, 오분류 분석)
- EXP 섹션 (방법론 비교 6가지, 혼동행렬 분석, sLLM 정당성)
- 실험 5 결과 (3모델 × 153번 그리드 서치, 최종 모델 선정)
- 실험 6 결과 (전처리 ablation, seed 안정성 검증, 최종 성능 확정)
- 실험 7 결과 (BERT vs GPT 최종 비교, 212문장 동일 조건)
- 실험 8 결과 (McNemar, Bootstrap CI, 모델 간 통계 검증)
- 실험 9 결과 (독립 테스트셋 blind 평가, confidence threshold 분석)

---

## 발표 스토리라인

1. **왜 sLLM?** → GPT 97.5% vs BERT 90%, 하지만 속도 68배 + 비용 $0 + 보안 (실험 1, 70문장 기준)
2. **약점은?** → 혼동행렬로 패턴 분석 -- general 폴백, multi-intent 혼동 (실험 2)
3. **개선 과정** → v1.0(72%)→v1.1(88%) judgment 해결, v1.2(85%)→v1.3(91.67%) boundary 해결 (실험 3~4)
4. **데이터 vs 하이퍼파라미터** → 그리드 서치로 "데이터 품질이 핵심" 실험적 증명 (실험 4)
5. **왜 이 모델?** → 3모델 × 153번 학습, 3모델 동급 성능 확인 후 BERT 선택 (실험 5)
6. **신뢰성 검증 + 전처리** (실험 6):
   - seed 1개(90.15%)로 보고하면 낙관적 → seed 3개 평균(88.56%)이 현실적 기대치
   - 전처리는 모든 seed에서 일관되게 +0.86~1.70%p 개선 → 실서비스 적용 근거
7. **GPT와 비교** (실험 7):
   - 212문장 기준 BERT(90.07%) vs GPT(86.30%)
   - 단, 통계적으로 유의미한 차이는 아님 (McNemar p=0.1116, 실험 8)
   - **핵심 메시지: "BERT는 GPT와 동급 정확도이면서 속도 45배 + 비용 $0 + 보안"**
8. **통계적 정직함** (실험 8) -- 발표 차별화 포인트:
   - "90%입니다"가 아니라 **"95% CI [85.5%, 93.8%]입니다"**
   - 3모델 차이가 seed 편차보다 작음을 스스로 밝힘
   - 결론을 과장하지 않는 정직한 연구 자세
9. **독립 검증 + 폴백 전략** (실험 9):
   - 모델 개발과 무관한 독립 셋에서 **F1 92.84%** (adversarial보다 높음)
   - confidence 0.7 threshold: Precision 93.0%, Recall 98.0%
   - **한계도 밝힘**: overconfident error(conf>0.9인데 틀림)가 57.7% → threshold만으로 한계
10. **최종 결론** → 동급 정확도 + 속도 45배 + 비용 $0 + 독립 검증 92.84% + 통계적 정직함
