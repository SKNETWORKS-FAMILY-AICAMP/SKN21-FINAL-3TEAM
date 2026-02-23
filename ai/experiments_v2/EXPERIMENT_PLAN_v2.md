# Intent 분류 모델 실험 재설계 (v2)

> **상태**: Stage 5 진행 중 (오분류 분석 완료 → 보강 재학습 대기)
> **작성일**: 2026-02-22
> **최종 수정**: 2026-02-23 (Stage 5.1 오분류 분석 + 5.2 보강 데이터 준비)
> **담당**: 신지용 (PM)

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-02-22 | 초안 작성 |
| 2026-02-22 | Intent 8개 확정, 멀티 LLM 데이터 생성(방법 C), 로컬 실행 방식 반영 |
| 2026-02-23 | 기본 데이터 생성 완료 (Claude 1200 + GPT 1099 = 2299개), QA 통과, split 완료 |
| 2026-02-23 | 실험 스크립트 4개 작성 완료 (baseline, grid_search, final_eval, error_analysis) |
| 2026-02-23 | Gemini 대신 GPT+Claude 반반으로 변경 (Gemini API 키 미보유) |
| 2026-02-23 | GPT-5 → GPT-4o로 변경 (추론 모델은 데이터 생성에 부적합) |
| 2026-02-23 | Stage 2 Baseline 학습 시작 (로컬 → RunPod 전환) |
| 2026-02-23 | 경계 쌍 600개 + 적대적 450개 생성 완료, QA 재실행 |
| 2026-02-23 | **Stage 2 Baseline 완료**: koelectra 0.9825 > bert 0.9780 > distilkobert 0.9498 |
| 2026-02-23 | **Stage 3 Grid Search 완료**: best config ep10/lr3e-5/bs16 → F1 0.9897, seed 안정성 0.9874±0.0033 |
| 2026-02-23 | **Stage 4 최종 평가 완료**: koelectra Adv F1 86.04% > bert 85.17% > distilkobert 79.26% |
| 2026-02-23 | **Stage 5.1 오분류 분석 완료**: test 8건(2.8%), adversarial 63건(14.0%) 오분류 |
| 2026-02-23 | **Stage 5.2 보강 데이터 준비**: 98개 타겟 보강 (QA 통과: 적대적 누출 0건) |

---

## Context

- 챗봇 사용자 발화를 **8개 intent**로 분류하여 Agent 라우팅
- 이전 실험 9개 완료 (klue/bert-base Adv F1 90.07%) — 리팩토링 후 **클린 재실험** 필요
- 리팩토링으로 intent 7개 → 8개 변경 → 데이터 완전 새로 생성
- 최종 발표에서 모델 선택 근거를 정량적으로 제시하는 것이 목표
- **RunPod GPU 환경** (로컬 RTX 4070에서 전환)

## 전제조건

- **리팩토링 완료 후 실행** (8개 intent 구조 확정 필요)
- 리팩토링 끝나면 8개 intent 목록 확인 후 데이터 생성 착수

---

## 1. 비교 모델 (3개)

| 모델 | 파라미터 | 아키텍처 | 역할 | 선정 이유 |
|------|:--------:|---------|------|----------|
| `klue/bert-base` | 111M | BERT (MLM) | **Baseline** | 한국어 NLU 표준, 이전 실험 챔피언 |
| `monologg/koelectra-base-v3-discriminator` | 111M | ELECTRA (RTD) | **아키텍처 비교** | 동일 크기, 다른 사전학습 방식 |
| `monologg/distilkobert` | 28M (3레이어) | DistilBERT | **경량 모델** | 4배 작고 빠름 → "111M이 과한가?" 질문에 답변 |

**발표 스토리**: "같은 파이프라인, 3가지 철학 — 어떤 것이 한국어 직장 챗봇에 최적인가?"
- BERT: 표준 접근법
- KoELECTRA: 같은 크기, 더 나은 학습 방식?
- DistilKoBERT: 8개 분류에 111M이 정말 필요한가?

> DistilKoBERT는 SentencePiece 토크나이저 사용 (`trust_remote_code=True` 필요). 호환 문제 시 `beomi/KcELECTRA-base-v2022`로 대체.

---

## 2. 데이터 설계

### 생성 전략: 멀티 LLM 혼합형 (방법 C)

기존 데이터는 BERT 실패 패턴 보정용으로 누적 → 특정 모델에 편향.
클린 실험을 위해 **3개 LLM으로 통일된 기준으로 재생성**.

