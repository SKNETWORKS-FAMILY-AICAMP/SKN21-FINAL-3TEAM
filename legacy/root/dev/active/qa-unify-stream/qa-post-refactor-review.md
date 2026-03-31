# QA 파이프라인 통합 리팩토링 — 사후 코드 리뷰

> 리뷰 일시: 2026-03-25
> 리뷰 대상: `_qa.py`, `_common.py`, `_stream.py`, `_entry.py`, `orchestrator.py`, `prompts.py`
> 리팩토링 목표: 스트리밍/비스트리밍 QA 경로를 동일 프롬프트 + 동일 후처리로 통합

---

## 1. 전체 평가

리팩토링의 핵심 목표(스트리밍/비스트리밍 일관성)는 **달성됨**. 두 경로 모두:
- 같은 프롬프트(`DOC_QA_STREAMING_PROMPT`) 사용
- 같은 confidence 계산(`min(rag_top_score, 0.85)`)
- 같은 후처리(`filter_and_build_citations()`)

코드 양이 줄었고 유지보수 포인트가 감소한 좋은 리팩토링이다. 아래는 발견된 이슈.

---

## 2. 이슈 목록

### [P1] `force_sub_type` 잔여 참조 — `state.py`에 필드 잔존

**파일**: `ai/agents/state.py:63`

```python
force_sub_type: Optional[str]  # "qa" | "summary" | "search" — _entry.py regex 스킵
```

`_entry.py`에서 `force_sub_type` 라우팅 블록이 제거되었지만, `AgentState` 타입 정의에는 필드가 남아있다. 기능적 문제는 없지만(사용하지 않는 필드일 뿐) 혼동을 줄 수 있다.

**권장**: `state.py`에서 `force_sub_type` 필드를 제거하거나, 주석으로 `# deprecated — _entry.py에서 미사용`을 명시.

---

### [P2] 비스트리밍 경로에 `model_name` 누락

**파일**: `ai/agents/document/_qa.py:157-165`

비스트리밍 QA 응답 dict에 `model_name` 키가 없다:

```python
return {
    "type": "doc_retrieve",
    "sub_type": "qa",
    "answer": clean_answer,
    "message": clean_answer,
    "citations": citations,
    "confidence": confidence,
    "sources": filtered_sources,
    # model_name 없음!
}
```

`_entry.py:167`에서 `get_last_model_name()`으로 보정하긴 하지만, 이는 `stream_pending`이 아닌 경우에만 동작한다. 비스트리밍 경로는 `_call_llm()`이 내부에서 `set_last_model_name()`을 호출하므로 `_entry.py`에서 정상 보정된다.

**결론**: 기능적 문제 없음. 하지만 스트리밍 경로(`_qa.py:116`)는 `model_name: "streaming"`을 명시적으로 넣고 있으므로, 일관성을 위해 비스트리밍 경로에도 명시적으로 넣는 것이 좋다.

---

### [P2] `_call_llm()` 에러 시 비스트리밍 QA의 예외 전파 경로

**파일**: `ai/agents/document/_qa.py:142-148`

```python
answer_text = await _call_llm(DOC_QA_STREAMING_PROMPT, user_prompt, task="qa")
clean_answer, filtered_sources, citations = filter_and_build_citations(sources, answer_text)
```

`_call_llm()`이 예외를 던지면(`DOC_AGENT_MODE != "mock"`인 경우 `raise`), `_qa.py`에서 catch하지 않는다. 이 예외는 `_entry.py:136-144`의 `try/except`에서 잡혀서 일반 오류 메시지로 변환된다.

**결론**: 정상 동작. `_entry.py`의 catch-all이 보호하고 있다. 하지만 QA 전용 에러 메시지(예: "문서 질의 중 오류 발생")가 아닌 일반 메시지("문서 처리 중 오류가 발생했습니다")가 표시되는 점은 UX 관점에서 아쉬울 수 있다.

---

### [P3] `filter_and_build_citations()` — 빈 `ref_titles`일 때 전체 sources 반환 가능성

**파일**: `ai/agents/document/_common.py:248-256`

```python
if ref_titles and sources:
    ref_set = {t.strip() for t in ref_titles}
    filtered_sources = [s for s in sources if s.get("title", "") in ref_set]
elif sources:
    filtered_sources = _filter_sources(sources, response_text)

# 최종 보장: 0건이면 상위 1건 유지
if not filtered_sources and sources:
    filtered_sources = sources[:1]
```

