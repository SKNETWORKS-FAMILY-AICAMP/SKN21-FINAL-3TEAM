# 오분류 분석 보고서 — test

총 286개 중 8개 오분류 (2.8%)

## 오분류 유형 분포

| 유형 | 건수 | 비율 |
|------|:----:|:----:|
| overconfident | 7 | 87.5% |
| boundary_high | 6 | 75.0% |
| short_text | 4 | 50.0% |

## 혼동 쌍 (Top 10)

| 실제 → 예측 | 건수 |
|------------|:----:|
| doc_qa → judgment | 2 |
| doc_summary → doc_qa | 2 |
| judgment → doc_qa | 1 |
| schedule_view → general | 1 |
| general → schedule_view | 1 |
| doc_generate → doc_summary | 1 |

## 과신뢰 오분류 (7건)

모델이 90% 이상 확신했지만 틀린 케이스:

- "급여는 언제 지급되나?"
  - 실제: `doc_qa` | 예측: `judgment` (99.70%)
- "다음 회의는 언제지?"
  - 실제: `schedule_view` | 예측: `general` (99.78%)
- "복리후생 혜택에 건강검진 포함돼?"
  - 실제: `doc_qa` | 예측: `judgment` (99.77%)
- "커피 타임 있어?"
  - 실제: `general` | 예측: `schedule_view` (99.68%)
- "이 기획서의 핵심 포인트가 대체 뭐야?"
  - 실제: `doc_summary` | 예측: `doc_qa` (99.72%)
- "이거 보고서로 정리 좀 해줘"
  - 실제: `doc_generate` | 예측: `doc_summary` (99.78%)
- "회의록 작성 가이드에서 필수 항목 알려줘"
  - 실제: `doc_summary` | 예측: `doc_qa` (99.59%)

## 경계 혼동 (6건)

- "급여는 언제 지급되나?"
  - 실제: `doc_qa` | 예측: `judgment` (99.70%)
  - Top3: [('judgment', 0.997), ('doc_qa', 0.0012), ('general', 0.001)]
- "휴가 내고 싶으면 어떻게 해야 해?"
  - 실제: `judgment` | 예측: `doc_qa` (82.20%)
  - Top3: [('doc_qa', 0.822), ('judgment', 0.1161), ('general', 0.0564)]
- "복리후생 혜택에 건강검진 포함돼?"
  - 실제: `doc_qa` | 예측: `judgment` (99.77%)
  - Top3: [('judgment', 0.9977), ('doc_qa', 0.0008), ('general', 0.0005)]
- "이 기획서의 핵심 포인트가 대체 뭐야?"
  - 실제: `doc_summary` | 예측: `doc_qa` (99.72%)
  - Top3: [('doc_qa', 0.9972), ('doc_summary', 0.0008), ('judgment', 0.0005)]
- "이거 보고서로 정리 좀 해줘"
  - 실제: `doc_generate` | 예측: `doc_summary` (99.78%)
  - Top3: [('doc_summary', 0.9978), ('doc_generate', 0.0004), ('schedule_add', 0.0004)]
- "회의록 작성 가이드에서 필수 항목 알려줘"
  - 실제: `doc_summary` | 예측: `doc_qa` (99.59%)
  - Top3: [('doc_qa', 0.9959), ('doc_summary', 0.0012), ('doc_search', 0.0008)]

## 전체 오분류 목록 (상위 50건)

| # | Text | True | Pred | Conf | Types |
|:-:|------|------|------|:----:|-------|
| 1 | 다음 회의는 언제지? | schedule_view | general | 1.00 | short_text, overconfident |
| 2 | 이거 보고서로 정리 좀 해줘 | doc_generate | doc_summary | 1.00 | boundary_high, overconfident |
| 3 | 복리후생 혜택에 건강검진 포함돼? | doc_qa | judgment | 1.00 | boundary_high, short_text, overconfident |
| 4 | 이 기획서의 핵심 포인트가 대체 뭐야? | doc_summary | doc_qa | 1.00 | boundary_high, overconfident |
| 5 | 급여는 언제 지급되나? | doc_qa | judgment | 1.00 | boundary_high, short_text, overconfident |
| 6 | 커피 타임 있어? | general | schedule_view | 1.00 | short_text, overconfident |
| 7 | 회의록 작성 가이드에서 필수 항목 알려줘 | doc_summary | doc_qa | 1.00 | boundary_high, overconfident |
| 8 | 휴가 내고 싶으면 어떻게 해야 해? | judgment | doc_qa | 0.82 | boundary_high |