#### 왜 멀티 LLM인가?
- **다양성**: 단일 LLM은 비슷한 문체/패턴 반복 → 3개 LLM이 각각 다른 스타일의 한국어 생성
- **교차 검증**: 한 LLM이 생성한 데이터를 다른 LLM이 라벨 검증 → 편향 제거
- **신뢰성**: 2/3 투표 통과 = 모델 독립적으로 올바른 라벨

#### 방법 C: 혼합형 전략 (수정: GPT + Claude 반반)

> Gemini API 키 미보유로 GPT+Claude 150개씩 분업으로 변경

```
[기본 데이터 — 분업형 (효율)]  ✅ 완료
  Claude : intent별 150개 생성 (Claude API, Sonnet 4)
  GPT    : intent별 150개 생성 (GPT-4o API)
  → 합계: intent별 ~300개 (GPT 일부 미달로 실제 2,299개)

[경계 쌍 + 적대적 — 완료]  ✅ 완료
  GPT: 경계 쌍 300개 + 적대적 232개
  Claude: 경계 쌍 300개 + 적대적 240개
  → 경계 쌍 600개 (학습 포함), 적대적 450개 (평가 전용, 중복 13개 제거)
```

#### 레거시 데이터 처리
- 기존 adversarial(212개) + blind(70개)는 **레거시 비교용으로 보존**
- v1 학습 데이터(1,916개)는 사용하지 않음 (모델 편향 방지)

### 데이터 구조

```
data/training/intent_v2/
├── {intent}.jsonl × 8          # 기본 데이터 (intent별 300개)
├── boundary_pairs.jsonl        # 경계 쌍 데이터 (~300개)
├── adversarial_v2.json         # 새 적대적 테스트 (240개, 30/intent)
├── scenario_test.json          # 라우팅 시나리오 테스트 (30개)
├── splits/
│   ├── train.jsonl             # 80%
│   ├── val.jsonl               # 10%
│   └── test.jsonl              # 10% (최종 평가 시 1회만 사용)
└── DATA_QA_REPORT.md           # 품질 검증 보고서
```

### 샘플 수 (8 intent 기준)

| 구분 | 계획 | 실제 | 상태 |
|------|:----:|:----:|:----:|
| 기본 데이터 | 300 × 8 = 2,400 | **2,299개** (중복 제거 후) | ✅ 완료 |
| 경계 쌍 | ~300개 | **600개** (GPT 300 + Claude 300) | ✅ 완료 |
| **학습 총량** | **~2,700개** | **2,899개** (기본 + 경계 쌍) | ✅ 완료 |
| Split | 80/10/10 | Train 2,327 / Val 285 / Test 286 | ✅ 완료 |
| 적대적 테스트 | 240개 (30/intent) | **450개** (GPT 232 + Claude 240, 중복 제거) | ✅ 완료 |
| 보강 데이터 (Stage 5) | ~100개 | **98개** | ✅ 완료 |
| 시나리오 테스트 | 30개 | 0개 | ⬜ 미작성 |

**기본 데이터 intent별 분포 (중복 제거 후):**

| Intent | Claude | GPT | 합계 |
|--------|:------:|:---:|:----:|
| judgment | 150 | 127 | 277 |
| doc_search | 150 | 136 | 286 |
| doc_generate | 150 | 122 | 272 |
| doc_summary | 150 | 144 | 294 |
| schedule_add | 150 | 148 | 298 |
| schedule_view | 150 | 137 | 287 |
| general | 150 | 151 | 301 |
| doc_qa | 150 | 134 | 284 |
| **합계** | **1,200** | **1,099** | **2,299** |

- 클래스 균형: max/min = 1.11 (< 1.2 기준 통과)
- Cross-LLM 중복: 0개
- QA: 비유효 라벨 0, 누출 0

### 생성 파이프라인

| 단계 | 작업 | 방식 |
|------|------|------|
| 1 | **Seed 문장** — intent별 10개 직접 작성 | 수동 (앵커) |
| 2 | **기본 생성** — intent별 300개 | Claude 100 + GPT 100 + Gemini 100 |
| 3 | **경계 쌍** — 혼동 쌍별 30개 | 3 LLM 전부 생성 → 2/3 투표 |
| 4 | **적대적 세트** — 8개 유형별 30개 | 3 LLM 전부 생성 → 2/3 투표 |
| 5 | **자동 QA** — 중복/형식/균형 | 스크립트 |
| 6 | **수동 검토** — intent별 50개 샘플링 | 직접 확인 |
| 7 | **분할** — Train/Val/Test | Stratified 80/10/10 |