`_filter_sources()`가 호출되는 경우(LLM이 `[참고:]` 태그를 안 썼을 때), 키워드 매칭이 하나도 안 되면 `_filter_sources()`는 원본 `sources` 전체를 반환한다(`return filtered if filtered else sources`, line 222). 이 경우 sources가 최대 10개까지 올 수 있다(entry.py에서 `top_k=10`). 의도된 동작인지 확인 필요.

**권장**: 스트리밍과 비스트리밍 모두 동일 함수를 쓰므로 일관성에는 문제 없음. 프론트엔드에서 sources 수가 많아도 괜찮다면 OK. 만약 상한이 필요하면 `filtered_sources[:5]` 등 제한 추가.

---

### [P3] `_filter_sources()` 키워드 분리 로직의 엣지케이스

**파일**: `ai/agents/document/_common.py:216-221`

```python
keywords = [w for w in title.replace("_", " ").split() if len(w) >= 3]
if not keywords:
    continue
```

파일 제목이 2글자 이하 단어로만 구성된 경우(예: "AI 개요", "HR 팀") keywords가 비어 해당 source가 항상 제외된다. 한국어 제목에서 2글자 단어("인사", "규정", "계약")는 흔하다.

**영향**: `[참고:]` 태그가 없는 LLM 응답에서만 해당. `[참고:]` 태그가 있으면 title 완전 매칭으로 동작하므로 괜찮다. DOC_QA_STREAMING_PROMPT가 `[참고: 문서제목]` 태그를 명시적으로 지시하므로 실제 발생 빈도는 낮을 것.

---

### [P3] `_format_chat_context` — assistant 잘림 400자의 적절성

**파일**: `ai/agents/document/_common.py:108`

```python
max_len = 400 if msg["role"] == "assistant" else 200
```

200→400으로 변경됨. vLLM `max_model_len=8192` 환경에서 대화 이력이 3턴(6메시지)이면 최대 `3*200 + 3*400 = 1800자 ≈ 2700토큰`. `_qa.py`의 계산 주석:

```
시스템프롬프트(~200) + 대화이력(~300) + 질문(~50) + max_tokens(2048) = ~2600
```

이 주석의 "대화이력(~300)"은 실제 최대치(1800자)와 맞지 않는다. 주석이 업데이트되지 않았다.

**영향**: 실제로 컨텍스트가 `MAX_CONTEXT_CHARS=5000`으로 제한되어 있어, 최악의 경우 총 토큰이 `200 + 2700 + 50 + 5000*1.5 + 2048 ≈ 12498토큰`이 될 수 있다. vLLM 8192 제한을 초과할 수 있다.

**권장**: 주석을 현실에 맞게 수정하고, `MAX_CONTEXT_CHARS`를 대화 이력 길이에 따라 동적으로 조정하는 것을 고려.

---

### [P1] 스트리밍 경로에서 `[참고:]` 태그가 토큰으로 사용자에게 전송되는 문제

**파일**: `ai/agents/document/_stream.py:123-126`

```python
if chunk.choices and chunk.choices[0].delta.content:
    token = chunk.choices[0].delta.content
    full_response += token
    yield token  # ← [참고: 문서제목] 태그도 그대로 전송됨
```

`filter_and_build_citations()`는 스트리밍 종료 후(line 158-168)에 호출된다. 즉 `[참고: 문서제목]` 태그는 먼저 토큰으로 프론트엔드에 전송된 후, `agent_response`에서만 제거된다. 사용자는 스트리밍 중 `[참고: 문서제목]` 텍스트를 일시적으로 볼 수 있다.

비스트리밍 경로에서는 전체 응답 생성 후 `filter_and_build_citations()`로 제거한 `clean_answer`만 반환하므로 이 문제가 없다.

**영향**: 스트리밍/비스트리밍 간 사용자 경험 차이. 스트리밍에서 `[참고:]` 태그가 일시적으로 보이다가 최종 응답에서는 제거됨.

**권장**: 프론트엔드에서 `[참고:...]` 패턴을 실시간 필터링하거나, `_stream.py`의 `clean_response != full_response` 분기 후 SSE로 교체 이벤트를 전송하는 방식 검토. 또는 프롬프트를 수정하여 `[참고:]` 태그를 답변 본문이 아닌 별도 구조로 출력하도록 유도.

