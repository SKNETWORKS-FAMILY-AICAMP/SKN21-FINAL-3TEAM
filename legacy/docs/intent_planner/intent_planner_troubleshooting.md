# Intent, Planner Trouble Shooting

---

# Part 1. Intent 분류 모델

## 1. koelectra 과적합 (Dev 90% vs Held-out 76.7%)

### 문제
- koelectra(112M)로 v4까지 반복 학습 → Dev(기존 ADV) 점수 **90.0%** 달성
- 그러나 한 번도 본 적 없는 Held-out 60건으로 검증하자 **76.7%** — 차이 **-13.3%p**
- 테스트셋 오답을 보고 학습 데이터를 만들었기 때문에, 같은 테스트에서만 높은 성능

### 원인
- **오답→보강→같은 테스트 평가 반복** 사이클이 과적합을 유발
- koelectra(112M)의 파라미터가 작아 패턴을 암기하는 방식으로 학습

### 해결: klue/roberta-large (338M) 모델 교체
- KLUE 벤치마크 분류 1위 모델로 교체
- 동일 데이터로 학습 → Held-out **76.7%** (동일)이지만 과적합 gap **-3.3%p** (건강한 일반화)

### 교훈
> Dev 점수를 믿으면 안 된다. **Held-out으로 검증해야 진짜 성능**이다.

---

## 2. 후보 모델 탐색 실패 (xlm-roberta 붕괴, DeBERTa 학습 불가)

### 문제
- roberta-large 외 다른 아키텍처로 크로스 모델 앙상블을 시도

### 시도한 모델과 결과

| 모델 | 파라미터 | 단일 Held-out | 앙상블 | 과적합 | 안정성 |
|------|---------|-------------|--------|--------|--------|
| klue/roberta-large | 338M | 88.3% | **93.3%** | -3.3%p ✅ | 5/5 성공 |
| KcBERT-large | 335M | 85.0% | 88.3% | -3.3%p | 5/5 성공 |
| xlm-roberta-large | 550M | 85.0% | **불가** | -10.0%p ⚠️ | **seed 붕괴** |
| DeBERTa-v3-large | 304M | **실패** | - | - | **전체 실패** |

### xlm-roberta-large (550M) 붕괴
- seed 42, 123, 456: 정상 학습 (85%+)
- **seed 789: 39.1%** — epoch 1에서 38% 달성 후 epoch 2부터 **0%로 추락**, 10 에포크 동안 회복 불가
- 원인: 특정 seed에서 gradient 불안정 → 학습 붕괴 (모델 고유 문제)
- transformers 업그레이드 + 캐시 정리 후에도 동일 → **안정적인 앙상블 구성 불가**

### DeBERTa-v3-large 실패
- SentencePiece 모델 파일(spm.model) 파싱 에러
- protobuf 미설치 + 캐시 손상으로 학습 자체 불가

### 교훈
> 파라미터가 크다고 성능이 좋은 게 아니다. xlm-r(550M)보다 roberta(338M)이 우수했다.

---

# Part 2. Planner 모델

## 5. 후처리 매핑 (Planner judgment↔doc_retrieve 혼동)

### 문제
- Planner가 "규정 찾아서 판단해줘" 같은 질문에서 judgment와 doc_retrieve를 혼동 — **15건 오분류**
- LoRA로 아무리 학습해도 베이스 모델(Kanana 8B)의 "규정 = 정보검색" 사전 지식을 덮어쓸 수 없었음

### 시도한 해결책 (전부 실패)

| 시도 | 방법 | 결과 |
|------|------|------|
| 시도 1 | +121건 judgment 데이터 보강 | 12건 그대로 ❌ |
| 시도 2 | 프롬프트에 구분 기준 명시 | PM +7건이지만 12건 여전 ❌ |
| 시도 3 | 5-label 전환 (judgment+doc_retrieve → knowledge_query) | PM 34.7% 대폭락 ❌ |

- **5-label 실패 원인**: 베이스 모델이 `knowledge_query`라는 새 라벨 자체를 무시하고 기존 라벨만 출력

### 발상의 전환 → 해결
- "모델을 바꾸려 하지 말고, 모델 출력을 바꾸자"
- 학습은 6-label 유지 → 평가/서빙에서만 judgment + doc_retrieve → `knowledge_query`로 후처리 매핑
- **결과: 혼동 12건 전부 해소, PM 69.5% → 83.2% (+13.7%p)**

### 교훈
> 모델 구조를 억지로 바꾸는 것보다 후처리로 우회하는 게 답일 때가 있다

---

## 6. Planner v6 재학습 대실패 (87% → 64%)

### 문제
- v5(87.0%)에서 더 올리려고 3가지를 동시에 변경:
  - lr 낮추기
  - MLP target_modules 추가 (q,v,k,o → + gate,up,down_proj)
  - judgment 오답 57건 타겟 보강

### 결과: PM 87% → 64% 폭락

| 지표 | v5 | v6 | 변화 |
|------|-----|-----|------|
| Perfect Match | 71.0% | 64.0% | -7%p |
| 과잉 분리 | 5건 | 9건 | +4건 |
| Step Collapse | 9.4% | 11.3% | +1.9%p |

### 원인: MLP + judgment 보강이 모델을 judgment 과잉 예측으로 밀어버림
- v5에서는 judgment→doc_retrieve 15건이 문제 → v6에서는 반대로 doc_retrieve→judgment 11건 발생
- 단일 step 질문을 2-3 step으로 과도하게 분해

### 교훈
- 한 번에 여러 변수를 바꾸면 뭐가 원인인지 알 수 없다
- 데이터/파라미터 늘린다고 항상 좋아지진 않는다
- v6 전체 폐기, v5 유지 결정
