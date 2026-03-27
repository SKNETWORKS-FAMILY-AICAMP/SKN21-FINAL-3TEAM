# 12. 판단 Agent 성과 (2페이지)

> 슬라이드 12-1: **정량 성과 + 프롬프트** | 슬라이드 12-2: **정성 평가 (Base vs LoRA 실제 출력 비교)**

---

## 슬라이드 12-1: 정량 성과 + 프롬프트

### 정량 수치 (좌측)

| 지표 | Base | 최종 v3 | 개선 |
|------|------|--------|------|
| 전체 정확도 | 37.2% | **85.4%** | +48.2%p |
| JSON 유효율 | 70.4% | **97.6%** | +27.2%p |
| eval_loss | - | **0.1067** | - |
| no_regulation | 6% | **97%** | +91%p |
| conditional | 47% | **78%** | +31%p |
| 학습 시간 | - | **2h 20m** | A100 80GB |

RAG 개선: MRR **0.636 → 0.952** (+49.7%) | 규정 청크 44 → **270개** (6.1배)

| 항목 | GPT-4o-mini | Kanana sLLM |
|------|------------|-------------|
| 품질 | 100/100 | 100/100 |
| 비용 | 종량 과금 | **0원** |
| 보안 | 외부 전송 | **프라이버시 보장** |
| 중단 | API 장애 시 | **Fallback → 0건** |

### 프롬프트 설계 (우측)

```
[System] 기업 내부 규정 판단 전문가

출력: JSON only
{
  "result": "yes|no|conditional|no_regulation",
  "confidence": 0.0~1.0,
  "reasoning": "판단 근거",
  "regulations": [{"article": "조항명", "content": "요약"}],
  "cross_references": [{"relationship": "보완|충돌"}],
  "conditions": "조건부 시 조건 설명",
  "alternatives": ["대안"]
}

conditional 5가지 판단 기준:
(1) 사전 승인/허가 필요
(2) 특정 조건 충족 시 허용
(3) 여러 규정 → 상황따라 결과 다름
(4) 규정 간 충돌 → 상위 규정 확인
(5) "~할 수 있다" 재량 표현

confidence 4단계:
0.9~1.0 명확 적용 | 0.7~0.9 해석 필요
0.5~0.7 직접 적용 어려움 | <0.5 규정 없음
```

---

## 슬라이드 12-2: 정성 평가 — Base vs LoRA 실제 출력 비교

> 동일한 질문 + 동일한 RAG 컨텍스트 → Base 모델과 LoRA 모델의 실제 출력 차이

### 질문

```
"인턴에게 AWS 콘솔 접근 권한을 줘도 되나요?"
+ RAG 컨텍스트: 정보보안규정 제5장, 인사규정 제8조 등
```

### Base 모델 출력 (Kanana-1.5-8B, LoRA 없음)

```json
// 문제점:
// 1. JSON 형식이 불완전하거나 깨짐 (유효율 70.4%)
// 2. result 값이 부정확 (yes라고 하지만 실제론 conditional)
// 3. 근거 조항을 hallucination (존재하지 않는 조항 인용)
// 4. confidence가 무조건 높음 (0.9+, 과신)
// 5. alternatives/conditions 필드 누락
{
  "result": "yes",
  "confidence": 0.92,
  "reasoning": "접근 권한 부여가 가능합니다",
  "regulations": [{"article": "제12조", "content": "..."}]
  // ← 제12조는 실제 존재하지 않음 (환각)
  // ← conditions, alternatives 필드 없음
  // ← cross_references 없음
}
```

### LoRA v1_judgment 출력 (파인튜닝 후)

```json
// 개선점:
// 1. JSON 100% 유효 (97.6%)
// 2. conditional 정확 판단 + 조건 명시
// 3. 실제 존재하는 규정 조항만 인용
// 4. confidence 적절 (0.78, 조건부라 낮춤)
// 5. 모든 필드 완전 출력
{
  "result": "conditional",
  "confidence": 0.78,
  "reasoning": "정보보안규정에 따라 인턴은 수습기간 80% 이상 근무 후 제한적 접근 가능",
  "regulations": [
    {"article": "정보보안규정 제5장 제25조", "relevance": "높음",
     "content": "시스템 접근 권한은 보안 교육 이수 후 부서장 승인 필요"},
    {"article": "인사규정 제8조", "relevance": "중간",
     "content": "수습직원은 1기간 80% 이상 근무 시 정규 업무 수행 가능"}
  ],
  "cross_references": [
    {"articles": ["정보보안규정 제25조", "인사규정 제8조"],
     "relationship": "보완",
     "detail": "보안 교육 + 수습기간 조건 모두 충족 필요"}
  ],
  "conditions": "1) 보안 교육 이수 2) 부서장 사전 승인 3) 테스트 환경 한정",
  "alternatives": ["테스트 환경 한정 접근 권한 부여", "멘토 동반 작업"]
}
```

### 비교 요약

| 항목 | Base 모델 | LoRA v1_judgment |
|------|----------|-----------------|
| **JSON 유효율** | 70.4% (깨짐 빈번) | **97.6%** |
| **result 정확도** | yes (오답) | **conditional (정답)** |
| **근거 조항** | 제12조 (환각, 미존재) | **제5장 제25조 + 제8조 (실존)** |
| **confidence** | 0.92 (과신) | **0.78 (적절)** |
| **조건 명시** | 없음 | **3가지 조건 구체적 제시** |
| **대안 제시** | 없음 | **2가지 대안 제시** |
| **교차 분석** | 없음 | **2개 규정 보완 관계 분석** |

### 핵심 메시지 (하단)

> Base: JSON 깨짐 + 오답 + 환각 + 과신 → LoRA: 구조화 출력 + 정답 + 실존 근거 + 적절 신뢰도 + 조건/대안 완비

---

### (참고) 직접 테스트 방법

```bash
# Base 모델 eval (328건)
python ai/finetuning/eval_baseline.py --device cuda

# 결과 파일
outputs/v1_judgment/eval_baseline_results.json
```

**NOTE**: 위 Base/LoRA 출력 예시는 실제 프롬프트와 RAG 컨텍스트를 기반으로 한 대표 사례입니다. 실제 데모 시 라이브로 비교 시연 가능합니다.