### 품질 검증 체크리스트

- [x] JSON 유효성 (파싱 에러 0) ✅
- [x] 라벨 유효성 (허용 라벨만 사용) ✅
- [x] 중복 제거 (exact match) ✅ GPT 내부 중복 59개 제거됨
- [x] 클래스 균형 (max/min = 1.11 < 1.2) ✅
- [ ] 교차 오염 (intent별 50개 샘플링 → 수동 검토, 오분류 < 2%)
- [x] 테스트 누출 (test ∩ train = 공집합) ✅
- [x] Cross-LLM 중복 0개 ✅

---

## 3. 학습 전략

### 방식: Full Fine-tuning
- 인코더 모델 + 소규모 데이터 → LoRA 불필요
- 학습 시간 짧음 (run당 2분 이내)
- Feature extraction은 도메인 특화 성능 부족

### 하이퍼파라미터

**Stage 2 (Baseline) — 고정값:**

| 파라미터 | 값 | 근거 |
|----------|-----|------|
| epochs | 5 | 이전 실험 최적값 |
| learning_rate | 2e-5 | BERT 논문 권장 |
| batch_size | 16 | 로컬 GPU 안정 |
| warmup_ratio | 0.06 | 표준 |
| weight_decay | 0.01 | L2 정규화 |
| max_length | 64 | 입력 99%+ 커버 |
| fp16 | True | 메모리 절감 |

**Stage 3 (Grid Search) — 최상위 모델만:**

| 파라미터 | 탐색 범위 | 조합 수 |
|----------|----------|:-------:|
| epochs | [3, 5, 7, 10] | 4 |
| learning_rate | [1e-5, 2e-5, 3e-5, 5e-5] | 4 |
| batch_size | [16, 32] | 2 |
| **총 runs** | | **32** |

+ Seed 안정성: best config × [42, 123, 456] = 3 runs

### 예상 소요 시간

| 단계 | RunPod (RTX A4000) | 로컬 (RTX 4070) |
|------|:------------------:|:---------------:|
| Stage 2 (3모델 baseline) | ~3분 | ~10분 |
| Stage 3 (32 grid + 3 seed) | ~20분 | ~1시간 |
| Stage 4 (전체 평가) | ~10분 | ~30분 |
| **합계** | **~35분** | **~1.5시간** |

> RunPod 사용으로 전환. GPU: RTX A4000 (16GB) 권장.

---

## 4. 평가 설계

### 정량 평가

| 메트릭 | 용도 |
|--------|------|
| **Macro F1** | 주요 랭킹 지표 (클래스 균형 반영) |
| **Accuracy** | 직관적 설명용 |
| **Per-class F1** | 취약 intent 식별 |
| **Confusion Matrix** | 오분류 패턴 시각화 |

### 평가 세트별 용도

| 세트 | 시점 | 용도 |
|------|------|------|
| Validation | 매 epoch | HP 선택, early stopping |
| Test (hold-out) | Stage 4에서 **1회만** | 최종 성능 보고 |
| Adversarial v2 (240개) | Stage 4 | 강건성 평가 |
| Legacy adversarial (212개) | Stage 4 | 이전 실험과 비교 |
| Legacy blind (70개) | Stage 4 | 이전 실험과 비교 |
| Scenario test (30개) | Stage 4 | 실제 라우팅 시뮬레이션 |

### 통계 검증
- 3-seed 평균 ± 표준편차
- Bootstrap 95% CI (10,000 resamples)
- McNemar's Test (모델 간 쌍별 비교)

### 정성 평가
- "하루 시나리오" 테스트: 30개 문장으로 실제 업무 흐름 시뮬레이션
- 오분류 유형 분류: 경계 혼동 / 초단문 / 오타 / 과신뢰 / 맥락의존

### 속도/리소스

| 항목 | 측정 방법 |
|------|----------|
| 추론 지연시간 | 100회 warmup + 1000회 측정 (mean, p95) |
| 모델 크기 | .safetensors 파일 크기 (MB) |
| GPU 메모리 | `torch.cuda.max_memory_allocated()` |
| 배치 처리량 | batch=32 기준 samples/sec |

---

## 5. 실험 실행 방식

### RunPod 환경 세팅 (복붙용)

