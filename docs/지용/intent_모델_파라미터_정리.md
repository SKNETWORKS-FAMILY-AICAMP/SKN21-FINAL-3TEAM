# Intent Classification 모델 파라미터 정리

> 최종 배포 모델 기준 (실험 5 best config, 2026-02-16 확정)

---

## 1. 모델 기본 정보

| 항목 | 값 |
|------|-----|
| **Base Model** | `klue/bert-base` |
| **Architecture** | BertForSequenceClassification |
| **총 파라미터 수** | 111M (1억 1,100만) |
| **Task** | 7-class single_label_classification |
| **Framework** | Hugging Face Transformers + Trainer |
| **Tokenizer** | `klue/bert-base` (BertTokenizer, vocab_size=32,000) |

---

## 2. 모델 구조 파라미터 (BERT 아키텍처)

| 항목 | 값 | 설명 |
|------|-----|------|
| `hidden_size` | 768 | 각 토큰의 임베딩 벡터 차원 |
| `num_hidden_layers` | 12 | Transformer 레이어(블록) 수 |
| `num_attention_heads` | 12 | 멀티헤드 어텐션의 헤드 수 |
| `intermediate_size` | 3,072 | FFN(피드포워드) 중간 레이어 차원 |
| `hidden_act` | gelu | 활성화 함수 |
| `max_position_embeddings` | 512 | 입력 가능한 최대 토큰 수 |
| `vocab_size` | 32,000 | 토크나이저 어휘 크기 |
| `type_vocab_size` | 2 | segment (문장 구분) 타입 수 |
| `attention_probs_dropout_prob` | 0.1 | 어텐션 가중치 드롭아웃 |
| `hidden_dropout_prob` | 0.1 | 히든 레이어 드롭아웃 |
| `layer_norm_eps` | 1e-12 | 레이어 정규화 epsilon |
| `initializer_range` | 0.02 | 가중치 초기화 범위 |
| `classifier_dropout` | null (기본 0.1) | 분류 헤드 드롭아웃 |
| `pad_token_id` | 0 | 패딩 토큰 ID |

---

## 3. 학습 하이퍼파라미터 (Fine-tuning)

### 최종 배포 설정 (실험 5 best config)

| 항목 | 값 | 비고 |
|------|-----|------|
| **Epochs** | **5** | 3~10 탐색 후 5가 최적 (10은 과적합 발생) |
| **Learning Rate** | **2e-5** | BERT 원논문 권장 범위, 1e-5~5e-5 탐색 |
| **Batch Size** | **16** | 8/16/32 탐색, 16이 최적 |
| **Warmup Ratio** | **0.0** | 0.0/0.06/0.1 탐색, 0.0이 최적 |
| **Weight Decay** | **0.01** | BERT 표준값 (고정) |
| **Max Length** | **64** | 입력 토큰 최대 길이 (평균 입력 대비 충분) |
| **Seed** | **42** | 재현성 보장 (seed 3개 검증: 42, 123, 456) |
| **Optimizer** | AdamW | Trainer 기본값 |
| **Best Model Selection** | f1_macro 기준 | epoch별 평가 후 최고 F1 모델 저장 |

### 하이퍼파라미터 탐색 범위 (실험 5, 153번 학습)

| 파라미터 | 탐색 범위 | 최적값 |
|---------|----------|--------|
| epochs | [3, 5, 7, 10] | **5** |
| learning_rate | [1e-5, 2e-5, 3e-5, 5e-5] | **2e-5** |
| batch_size | [8, 16, 32] | **16** |
| warmup_ratio | [0.0, 0.06, 0.1] | **0.0** |

> 탐색 방법: 3모델(BERT/RoBERTa/KoELECTRA) x 51조합 = 153번 Grid Search (RunPod RTX 4090)

---

## 4. 학습 데이터

| 항목 | 값 |
|------|-----|
| **총 학습 데이터** | 1,916문장 (v1.3) |
| **Train / Eval 분할** | 85:15 층화(stratified) 분할 |
| **Train** | ~1,629문장 |
| **Eval** | ~287문장 |
| **데이터 출처** | Claude 생성 + 수동 증강 + 라벨 QA |

### 카테고리별 분포 (7개 클래스)

| 카테고리 | 설명 | 데이터 수 (대략) |
|----------|------|:----------------:|
| judgment | 규정 기반 판단 | ~255 + 증강 |
| doc_search | 문서 검색 | ~200 + 증강 |
| doc_generate | 문서 생성 | ~200 + 증강 |
| meeting_generate | 회의록 생성 | ~200 + 증강 |
| schedule_add | 일정 추가 | ~200 + 증강 |
| schedule_view | 일정 조회 | ~200 + 증강 |
| general | 일반 질문 | ~200 + 증강 |

### 데이터 버전 히스토리

