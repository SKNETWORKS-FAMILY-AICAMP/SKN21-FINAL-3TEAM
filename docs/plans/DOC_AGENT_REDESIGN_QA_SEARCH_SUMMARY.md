# 3월 20일 — 문서 Agent 재설계: 검색 / QA / 요약

> **작성일**: 2026-03-20 | **담당**: 신지용 (PM) | **상태**: 플랜 완성, 구현 대기
> **다음 세션에서**: 이 플랜 읽고 바로 구현 시작

## Context
현재 문서 agent의 검색/QA/요약 파이프라인이 **agent 모듈과 chat.py에 분산**되어 있음.
- 스트리밍 시 agent는 RAG만 하고 `stream_pending=True` + 프롬프트를 던짐
- chat.py가 나머지 전부 처리 (LLM 호출, 소스 필터링, DB 업데이트, 규정 체크) — 170줄
- QA/검색은 대충 구현된 상태, summary만 어느정도 완성
- generate는 별도 CLI에서 작업 중 → **이 플랜에서 제외**

**환경**: API 사용 X. 온프레미스 sLLM (vLLM 엔드포인트) base 모델로 서빙 중.
- QA: sLLM base (LoRA 없음, 추후 학습 예정)
- Summary: v3_summary LoRA
- Search: RAG only (LLM 없음)

**결정사항** (2026-03-20 세션에서 확정):
- 라우팅: 기존 regex 유지 (_is_pure_search, _is_summary)
- 헬퍼 위치: chat.py 안에
- Reranker: 항상 켜기
- generate 코드 건드리지 않음

**목표**: agent가 파이프라인을 소유하고, chat.py는 토큰 릴레이만 하는 구조

---

## Phase 1: StreamRequest 프로토콜 통일

### 핵심 아이디어
agent가 스트리밍이 필요하면 `StreamRequest`를 반환. chat.py는 이 규격만 보고 LLM 호출 + 토큰 릴레이.

### StreamRequest 규격 (agent → chat.py)
```python
# agent_response에 포함
{
    "stream_pending": True,

    # ── LLM 호출 설정 (chat.py가 이대로 실행) ──
    "llm_config": {
        "sys_prompt": str,
        "user_prompt": str,
        "temperature": float,       # agent가 결정 (QA=0.1, summary=0.1)
        "max_tokens": int,          # agent가 결정 (QA=1024, summary=1024)
        "task": str,                # "qa" | "summary" — LoRA 어댑터 라우팅용
    },

    # ── 스트리밍 완료 후 처리 (chat.py가 실행) ──
    "post_stream": {
        "update_summary_db": int | None,   # document_id → DB 요약 업데이트
        "check_regulation": bool,           # 규정 연결 여부
        "filter_sources": bool,             # 소스 필터링 여부
    },

    # ── 프론트에 전달할 데이터 (이미 확정, 스트리밍과 무관) ──
    "type": "doc_retrieve",
    "sub_type": "qa" | "summary",
    "sources": [...],               # agent가 이미 준비 완료
    "citations": [...],             # QA용
    "tags": [...],                  # summary용
}
```

### chat.py document_agent 핸들러 (170줄 → ~40줄)
```python
elif node_name == "document_agent":
    agent_response = node_output.get("agent_response", {})

    # 즉시 응답 (search, doc_pick 등 — 스트리밍 불필요)
    if not agent_response.get("stream_pending"):
        if agent_response.get("message"):
            yield sse("token", agent_response["message"])
        continue

    # StreamRequest → vLLM 스트리밍 호출
    cfg = agent_response["llm_config"]
    post = agent_response.get("post_stream", {})

    client, model = _get_vllm_client(cfg["task"])  # vLLM 클라이언트 + LoRA 분기
    stream = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": cfg["sys_prompt"]},
            {"role": "user", "content": cfg["user_prompt"]},
        ],
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
        stream=True,
    )

    full_response = ""
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            full_response += token
            yield sse("token", token)

    # post_stream 처리
    agent_response["message"] = full_response
    agent_response["answer"] = full_response

    if post.get("update_summary_db"):
        await _update_summary_db(db, post["update_summary_db"], full_response)
    if post.get("check_regulation"):
        reg = await _stream_regulation(full_response, user.id)
        if reg:
            agent_response["regulation_check"] = reg
            yield sse("token", reg["summary"])
    if post.get("filter_sources"):
        agent_response["sources"] = _filter_sources(agent_response["sources"], full_response)

    # cleanup
    for k in ("stream_pending", "llm_config", "post_stream"):
        agent_response.pop(k, None)
    agent_response["model_name"] = model
    final_state["agent_response"] = agent_response
```

