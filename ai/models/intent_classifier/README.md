---
language: ko
license: apache-2.0
base_model: monologg/koelectra-base-v3-discriminator
tags:
  - intent-classification
  - koelectra
  - korean
  - text-classification
  - workflow-agent
metrics:
  - f1
  - accuracy
pipeline_tag: text-classification
model-index:
  - name: koelectra-intent-classifier
    results:
      - task:
          type: text-classification
          name: Intent Classification
        metrics:
          - name: Test F1
            type: f1
            value: 0.9788
          - name: Adversarial F1
            type: f1
            value: 0.8784
          - name: Inference Speed
            type: latency
            value: 7.9
            unit: ms
---

# KoELECTRA Intent Classifier

업무 자동화 워크플로우 에이전트(듀듀)를 위한 **한국어 의도 분류 모델**입니다.

사용자의 자연어 입력을 8개 업무 의도(intent)로 분류합니다.

## Model Details

| Item | Detail |
|------|--------|
| **Base Model** | [monologg/koelectra-base-v3-discriminator](https://huggingface.co/monologg/koelectra-base-v3-discriminator) |
| **Architecture** | ElectraForSequenceClassification |
| **Parameters** | 112.9M |
| **Language** | Korean |
| **Experiment** | v2_stage6 |

## Intent Labels (8 classes)

| ID | Intent | Description |
|----|--------|-------------|
| 0 | `judgment` | 업무 판단 요청 (승인/반려/검토) |
| 1 | `doc_search` | 문서 검색 |
| 2 | `doc_generate` | 문서 생성 (회의록, 보고서 등) |
| 3 | `doc_summary` | 문서 요약 |
| 4 | `schedule_add` | 일정 추가/등록 |
| 5 | `schedule_view` | 일정 조회/확인 |
| 6 | `general` | 일반 대화/질문 |
| 7 | `doc_qa` | 문서 기반 Q&A |

## Performance

| Metric | Score |
|--------|-------|
| **Test F1** | 97.88% |
| **Adversarial F1** | 87.84% |
| **Inference Speed** | 7.9ms / sample |

- Training Data: 2,425 sentences (2,327 base + 98 augmented)
- Test Data: 286 samples + 450 adversarial samples
- Label Smoothing: 0.1

## Usage

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

model_name = "jiyong1110/koelectra-intent-classifier"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)

text = "내일 오후 3시에 회의 잡아줘"
inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=128)

with torch.no_grad():
    outputs = model(**inputs)
    pred = torch.argmax(outputs.logits, dim=-1).item()

id2label = model.config.id2label
print(f"Intent: {id2label[pred]}")  # schedule_add
```

## Training Details

7단계 실험을 거쳐 최적화된 모델입니다:

1. **Stage 1**: Claude + GPT-4o 기반 학습 데이터 생성
2. **Stage 2**: 3개 모델 베이스라인 비교 (BERT, KoBERT, KoELECTRA)
3. **Stage 3**: 32-point 하이퍼파라미터 그리드 서치
4. **Stage 4**: 최종 평가 (적대적 테스트, 속도 벤치마크)
5. **Stage 5**: 에러 분석 및 타겟 증강
6. **Stage 6**: Label smoothing 적용
7. **Stage 7**: 시나리오 테스트 (100 samples)

## Project

SKN21-FINAL-3TEAM — WorkFlow Agent (듀듀)

LangGraph 기반 멀티 에이전트 업무 자동화 시스템의 Intent Classification 모듈입니다.