| 버전 | 총 데이터 | 변경 내용 |
|------|:---------:|----------|
| v1.0 | 1,405 | 초기 파인튜닝 (카테고리별 200문장) |
| v1.1 | 1,455 | +50 judgment 캐주얼 문장 |
| v1.2 | 1,755 | +300 비정형/인터넷 슬랭/초성 (6카테고리 x 50) |
| **v1.3** | **1,916** | **+163 boundary 타겟 증강 + 라벨 QA 3건 수정** |

---

## 5. 추론 시 설정

### 전처리 파이프라인 (4단계, 추론 시에만 적용)

| 순서 | 단계 | 처리 내용 | 예시 |
|:---:|------|----------|------|
| P4 | 공백/특수문자 정리 | 불필요한 공백, 이모지, 특수문자 제거 | "회의록 ㅋㅋ   만들어줘!!" → "회의록 만들어줘" |
| P1 | 맞춤법 교정 | 규칙 기반 오타 교정 | "연챠 규정" → "연차 규정" |
| P2 | 초성 복원 | 한글 초성을 의미 있는 단어로 변환 | "ㅎㅇㄹ 만들어줘" → "회의록 만들어줘" |
| P3 | 슬랭/축약어 정규화 | 인터넷 용어를 표준어로 | "걍 그거 해주셈" → "그냥 그거 해주세요" |

> 전처리 기여도 (Adversarial F1): P1(맞춤법) > P2(초성) > P3(슬랭) > P4(공백)
> 전체 적용 시 +1.3%p 개선 (실험 6, 3-seed 평균)

### Confidence Threshold 설정

| 항목 | 값 | 동작 |
|------|-----|------|
| `INTENT_CONFIDENCE_THRESHOLD` | **0.7** | 이하면 사용자에게 clarify 요청 (top-3 후보 제시) |
| `INTENT_FALLBACK_THRESHOLD` | **0.5** | 이하면 general 강제 전환 |
| `COMPLEXITY_GAP_THRESHOLD` | **0.3** | top-2 confidence gap 기준 (복합 질문 감지용) |

### 알려진 오분류 보정 (규칙 기반 오버라이드)

| 패턴 | 보정 결과 | 예시 |
|------|----------|------|
| (인센티브\|성과급\|보너스).*(기준\|조건) | judgment | "인센티브 지급 기준 알려줘" |
| (남은\|다음).*(공휴일\|휴일) | schedule_view | "남은 공휴일이 언제야?" |
| (규정\|규칙\|지침).*(알려\|설명) | judgment | "연차 규정 알려줘" |
| (복리후생\|복지\|수당).*(뭐\|어떤\|있어) | judgment | "복리후생 뭐 있어?" |
| (퇴직금\|급여).*(계산\|산정) | judgment | "퇴직금 계산해줘" |
| (지각\|결근).*(어떻게\|징계) | judgment | "지각하면 어떻게 돼?" |

> Blind 테스트에서 틀린 5건 중 2건은 이 오버라이드로 커버됨

---

## 6. 최종 성능 요약

| 지표 | 값 |
|------|-----|
| Eval F1 (정규 입력) | **98.23%** |
| Adversarial F1 (212문장, seed=42, 전처리) | **90.07%** |
| Adversarial F1 (3-seed 평균, 전처리) | **88.56% ± 2.28%** |
| 95% CI (Bootstrap 10,000회) | **[85.52%, 93.84%]** |
| Blind F1 (독립 70문장) | **92.84%** |
| 추론 속도 | **7.48ms/문장** (RTX 4090) |
| 운영 비용 | **$0** |

### 비교 모델 탈락 사유

| 모델 | Adv F1 | 탈락 사유 |
|------|:------:|----------|
| klue/roberta-base | 0.8990 | BERT와 동급이나 Adversarial에서 약간 뒤짐 |
| monologg/koelectra-base-v3 | 0.8856 | 수렴에 epochs=10 필요, 학습 비용 대비 효과 낮음 |
| GPT-4o-mini Few-shot | 0.8630 | 1~2어절 짧은 입력에서 취약, 속도 45배 느림, 유료 |

---

## 7. 파일 위치

| 항목 | 경로 |
|------|------|
| 모델 weights | `ai/models/intent_classifier/model.safetensors` |
| 모델 config | `ai/models/intent_classifier/config.json` |
| Label map | `ai/models/intent_classifier/label_map.json` |
| Tokenizer | `ai/models/intent_classifier/tokenizer.json` |
| 추론 코드 | `ai/agents/intent_classifier.py` |
| 전처리 코드 | `ai/experiments/preprocessing.py` → `ai/agents/preprocessing.py` |
| Threshold 설정 | `ai/agents/config.py` |
| 학습 로그 | `ai/models/TRAINING_LOG.md` |
| 실험 기획서 | `ai/experiments/EXPERIMENT_PLAN.md` |
