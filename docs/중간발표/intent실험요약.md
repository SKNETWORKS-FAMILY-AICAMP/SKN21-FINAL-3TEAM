# Intent Classification 실험 요약 (팀 공유용)

## 1. 실험 목적
사용자 입력을 **8개 Intent로 정확히 분류**하여 각 Agent로 올바르게 라우팅하는 것이 목표.

➡️ Intent 오분류 = 잘못된 기능 실행

---

## 2. 전체 데이터 구성
### 학습용 데이터
- 기본 데이터: 2,299
- 경계쌍: 600

→ Stratified split

- Train: 2,327
- Val: 285
- Test: 286

### 강건성 평가용 데이터
- Adversarial: 450
- 시나리오 테스트: 100

---

## 3. 실험 흐름 (7 Stage)
### Stage 1 — 데이터 생성 & 검수
- GPT + Claude 혼합 생성
- 클래스 불균형 최소화
- 데이터 누출 0건

### Stage 2 — Baseline 모델 비교
동일 조건에서 3개 모델 비교
- KLUE BERT
- KoELECTRA
- DistilKoBERT

➡️ KoELECTRA 성능 우세

### Stage 3 — Grid Search
- KoELECTRA 하이퍼파라미터 최적화
- 3-seed 안정성 검증

➡️ 데이터 품질 영향이 더 큼 확인

### Stage 4 — 최종 모델 평가
Adversarial 포함 평가

모델 선택 기준:
- Test F1 ❌
- Adversarial F1 ⭕

➡️ 실전 강건성 기준으로 KoELECTRA 채택

### Stage 5 — 오분류 분석 & 타겟 보강
오류 유형:
- 짧은 문장
- 경계 intent
- 과신뢰

타겟 데이터 98개 추가 후 재학습

➡️ Adversarial F1 +1.8%p 개선

### Stage 6 — Label Smoothing
목적: 과신뢰 해결

결과:
- F1 거의 동일
- 오답 confidence 감소

➡️ Confidence 기반 clarify 라우팅 가능

### Stage 7 — 라벨 품질 검증
오분류 수동 분석 결과:
- 모델 오류: 37%
- 라벨 애매/오류: 63%

➡️ doc intent 성능 저하는 라벨 영향 큼
➡️ 소량 보강(25개)은 효과 없음
➡️ 최종 모델은 Stage 6 유지

---

## 4. 최종 성능
### 정량 성능
- Test F1: **97.88%**
- Adversarial F1: **87.58%**
- 추론 속도: **7.9ms**

### 정성 평가 (시나리오 100개)
- 전체 정확도: **85%**
- normal: 100%
- short: 93.3%
- informal: 76%

---

## 5. 서비스 적용 방식
Confidence 기반 라우팅:

- ≥ 0.85 → 자동 실행
- < 0.85 → 사용자 clarify

➡️ 오분류 시 잘못된 기능 실행 방지

---

## 6. 핵심 인사이트
1. 모델보다 **데이터 보강이 성능 개선에 더 효과적**
2. Test 성능보다 **Adversarial 성능이 실전 지표**
3. Label smoothing으로 **과신뢰 문제 해결**
4. doc intent 성능 문제의 주요 원인은 **라벨 품질**

---

## 7. 한계 및 향후 계획
- doc 경계 데이터 대량 확보 필요
- 슬랭 / 구어체 데이터 추가
- 실서비스 로그 기반 재학습
- Multi-intent 처리 확장

---

# 🔥 한 줄 요약
KoELECTRA 기반 Intent 분류기를 구축했고,  
Adversarial F1 87.6%까지 개선했으며,  
Confidence 기반 안전 라우팅이 가능해짐.