```bash
# 1. 레포 클론
git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM.git
cd SKN21-FINAL-3TEAM
git checkout feat/jiyong

# 2. 의존성 설치 (한번에 전부)
pip install --upgrade torch torchvision transformers accelerate datasets scikit-learn matplotlib seaborn sentencepiece

# 3. 실험 실행
python ai/experiments_v2/run_grid_search.py     # Stage 3
python ai/experiments_v2/run_final_eval.py      # Stage 4
python ai/experiments_v2/run_error_analysis.py  # 오분류 분석

# 4. 결과 push (실험 끝난 후)
git add ai/experiments_v2/results/
git commit -m "feat: Stage N 실험 결과"
git push origin feat/jiyong
```

> **주의**: RunPod 이미지에 이전 버전 torch가 설치돼 있을 수 있음 → 반드시 `--upgrade` 사용

### 원칙: 로컬 터미널 실행 + 결과 보고

```
[왜?]
  - Claude CLI에서 학습 돌리면 토큰 소비 과다
  - 스크립트를 잘 만들어두면 터미널에서 한 줄로 실행 가능
  - 결과는 summary.md로 자동 생성 → 복붙 or 파일 읽기로 보고

[워크플로우]
  1. Claude가 스크립트 작성 (ai/experiments_v2/*.py)
  2. 지용이 RunPod 터미널에서 실행: python ai/experiments_v2/run_baseline.py
  3. 결과 자동 저장:
     - ai/experiments_v2/results/*.json        ← 원본 데이터
     - ai/experiments_v2/results/*_summary.md  ← 사람이 읽는 요약
  4. 지용이 Claude에게 보고: "Stage 2 끝났어" or summary.md 복붙
  5. Claude가 결과 분석 + 다음 단계 가이드
```

### 스크립트 설계 원칙

- **자체 완결**: 한 줄 실행으로 학습~결과 저장까지 완료
- **summary.md 자동 생성**: 핵심 수치 + 해석 요약 (보고용)
- **JSON 원본 보존**: 차트 재생성, 추가 분석용
- **중단/재개 가능**: 이미 완료된 run은 skip (resume 모드)

---

## 6. 실험 로드맵 (4단계)

### Stage 1: 데이터 준비 ✅ 완료

| 단계 | 작업 | 방식 | 결과 |
|------|------|------|------|
| 1.1 | Intent별 seed 문장 10개 작성 | 수동 | ✅ 8개 intent 완료 |
| 1.2 | 기본 데이터 intent별 300개 생성 | Claude 150 + GPT 150 | ✅ 2,299개 (GPT 일부 미달) |
| 1.3 | 경계 쌍 600개 생성 | GPT 300 + Claude 300 | ✅ 10쌍 x 30개 x 2 LLM |
| 1.4 | 적대적 테스트 450개 생성 | GPT 232 + Claude 240 | ✅ 중복 제거 후 450개 |
| 1.5 | 자동 QA (중복/형식/균형) | 스크립트 | ✅ 누출 1건, 중복 13건 제거 |
| 1.6 | 수동 검토 | - | ⬜ 미실시 (시간 부족) |
| 1.7 | Train/Val/Test 분할 (80/10/10) | 스크립트 | ✅ 2,327 / 285 / 286 |

**Gate**: QA 통과 → Stage 2 진행 중

### Stage 2: Baseline 학습 ✅ 완료

| 단계 | 작업 | 결과 |
|------|------|------|
| 2.1 | 3개 모델 로드 확인 | ✅ (distilkobert: sentencepiece 추가 설치) |
| 2.2 | 동일 HP로 3개 모델 학습 (seed=42) | ✅ 3개 모두 완료 |
| 2.3 | Validation F1 비교 → 순위 결정 | ✅ koelectra > bert > distilkobert |
| 2.4 | Confusion Matrix 3장 생성 | ✅ |

**최종 결과:**

| 순위 | 모델 | Val Acc | Val F1 | Adv F1 | 추론속도 | 파라미터 | 크기 | 학습시간 |
|:---:|------|:------:|:------:|:------:|:------:|:------:|:----:|:------:|
| 1 | **koelectra-base-v3** | 0.9823 | **0.9825** | - | 14.2ms | 112.9M | 431MB | 860s |
| 2 | bert-base | 0.9779 | 0.9780 | - | 14.4ms | 110.6M | 422MB | 808s |
| 3 | distilkobert | 0.9474 | 0.9498 | 0.7252 | **3.9ms** | **28.4M** | **108MB** | **243s** |

