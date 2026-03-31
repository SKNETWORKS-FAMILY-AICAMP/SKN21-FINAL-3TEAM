# v3_generate 성능 개선 플랜 (v2)

> 작성일: 2026-03-27
> 모델: kakaocorp/kanana-1.5-8b-instruct-2505 + QLoRA 4bit
> 태스크: 문서 생성 (회의록/보고서/제안서 JSON 구조화 출력)
> 인프라: RunPod H200
> 제약: 데이터 추가 생성 불가

---

## 1. 현황 진단

### 1-1. v3 설계 의도 (정확한 해석)

v3는 **"입력에 근거가 있는 필드만 채우고, 근거 없으면 비워라"**를 학습시킨 모델이다.

- 길이별 sparse 비율: short(60%) / mid(30%) / long(20%) / xlong(10%)
- budget: "문서에 수치가 있을 때만" 채움
- priority 필드: 80% 포함 (20%는 의도적으로 빈 상태)

따라서 **필드 채움률 하락은 문제가 아니라 의도된 동작**이며, Base의 94~100% 채움률이 오히려 할루시네이션(False Fill 44.3%)이었다.

### 1-2. 현재 지표 (checkpoint-170, epoch 2)

| 지표 | Base | FT (ep2) | 판정 |
|------|------|----------|------|
| JSON 유효율 | 77.3% | 87.3% | ⚠️ **12.7% 실패 — 핵심 개선 대상** |
| ROUGE-L | 0.465 | 0.665 | ✅ +43% |
| BERTScore F1 | 0.896 | 0.926 | ✅ +3.4% |
| False Fill율 | 44.3% | 17.9% | ✅ -59%, **추가 억제 가능** |
| 빈 필드 정확도 | 55.7% | 82.1% | ✅ 근거 판단 능력 학습됨 |

### 1-3. 개선 대상 3가지 (우선순위 순)

| # | 지표 | 현재 | 목표 | 왜 개선해야 하는가 |
|---|------|------|------|-------------------|
| 1 | **JSON 유효율** | 87.3% | 95%+ | 파싱 실패 = 서비스 불가. 가장 치명적 |
| 2 | **False Fill율** | 17.9% | 10%↓ | 근거 없이 채운 필드 = 사용자 신뢰↓ |
| 3 | **ROUGE-L** | 0.665 | 0.70+ | 채운 필드의 내용 품질 향상 |

**채움률은 개선 대상이 아님** — 현재 동작이 설계 의도와 일치.

### 1-4. JSON 유효율 실패 근본 원인 분석

eval 스크립트(`eval_v3_generate.py:131-137`)의 추론 설정:
```python
inputs = tokenizer(prompt, truncation=True, max_length=2560)  # 입력 2560 토큰
outputs = model.generate(**inputs, max_new_tokens=1024)        # 출력 1024 토큰
```

**원인 1: 출력 토큰 부족 (주요 원인, 추정 60~70%)**
- 평균 출력 길이 1395자 → `max_new_tokens=1024`에 매우 근접
- 복잡한 제안서(budget/schedule 필드가 긴 리스트)는 1024 토큰 초과 → JSON이 중간에 잘림 → 파싱 실패
- 제안서가 ROUGE-L 개선 최대(+39.8%)이면서 필드 결손 최대인 이유도 이것

**원인 2: 학습 시 max_length=2560 (입력+출력 합산)**
- 학습 시 시퀀스 전체가 2560에 맞춰지므로, 긴 입력 + 긴 출력 조합이 잘림
- 모델이 "긴 JSON을 끝까지 닫는" 패턴을 충분히 학습하지 못함

**원인 3: 인코딩/구조 오류 (추정 10~20%)**
- 한글 텍스트 내 이스케이프 안 된 따옴표, 개행 등

---

## 2. 실험 설계

### 개선 전략 구분

