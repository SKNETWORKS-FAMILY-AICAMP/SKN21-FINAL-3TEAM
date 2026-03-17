# 문서 생성 sLLM 파인튜닝 v3 — 학습 데이터 재설계

> GPU: RunPod | 태스크: 문서 생성 (회의록/보고서/제안서) | 모델: Kanana-1.5-8B
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
  보고서: tasks, next_plan
  제안서: schedule, budget

content (랜덤):
  나머지 (agenda, risks, notes, achievements 등)
```

**설계 근거**:
- always: 추론 시 항상 요청하는 필드 → 학습도 100%로 매칭
- priority: 80% 채움 + 20% 빈 값 → "채우는 법 + 안 채우는 법" 동시 학습
- content: 다양한 조합 학습 → 필드 명세를 읽고 따르는 능력

### 2-2. 입력 길이 다양화

v2는 모든 입력이 500~1500자로 균일했으나, 실서비스에서는:

```
v2: 500~1500자 100%
v3: short(50~200) 30% / mid(200~800) 40% / long(800~1500) 20% / xlong(1500+) 10%
```

| 길이 | 비율 | 사용 패턴 |
|------|:----:|----------|
| short (50~200자) | 30% | 폼에서 제목+한줄 메모 |
| mid (200~800자) | 40% | 챗봇 일반 입력 |
| long (800~1500자) | 20% | 상세 기술 |
| xlong (1500~3000자) | 10% | 회의 전체 내용 붙여넣기 |

**핵심**: 짧은 입력에서 풍부한 문서를 만드는 게 가장 어려운 태스크 — v2에는 이 패턴이 없었음.

### 2-3. 할루시네이션 방지 설계

| 방지 수단 | 방법 |
|-----------|------|
| **sparse 샘플 30%** | OMITTABLE_FIELDS만 비움 (priority는 보호) |
| **next_plan 81%** | 100%면 "항상 채워야 한다"로 학습 → 81%로 조정 |
| **content str 강제** | description에 "서술형 문자열로"를 명시하여 list/dict 방지 |
| **budget 근거 기반** | "문서에 수치가 있을 때만" — 숫자 할루시네이션 방지 |

---

## 3. 데이터 파이프라인

### 3-1. 처리 흐름

```
① Synthetic 800건 생성 (GPT-4o)
   → always_content 100% + priority 80% + 입력 길이 다양화
②  AI Hub 700건 정제 (GPT-4o-mini)
   → 빈 priority 필드 보충 + 25% 입력 축약
③ 필터링 (filter_and_select.py)
   → C급(always 미달) 154건 제거 + short 초과분 선별 → 1077건
④ Priority 보완 (boost_priority.py)
   → B급의 빈 priority를 GPT로 보충 → 327건 보완
⑤ 서술형 필드 str 변환
   → content/main_content list/dict → str 664건 변환
⑥ 부족분 추가 생성 (generate_supplement.py)
   → 502건 (mid/long/xlong만, min_length 검증 + 2차 boost)
⑦ 합치기 + 분할 (merge_and_split.py)
   → 초과분 79건 제거 → 1500건 → train 1350 / eval 150
```

### 3-2. 데이터 소스

| 소스 | 원본 | 필터 후 | 역할 |
|------|:----:|:------:|------|
| Synthetic (v2 재생성) | 800건 | 521건 | always/priority 계층 + 입력 길이 다양화 |
| AI Hub (정제) | 700건 | 556건 | 실제 문서 패턴 + 근거 기반 보충 |
| Supplement (부족분) | 502건 | 502건 | mid/long/xlong 부족분 보충 |
| **합계** | **2002건** | **1579건** | **→ 1500건 (초과 제거)** |

### 3-3. 최종 분포 목표

**유형 × 길이:**
```
              short   mid    long   xlong   합계
