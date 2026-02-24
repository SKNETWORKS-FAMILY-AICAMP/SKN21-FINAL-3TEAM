# 오분류 분석 보고서 — adversarial

총 450개 중 63개 오분류 (14.0%)

## 오분류 유형 분포

| 유형 | 건수 | 비율 |
|------|:----:|:----:|
| short_text | 47 | 74.6% |
| overconfident | 42 | 66.7% |
| boundary_high | 30 | 47.6% |
| boundary_medium | 10 | 15.9% |
| typo_chosung | 7 | 11.1% |
| other | 5 | 7.9% |
| low_confidence | 3 | 4.8% |
| informal | 2 | 3.2% |

## 혼동 쌍 (Top 10)

| 실제 → 예측 | 건수 |
|------------|:----:|
| doc_qa → doc_search | 10 |
| doc_generate → doc_summary | 5 |
| doc_qa → doc_summary | 5 |
| schedule_add → schedule_view | 4 |
| general → doc_qa | 4 |
| general → doc_search | 4 |
| doc_qa → schedule_view | 4 |
| judgment → general | 3 |
| doc_search → doc_generate | 3 |
| schedule_view → doc_qa | 3 |

## 과신뢰 오분류 (42건)

모델이 90% 이상 확신했지만 틀린 케이스:

- "경조사 휴가가 몇일인지 확인좀요"
  - 실제: `judgment` | 예측: `doc_qa` (97.19%)
- "사외 강연하고 싶은데 별도 수입이 생길 수도 있거든..."
  - 실제: `judgment` | 예측: `general` (98.46%)
- "ㅇㅊ ㄱㄴ?"
  - 실제: `judgment` | 예측: `general` (99.50%)
- "어딘가에 매뉴얼이 있었던 것 같은데..."
  - 실제: `doc_search` | 예측: `general` (98.07%)
- "회이록 정리해조"
  - 실제: `doc_generate` | 예측: `doc_summary` (99.77%)
- "방금 한 얘기 문서로 정리해줘"
  - 실제: `doc_generate` | 예측: `doc_summary` (99.79%)
- "ㅎㅇㄹ 정리해줘"
  - 실제: `doc_generate` | 예측: `doc_summary` (99.79%)
- "워크샵 결과 보고서 양식으로 정리해줘"
  - 실제: `doc_generate` | 예측: `doc_summary` (99.70%)
- "전체 다 읽을 시간이 없어서 중요한 것만 알면 되거든"
  - 실제: `doc_summary` | 예측: `general` (99.41%)
- "팀 회식 날짜를 정해야 하는데..."
  - 실제: `schedule_add` | 예측: `judgment` (95.69%)

## 경계 혼동 (40건)

- "경조사 휴가가 몇일인지 확인좀요"
  - 실제: `judgment` | 예측: `doc_qa` (97.19%)
  - Top3: [('doc_qa', 0.9719), ('schedule_view', 0.0234), ('general', 0.0018)]
- "아까 물어본 건 괜찮은 거야?"
  - 실제: `judgment` | 예측: `general` (84.30%)
  - Top3: [('general', 0.843), ('judgment', 0.1487), ('doc_qa', 0.0039)]
- "사외 강연하고 싶은데 별도 수입이 생길 수도 있거든..."
  - 실제: `judgment` | 예측: `general` (98.46%)
  - Top3: [('general', 0.9846), ('judgment', 0.0117), ('doc_search', 0.0012)]
- "ㅇㅊ ㄱㄴ?"
  - 실제: `judgment` | 예측: `general` (99.50%)
  - Top3: [('general', 0.995), ('judgment', 0.0028), ('doc_qa', 0.0007)]
- "예전에 공유받은 그 양식"
  - 실제: `doc_search` | 예측: `doc_generate` (86.29%)
  - Top3: [('doc_generate', 0.8629), ('doc_search', 0.1168), ('doc_summary', 0.0093)]
- "보안 서약서 양식이 올해 바뀌었다고 하던데 최신 버전 파일 위치 좀"
  - 실제: `doc_search` | 예측: `doc_qa` (85.27%)
  - Top3: [('doc_qa', 0.8527), ('doc_search', 0.1187), ('judgment', 0.0134)]
- "회이록 정리해조"
  - 실제: `doc_generate` | 예측: `doc_summary` (99.77%)
  - Top3: [('doc_summary', 0.9977), ('doc_search', 0.0005), ('doc_generate', 0.0005)]
