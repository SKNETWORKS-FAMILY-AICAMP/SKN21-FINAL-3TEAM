# 판단 Agent 스트리밍 경로 수정 플랜

> 작성일: 2026-03-26
> 대상 파일: `ai/agents/orchestrator.py`, `ai/agents/judgment_stream.py`, `ai/agents/judgment_agent.py`

---

## 현재 상황 요약

판단 Agent의 스트리밍 경로에 4가지 문제가 있다:

| # | 문제 | 위치 | 심각도 |
|---|------|------|--------|
| 1 | RAG 검색 시 reranker/HyDE/score_threshold 누락 | `orchestrator.py` L146 | 높음 |
| 2 | top_k 불일치 (10 vs 5) | `orchestrator.py` L146 | 중간 |
| 3 | 후처리 보조장치 누락 | `judgment_stream.py` L129-178 | 이미 해결됨 |
| 4 | 로직 중복 (orchestrator가 내부 함수 직접 import) | `orchestrator.py` L130-155 | 중간 |

---

## 문제별 상세 분석

### 문제 1+2: RAG 검색 파라미터 불일치

**현재 (orchestrator.py L146):**
```python
context = pipeline.retrieve(query=user_input, user_id=user_id, top_k=10, filter={"source": "regulations"})
```

**기대 (judgment_agent.py L679-684):**
```python
context = pipeline.retrieve(
    query=user_input, user_id=user_id, top_k=5,
    filter={"source": "regulations"},
    use_reranker=True,       # Cross-Encoder로 관련도 재정렬
    score_threshold=0.0,     # Cross-Encoder 점수 0 이하 제거
    use_hyde=True,           # HyDE로 벡터 검색 품질 향상
)
```

**영향:**
- reranker 없이 top_k=10 → 노이즈 문서가 컨텍스트에 포함됨
- HyDE 미적용 → 벡터 검색 품질 저하
- score_threshold 미적용 → 관련 없는 문서가 필터링되지 않음
- 결과적으로 LLM이 잘못된 규정을 참조할 확률 증가 (환각 유발)

### 문제 3: 후처리 보조장치 — 이미 해결됨

`judgment_stream.py` L129-178을 분석한 결과, 이 파일에서 이미 스트리밍 완료 후 동일한 3중 검증을 수행하고 있다:
- L140-142: `_parse_llm_response` + `_validate_result_category`
- L144-146: `_check_keyword_match` + `_validate_article_exists`
- L148-154: `_calibrate_confidence`
- L157-158: `_group_regulations`
- L160-166: 환각 조항 경고
- L168-171: `_check_consistency`

**결론:** 문제 3은 현재 코드에서 이미 구현되어 있으므로 수정 불필요.

### 문제 4: 로직 중복

**현재 구조:**
```
orchestrator.py (L130-155):
  - judgment_agent에서 _build_context_prompt, _build_user_prompt, _extract_judgment_history import
  - 직접 RAG 검색 + 프롬프트 빌드
  - stream_pending 상태로 반환

judgment_agent.py (L674-760):
  - 동일한 RAG 검색 + 프롬프트 빌드 로직
  - 비스트리밍 시 사용
```

orchestrator가 judgment_agent의 내부 함수(`_` prefix)를 직접 import하는 것은 캡슐화 위반이며, RAG 파라미터 변경 시 두 곳을 동시에 수정해야 하는 위험이 있다.

---

## 구현 계획

### Step 1: judgment_agent.py에 스트리밍 준비 함수 추가

`judgment_agent.py`에 `prepare_judgment_stream()` 공개 함수를 추가하여 RAG 검색 + 프롬프트 빌드를 캡슐화한다.

**추가 위치:** `judgment_agent.py` L670 근처 (`async def judgment_agent` 함수 바로 위)

```python
async def prepare_judgment_stream(state: dict) -> dict:
    """스트리밍 모드용 RAG 검색 + 프롬프트 빌드 (orchestrator에서 호출)

    Returns:
        agent_response dict (stream_pending=True, sys_prompt, user_prompt, _rag_context 포함)
    """
    from ai.llm.prompts import JUDGMENT_STREAMING_SYSTEM_PROMPT

    user_input = state["user_input"]
    user_id = state.get("user_id")
    chat_history = state.get("chat_history", [])

    # RAG 검색 (judgment_agent과 동일한 파라미터)
    _t_rag = time.time()
    logger.info("[JudgmentAgent] 스트리밍 RAG 검색 시작 (top_k=5, reranker=True, hyde=True)...")
    pipeline = get_qdrant_pipeline()
    context = pipeline.retrieve(
        query=user_input, user_id=user_id, top_k=5,
        filter={"source": "regulations"},
        use_reranker=True,
        score_threshold=0.0,
        use_hyde=True,
    )
    logger.info("[JudgmentAgent] 스트리밍 RAG 완료 (%.2fs) | %d개 문서", time.time()-_t_rag, len(context))

    # 프롬프트 빌드
    judgment_history = _extract_judgment_history(chat_history)
    context_text = _build_context_prompt(context)
    user_prompt = _build_user_prompt(
        user_input, context_text, chat_history, judgment_history,
        prev_agent_context=state.get("prev_agent_context"),
    )

    return {
        "context": context,
        "agent_response": {
            "type": "judgment",
            "message": "",
            "stream_pending": True,
            "sys_prompt": JUDGMENT_STREAMING_SYSTEM_PROMPT,
            "user_prompt": user_prompt,
            "_rag_context": context,
        },
    }
```

