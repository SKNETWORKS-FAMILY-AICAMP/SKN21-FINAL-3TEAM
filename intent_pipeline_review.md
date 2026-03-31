# Intent 파이프라인 검토 및 리팩토링 계획

> 2026-03-31 | 검토자: 신지용 (PM)

---

## 현재 파이프라인 전체 흐름도

```
사용자 입력
    │
    ▼
classify_intent (ONNX 멀티라벨)
    │
    ├─ is_compound=True (threshold 이상 intent 2개+)
    │       │
    │       ▼
    │   route_by_intent → "decompose_query"
    │       │
    │       ▼
    │   decompose_query
    │       ├─ sLLM 모드: Planner LoRA → step 분해
    │       │    → knowledge_query 매핑 (dead code)
    │       │    → 각 step ONNX 재분류 → hint 덮어씀
    │       │
    │       └─ rule 모드: 텍스트 분리 ("하고/그리고")
    │            → 각 part ONNX 분류 → hint
    │       │
    │       ▼
    │   compound_pending → chat.py로 전달
    │       │
    │       ▼
    │   chat.py: for sq in sub_queries:
    │       force_intent = sq["hint"]    ←── ONNX 결과를 그대로
    │       graph.ainvoke(sub_state)      ←── 그래프 전체 재실행
    │           → classify_intent에서 force_intent 감지 → ONNX 스킵
    │           → route_by_intent → Agent 실행
    │
    ├─ is_compound=False + gap < 0.40
    │       → clarify_with_candidates (사용자에게 확인)
    │
    ├─ is_compound=False + confidence < 0.85
    │       → clarify_with_candidates
    │
    └─ is_compound=False + confidence >= 0.85
            → route_by_intent → Agent 직접 실행
```

---

## 발견된 문제점 6가지

### 1. 복합질문에서 graph 전체를 다시 돌림 (가장 큰 문제)

**위치**: `chat.py` 331-344줄

```python
sub_state = {**initial_state, "user_input": sq_query, "force_intent": sq_hint}
sub_result = await graph.ainvoke(sub_state)  # ← 전체 그래프 재실행
```

force_intent가 있으니까 classify_intent에서 ONNX는 스킵하지만, LangGraph 노드 순회는 전부 다시 함 (classify_intent → route_by_intent → agent → format_response). 복합질문 3개면 그래프를 **4번** 실행 (1번 원래 + 3번 sub).

**실제로 필요한 건 Agent 함수 직접 호출뿐.**

---

### 2. 복합 감지 기준이 너무 단순 — "모델이 헷갈리는 것"과 "실제 복합 질문"을 구분 못 함

**위치**: `intent_classifier.py` 437줄

```python
"is_compound": len(intents) >= 2,
```

ONNX sigmoid 결과에서 threshold(0.55) 넘는 intent가 2개 이상이면 무조건 복합.

- "연차 규정 알려줘" → judgment 0.6, doc_retrieve 0.58 → **둘 다 threshold 넘음 → 복합으로 오판**
- 실제로는 단일 질문인데 모델이 헷갈려서 2개가 나온 것뿐

`_apply_multilabel_rules`에서 일부 보정하지만 judgment/doc_retrieve 동시 발화만 잡는 수준.

---

### 3. ONNX 분류를 3번 중복 호출

```
1회차: classify_intent에서 predict_multilabel() → 복합 감지 + primary intent
2회차: decompose_query에서 각 part마다 predict() → hint 결정
3회차: chat.py에서 graph.ainvoke → force_intent로 스킵되긴 함
```

1회차에서 이미 `_compound_intents = [judgment, doc_retrieve]`로 intent를 알고 있는데, 2회차에서 분리된 텍스트로 다시 ONNX를 돌림. 결과가 1회차와 다를 수 있어서 **일관성이 깨질 수 있음**.

---

### 4. decompose에서 텍스트 분리 실패 시 원문을 그대로 넣음

**위치**: `orchestrator.py` 327-334줄

```python
# 분리 실패 → ONNX intent 순서대로 원문 그대로
for i, intent_info in enumerate(compound_intents):
    sub_queries.append({
        "query": user_input,         # ← 원문 전체
        "hint": intent_info["intent"],
    })
```

"연차 규정 확인하고 보고서 작성해줘"가 분리 실패하면:
- sub_query 1: query="연차 규정 확인하고 보고서 작성해줘", hint=judgment
- sub_query 2: query="연차 규정 확인하고 보고서 작성해줘", hint=doc_generate

**같은 원문을 2번 다른 Agent로 보냄.** judgment Agent가 "보고서 작성해줘" 부분을 무시하고, doc_generate Agent가 "연차 규정 확인" 부분도 보고서에 넣으려 함.

---

### 5. knowledge_query 매핑은 dead code

**위치**: `orchestrator.py` 405-408줄

```python
if intent in _KNOWLEDGE_QUERY_INTENTS:
    intent = "knowledge_query"
```

408줄에서 매핑하지만 304줄에서 ONNX가 `sq["hint"]`를 덮어씀. route_by_intent에 knowledge_query 경로도 없음. 로그만 오염시킴.

---

### 6. 복합질문 sub_query에서 stream_mode=False 강제

**위치**: `chat.py` 334줄

```python
"stream_mode": False,
```

복합질문의 각 sub는 비스트리밍으로 처리. 버그는 아니지만 **복합질문에서는 스트리밍 UX가 없어서 사용자가 오래 기다림**.

---

## 리팩토링 우선순위

| 우선순위 | 항목 | 내용 | 난이도 |
|:---:|------|------|:---:|
| 1 | **복합 vs 혼동 구분** | `is_compound` 판단을 "threshold 2개 이상"이 아니라, 실제 복합 패턴(접속사/동사 2개+)과 결합해서 판단 | 중 |
| 2 | **dead code 제거** | knowledge_query 매핑 (`_KNOWLEDGE_QUERY_INTENTS`, 405-408줄) 삭제 | 하 |
| 3 | **ONNX 중복 호출 제거** | 1회차 결과를 재활용하거나, decompose에서 Planner가 만든 query만 분리하고 intent는 1회차 것 사용 | 중 |
| 4 | **분리 실패 시 fallback** | 원문 그대로 보내지 말고, 단일 질문으로 처리 (primary_intent로) | 하 |
| 5 | **sub_query 직접 Agent 호출** | graph 전체 재실행 대신 `safe_*_agent()` 직접 호출 | 상 |
| 6 | **sub_query 스트리밍** | 복합질문에서도 스트리밍 UX 제공 | 상 |

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| `ai/agents/orchestrator.py` | LangGraph 그래프, classify_intent, decompose_query, route_by_intent |
| `ai/agents/intent_classifier.py` | ONNX 멀티라벨 분류, predict_multilabel, KNOWN_OVERRIDES |
| `ai/agents/config.py` | INTENT_CONFIDENCE_THRESHOLD(0.85), INTENT_GAP_THRESHOLD(0.40) |
| `backend/app/api/v1/chat.py` | SSE 스트리밍, compound_pending 처리, sub_query graph 재실행 |
