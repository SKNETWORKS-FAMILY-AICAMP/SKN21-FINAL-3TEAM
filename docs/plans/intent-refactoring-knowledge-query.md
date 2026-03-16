# Intent 리팩토링: knowledge_query 통합

> 작성일: 2026-03-16 | 작성자: 신지용(PM)

## 배경

- 기존 intent 6개 중 `judgment`와 `doc_retrieve`의 경계가 모호
- BERT 모델이 둘을 혼동하는 케이스 빈번
- "규정 알려줘"가 judgment인지 doc_retrieve인지 사람도 헷갈림
- regex override로 억지 보정 중 (intent_classifier.py 538-565줄) → 유지보수 어려움

### 근본 원인

intent를 **데이터 소스**(규정 vs 문서)로 나눴는데, 실제로는 규정에 대해 검색도 하고 판단도 해야 함.
분류 시점(검색 전)에 행동을 결정하는 것보다, RAG 검색 후 결과를 보고 결정하는 게 정확함.

## 변경 내용

### Intent 체계 변경 (6개 → 5개)

| 기존 | 변경 후 | 비고 |
|------|---------|------|
| judgment | **knowledge_query** | 통합 |
| doc_retrieve | **knowledge_query** | 통합 |
| doc_generate | doc_generate | 유지 |
| schedule_add | schedule_add | 유지 |
| schedule_view | schedule_view | 유지 |
| general | general | 유지 |

### BERT 모델 재학습: 불필요

기존 모델 그대로 사용. 후처리에서 매핑만 추가:

```python
# intent_classifier.py 후처리
bert_intent = model.predict(query)

if bert_intent in ("judgment", "doc_retrieve"):
    final_intent = "knowledge_query"
else:
    final_intent = bert_intent
```

### knowledge_query agent 내부 2단계 라우팅

```
knowledge_query
  ├─ 1) RAG 검색 (regulations + documents 필터 없이 전부)
  ├─ 2) 행동 결정:
  │     - 검색 결과의 source 비율 확인 (regulations vs documents)
  │     - BERT 원래 출력(judgment/doc_retrieve)을 힌트로 활용
  │     - 판단성 쿼리 패턴 ("~해도 돼?", "위반이야?", "조건이 뭐야?")
  │
  │     ├── 판단 필요 → judgment 로직 (yes/no/conditional + 4중 검증)
  │     └── 정보 조회 → retrieval 로직 (검색 결과 반환)
```

```python
# knowledge_query_agent.py 핵심 로직
def process(state):
    query = state["user_input"]

    # 1. RAG 검색 (필터 없이 전부)
    results = rag.retrieve(query, top_k=10, use_reranker=True)

    # 2. BERT 원래 출력을 힌트로 보존
    bert_hint = state.get("bert_raw_intent")  # "judgment" or "doc_retrieve"

    # 3. 검색 결과 기반 행동 결정
    reg_ratio = sum(1 for r in results if r.metadata["source"] == "regulations") / max(len(results), 1)
    needs_judgment = bert_hint == "judgment" or reg_ratio > 0.7

    if needs_judgment:
        return judgment_logic(state, results)
    else:
        return retrieval_logic(state, results)
```

## 수정 대상 파일

| 파일 | 수정 내용 |
|------|----------|
| `ai/agents/intent_classifier.py` | 후처리 매핑 추가, regex override 정리 |
| `ai/agents/orchestrator.py` | `knowledge_query` 라우팅 추가 |
| `ai/agents/knowledge_query_agent.py` | **신규** — judgment + document retrieval 통합 agent |
| `ai/agents/state.py` | `bert_raw_intent` 필드 추가 (힌트용) |
| `ai/agents/config.py` | knowledge_query 관련 threshold 추가 |
| `frontend/src/utils/constants.js` | intent 목록 동기화 |

### 기존 파일 재사용

- `ai/agents/judgment_agent.py` → 내부 함수를 knowledge_query_agent에서 import
- `ai/agents/document_agent.py` → doc_retrieve 관련 함수를 knowledge_query_agent에서 import
- 두 파일 삭제하지 않음 (doc_generate는 document_agent에 남아있음)

## 평가 방법

### 1. Intent 분류 평가 (BERT)

기존 테스트셋에서 라벨 매핑 후 재평가:

```python
# 테스트셋 라벨 매핑
for sample in test_set:
    if sample.label in ("judgment", "doc_retrieve"):
        sample.label = "knowledge_query"

# 모델 출력도 동일하게 매핑
for pred in predictions:
    if pred in ("judgment", "doc_retrieve"):
        pred = "knowledge_query"

# accuracy, F1 재산출
```

- judgment↔doc_retrieve 혼동이 더 이상 오답이 아니므로 정확도 상승 예상

### 2. knowledge_query 내부 행동 평가

| query | expected_action | expected_source |
|-------|-----------------|-----------------|
| "연차 규정 알려줘" | retrieval | regulations |
| "이거 규정 위반이야?" | judgment | regulations |
| "출장비 기준이 뭐야?" | judgment | regulations |
| "마케팅 보고서 찾아줘" | retrieval | documents |
| "회의록에 뭐라고 써있어?" | retrieval | documents |
| "인센티브 지급 조건?" | judgment | regulations |

평가 지표:
- **Action 정확도**: judgment vs retrieval 행동 선택이 맞았는가
- **Source 정확도**: RAG가 맞는 데이터 소스에서 가져왔는가
- **응답 품질**: 판단이면 yes/no/conditional 정확성, 검색이면 관련 문서 반환 여부

### 3. E2E 평가

LLM-as-judge 또는 사람 평가로 최종 응답 품질 확인

## 기대 효과

1. **모델 학습 부담 감소** — 애매한 경계 데이터 고민 불필요
2. **분류 정확도 상승** — 혼동 케이스가 정답 처리됨
3. **regex override 대부분 제거** — 유지보수 개선
4. **RAG 활용도 향상** — 규정+문서 통합 검색으로 recall 증가
5. **사용자 경험 개선** — "규정 찾아줘"에도 정상 응답