### Step 2: orchestrator.py 스트리밍 블록 간소화

`orchestrator.py` L129-167을 `prepare_judgment_stream()` 호출로 교체한다.

**현재 (L129-167):**
```python
if state.get("stream_mode"):
    from ai.agents.judgment_agent import (
        _build_context_prompt,
        _build_user_prompt,
        _extract_judgment_history,
    )
    from ai.llm.prompts import JUDGMENT_STREAMING_SYSTEM_PROMPT
    from ai.rag.qdrant_pipeline import get_qdrant_pipeline

    user_input = state["user_input"]
    user_id = state.get("user_id")
    chat_history = state.get("chat_history", [])

    # RAG 검색
    _t_rag = time.time()
    logger.debug("[Orchestrator] judgment 스트리밍: RAG 검색 시작 (top_k=10)...")
    pipeline = get_qdrant_pipeline()
    context = pipeline.retrieve(query=user_input, user_id=user_id, top_k=10, filter={"source": "regulations"})
    logger.debug("[Orchestrator] judgment RAG 완료 (%.2fs) | %d개 문서", time.time()-_t_rag, len(context))

    # 프롬프트 빌드
    judgment_history = _extract_judgment_history(chat_history)
    context_text = _build_context_prompt(context)
    user_prompt = _build_user_prompt(
        user_input, context_text, chat_history, judgment_history,
        prev_agent_context=state.get("prev_agent_context"),
    )

    state["context"] = context
    state["agent_response"] = {
        "type": "judgment",
        "message": "",
        "stream_pending": True,
        "sys_prompt": JUDGMENT_STREAMING_SYSTEM_PROMPT,
        "user_prompt": user_prompt,
        "_rag_context": context,
    }
    logger.debug("[Orchestrator] judgment stream_pending 반환 (%.2fs)", time.time()-_t)
    return state
```

**변경 후:**
```python
if state.get("stream_mode"):
    from ai.agents.judgment_agent import prepare_judgment_stream

    result = await prepare_judgment_stream(state)
    state["context"] = result["context"]
    state["agent_response"] = result["agent_response"]
    logger.debug("[Orchestrator] judgment stream_pending 반환 (%.2fs)", time.time()-_t)
    return state
```

**변경 효과:**
- 14줄 → 5줄로 축소
- 내부 함수(`_` prefix) import 제거
- RAG 파라미터가 judgment_agent.py 한 곳에서만 관리됨
- 문제 1, 2, 4가 동시에 해결됨

---

## 수정 파일 목록

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `ai/agents/judgment_agent.py` | 함수 추가 | `prepare_judgment_stream()` 공개 함수 추가 (~30줄) |
| `ai/agents/orchestrator.py` | 블록 교체 | L129-167 → `prepare_judgment_stream()` 위임 (~5줄) |

**변경하지 않는 파일:**
- `ai/agents/judgment_stream.py` — 후처리 로직 이미 정상 구현
- `backend/app/api/v1/chat.py` — 스트리밍 위임 구조 변경 없음
- `frontend/src/components/chat/JudgmentCard.jsx` — 필드 구조 변경 없음

---

## 테스트 계획

### 1. 단위 테스트
- `prepare_judgment_stream()`이 올바른 구조의 dict를 반환하는지 확인
  - `context`: list
  - `agent_response.stream_pending`: True
  - `agent_response.sys_prompt`: 비어있지 않은 문자열
  - `agent_response.user_prompt`: 비어있지 않은 문자열
  - `agent_response._rag_context`: context와 동일

### 2. 통합 테스트 (수동)
- 프론트엔드에서 규정 판단 질문 입력 (예: "경조사 휴가 사용 가능한가요?")
- 스트리밍 토큰이 정상적으로 출력되는지 확인
- 최종 JudgmentCard에 다음 필드가 모두 표시되는지 확인:
  - `regulations` (관련 규정 목록)
  - `confidenceBreakdown` (llm_weighted, rag_weighted, coverage_weighted, final)
  - `warnings` (환각 경고 등)
  - `confidence` (보정된 신뢰도)

### 3. 비스트리밍 회귀 테스트
- 비스트리밍 경로 (`stream_mode=False`)가 기존과 동일하게 동작하는지 확인
- `judgment_agent()` 함수 자체는 변경 없으므로 회귀 위험 낮음

---

## 예상 소요 시간

- 구현: ~15분
- 테스트: ~10분
- 총: ~25분