### 공통 헬퍼 함수 (chat.py 상단)
```python
def _get_vllm_client(task: str) -> tuple:
    """vLLM 클라이언트 + task별 모델명(LoRA) 반환

    Returns: (AsyncOpenAI client, model_name str)
    - task="summary" → v3_summary (LoRA)
    - task="qa" → base model (LoRA 없음)
    - task="generate" → v3_generate (LoRA)
    - 기타 → base model
    """
    import os, httpx
    from openai import AsyncOpenAI
    vllm_base = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    vllm_api_key = os.getenv("VLLM_API_KEY", "EMPTY")
    vllm_model = os.getenv("VLLM_MODEL", "kakaocorp/kanana-1.5-8b-instruct-2505")
    use_lora = os.getenv("VLLM_USE_LORA", "false").lower() == "true"

    LORA_MAP = {"summary": "v3_summary", "generate": "v3_generate"}
    model = LORA_MAP.get(task, vllm_model) if use_lora else vllm_model

    client = AsyncOpenAI(
        api_key=vllm_api_key, base_url=vllm_base,
        timeout=httpx.Timeout(60.0, connect=15.0), max_retries=0,
    )
    return client, model

async def _update_summary_db(db, document_id: int, response_text: str):
    """요약 결과 파싱 → DB 업데이트"""
    from ai.agents.document._summary import parse_summary_output
    from app.models.document import Document
    parsed = parse_summary_output(response_text)
    if not parsed["tags"]:
        return
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc:
        doc.summary = parsed["summary"]
        doc.tags = parsed["tags"]
        await db.commit()

async def _stream_regulation(text: str, user_id: int) -> dict | None:
    """규정 연결 → 결과 반환 (있으면)"""
    from ai.agents.regulation_validator import check_content_regulations
    result = await check_content_regulations(text, user_id=user_id)
    return result if result.get("notes") else None

def _filter_sources(sources: list, response_text: str) -> list:
    """LLM 답변에 실제 언급된 소스만 필터링"""
    if not sources or not response_text:
        return sources
    filtered = []
    for src in sources:
        title = src.get("title", "")
        keywords = [w for w in title.replace("_", " ").split() if len(w) >= 3]
        if not keywords:
            continue
        match = sum(1 for kw in keywords if kw in response_text)
        if match >= max(len(keywords) // 2, 1):
            filtered.append(src)
    return filtered if filtered else sources  # 전부 필터되면 원본 유지
```

---

## Phase 2: QA 재설계 (`_qa.py`)

### 현재 문제
1. context 있어도 RAG 재실행 (중복 호출)
2. 스트리밍/비스트리밍 프롬프트 불일치 (인라인 vs prompts.py)
3. chat_history 미지원 (멀티턴 불가)
4. JSON 파싱 실패 시 빈약한 fallback
5. sLLM base 모델용 최적화 없음

### 새 `_handle_doc_qa` 설계
```python
async def _handle_doc_qa(
    query: str,
    context: list = None,
    user_id: int = None,
    user_team: str = None,
    stream_mode: bool = False,
    chat_history: list = None,
    document_content: str = None,
) -> Dict[str, Any]:
```

### QA 흐름
```
1. context 확보:
   a. document_content 있음 → 단일 문서 context (RAG 스킵)
   b. context 이미 있음 → 그대로 사용 (RAG 스킵)
   c. 둘 다 없음 → _retrieve_context(query, use_reranker=True, top_k=7)
2. context 없으면 → "관련 문서 없음" 즉시 반환
3. user_prompt 구성:
   - chat_history 있으면 [이전 대화] 섹션 추가
   - context를 [참고 문서] 섹션으로 포함
   - query를 [질문] 섹션으로 포함
4. stream_mode 분기:
   → True: StreamRequest 반환 (task="qa", filter_sources=True)
   → False: _call_llm(task="qa") → JSON 파싱 → 구조화 응답
```