```
[A] 학습 없이 즉시 적용 (서빙/추론 설정)  — 소요: 수분
[B] 하이퍼파라미터 튜닝 (재학습 필요)      — 소요: 실험당 50~60분
[C] 기존 체크포인트 활용 (평가만)           — 소요: 30분
```

---

### 실험 A: 추론 설정 변경 (학습 불필요)

#### A-1. max_new_tokens 확대

JSON 출력 잘림이 유효율 실패의 주요 원인. 추론 시 토큰 한도만 늘리면 즉시 개선.

| 변경 | 현재 | 변경 후 |
|------|------|---------|
| `max_new_tokens` | 1024 | **1536** |

```python
# eval_v3_generate.py:136
outputs = model.generate(**inputs, max_new_tokens=1536, ...)  # 기존 1024
```

**기대 효과**: JSON 유효율 87.3% → 92~95% (출력 truncation에 의한 실패 대부분 해결)
**리스크**: 추론 시간 소폭 증가 (모델이 EOS를 제대로 생성하면 실제론 비슷)

#### A-2. Temperature / Sampling 전략

현재 `do_sample=False` (greedy). False Fill 억제를 위한 추가 옵션 없음.

| 서빙 옵션 | 현재 | 추천 |
|-----------|------|------|
| `do_sample` | False | False (유지) |
| `repetition_penalty` | 없음 | **1.1** |

> greedy가 JSON 구조화 태스크에는 최적. repetition_penalty로 반복 패턴(할루시네이션의 일종) 억제 가능.

#### A-3. vLLM 서빙 시 Guided Decoding

vLLM 서빙 환경에서 `guided_json` 파라미터로 JSON 스키마 강제:

```python
# vLLM 서빙 호출 시
response = client.chat.completions.create(
    model="...",
    messages=messages,
    extra_body={
        "guided_json": json_schema,  # 문서 유형별 JSON 스키마
    }
)
```

**기대 효과**: JSON 유효율 사실상 100%
**제약**: vLLM 서빙 환경에서만 가능 (평가 스크립트에서는 peft 직접 로드이므로 불가)

---

### 실험 B: 하이퍼파라미터 재학습

#### B-1. max_length 확대 (가장 중요)

학습 시 입력+출력 합산 길이를 늘려서, 모델이 **긴 JSON을 끝까지 생성하는 패턴**을 학습.

| 항목 | 현재 | 변경 |
|------|------|------|
| `max_length` | 2560 | **4096** |

```yaml
# v3_generate.yaml
training:
  max_length: 4096  # 기존 2560
```

**근거**:
- v3_summary는 max_length를 2560→8192로 올려서 truncation 문제를 해결한 전례가 있음
- generate의 출력이 1300~1600자인 점 감안, 입력(~1000자) + 출력(~1600자) = ~2600자 → 2560이면 잘리는 샘플 존재
- 4096이면 xlong(3000자) 입력 + 긴 출력도 커버

**기대 효과**: JSON 유효율 ↑ (잘림 방지), ROUGE-L ↑ (전체 입력을 보고 생성)
**비용**: VRAM 소폭 증가 (5.7GB → ~7GB 추정), 학습 시간 소폭 증가

#### B-2. Learning Rate 낮추기

현재 1e-4에서 epoch 2가 best, epoch 3부터 overfitting. LR을 낮추면:
- 수렴이 느려져서 더 많은 epoch에 걸쳐 점진적 학습
- Base의 JSON 생성 능력을 덜 훼손
- epoch 1~2 사이의 "급격한 변화" 완화

| 실험 | LR | epochs | 근거 |
|------|-----|--------|------|
| B-2a | **5e-5** | 7 | 현재의 절반, epoch 수 보상 |
| B-2b | **3e-5** | 10 | 보수적, 충분한 step 확보 |

```yaml
training:
  learning_rate: 5e-5  # 기존 1e-4
  num_epochs: 7        # 기존 5
```