meeting:      150     200    100    50      500
report:       150     200    100    50      500
proposal:     150     200    100    50      500
합계:         450     600    300    150     1500
```

**필드 채움률 (boost 후 + supplement 반영 예상):**

| 필드 | v2 | v3 (기존 1077건) | v3 (supplement 포함 예상) |
|------|:--:|:----------------:|:----------------------:|
| content/summary | 32~34% | 100% | 100% |
| decisions | 34% | 93% | ~90% |
| action_items | 34% | 96% | ~93% |
| tasks | 14% | 73% | ~80% |
| next_plan | 34% | 81% | ~81% |
| schedule | 25% | 87% | ~85% |
| budget | 25% | 43% | ~50% |

---

## 4. 학습 설정 (v2와 동일)

| 항목 | 값 | 비고 |
|------|-----|------|
| Base Model | kakaocorp/kanana-1.5-8b-instruct-2505 | v2와 동일 |
| 양자화 | 4-bit (NF4) QLoRA | v2와 동일 |
| LoRA r | 32 | v2와 동일 |
| LoRA alpha | 64 | v2와 동일 |
| Target Modules | q, k, v, o, gate, up_proj | v2와 동일 |
| Epochs | 5 (eval loss로 best 선택) | v2와 동일 |
| Batch size | 4 (grad accum 4 = effective 16) | v2와 동일 |
| Learning rate | 1e-4 | v2와 동일 |
| max_length | 2560 | v2와 동일 |

**변경 없는 이유**: v2의 학습 설정 자체는 문제 없었음. 문제는 데이터 분포. 동일 설정으로 데이터만 개선하여 효과를 순수하게 측정.

---

## 5. v2 → v3 변경 요약

| 항목 | v2 | v3 |
|------|:--:|:--:|
| 필드 계층 | 2계층 (core + 랜덤) | **3계층 (always + priority + 랜덤)** |
| content 포함률 | 32% | **100%** |
| decisions 포함률 | 34% | **~80%** |
| tasks 포함률 | 14% | **~80%** |
| 입력 길이 | 500~1500자 균일 | **50~3000자 다양화** |
| 짧은 입력 패턴 | 없음 | **30% (50~200자)** |
| content list/dict | 방치 | **str 강제 변환** |
| 데이터 파이프라인 | 1단계 (생성만) | **7단계 (생성→정제→필터→보완→변환→보충→합치기)** |

---

## 6. 평가 계획

### 구조 지표 (v2와 동일)

| 지표 | v2 결과 | v3 목표 |
|------|:-------:|:------:|
| JSON 유효율 | 98.67% | 98%+ |
| 필드 완성도 | 98.67% | 98%+ |
| 필드 정확도 | 100% | 100% |

### 내용 품질 지표

| 지표 | v2 결과 | v3 목표 | 의미 |
|------|:-------:|:------:|------|
| 빈 필드 정확도 | 83.07% | 85%+ | 할루시네이션 감소 |
| false fill율 | 16.93% | 15% 이하 | 지어내기 감소 |
| ROUGE-L | 0.5779 | 0.60+ | 내용 일치도 향상 |
| BERTScore F1 | 0.9222 | 0.93+ | 의미 유사도 향상 |

### 신규 지표 (v3 추가)

| 지표 | 정의 | 목표 |
|------|------|:----:|
| **decisions 채움률** | decisions가 필드 명세에 있을 때 빈 배열이 아닌 비율 | 80%+ |
| **tasks 채움률** | tasks가 필드 명세에 있을 때 빈 배열이 아닌 비율 | 70%+ |
| **schedule 채움률** | 동일 | 70%+ |
| **짧은 입력 대응** | 50~200자 입력에서 content 300자+ 생성 비율 | 90%+ |

---

## 7. 실행 상태

| 단계 | 상태 |
|------|:----:|
| Synthetic 800건 생성 | ✅ 완료 |
| AI Hub 700건 정제 | ✅ 완료 |
| 필터링 (1077건) | ✅ 완료 |
| Priority 보완 (327건) | ✅ 완료 |
| 서술형 필드 str 변환 | ✅ 완료 |
| Supplement 502건 추가 생성 | ⏳ 진행 중 (500/502) |
| merge_and_split → train/eval | ⏰ 대기 |
| RunPod LoRA v3 학습 | ⏰ 대기 |
| 평가 (구조 + 내용 + 신규 지표) | ⏰ 대기 |

---

## 8. 학습 결과

> 학습 후 기록

### 8-1. Epoch별 지표 추이

| Epoch | Train Loss | Eval Loss | Token Accuracy | 비고 |
|-------|-----------|-----------|----------------|------|
| 1 | — | — | — | |
| 2 | — | — | — | |
| 3 | — | — | — | |
| 4 | — | — | — | |
| 5 | — | — | — | |

> Best checkpoint: **Epoch ?** (eval_loss = ?)

### 8-2. Loss 변화 상세

```
Epoch 1    ░░░░░░░░░░░░░░░░░░░░░░░░░  Train: ? → Eval: ?
Epoch 2    ░░░░░░░░░░░░░░░░░░░░░░░░░  Train: ? → Eval: ?
Epoch 3    ░░░░░░░░░░░░░░░░░░░░░░░░░  Train: ? → Eval: ?
Epoch 4    ░░░░░░░░░░░░░░░░░░░░░░░░░  Train: ? → Eval: ?
Epoch 5    ░░░░░░░░░░░░░░░░░░░░░░░░░  Train: ? → Eval: ?
```

### 8-3. 학습 효율

| 항목 | 수치 |
|------|------|
| 총 학습 시간 | — |
| 처리 속도 | — samples/sec |
| 총 스텝 수 | — steps |
| VRAM 사용량 | — GB (학습) / — GB (추론) |
| 어댑터 크기 | — MB |

---

## 9. 평가 결과

### 9-1. 구조 지표 (v2 → v3)

| 지표 | v2 결과 | v3 결과 | 변화 |
|------|:-------:|:-------:|:----:|
| JSON 유효율 | 98.67% | —% | — |
| 필드 완성도 | 98.67% | —% | — |
| 필드 정확도 | 100% | —% | — |

### 9-2. 내용 품질 지표 (v2 → v3)

| 지표 | v2 결과 | v3 결과 | 변화 | 의미 |
|------|:-------:|:-------:|:----:|------|
| 빈 필드 정확도 | 83.07% | —% | — | 할루시네이션 |
| false fill율 | 16.93% | —% | — | 지어내기 |
| ROUGE-L | 0.5779 | — | — | 내용 일치도 |
| BERTScore F1 | 0.9222 | — | — | 의미 유사도 |
| 평균 출력 길이 | 974자 | —자 | — | 간결성 |

> BERTScore 모델: `klue/roberta-large` (한국어 특화 임베딩)

### 9-3. 신규 지표 — 핵심 필드 채움률

| 지표 | v2 | v3 | 목표 |
|------|:--:|:--:|:----:|
| decisions 채움률 | 34% | —% | 80%+ |
| action_items 채움률 | 34% | —% | 80%+ |
| tasks 채움률 | 14% | —% | 70%+ |
| next_plan 채움률 | 34% | —% | 70%+ |
| schedule 채움률 | 25% | —% | 70%+ |
| budget 채움률 | 25% | —% | 50%+ |

### 9-4. 짧은 입력 대응력

| 입력 길이 | 건수 | content 300자+ 비율 | JSON 유효율 |
|----------|:----:|:------------------:|:-----------:|
| short (50~200자) | — | —% | —% |
| mid (200~800자) | — | —% | —% |
| long (800~1500자) | — | —% | —% |
| xlong (1500+자) | — | —% | —% |

### 9-5. 3-Way 비교 (Base vs Fine-tuned vs GPT-4o-mini)

| 모델 | JSON 유효율 | ROUGE-L | BERTScore F1 | 빈 필드 정확도 |
|------|:-----------:|:-------:|:------------:|:-------------:|
| Base Kanana (LoRA 없음) | —% | — | — | —% |
| Fine-tuned Kanana (v3) | —% | — | — | —% |
| GPT-4o-mini (API) | —% | — | — | —% |

### 9-6. 정성 평가 — Before/After

**예시 1: 핵심 필드 채움 개선** (v2 빈 배열 → v3 채움)

| 필드 | 정답 | v2 예측 | v3 예측 |
|------|------|---------|---------|
| decisions | [...] | [] | — |
| action_items | [...] | [] | — |

**예시 2: 짧은 입력 대응**

| | v2 | v3 |
|---|---|---|
| 입력 | (짧은 입력 없었음) | "마케팅 회의 결과 정리해줘" |
| content 길이 | N/A | —자 |

---

## 10. 결론 및 향후 계획

### 성과

> 학습 후 기록

- v2 대비 핵심 필드 채움률: decisions ?% → ?%, tasks ?% → ?%
- 짧은 입력 대응: —
- ROUGE-L: 0.5779 → ?
- BERTScore F1: 0.9222 → ?

### v2 → v3 핵심 개선점

| 항목 | v2 | v3 |
|------|:--:|:--:|
| 핵심 필드 채움 | 14~34% | —% |
| 짧은 입력 대응 | 불가 | — |
| 할루시네이션 | false fill 17% | —% |
| 데이터 파이프라인 | 1단계 | 7단계 |

### 향후

1. vLLM 서빙 연동 (v3 어댑터 로드)
2. summary/qa LoRA 추가 학습 → 멀티 어댑터 서빙
3. GPT-4o 대비 정량 비교 후 sLLM 전환 최종 판단

---

## 11. 산출물

| 파일 | 경로 |
|------|------|
| LoRA 어댑터 | `outputs/v2_generate/kanana-1.5-8b-instruct-2505/final/` |
| 평가 결과 | `outputs/v2_generate/kanana-1.5-8b-instruct-2505/eval_results.json` |
| 3-Way 비교 | `outputs/v2_generate/kanana-1.5-8b-instruct-2505/comparison_results.json` |
| 학습 로그 | `outputs/v2_generate/kanana-1.5-8b-instruct-2505/train_log.json` |
| 학습 설정 | `ai/finetuning/configs/v2_generate.yaml` |
| 학습 데이터 | `data/training/v2_generate/train.jsonl` |
| 평가 데이터 | `data/training/v2_generate/eval.jsonl` |

## 12. 실행 명령어

```bash
# 학습 + 평가
python ai/finetuning/train_v2_document.py --task generate --mode all

# 학습만
python ai/finetuning/train_v2_document.py --task generate --mode train

# 평가만
python ai/finetuning/train_v2_document.py --task generate --mode eval \
    --adapter_path outputs/v2_generate/kanana-1.5-8b-instruct-2505/final

# 3개 모델 비교
python ai/finetuning/train_v2_document.py --task generate --mode compare
```