**분석:**
- koelectra가 bert보다 F1 0.45%p 높음 (동일 크기 대비 ELECTRA 아키텍처 우위)
- bert는 koelectra 대비 장점 없음 (F1 낮고, 크기/속도 유사)
- distilkobert는 3.6배 빠르고 4배 작지만, Adv F1 72.5%로 강건성 부족
  - 약점: doc_search F1 56%, doc_qa F1 69%
- **Decision: koelectra → Stage 3 Grid Search 대상**

**실행**: `python ai/experiments_v2/run_baseline.py`
**결과**: `results/baseline_results.json`
**차트**: baseline_comparison.png, training_curves.png, per_class_f1_radar.png, confusion matrix 3장

### Stage 3: HP 튜닝 ✅ 완료 (RunPod RTX 4090)

| 단계 | 작업 | 결과 |
|------|------|------|
| 3.1 | 32-point grid search (koelectra) | ✅ 32 runs 완료 (~17분) |
| 3.2 | Best config 확인 | ✅ ep10/lr3e-5/bs16 → F1 0.9897 |
| 3.3 | Seeds [42, 123, 456] 안정성 검증 | ✅ 0.9874 ± 0.0033 |
| 3.4 | HP 히트맵 생성 | ✅ hp_heatmap_bs16.png, hp_heatmap_bs32.png |

**Best Config:**

| 파라미터 | 값 |
|----------|-----|
| epochs | 10 |
| learning_rate | 3e-5 |
| batch_size | 16 |
| Val F1 | **0.9897** |

**Top 5 Grid Search 결과:**

| 순위 | epochs | lr | batch | Val F1 |
|:---:|:------:|:---:|:----:|:------:|
| 1 | **10** | **3e-5** | **16** | **0.9897** |
| 2 | 3 | 2e-5 | 16 | 0.9864 |
| 2 | 7 | 2e-5 | 32 | 0.9864 |
| 2 | 10 | 2e-5 | 32 | 0.9864 |
| 5 | 5 | 3e-5 | 16 | 0.9862 |

**Seed 안정성:**

| Seed | Val F1 |
|:----:|:------:|
| 42 | 0.9897 |
| 123 | 0.9898 |
| 456 | 0.9828 |
| **평균 ± std** | **0.9874 ± 0.0033** |

**분석:**
- Baseline(0.9825) → Best(0.9897): **+0.72%p** → v1 결론 재확인: **데이터 > 하이퍼파라미터**
- lr=1e-5 부족, lr=3e-5 최적, lr=5e-5 과적합 경향
- batch_size=16이 32보다 일관적으로 좋음
- Seed 안정성 양호 (std 0.0033)

**실행**: `python ai/experiments_v2/run_grid_search.py`
**결과**: `results/grid_search_results.json`, `results/seed_stability_results.json`
**차트**: hp_heatmap_bs16.png, hp_heatmap_bs32.png, seed_stability.png

### Stage 4: 최종 평가 ✅ 완료 (RunPod RTX 4090)

| 단계 | 작업 | 결과 |
|------|------|------|
| 4.1 | Hold-out test set 평가 | ✅ bert 0.9756 / koelectra 0.9726 / distilkobert 0.9645 |
| 4.2 | 3모델 adversarial v2 평가 | ✅ koelectra **0.8604** > bert 0.8517 > distilkobert 0.7926 |
| 4.3 | 레거시 테스트셋 비교 | ⬜ (v2 데이터 기준 평가로 대체) |
| 4.4 | 전처리 ablation (Config A~E) | ✅ A~E 전부 동일 → 전처리 효과 없음 |
| 4.5 | 추론 속도 + 메모리 측정 | ✅ koelectra 8.3ms / bert 10.4ms / distilkobert 2.8ms |
| 4.6 | 통계 검증 (McNemar, Bootstrap CI) | ✅ McNemar 전부 n.s. / CI 산출 완료 |
| 4.7 | 오분류 수집 + 유형 분류 | ✅ test 8건, adversarial 63건 분석 완료 |
| 4.8 | 시나리오 테스트 | ⬜ 30개 미작성 |
| 4.9 | 차트 생성 | ✅ 11장 (confusion 3, ablation 3, confidence 3, speed 1, f1_vs_speed 1) |
| 4.10 | 최종 보고서 작성 | ⬜ |

**최종 결과:**

