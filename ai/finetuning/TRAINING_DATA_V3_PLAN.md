# LoRA v3 학습 데이터 재설계 기록

> 작성일: 2026-03-17
> 작성자: 신지용 (PM)

## 배경

LoRA v2 테스트 결과 핵심 필드 60~86% 빈 배열 문제 발견:
- 원인: 학습 데이터에서 priority 필드(decisions/tasks/schedule 등) 포함률이 ~34%로 낮음
- content/summary도 32~34%만 포함 (랜덤 선택 풀에서 동일 확률)

## 설계 원칙

### 필드 계층 (3계층)
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
  나머지 필드들 (agenda, risks, notes, achievements 등)
```

### 입력 길이 분포
```
short  (<200자):   30% — 폼에서 간단 입력
mid    (200~800자): 40% — 챗봇 일반 입력
long   (800~1500자): 20% — 상세 기술
xlong  (1500~3000자): 10% — 긴 내용 붙여넣기
```

### 채움률 목표
```
always 필드: 100%
priority 필드: ~80% (20%는 빈 값 → "안 채우는 법" 학습)
서술형 필드: 전부 str 타입 (list/dict 금지)
```

### 할루시네이션 방지
- sparse 샘플 30% — OMITTABLE_FIELDS만 비움 (priority는 보호)
- next_plan 100% → 81%로 조정 (항상 채우는 패턴 방지)
- budget은 수치 근거 있을 때만 채움

## 데이터 소스

### 1. Synthetic (synthesize_generate.py)
- GPT-4o로 800건 생성 (회의록 400 / 보고서 210 / 제안서 190)
- FIELD_POOLS에 always_content + priority_content 계층 추가
- 입력 길이 다양화 (LENGTH_PROFILES)
- 긴 시나리오 max_tokens 4096
- OMITTABLE_FIELDS에서 priority 필드 제거

### 2. AI Hub (clean_aihub.py)
- 원본 700건 정제
- 빈 priority 필드를 GPT-4o-mini로 보충 (맥락 기반, 근거 없으면 빈 값)
- 입력 축약 175건 (25%) — 짧은 입력 패턴 생성

### 3. 필터링 (filter_and_select.py)
- C급 제거 (always 필드 빈 값): Syn 10건 + AHub 144건 = 154건 제거
- short 초과분 선별: A급 80% / B급 20% 비율로 유형별 150건씩
- 결과: 1077건 (Syn 521 + AHub 556)

### 4. Priority 보완 (boost_priority.py)
- B급 샘플의 빈 priority 필드를 GPT-4o-mini로 보충
- 프롬프트: "빠짐없이 정리 + 없으면 빈 배열 + budget은 수치 있을 때만"
- 결과: 327건 보완, 259건 스킵(근거 없음)

### 5. 서술형 필드 str 변환
- content/main_content 등이 list/dict로 돼있는 664건 → str로 변환
- 변환 규칙: list_of_str → 줄바꿈 연결, list_of_dict → key/value 연결

### 6. 부족분 추가 생성 (generate_supplement.py)
- 목표 1500건 대비 부족한 길이/유형 조합 502건 추가
- min_length 검증 (미달 시 최대 3회 재생성)
- 2차 boost 내장 (1차 생성 후 빈 priority → GPT로 채움)
- content str 변환 내장

```
추가 생성 상세:
  meeting mid(200~800):     84건
  meeting long(800~1500):   85건
  meeting xlong(1500~3000): 50건
  report mid(200~800):      70건
  report long(800~1500):    48건
  report xlong(1500~3000):  50건
  proposal mid(200~800):    65건
  proposal xlong(1500~3000): 50건
```

### 7. 합치기 + 분할 (merge_and_split.py)
- filtered 1077건 + supplement 502건 = 1579건
- 초과분 79건 제거 (셀별 목표 초과 시 랜덤 제거)
- 최종 1500건 → train 1350 / eval 150

## 목표 분포 (1500건)

```
유형 × 길이:
              short   mid    long   xlong   합계
meeting:      150     200    100    50      500
report:       150     200    100    50      500
proposal:     150     200    100    50      500
합계:         450     600    300    150     1500
```

## boost 후 채움률 (기존 1077건)

```
decisions:      93%
action_items:   96%
tasks:          73%
next_plan:      81%
schedule:       87%
budget:         43% (AI Hub에 예산 수치 없는 문서가 대부분)
```

## 스크립트 목록

| 스크립트 | 용도 | 상태 |
|----------|------|------|
| `ai/finetuning/scripts/synthesize_generate.py` | Synthetic 800건 생성 | ✅ 완료 |
| `data/training/v2_generate/clean_aihub.py` | AI Hub 700건 정제 | ✅ 완료 |
| `data/training/v2_generate/filter_and_select.py` | C급 제거 + short 선별 | ✅ 완료 |
| `data/training/v2_generate/boost_priority.py` | B급 priority 보완 | ✅ 완료 |
| `data/training/v2_generate/generate_supplement.py` | 부족분 502건 추가 | ⏳ 진행 중 |
| `data/training/v2_generate/merge_and_split.py` | 합치기 + 분할 | ⏰ 대기 |

## 실행 순서

```bash
# 1. Synthetic 생성 (완료)
python ai/finetuning/scripts/synthesize_generate.py

# 2. AI Hub 정제 (완료)
python data/training/v2_generate/clean_aihub.py

# 3. 필터링 (완료)
python data/training/v2_generate/filter_and_select.py

# 4. Priority 보완 (완료)
python data/training/v2_generate/boost_priority.py

# 5. 부족분 추가 생성 (진행 중)
python data/training/v2_generate/generate_supplement.py

# 6. 합치기 + 분할
python data/training/v2_generate/merge_and_split.py

# 7. RunPod LoRA v3 학습
# train.jsonl + eval.jsonl 업로드 후 학습
```

## 다음 단계

1. supplement 502건 생성 완료 대기
2. 전수 검증 (길이/필드/타입/채움률)
3. merge_and_split 실행 → train.jsonl + eval.jsonl
4. RunPod에 올려서 LoRA v3 학습
5. 학습 후 QA 테스트