**기대 효과**: False Fill ↓ (Base 판단력 보존), JSON 유효율 유지/소폭 ↑

#### B-3. LoRA rank 축소

| 항목 | 현재 | 변경 | 근거 |
|------|------|------|------|
| r | 32 | **16** | v3_summary(r=16)가 이미 잘 동작. 수정 범위 축소 → Base 보존 |
| alpha | 64 | **32** | alpha/r = 2.0 비율 유지 |

**기대 효과**: False Fill ↓ (과도한 파라미터 수정 방지), 학습 시간 ↓
**리스크**: 학습 용량 부족 시 JSON 유효율 하락 가능 → eval_loss로 모니터링

#### B-4. 세분화 체크포인트 (B-1~3과 함께 적용)

현재 `save_strategy="epoch"`라서 epoch 단위로만 체크포인트. Epoch 1(0.520) → Epoch 2(0.508) 사이에 최적점 존재 가능.

```yaml
output:
  save_steps: 25  # epoch당 ~3.4개 체크포인트
```

```python
# train_v2_document.py 수정
training_args = SFTConfig(
    save_strategy="steps",
    save_steps=25,
    eval_strategy="steps",
    eval_steps=25,
    ...
)
```

---

### 실험 C: 기존 체크포인트 평가 (학습 불필요)

#### C-1. checkpoint-85 (epoch 1) + max_new_tokens=1536

추가 학습 없이 기존 체크포인트에 A-1(출력 토큰 확대)만 적용하여 평가.

```bash
# eval 스크립트에서 max_new_tokens=1536으로 변경 후 실행
python ai/finetuning/scripts/eval_v3_generate.py \
  --adapter outputs/v3_generate/kanana-1.5-8b-instruct-2505/checkpoints/checkpoint-85
```

**확인할 것**:
- Epoch 1에서 JSON 유효율이 더 높은가? (덜 학습 = JSON 구조 보존)
- False Fill이 epoch 2보다 낮은가? 높은가?
- 근거 판단 능력은 이미 epoch 1에서 충분한가?

#### C-2. checkpoint-170 (epoch 2) + max_new_tokens=1536 재평가

동일 체크포인트를 출력 토큰만 늘려서 재평가. **A-1의 효과만 순수 측정.**

```bash
# max_new_tokens=1536으로 변경 후 기존 checkpoint-170 재평가
python ai/finetuning/scripts/eval_v3_generate.py \
  --adapter outputs/v3_generate/kanana-1.5-8b-instruct-2505/checkpoints/checkpoint-170
```

---

## 3. 실험 순서

```
Phase 0: 즉시 적용 (소요: 10분)
├── A-1: eval 스크립트 max_new_tokens 1024→1536 변경
└── A-2: repetition_penalty=1.1 추가

Phase 1: 기존 체크포인트 재평가 (소요: ~1시간)
├── C-2: checkpoint-170 + max_new_tokens=1536 재평가     [30분]
│   → JSON 유효율 변화 확인 (출력 잘림이 원인이었는지 검증)
└── C-1: checkpoint-85 + max_new_tokens=1536 평가        [30분]
│   → epoch 1 vs epoch 2 비교
└── 분석: C-2에서 JSON 유효율이 92%+ 나오면 "출력 잘림이 주원인" 확정

Phase 2: 재학습 (소요: ~2시간, Phase 1 결과에 따라 선택)
├── 설정: B-1(max_length=4096) + B-2a(LR=5e-5) + B-4(save_steps=25)
│   → epochs=7, 나머지 동일
│   → 학습 ~60분 + 유망 체크포인트 2~3개 평가 ~60분
│
└── (Phase 2 결과가 불충분 시)
    B-3 추가: r=16, alpha=32 + 위 설정 조합
    → 학습 ~50분 + 평가 ~30분

Phase 3: 서빙 최적화 (학습 완료 후)
└── A-3: vLLM guided_json 적용
```