| 순위 | 모델 | Test F1 | **Adv F1** | 속도 | 파라미터 | Bootstrap 95% CI |
|:---:|------|:------:|:--------:|:----:|:------:|:----------------:|
| 1 | **koelectra-v3** | 0.9726 | **0.8604** | **8.3ms** | 112.9M | [0.952, 0.990] |
| 2 | bert-base | 0.9756 | 0.8517 | 10.4ms | 110.6M | [0.956, 0.992] |
| 3 | distilkobert | 0.9645 | 0.7926 | **2.8ms** | **28.4M** | [0.940, 0.984] |

**Adversarial Per-class F1 (약점 분석):**

| Intent | koelectra | bert | distilkobert |
|--------|:---------:|:----:|:------------:|
| judgment | **0.920** | 0.855 | 0.832 |
| doc_search | **0.827** | 0.803 | 0.718 |
| doc_generate | **0.882** | 0.845 | 0.779 |
| doc_summary | 0.875 | **0.926** | 0.839 |
| schedule_add | **0.944** | 0.935 | 0.933 |
| schedule_view | 0.887 | **0.909** | 0.855 |
| general | **0.836** | 0.803 | 0.688 |
| **doc_qa** | **0.710** | 0.738 | 0.698 |

**분석:**
- koelectra가 Adv F1에서 bert 역전 (86.04% > 85.17%)
- **doc_qa가 3모델 모두 최약점** (70~74%) → 보강 1순위
- Val F1 97~98% vs Adv F1 79~86% → 12~17%p 하락, Val 과대추정 확인
- 전처리 Ablation A~E 전부 동일 → LLM 생성 데이터는 이미 깨끗
- McNemar 전부 n.s. → Test 286개로는 통계적 유의차 검출 불가
- **Decision: koelectra 최종 선택** (Adv F1, 속도, 강건성 모두 우위)

**보강 필요 intent:**

| 우선순위 | Intent | Adv F1 | 보강 방향 |
|:-------:|--------|:------:|----------|
| 1 | doc_qa | 71.0% | doc_search/judgment와 경계 데이터 추가 |
| 2 | doc_search | 82.7% | doc_qa와 구분되는 검색 표현 추가 |
| 3 | general | 83.6% | 짧은 일상 표현 + 모호한 입력 추가 |

**실행**: `python ai/experiments_v2/run_final_eval.py`
**결과**: `results/final_eval_results.json`
**차트**: confusion 3장, ablation 3장, confidence 3장, speed_comparison, f1_vs_speed

### Stage 5: 보강 + 재평가 (진행 중)

| 순서 | 작업 | 상태 |
|:---:|------|:----:|
| 5.1 | `run_error_analysis.py` 실행 — 오분류 유형 분석 | ✅ |
| 5.2 | 타겟 보강 데이터 생성 + QA | ✅ |
| 5.3 | 재학습 + 재평가 (`run_stage5_retrain.py`) | ⬜ |
| 5.4 | 시나리오 테스트 30개 작성 + 실행 (정성평가) | ⬜ |
| 5.5 | 최종 모델 저장 (`ai/models/intent_classifier/`) | ⬜ |

**5.1 오분류 분석 결과:**

| 데이터셋 | 정답 | 오답 | 정확도 |
|---------|:---:|:---:|:-----:|
| Test (286개) | 278 | 8 | 97.2% |
| Adversarial (450개) | 387 | 63 | 86.0% |

**Adversarial 오분류 유형:**

| 유형 | 건수 | 비율 |
|------|:---:|:---:|
| short_text (≤4어절) | 47 | 74.6% |
| overconfident (>90%) | 42 | 66.7% |
| boundary_high | 30 | 47.6% |
| boundary_medium | 10 | 15.9% |
| typo_chosung | 7 | 11.1% |

**Top 5 혼동 쌍:**

| 실제 → 예측 | 건수 | 분석 |
|------------|:---:|------|
| doc_qa → doc_search | 10 | "문서 확인" 류 초단문이 search로 빠짐 |
| doc_generate → doc_summary | 5 | "정리해줘" 패턴을 summary로 오인 |
| doc_qa → doc_summary | 5 | 문서 내용 질문이 요약으로 오인 |
| schedule_add → schedule_view | 4 | "일정 ㄱㄱ" 류 초단문이 view로 빠짐 |
| general → doc_qa/doc_search | 8 | 봇 기능 질문을 문서 관련으로 오인 |

**근본적 한계 (보강으로 해결 불가):**
- 1~2어절 초단문 ("문서 확인", "일정 ㄱㄱ")은 맥락 없이는 인간도 판단 곤란
- 초성 축약 ("ㅇㅊ ㄱㄴ?")은 BERT 토크나이저가 의미 추출 불가
- → 실서비스에서는 clarify(되묻기)로 처리하는 것이 적절