### 프롬프트 구성

**prompts.py에 추가:**
```python
DOC_QA_STREAMING_PROMPT = """\
당신은 기업 문서 기반 질의응답 전문가입니다.
주어진 문서 내용을 근거로 사용자의 질문에 정확하게 답변하세요.

규칙:
- 반드시 제공된 문서 내용만을 근거로 답변하세요.
- 답변 근거가 되는 문서를 자연스럽게 언급하세요 (예: "XX 규정에 따르면...")
- 문서에서 답을 찾을 수 없으면 솔직히 "제공된 문서에서 해당 내용을 찾을 수 없습니다"라고 답하세요.
- 추측이나 외부 지식으로 보충하지 마세요.
- 한국어로 답변하세요.\
"""
```

**user_prompt 템플릿:**
```
[이전 대화]  ← chat_history가 있을 때만
사용자: 출장비 규정 알려줘
어시스턴트: 출장비는 규정 제8조에 따르면...

[참고 문서]
[문서 제목: 출장비 규정]
출장비는 실비 지급을 원칙으로 하며...

[문서 제목: 복리후생 규정]
...

[질문]
더 자세하게 알려줘
```

### 비스트리밍 JSON 파싱 강화
```python
# 기존: json.loads 한 번 시도 후 raw text fallback
# 개선: 코드블록 추출 → json.loads → regex 추출 → raw fallback
def _parse_qa_json(text: str) -> dict:
    # 1. ```json ... ``` 블록 추출
    # 2. json.loads 시도
    # 3. 실패 시 {"answer": ..., "citations": []} 형태 regex
    # 4. 최종 fallback: {"answer": text, "citations": [], "confidence": 0.5}
```

---

## Phase 3: 검색 재설계 (`_search.py`)

### 현재 문제
1. reranker 미사용 → 정밀도 낮음
2. 단순 포맷팅만 (개선 여지)

### 변경사항

1. **reranker 항상 적용**: `_retrieve_context(use_reranker=True)`
2. **score_threshold=0.1**: 관련없는 결과 제거
3. **top_k=10**: reranker가 재정렬하므로 더 많이 가져와서 정밀 필터
4. **search는 스트리밍 불필요**: LLM 안 쓰므로 항상 즉시 반환

### _retrieve_context 개선 (`_common.py`)
```python
async def _retrieve_context(
    query: str,
    user_id: int = None,
    user_team: str = None,
    top_k: int = 7,
    use_reranker: bool = False,      # NEW
    score_threshold: float = None,   # NEW
) -> tuple:
    # pipeline.retrieve()에 파라미터 전달
    search_results = pipeline.retrieve(
        query, user_id=user_id, user_team=user_team,
        top_k=top_k, filter={"source": "documents"},
        use_reranker=use_reranker,
        score_threshold=score_threshold,
    )
```

### 검색 흐름 (변경 최소화)
```
1. _retrieve_context(query, use_reranker=True, score_threshold=0.1, top_k=10)
2. document_id 기준 중복 제거 (기존 유지)
3. 카드형 포맷팅 (기존 유지)
4. 즉시 반환 (stream_pending 없음, LLM 없음)
```

---

## Phase 4: 요약 정리 (`_summary.py`)

### 현재 상태: 거의 완성, StreamRequest 프로토콜만 적용

### 변경사항

1. **StreamRequest 프로토콜 적용**: 기존 `stream_pending` → `llm_config` + `post_stream` 구조
2. **DB 업데이트**: 스트리밍 시 `post_stream.update_summary_db = document_id` → chat.py 헬퍼가 처리
3. **chat_history 파라미터 추가** (인터페이스 통일)
4. **비스트리밍 경로는 기존 유지** (잘 동작하므로)

### 요약 스트리밍 반환 (변경 전 → 후)
```python
# 변경 전
return {
    "type": "doc_retrieve",
    "sub_type": "summary",
    "stream_pending": True,
    "sys_prompt": sys_prompt,
    "user_prompt": user_prompt,
    "document_id": document_id,
}

# 변경 후
return {
    "type": "doc_retrieve",
    "sub_type": "summary",
    "stream_pending": True,
    "llm_config": {
        "sys_prompt": sys_prompt,
        "user_prompt": user_prompt,
        "temperature": 0.1,
        "max_tokens": 1024,
        "task": "summary",
    },
    "post_stream": {
        "update_summary_db": document_id,
        "check_regulation": True,
        "filter_sources": False,
    },
}
```

