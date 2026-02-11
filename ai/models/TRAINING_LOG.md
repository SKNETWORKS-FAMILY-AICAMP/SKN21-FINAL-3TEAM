# Intent Classification 학습 로그

> 모델 학습/평가 결과를 기록합니다. 데이터 증강이나 재학습 시 이전 결과와 비교할 수 있습니다.

---

## v1.0 — 초기 파인튜닝 (2026-02-11)

### 모델 정보
| 항목 | 값 |
|------|-----|
| Base Model | klue/bert-base (111M params) |
| Task | 7-class intent classification |
| Framework | Hugging Face Transformers + Trainer |
| Hardware | RunPod GPU (On-Demand) |
| Training Time | ~1-2분 |

### 데이터
| 항목 | 값 |
|------|-----|
| 총 데이터 | 1,405문장 (7개 카테고리) |
| Train | 1,194 (85%) |
| Eval | 211 (15%) |
| 데이터 출처 | Claude 생성 (카테고리별 시드 기반 증강) |

### 카테고리별 분포
| 카테고리 | 전체 | Train | Eval |
|----------|:----:|:-----:|:----:|
| judgment | 205 | 171 | 34 |
| doc_search | 200 | 174 | 26 |
| doc_generate | 200 | 165 | 35 |
| meeting_generate | 200 | 174 | 26 |
| schedule_add | 200 | 179 | 21 |
| schedule_view | 200 | 173 | 27 |
| general | 200 | 158 | 42 |

### 하이퍼파라미터
| 항목 | 값 |
|------|-----|
| Epochs | 5 |
| Batch Size | 16 |
| Learning Rate | 2e-5 |
| Weight Decay | 0.01 |
| Max Length | 64 |
| Best Model | epoch 기준 f1_macro best |

### 성능 비교 (Base → Fine-tuned)
| 지표 | Base (학습 전) | v1.0 (파인튜닝 후) | 변화 |
|------|:---:|:---:|:---:|
| F1 (macro) | ~14.3% (랜덤 1/7) | **99.08%** | +84.8%p |
| Accuracy | ~14.3% | **99.05%** | +84.7%p |

> Base 모델(klue/bert-base)은 사전학습된 한국어 이해 능력만 있고, intent 분류용 classification head가 없어 학습 전에는 랜덤 수준입니다.

### 평가 결과
| 지표 | 값 |
|------|-----|
| **Accuracy** | **0.9905** |
| **F1 (macro)** | **0.9908** |
| **F1 (weighted)** | **0.9905** |

### 카테고리별 상세
| 카테고리 | Precision | Recall | F1-score | Support |
|----------|:---------:|:------:|:--------:|:-------:|
| judgment | 1.0000 | 1.0000 | 1.0000 | 34 |
| doc_search | 0.9630 | 1.0000 | 0.9811 | 26 |
| doc_generate | 1.0000 | 0.9714 | 0.9855 | 35 |
| meeting_generate | 0.9630 | 1.0000 | 0.9811 | 26 |
| schedule_add | 1.0000 | 1.0000 | 1.0000 | 21 |
| schedule_view | 1.0000 | 1.0000 | 1.0000 | 27 |
| general | 1.0000 | 0.9762 | 0.9880 | 42 |

### 오분류 패턴
- 211개 중 **2개 오분류**
- doc_generate → 다른 카테고리 1건
- general → 다른 카테고리 1건

### 한계점 및 참고
- 학습/평가 데이터 모두 Claude 생성 → 실사용자 대비 패턴 편향 가능
- 실서비스 예상 정확도: 85~95% (사용자 입력 다양성 반영 시)
- 추후 실사용자 로그 기반 재평가 필요

---

## 다음 계획

- [ ] 실사용자 데이터 수집 후 v1.1 재학습
- [ ] 혼동 잘 되는 카테고리 (doc_search ↔ doc_generate) 데이터 증강
- [ ] adversarial 테스트 (일부러 헷갈리는 문장으로 테스트)
- [ ] 4단계에서 카테고리별 500개로 확장

---

> 새로운 학습 결과는 아래에 추가합니다.