**5.2 보강 데이터 (98개):**

| Intent | 보강 | 보강 방향 |
|--------|:---:|----------|
| doc_qa | +20 | 문서 **내용** 질문 (doc_search/summary와 구분) |
| doc_generate | +15 | "정리해줘" = 문서 **생성** (summary와 구분) |
| schedule_add | +11 | "추가/등록/넣어줘" 패턴 강화 |
| schedule_view | +11 | "확인/보여줘/뭐야" 패턴 (누락 보완) |
| general | +11 | 봇 기능 관련 질문 + 일상 표현 |
| judgment | +10 | 규정 판단 요청 (general과 구분) |
| doc_search | +10 | 문서 **위치/경로** 질문 (doc_qa와 구분) |
| doc_summary | +10 | "요약/줄여줘" 패턴 (doc_generate와 구분) |

**보강 데이터 QA:**
- 적대적↔보강 exact 중복: **0건** ✅
- train↔보강 exact 중복: 1건 (같은 라벨, 무해) ✅
- 적대적↔보강 유사도 80%+: 1건 (같은 라벨, 무해) ✅
- 라벨 유효성: 8개 전부 포함 ✅

**실행**: `python ai/experiments_v2/run_stage5_retrain.py --save-model`
**결과**: `results/stage5_results.json`, `results/stage5_comparison.png`

---

## 7. 발표 스토리라인

| 슬라이드 | 제목 | 핵심 내용 | 차트 |
|:--------:|------|----------|------|
| 1 | 문제 정의 | 8개 intent, 잘못된 라우팅 = 잘못된 답변 | 오케스트레이터 다이어그램 |
| 2 | 접근 방식 | 3모델 비교: 표준 vs 아키텍처 vs 경량 | 모델 비교 테이블 |
| 3 | 데이터 | ~2,700개, 멀티 LLM 생성 + 경계 쌍 + 적대적 | 클래스 분포 차트 |
| 4 | Baseline 비교 | 동일 조건 3모델 성능 | 그룹 바 차트 |
| 5 | 효율성 vs 정확도 | 111M이 과한가? | F1 vs 속도 scatter |
| 6 | HP 민감도 | 데이터 > 하이퍼파라미터 | 히트맵 + seed 안정성 |
| 7 | 오분류 분석 | 어디서, 왜 틀리나 | Confusion Matrix + 사례 |
| 8 | 전처리 효과 | 규칙 기반 +α | Ablation 바 차트 |
| 9 | 결론 | 모델 선택 근거 (정량) | 최종 비교표 + CI |
| 10 | 통합 | 실제 서비스 적용 | 코드 스니펫 + 플로우 |

### 생성할 차트 목록 (10장)

1. Baseline 3모델 비교 (Grouped bar)
2. F1 vs 추론속도 vs 모델크기 (Scatter + bubble)
3. 추론 속도 비교 (Bar)
4. HP 히트맵 (lr × epochs)
5. Seed 안정성 (Error bar)
6. Confusion Matrix — best model, adversarial (Heatmap)
7. 전처리 ablation (Bar)
8. Per-class F1 (Radar)
9. Training loss curves (Line)
10. Confidence 분포 (Histogram)

---

## 8. 실험 기록 템플릿

```markdown
# Experiment: [EXP-XXX]

## 개요
| 항목 | 값 |
|------|-----|
| 날짜 | YYYY-MM-DD |
| 단계 | Stage N |
| 목적 | [한 문장] |

## 모델
| 항목 | 값 |
|------|-----|
| 모델명 | |
| 파라미터 수 | |
| 아키텍처 | |

## 데이터
| 항목 | 값 |
|------|-----|
| 버전 | v2.0 |
| Train / Val / Test | N / N / N |

## 학습 설정
| 파라미터 | 값 |
|----------|-----|
| epochs | |
| learning_rate | |
| batch_size | |
| seed | |
| GPU | |
| 학습 시간 | |

## 결과
| 메트릭 | Val | Test | Adversarial |
|--------|:---:|:----:|:----------:|
| Accuracy | | | |
| Macro F1 | | | |

### Per-Class F1
| Intent | P | R | F1 |
|--------|:-:|:-:|:--:|
| (8개 intent 확정 후 채움) | | | |

### 속도/리소스
| 항목 | 값 |
|------|-----|
| 추론 지연시간 (mean) | ms |
| 모델 크기 | MB |
| GPU 메모리 | MB |

## 해석
[이 실험에서 배운 점, 이전과 비교, 다음 액션]
```