- "방금 한 얘기 문서로 정리해줘"
  - 실제: `doc_generate` | 예측: `doc_summary` (99.79%)
  - Top3: [('doc_summary', 0.9979), ('schedule_add', 0.0004), ('doc_search', 0.0004)]
- "ㅎㅇㄹ 정리해줘"
  - 실제: `doc_generate` | 예측: `doc_summary` (99.79%)
  - Top3: [('doc_summary', 0.9979), ('schedule_view', 0.0005), ('doc_search', 0.0004)]
- "JD 하나 ㄱㄱ"
  - 실제: `doc_generate` | 예측: `doc_summary` (47.93%)
  - Top3: [('doc_summary', 0.4793), ('general', 0.3639), ('doc_generate', 0.108)]
- "워크샵 결과 보고서 양식으로 정리해줘"
  - 실제: `doc_generate` | 예측: `doc_summary` (99.70%)
  - Top3: [('doc_summary', 0.997), ('doc_generate', 0.001), ('doc_search', 0.0006)]
- "일정 ㄱㄱ"
  - 실제: `schedule_add` | 예측: `schedule_view` (99.68%)
  - Top3: [('schedule_view', 0.9968), ('schedule_add', 0.001), ('general', 0.0008)]
- "스케줄 ㄴㅎ"
  - 실제: `schedule_add` | 예측: `schedule_view` (99.68%)
  - Top3: [('schedule_view', 0.9968), ('schedule_add', 0.0012), ('general', 0.0007)]
- "이번 달 마지막 주 금요일에 팀 빌딩 행사가 있는데 오후 반차 이후 시간으로 일정 등록하고 전체 팀원한테 공유해줘"
  - 실제: `schedule_add` | 예측: `schedule_view` (97.68%)
  - Top3: [('schedule_view', 0.9768), ('schedule_add', 0.0202), ('doc_summary', 0.0009)]
- "다른 팀에서도 이 시스템 쓰고 있어? 우리 팀만 쓰는 건지 전사적으로 도입된 건지 궁금해서"
  - 실제: `general` | 예측: `judgment` (93.31%)
  - Top3: [('judgment', 0.9331), ('general', 0.0602), ('doc_qa', 0.0036)]

## 전체 오분류 목록 (상위 50건)