---

## Phase 5: _entry.py + chat_history 전달

### _entry.py 변경
```python
async def document_agent(state: AgentState) -> AgentState:
    chat_history = state.get("chat_history", [])
    document_content = state.get("document_content") or state.get("extracted_text")

    # doc_retrieve 분기 시 chat_history, document_content 전달
    if intent == "doc_retrieve":
        if _is_summary:
            response_data = await _handle_doc_summary(
                user_input, document_content=document_content,
                document_id=document_id, user_id=user_id,
                user_team=user_team, stream_mode=stream_mode,
                chat_history=chat_history,
            )
        elif _is_pure_search(user_input):
            response_data = await _handle_doc_search(
                user_input, context, user_id, user_team=user_team,
                stream_mode=stream_mode,
            )
        else:
            response_data = await _handle_doc_qa(
                user_input, context, user_id=user_id,
                user_team=user_team, stream_mode=stream_mode,
                chat_history=chat_history,
                document_content=document_content,
            )
```

### chat_history → user_prompt 변환 (`_common.py`)
```python
def _format_chat_context(chat_history: list, max_turns: int = 3) -> str:
    """최근 N턴 대화를 프롬프트용 텍스트로 변환"""
    if not chat_history:
        return ""
    recent = chat_history[-max_turns * 2:]
    lines = []
    for msg in recent:
        role = "사용자" if msg["role"] == "user" else "어시스턴트"
        content = msg.get("content", "")[:200]
        if content:
            lines.append(f"{role}: {content}")
    if not lines:
        return ""
    return "[이전 대화]\n" + "\n".join(lines)
```

---

## 수정 파일 목록

| # | 파일 | 변경 내용 | 난이도 |
|---|------|----------|--------|
| 1 | `ai/agents/document/_common.py` | `_retrieve_context`에 reranker/threshold 파라미터 추가, `_format_chat_context` 추가 | 하 |
| 2 | `ai/llm/prompts.py` | `DOC_QA_STREAMING_PROMPT` 추가 | 하 |
| 3 | `ai/agents/document/_qa.py` | **전면 재작성** — RAG 중복 제거, 프롬프트 통일, chat_history, StreamRequest | 상 |
| 4 | `ai/agents/document/_search.py` | reranker=True, score_threshold=0.1, top_k=10 적용 | 하 |
| 5 | `ai/agents/document/_summary.py` | StreamRequest 프로토콜 적용 (llm_config + post_stream) | 중 |
| 6 | `ai/agents/document/_entry.py` | chat_history, document_content 핸들러 전달 | 하 |
| 7 | `backend/app/api/v1/chat.py` | document_agent 170줄 → ~40줄 + 공통 헬퍼 4개 | 상 |

**generate 관련 코드는 건드리지 않음** (별도 CLI에서 작업 중)

---

## 구현 순서

1. **`_common.py`** — `_retrieve_context` 개선 + `_format_chat_context` 추가
2. **`prompts.py`** — QA 스트리밍 프롬프트 추가
3. **`_qa.py`** — 전면 재작성
4. **`_search.py`** — reranker + threshold 적용
5. **`_summary.py`** — StreamRequest 프로토콜 적용
6. **`_entry.py`** — chat_history 전달
7. **`chat.py`** — document_agent 블록 재작성 + 공통 헬퍼

---

## 검증 방법

1. **비스트리밍** (`POST /api/v1/chat/`)
   - QA: "출장비 규정이 뭐야?" → answer + citations + confidence
   - 검색: "보고서 찾아줘" → sources 카드
   - 요약: document_id + "요약해줘" → tags + summary

2. **스트리밍** (`POST /api/v1/chat/stream`)
   - QA: 토큰 스트리밍 → result에 sources 포함
   - 요약: 토큰 스트리밍 → DB 업데이트 확인
   - 검색: 즉시 result (스트리밍 없음)

3. **멀티턴**: "출장비 규정 알려줘" → "더 자세하게" → 이전 컨텍스트 유지

4. **프론트 호환**: `type`, `sub_type`, `sources`, `citations`, `tags` 필드 보존