---

### [P3] `_common.py`의 `_get_mock_response`에 삭제된 JSON QA 포맷 잔존

**파일**: `ai/agents/document/_common.py:373-382`

```python
if json_mode:
    if "question" in prompt_lower or "answer" in prompt_lower:
        return json.dumps({
            "answer": "...",
            "citations": [...],
            "confidence": 0.85,
        }, ensure_ascii=False)
```

`DOC_QA_SYSTEM_PROMPT`(JSON 포맷)이 삭제되고 QA는 이제 자연어 프롬프트를 사용하므로 `json_mode=True`로 `_call_llm`을 호출하는 QA 경로는 없다. 이 mock 분기는 dead code가 되었다. 다만 mock 모드는 테스트용이라 기능적 문제는 없다.

---

### [INFO] `orchestrator.py` — `force_sub_type` 제거 확인

`orchestrator.py`에서 `force_sub_type` 관련 코드가 완전히 제거된 것을 확인. 검색 결과 `orchestrator.py`에는 더 이상 참조가 없다.

---

### [INFO] `prompts.py` — `DOC_QA_SYSTEM_PROMPT` 삭제 확인

`prompts.py`에서 `DOC_QA_SYSTEM_PROMPT`가 삭제됨을 확인. 코드베이스 전체 grep 결과 해당 상수에 대한 import/참조가 없음. 깨끗하게 제거됨.

---

### [INFO] Compound Query 호환성

`_entry.py`에서 compound query 처리는 `orchestrator.py`의 `decompose_query` → `compound_pending`을 통해 이루어지며, 각 sub_query가 개별적으로 `_handle_doc_qa()`를 호출한다. `_handle_doc_qa()`의 시그니처와 반환값은 변경되지 않았으므로 호환성에 문제 없음.

---

## 3. 일관성 검증 매트릭스

| 항목 | 스트리밍 | 비스트리밍 | 일치? |
|------|---------|-----------|-------|
| 프롬프트 | `DOC_QA_STREAMING_PROMPT` | `DOC_QA_STREAMING_PROMPT` | O |
| confidence | `min(rag_top_score, 0.85)` | `min(rag_top_score, 0.85)` | O |
| 후처리 함수 | `filter_and_build_citations()` | `filter_and_build_citations()` | O |
| `[참고:]` 태그 제거 시점 | 스트리밍 종료 후 | LLM 응답 직후 | **X** (P1 참고) |
| citations 상한 | 3건 | 3건 | O |
| sources 필터링 | 동일 로직 | 동일 로직 | O |
| temperature | 0.1 | 0.1 | O |
| max_tokens | 2048 | (task default) | **?** |

`max_tokens` 차이: 스트리밍 경로는 `llm_config`에 `max_tokens: 2048`을 명시하지만, 비스트리밍의 `_call_llm()`은 하위 provider의 기본값을 사용한다. `VLLMProvider`나 OpenAI의 기본 `max_tokens`가 다를 수 있다.

---

## 4. 요약

| 우선순위 | 이슈 | 영향도 |
|---------|------|--------|
| **P1** | `[참고:]` 태그 스트리밍 중 사용자에게 노출 | UX 차이 — 스트리밍/비스트리밍 불일치 |
| **P1** | `force_sub_type` 잔여 (state.py) | 혼동 유발, dead field |
| **P2** | 비스트리밍 응답에 `model_name` 미포함 | `_entry.py`에서 보정되나 명시성 부족 |
| **P2** | `_call_llm()` 에러 시 QA 전용 메시지 없음 | 일반 에러 메시지만 표시 |
| **P3** | `MAX_CONTEXT_CHARS` 주석과 실제 토큰 계산 불일치 | vLLM 8192 초과 위험 (이론적) |
| **P3** | `_filter_sources` 2글자 이하 키워드 제외 | 한국어 제목 매칭 실패 가능 |
| **P3** | mock QA 응답에 JSON 포맷 잔존 | dead code (기능 무영향) |
| **P3** | `max_tokens` 스트리밍(2048) vs 비스트리밍(기본값) 차이 | 출력 길이 불일치 가능 |

---

*리뷰어: Claude (자동 리뷰)*