| # | Text | True | Pred | Conf | Types |
|:-:|------|------|------|:----:|-------|
| 1 | 방금 한 얘기 문서로 정리해줘 | doc_generate | doc_summary | 1.00 | boundary_high, overconfident |
| 2 | ㅎㅇㄹ 정리해줘 | doc_generate | doc_summary | 1.00 | boundary_high, short_text, typo_chosung, informal, overconfident |
| 3 | 업무 지원 범위가 어디까지인지 상세히 안내 부탁드립니다 | general | doc_qa | 1.00 | overconfident |
| 4 | 위반 사항? | judgment | doc_qa | 1.00 | boundary_high, short_text, overconfident |
| 5 | 문서 확인 | doc_qa | doc_search | 1.00 | boundary_high, short_text, overconfident |
| 6 | 봇 기능 있어? | general | doc_search | 1.00 | short_text, overconfident |
| 7 | 문서 정보 확인 | doc_qa | doc_search | 1.00 | boundary_high, short_text, overconfident |
| 8 | 회이록 정리해조 | doc_generate | doc_summary | 1.00 | boundary_high, short_text, overconfident |
| 9 | 봇 기능 뭐야? | general | doc_qa | 1.00 | short_text, overconfident |
| 10 | 문서 뭐지? | doc_qa | doc_search | 1.00 | boundary_high, short_text, overconfident |
| 11 | 봇 기능 있나요? | general | doc_search | 1.00 | short_text, overconfident |
| 12 | 문서에 뭐 있어? | doc_qa | doc_search | 1.00 | boundary_high, short_text, overconfident |
| 13 | 문서 확인해줘 | doc_qa | doc_search | 1.00 | boundary_high, short_text, overconfident |
| 14 | 워크샵 결과 보고서 양식으로 정리해줘 | doc_generate | doc_summary | 1.00 | boundary_high, overconfident |
| 15 | 문서 숫자 | doc_qa | doc_search | 1.00 | boundary_high, short_text, overconfident |
| 16 | 일정 ㄱㄱ | schedule_add | schedule_view | 1.00 | boundary_high, short_text, typo_chosung, overconfident |
| 17 | 스케줄 ㄴㅎ | schedule_add | schedule_view | 1.00 | boundary_high, short_text, typo_chosung, informal, overconfident |
| 18 | 문서 정보 | doc_qa | doc_search | 1.00 | boundary_high, short_text, overconfident |
| 19 | 아까 말한 날짜에 비어있어? | schedule_view | doc_qa | 1.00 | short_text, overconfident |
| 20 | 기능이 뭐잇나요 | general | doc_qa | 1.00 | short_text, overconfident |
| 21 | ㅇㅊ ㄱㄴ? | judgment | general | 0.99 | boundary_medium, short_text, typo_chosung, overconfident |
| 22 | 숫자 확인해줘 | doc_qa | schedule_view | 0.99 | short_text, overconfident |
| 23 | 전체 다 읽을 시간이 없어서 중요한 것만 알면 되거든 | doc_summary | general | 0.99 | overconfident |
| 24 | ㄷㅈ ㅇㅈ ㅇㄸ? | schedule_view | general | 0.99 | short_text, typo_chosung, overconfident |
| 25 | 문서에 뭐 있나? | doc_qa | doc_search | 0.99 | boundary_high, short_text, overconfident |
| 26 | 새 일정 | schedule_add | schedule_view | 0.99 | boundary_high, short_text, overconfident |
| 27 | 이거 뭐지? | doc_qa | general | 0.99 | short_text, overconfident |
| 28 | 사외 강연하고 싶은데 별도 수입이 생길 수도 있거든... | judgment | general | 0.98 | boundary_medium, overconfident |
| 29 | 어딘가에 매뉴얼이 있었던 것 같은데... | doc_search | general | 0.98 | overconfident |
| 30 | 정보 좀 확인 | doc_qa | doc_search | 0.98 | boundary_high, short_text, overconfident |
| 31 | 이번 달 마지막 주 금요일에 팀 빌딩 행사가 있는데 오후 반차 이후 시간... | schedule_add | schedule_view | 0.98 | boundary_high, overconfident |
| 32 | 경조사 휴가가 몇일인지 확인좀요 | judgment | doc_qa | 0.97 | boundary_high, short_text, overconfident |
| 33 | 정보 확인해줘 | doc_qa | schedule_view | 0.97 | short_text, overconfident |
| 34 | 파일 정리부탁 | doc_summary | doc_generate | 0.96 | boundary_high, short_text, overconfident |
| 35 | 팀 회식 날짜를 정해야 하는데... | schedule_add | judgment | 0.96 | overconfident |
| 36 | 서류 좀 | doc_search | doc_generate | 0.95 | boundary_medium, short_text, overconfident |
| 37 | 문서 부탁 | doc_generate | doc_search | 0.94 | boundary_medium, short_text, overconfident |
| 38 | 정책 이해하려면? | judgment | doc_search | 0.94 | boundary_high, short_text, overconfident |
| 39 | 다른 팀에서도 이 시스템 쓰고 있어? 우리 팀만 쓰는 건지 전사적으로 도... | general | judgment | 0.93 | boundary_medium, overconfident |
| 40 | 결정 확인 | doc_qa | schedule_view | 0.93 | short_text, overconfident |
| 41 | 문서 결과 | doc_qa | doc_summary | 0.91 | boundary_high, short_text, overconfident |
| 42 | 정보 확인 | doc_qa | doc_search | 0.91 | boundary_high, short_text, overconfident |
| 43 | 예전에 공유받은 그 양식 | doc_search | doc_generate | 0.86 | boundary_medium, short_text |
| 44 | 보안 서약서 양식이 올해 바뀌었다고 하던데 최신 버전 파일 위치 좀 | doc_search | doc_qa | 0.85 | boundary_high |
| 45 | 아까 물어본 건 괜찮은 거야? | judgment | general | 0.84 | boundary_medium |
| 46 | ㅇㅇ 3줄로 | doc_summary | schedule_add | 0.83 | short_text, typo_chosung |
| 47 | 결정 확인해줘 | doc_qa | schedule_view | 0.83 | short_text |
| 48 | 이거 정보 | doc_qa | doc_summary | 0.80 | boundary_high, short_text |
| 49 | 보고서 줘 | doc_search | doc_generate | 0.79 | boundary_medium, short_text |
| 50 | 숫자 좀 알려줘 | doc_qa | doc_summary | 0.78 | boundary_high, short_text |