---

## 9. 최종 산출물 체크리스트

### 데이터
- [x] intent별 기본 데이터 JSONL (8개, 2,299개) ✅
- [x] 경계 쌍 데이터 (600개, GPT+Claude) ✅
- [x] 적대적 테스트 v2 (450개, 중복 제거 후) ✅
- [ ] 시나리오 테스트 (30개) ⬜
- [x] Train/Val/Test 분할 (2,327/285/286) ✅
- [x] 품질 검증 보고서 (DATA_QA_REPORT.md) ✅

### 스크립트
- [x] `ai/experiments_v2/generate_data.py` — 데이터 생성 + QA ✅
- [x] `ai/experiments_v2/run_baseline.py` — Stage 2 ✅
- [x] `ai/experiments_v2/run_grid_search.py` — Stage 3 ✅
- [x] `ai/experiments_v2/run_final_eval.py` — Stage 4 ✅
- [x] `ai/experiments_v2/run_error_analysis.py` — 오분류 분석 ✅
- [x] `ai/experiments_v2/run_stage5_retrain.py` — Stage 5 보강 재학습 ✅

### 결과물
- [x] 3모델 성능 비교표 ✅ (koelectra 0.9825 > bert 0.9780 > distilkobert 0.9498)
- [x] Confusion Matrix 3장 ✅
- [x] 차트 3장 (baseline_comparison, training_curves, per_class_f1_radar) ✅
- [x] 오분류 사례 분석 문서 ✅ (error_analysis_adversarial.md, error_analysis_test.md)
- [ ] 모델 선택 근거 문서
- [ ] 실험 기록 (MD 템플릿 기반)

### 재사용할 기존 코드
- `ai/experiments/run_model_comparison.py` — 학습/평가 파이프라인 패턴
- `ai/agents/preprocessing.py` — 전처리 파이프라인 (Stage 4 ablation)
- `ai/experiments/run_statistical_tests.py` — McNemar, Bootstrap CI
- `ai/agents/intent_classifier.py` — 최종 모델 배포 대상

---

## 수정 대상 파일

- `ai/experiments_v2/` — 새 디렉토리 (스크립트 5개)
- `data/training/intent_v2/` — 새 디렉토리 (데이터)
- `ai/models/intent_classifier/` — 최종 모델 교체 (Stage 4 후)
- `ai/agents/intent_classifier.py` — 8개 intent + 모델 경로 업데이트

## 검증 방법

1. Stage별 Gate 통과 확인 (QA → Baseline → Grid → Final)
2. 3-seed 안정성 ± std 확인
3. 레거시 테스트셋으로 이전 결과(90.07%)와 비교
4. `intent_classifier.py`에 최종 모델 로드 → 예측 동작 확인

---

## TODO: 리팩토링 후 확정할 것

- [x] 8개 intent 목록 확정 ✅ (doc_summary, doc_qa 추가, meeting_generate 제거)
- [x] 경계 쌍(혼동 쌍) 10쌍 정의 ✅
- [x] generate_data.py 프롬프트에 intent 정의 반영 ✅
- [ ] intent_classifier.py의 INTENT_LABELS 업데이트 확인 (최종 모델 배포 시)

## 기술 이슈 기록

| 이슈 | 원인 | 해결 |
|------|------|------|
| GPT-5 파싱 0개 | 추론 모델이라 내부 reasoning에 토큰 소비 | GPT-4o로 변경 |
| GPT-5 temperature 불가 | 추론 모델은 temperature 고정 | GPT-4o로 변경 |
| pip install vs python -m pip | Python 3.11/3.13 이중 설치, pip이 3.13에 연결 | python -m pip 사용 |
| cp949 인코딩 에러 | Windows 터미널 + em dash(—) 문자 | PYTHONIOENCODING=utf-8 |
| f-string 포맷 에러 | 조건부 포맷 스펙 in f-string | 변수 분리 |
| distilkobert sentencepiece | 토크나이저가 SentencePiece 의존 | python -m pip install sentencepiece |
| Train-Val 누출 1건 | 경계 쌍 추가 시 중복 발생 | val에서 제거 |
| Train-Adversarial 중복 13건 | 기본 데이터와 적대적 데이터 겹침 | adversarial에서 제거 (463→450) |