**총 예상 소요: 3~4시간**

---

## 4. 실험별 config 변경 요약

| 실험 | 변경 대상 | 변경 내용 |
|------|----------|----------|
| A-1 | `eval_v3_generate.py:136` | `max_new_tokens: 1024 → 1536` |
| A-2 | `eval_v3_generate.py:136` | `repetition_penalty=1.1` 추가 |
| B-1 | `v3_generate.yaml` | `max_length: 2560 → 4096` |
| B-2a | `v3_generate.yaml` | `learning_rate: 1e-4 → 5e-5`, `num_epochs: 5 → 7` |
| B-3 | `v3_generate.yaml` | `r: 32 → 16`, `lora_alpha: 64 → 32` |
| B-4 | `train_v2_document.py:315-316` | `save_strategy: "steps"`, `save_steps: 25`, `eval_steps: 25` |
| C-1 | 없음 (eval 경로만 변경) | `--adapter checkpoint-85` |

---

## 5. 성공 기준

### 최소 기준 (발표 가능)
- JSON 유효율 >= 93%
- False Fill율 <= 15%
- ROUGE-L >= 0.65
- 빈 필드 정확도 >= 82% (현재 수준 유지 = 근거 판단 능력 보존)

### 목표 기준 (만족스러운 결과)
- JSON 유효율 >= 95%
- False Fill율 <= 12%
- ROUGE-L >= 0.70
- BERTScore F1 >= 0.92

### 이상적 기준 (서빙 시 guided_json 포함)
- JSON 유효율 ~100% (guided decoding)
- False Fill율 <= 10%
- ROUGE-L >= 0.70

> **주의: 빈 필드 정확도(82.1%)가 하락하면 안 됨.** 이 지표가 떨어지면 모델이 "근거 판단" 능력을 잃고 다시 할루시네이션으로 회귀하는 것.

---

## 6. 리스크 및 대응

| 리스크 | 영향 | 대응 |
|--------|------|------|
| max_length 4096으로 VRAM 부족 | 학습 불가 | `batch_size: 4 → 2` + `gradient_accumulation: 4 → 8` (effective 동일) |
| LR 낮추면 수렴 안 됨 | JSON 유효율 ↓ | epoch 수 충분히 확보 (7~10), eval_loss 모니터링 |
| max_new_tokens 늘려도 JSON 유효율 변화 없음 | 원인 오진 | → 인코딩/구조 오류가 주원인. parse_json 로직 보강 (후처리 수리) |
| r=16이면 학습 용량 부족 | JSON 유효율 ↓ | eval_loss가 수렴 안 하면 r=32 유지 |

---

## 7. 결과 기록 템플릿

```
### 실험 X 결과 (YYYY-MM-DD)
- 설정: LR=, r=, alpha=, epochs=, max_length=, max_new_tokens=
- 최적 checkpoint: step N (eval_loss=)
- JSON 유효율: % (기존 87.3%)
- False Fill율: % (기존 17.9%)
- 빈 필드 정확도: % (기존 82.1% — 이 값 유지/상승이 필수)
- ROUGE-L: (기존 0.665)
- BERTScore F1: (기존 0.926)
- 판정: 채택 / 기각 / 추가 실험
- 비고:
```

---

## 8. 핵심 요약

```
v3_generate의 근거 기반 판단 능력은 정상 동작 중.
개선해야 할 것은 "무엇을 채울지"가 아니라 "어떻게 출력하는지":

1. JSON 유효율 87.3% → 95%+  (출력 잘림 해결 + 학습 max_length 확대)
2. False Fill 17.9% → 10%↓    (LR 낮추기 + rank 축소로 판단력 강화)
3. ROUGE-L 0.665 → 0.70+      (입력 truncation 방지 + 세분화 체크포인트)

빈 필드 정확도(82.1%)는 유지/상승해야 함 = 근거 판단 능력 보존 필수.
```
