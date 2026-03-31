# Judgment Agent 스트리밍 경로 수정 — 사후 리뷰

**날짜**: 2026-03-26
**대상 파일**:
- `ai/agents/judgment_agent.py` (L639-685: `prepare_judgment_stream()`)
- `ai/agents/orchestrator.py` (L123-156: `safe_judgment_agent()`)
- `ai/agents/judgment_stream.py` (L168-174: consistency warning 추가)

---

## 1. RAG 파라미터 일치 여부

| 파라미터 | `judgment_agent()` (L731-737) | `prepare_judgment_stream()` (L658-664) | 일치 |
|----------|-------------------------------|----------------------------------------|------|
| `top_k` | 5 | 5 | O |
| `filter` | `{"source": "regulations"}` | `{"source": "regulations"}` | O |
| `use_reranker` | True | True | O |
| `score_threshold` | 0.0 | 0.0 | O |
| `use_hyde` | True | True | O |

**결론**: 5개 RAG 파라미터 모두 완벽 일치. 이전 orchestrator에서 인라인으로 작성했을 때 발생하던 파라미터 불일치 문제가 해소됨.

---

## 2. orchestrator.py 잔여 import 확인

`orchestrator.py`에서 judgment 관련 import는 정확히 2개만 존재:
- L130: `from ai.agents.judgment_agent import prepare_judgment_stream` (스트리밍 모드)
- L138: `from ai.agents.judgment_agent import judgment_agent` (비스트리밍 모드)

이전에 사용하던 내부 함수 import들 (`_build_context_prompt`, `_build_user_prompt`, `_extract_judgment_history`, `get_qdrant_pipeline`, `JUDGMENT_STREAMING_SYSTEM_PROMPT`) 은 **모두 제거 확인됨**. 잔여 참조 없음.

---

## 3. 반환 구조 호환성

`prepare_judgment_stream()` 반환값 (L675-685):
```python
{
    "context": context,            # list — state["context"]에 대입
    "agent_response": {
        "type": "judgment",
        "message": "",
        "stream_pending": True,    # chat.py에서 스트리밍 트리거
        "sys_prompt": JUDGMENT_STREAMING_SYSTEM_PROMPT,
        "user_prompt": user_prompt,
        "_rag_context": context,   # judgment_stream.py에서 후처리용
    },
}
```

`safe_judgment_agent()`에서의 사용 (L132-134):
```python
result = await prepare_judgment_stream(state)
state["context"] = result["context"]
state["agent_response"] = result["agent_response"]
```

**chat.py 연동 (L464-476)**:
- `node_output.get("agent_response", {})` → `agent_response.get("stream_pending")` 체크 → `execute_judgment_stream()` 위임
- `stream_pending=True` 가 설정되어 있으므로 정상 트리거됨

**결론**: 반환 구조 호환성 문제 없음. `chat.py`가 기대하는 `stream_pending`, `sys_prompt`, `user_prompt`, `_rag_context` 필드 모두 포함.

---

## 4. judgment_stream.py warnings 추가 일치 여부

**judgment_agent.py** (L791-797):
```python
inconsistency = _check_consistency(user_input, parsed)
if inconsistency:
    parsed["consistency_flag"] = inconsistency
    parsed.setdefault("warnings", []).append(
        f"일관성 경고: 동일 질문에 이전과 다른 결과 "
        f"({inconsistency['previous_result']} → {inconsistency['current_result']})"
    )
```

**judgment_stream.py** (L168-174):
```python
inconsistency = _check_consistency(user_input, parsed)
if inconsistency:
    parsed["consistency_flag"] = inconsistency
    parsed.setdefault("warnings", []).append(
        f"일관성 경고: 동일 질문에 이전과 다른 결과 "
        f"({inconsistency['previous_result']} → {inconsistency['current_result']})"
    )
```

**결론**: 문자열 포맷, `setdefault` 패턴, `consistency_flag` 설정 모두 동일. 이전에는 `consistency_flag`만 설정하고 `warnings` 배열에 추가하지 않아서 프론트에서 일관성 경고가 표시되지 않던 문제가 수정됨.

---

## 5. 비스트리밍 경로 영향

`safe_judgment_agent()` (L137-142):
```python
# stream_mode가 아닌 경우
from ai.agents.judgment_agent import judgment_agent
result = await judgment_agent(state)
return result
```

`prepare_judgment_stream()`은 `judgment_agent()` 함수 **앞**(L639)에 위치하며, `judgment_agent()` 코드를 전혀 수정하지 않음 (L691-834 그대로). 비스트리밍 경로는 `stream_mode` 체크로 분기되므로 **영향 없음**.

---

## 6. chat.py 영향

chat.py의 judgment 스트리밍 처리 (L464-476)는 변경 없음:
- `node_name == "judgment_agent"` 분기
- `agent_response.get("stream_pending")` 체크
- `execute_judgment_stream(agent_response, user_input)` 위임
- 위임 후 `final_state["agent_response"] = agent_response` (in-place 업데이트된 결과 사용)

`prepare_judgment_stream()`이 생성하는 `agent_response` 구조가 기존과 동일하므로 **chat.py 수정 불필요**.

---

## 7. 프론트 JudgmentCard 영향

judgment_stream.py의 최종 `agent_response` 업데이트 로직 (L178-182)은 변경 없음:
- `stream_pending`, `sys_prompt`, `user_prompt`, `_rag_context` 제거
- `parsed` 딕셔너리로 업데이트 (`result`, `confidence`, `reasoning`, `regulations`, `warnings` 등)
- `model_name` 추가

프론트가 소비하는 필드 (`type`, `result`, `confidence`, `reasoning`, `regulations`, `warnings`, `cross_references`, `conditions`, `alternatives`, `regulation_groups`)는 모두 기존과 동일하게 생성됨. **프론트 영향 없음**.

단, warnings 배열에 consistency 경고가 **새로 추가**되므로, JudgmentCard가 warnings를 렌더링한다면 이전에 안 보이던 일관성 경고가 표시될 수 있음. 이는 **의도된 동작 개선**.

---

## 총평

| 항목 | 판정 |
|------|------|
| RAG 파라미터 일치 | PASS |
| import 정리 | PASS |
| 반환 구조 호환 | PASS |
| warnings 추가 일치 | PASS |
| 비스트리밍 경로 | PASS (영향 없음) |
| chat.py 호환 | PASS (수정 불필요) |
| 프론트 호환 | PASS (신규 warning 표시는 의도된 개선) |

**리스크 없음.** `prepare_judgment_stream()` 도입으로 RAG 파라미터가 단일 소스(judgment_agent.py)에서 관리되어 향후 파라미터 변경 시 불일치 위험이 제거됨.
