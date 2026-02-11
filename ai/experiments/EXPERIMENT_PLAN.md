# ML 비교 실험 기획서

> Intent Classification 모델의 성능을 다각도로 검증하고, 중간발표용 시각 자료를 생성하기 위한 실험 계획.

---

## 실험 목적

발표에서 답해야 할 3가지 질문:

1. **"왜 이 방법을 선택했나?"** → 실험 1 (방법론 비교)
2. **"어디가 약하고 어떻게 대응하나?"** → 실험 2 (혼동행렬)
3. **"개선할 줄 아나?"** → 실험 3 (v1.0→v1.1 개선 차트)

---

## 데이터 현황

| 용도 | 파일 | 크기 |
|------|------|:----:|
| 학습 | `data/training/intent/train.jsonl` | 1,236문장 |
| 정규 평가 | `data/training/intent/eval.jsonl` | 219문장 |
| Adversarial 평가 | `data/training/intent/adversarial_test.json` | 70문장 |

---

## 실험 1: 방법론 비교

**질문**: 파인튜닝이 다른 방법보다 나은가?

### 비교 대상 (6가지)

| # | 방법 | 설명 |
|---|------|------|
| 1 | **Random** | 7개 중 무작위 선택 (이론값 14.3%) |
| 2 | **Rule-based** | 키워드 매칭 (회의→meeting, 규정→judgment 등) |
| 3 | **BERT Base (학습 전)** | klue/bert-base에 classification head만 붙인 상태 |
| 4 | **GPT Zero-shot** | GPT-4o-mini + 시스템 프롬프트만 |
| 5 | **GPT Few-shot** | GPT-4o-mini + 카테고리별 3개 예시 |
| 6 | **BERT Fine-tuned** | 우리 모델 (v1.1) |

### 측정 항목

| 항목 | 내용 |
|------|------|
| 테스트셋 | `adversarial_test.json` 70문장 |
| 측정 | F1 macro, Accuracy, 평균 추론 시간(ms) |
| 출력 | 막대 그래프 (F1 비교) + 속도/비용 테이블 |
| 실행 환경 | RunPod (BERT 계열) + 로컬 또는 RunPod (GPT) |

### 스크립트

| 파일 | 내용 | 실행 위치 |
|------|------|-----------|
| `run_method_comparison.py` | Random + Rule + BERT Base + BERT Fine-tuned | RunPod |
| `run_gpt_comparison.py` | GPT Zero-shot + Few-shot | OPENAI_API_KEY 있는 곳 |
| `run_visualize.py` | 결과 JSON 합쳐서 차트 생성 | 어디서든 |

---

## 실험 2: 혼동행렬

**질문**: 어떤 카테고리끼리 헷갈리는가?

| 항목 | 내용 |
|------|------|
| 방법 | eval (219문장) + adversarial (70문장) 각각 혼동행렬 |
| 출력 | 히트맵 이미지 2장 |
| 실행 환경 | RunPod |

> `run_method_comparison.py`에서 BERT Fine-tuned 추론할 때 혼동행렬도 같이 생성.

---

## 실험 3: v1.0 → v1.1 개선 차트

**질문**: 문제를 발견하고 개선할 수 있는가?

| 항목 | 내용 |
|------|------|
| 방법 | TRAINING_LOG.md에 이미 기록된 수치를 시각화 |
| 출력 | Before/After 비교 차트 1장 |
| 재학습 | **불필요** (기존 숫자 활용) |

### 사용할 데이터 (이미 확보)

| 지표 | v1.0 | v1.1 |
|------|:----:|:----:|
| Eval F1 | 99.08% | 98.80% |
| Adversarial (25문장) | 72% (18/25) | 88% (22/25) |
| judgment→general 오분류 | 5건 | 0건 |

> `run_visualize.py`에서 개선 차트도 같이 생성.

---

## 결과 파일 위치

```
ai/experiments/
├── EXPERIMENT_PLAN.md              ← 이 문서
├── run_method_comparison.py        ← 실험1 (Rule+BERT) + 실험2 (혼동행렬)
├── run_gpt_comparison.py           ← 실험1 (GPT zero/few-shot)
├── run_visualize.py                ← 차트 생성 (실험1+2+3 통합)
└── results/
    ├── method_comparison.json      ← 실험1 수치
    ├── gpt_comparison.json         ← 실험1 GPT 수치
    ├── method_comparison.png       ← 실험1 막대 그래프
    ├── confusion_eval.png          ← 실험2 혼동행렬 (eval)
    ├── confusion_adv.png           ← 실험2 혼동행렬 (adversarial)
    └── improvement_v1.png          ← 실험3 개선 차트

data/training/intent/
└── adversarial_test.json           ← 공용 테스트셋 (70문장)
```

---

## 결과 기록

실험 완료 후 `ai/models/TRAINING_LOG.md`에 아래 섹션 추가:

```markdown
## 실험 결과 — 방법론 비교 (EXP)
(방법별 F1, 속도, 비용 테이블)

## 실험 결과 — 혼동행렬 (EXP)
(이미지 경로 + 분석 코멘트)
```

---

## 전처리 기록 방안 (추후)

| 상황 | 기록 방식 |
|------|-----------|
| 전처리 ON/OFF 비교만 | TRAINING_LOG.md에 `EXP-전처리` 섹션 추가 |
| 전처리 데이터로 재학습 | TRAINING_LOG.md에 `v2.0` 버전 추가 |
