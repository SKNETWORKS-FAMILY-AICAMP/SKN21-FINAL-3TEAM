# 상호작용 멀티에이전트 전환 - 전략 플랜

## Executive Summary

현재 "라우터 기반 멀티에이전트" 아키텍처를 "상호작용 가능 멀티에이전트"로 전환한다.
핵심은 **에이전트가 실행 중 다른 에이전트에게 후속 작업을 요청할 수 있는 메커니즘**을 LangGraph 그래프에 도입하는 것이다.
기존 기능을 깨뜨리지 않으면서 점진적으로 마이그레이션하며, 무한루프 방지와 스트리밍 호환성을 핵심 제약으로 관리한다.

---

## 1. 현재 상태 분석

### 1.1 현재 그래프 구조
```
classify_intent
  ├── compound → decompose_query → compound_pending → format_response → END
  ├── low_confidence → clarify_with_candidates → format_response → END
  └── single → [judgment|document|schedule|general] → format_response → END
```

### 1.2 핵심 한계

| 한계 | 상세 |
|------|------|
| 단일 실행 | 한 턴에 하나의 에이전트만 실행 (compound도 순차 독립 실행) |
| 라우터 독점 | 라우팅 결정권이 오케스트레이터에만 있음 (에이전트 자율성 없음) |
| 결과 기반 체이닝 불가 | 문서 생성 → 규정 체크 → 일정 추가 같은 동적 파이프라인 불가 |
| prev_agent_context 한계 | 이전 **턴**의 결과만 참조 가능, 같은 턴 내 실시간 공유 불가 |

### 1.3 기존 잘 되는 것 (보존해야 할 것)

- ONNX 멀티라벨 intent 분류 + compound 감지
- SSE 스트리밍 (chat.py에서 노드별 이벤트 처리)
- safe_*_agent 래퍼 패턴 (에러 격리)
- prev_agent_context 크로스턴 맥락
- compound_pending의 sub_query 순차 처리

---

## 2. 가능성 분석: LangGraph에서 어떻게 전환 가능한가

### 2.1 LangGraph의 조건부 엣지 활용

LangGraph `StateGraph`는 **노드 실행 후 다음 노드를 동적으로 결정**하는 `add_conditional_edges`를 지원한다.
현재는 `classify_intent → route_by_intent → Agent → format_response → END`의 일직선이지만,
Agent 노드 **뒤에도** 조건부 엣지를 추가하면 "Agent → 판단 → 다음 Agent or END" 패턴이 가능하다.

```python
# 현재
graph.add_edge("document_agent", "format_response")

# 변경 후
graph.add_conditional_edges(
    "document_agent",
    route_after_agent,  # agent_response의 next_actions를 보고 판단
    {"schedule_agent": "schedule_agent", "done": "format_response", ...}
)
```

### 2.2 에이전트 결과 기반 라우팅 (핵심 메커니즘)

각 에이전트가 `agent_response`에 **`next_actions`** 필드를 선택적으로 포함:

```python
# document_agent가 문서 생성 후 반환
state["agent_response"] = {
    "type": "doc_generate",
    "message": "보고서가 생성되었습니다.",
    "content": {...},
    # ↓ 새로운 필드: 후속 에이전트 요청
    "next_actions": [
        {"agent": "judgment", "query": "이 보고서가 사내 보고서 작성 규정에 맞는지 확인"},
        {"agent": "schedule", "query": "보고서 제출 마감일 일정에 추가"},
    ]
}
```

### 2.3 왜 LangGraph에서 가능한가

1. **StateGraph는 DAG가 아니다** - 사이클을 허용하므로 Agent → Dispatcher → Agent 루프 가능
2. **조건부 엣지 + 상태 기반 판단** = 동적 체이닝의 자연스러운 구현
3. **기존 노드를 그대로 재사용** - safe_*_agent 래퍼 변경 최소화

---

## 3. 문제점과 해결 방안

### 3.1 무한루프 방지

**문제**: Agent A → Agent B → Agent A → ... 의 무한 사이클

**해결**:
- `AgentState`에 `agent_chain: list[str]` 필드 추가 (실행된 에이전트 이력)
- `agent_chain_depth: int` 필드로 현재 깊이 추적
- **MAX_CHAIN_DEPTH = 3** 하드 리밋 (오케스트레이터에서 강제)
- 같은 에이전트 재호출 금지 (agent_chain에 이미 있으면 스킵)

```python
def route_after_agent(state: AgentState) -> str:
    chain = state.get("agent_chain", [])
    depth = state.get("agent_chain_depth", 0)
    next_actions = state.get("agent_response", {}).get("next_actions", [])

    # 깊이 초과 or 후속 액션 없음 → 종료
    if depth >= MAX_CHAIN_DEPTH or not next_actions:
        return "format_response"

    # 다음 에이전트 결정 (이미 실행된 에이전트 제외)
    for action in next_actions:
        target = action["agent"]
        if target not in chain:
            return f"{target}_agent"

    return "format_response"
```

### 3.2 스트리밍 호환성

**문제**: chat.py의 SSE 스트리밍은 노드 이름으로 분기 (`elif node_name == "document_agent":`).
같은 노드가 2번 실행되면 스트리밍 핸들러가 혼란.

**해결**:
- **Dispatcher 노드 도입**: Agent 실행 후 결과를 수집하는 중간 노드
- chat.py에서 `agent_dispatcher` 노드 이벤트를 받으면 "후속 처리 중..." SSE 이벤트 전송
- 후속 에이전트 결과는 `chain_responses: list[dict]`에 누적
- 최종 `format_response`에서 체인 결과를 병합하여 단일 응답 생성

```
classify_intent → Agent → agent_dispatcher → [다음 Agent → agent_dispatcher → ...] → format_response → END
```

### 3.3 상태 관리: 에이전트 간 메시지 패싱

**문제**: 현재 `agent_response`는 단일 dict로, 체인 중 덮어씌워짐.

**해결**:
- `chain_responses: list[dict]` - 체인 내 모든 에이전트 결과 누적
- `chain_context: dict` - 현재 체인의 공유 맥락 (이전 에이전트 결과 요약)
- 각 에이전트는 `chain_context`를 읽어서 이전 에이전트의 결과를 참조

```python
# agent_dispatcher에서 처리
chain_responses = state.get("chain_responses", [])
chain_responses.append({
    "agent": current_agent,
    "response": state["agent_response"],
    "timestamp": time.time(),
})
state["chain_responses"] = chain_responses

# chain_context에 이전 결과 요약 → 다음 에이전트가 참조
state["chain_context"] = _summarize_chain(chain_responses)
```

### 3.4 에이전트 자율성 vs 통제

**문제**: 에이전트가 자유롭게 next_actions를 생성하면 예측 불가능한 동작 발생.

**해결**: **화이트리스트 기반 허용 체인**

```python
ALLOWED_CHAINS = {
    "doc_generate": ["judgment", "schedule"],      # 문서 생성 → 규정체크 or 일정추가
    "judgment": ["doc_retrieve", "schedule"],       # 판단 → 관련문서검색 or 일정
    "doc_retrieve": ["doc_generate", "judgment"],   # 문서검색 → 문서생성 or 규정체크
    "schedule": [],                                 # 일정은 체인 종점
}
```

---

## 4. 구체적 구현 방향

### 4.1 AgentState 확장

파일: `ai/agents/state.py`

```python
class AgentState(TypedDict):
    # ... 기존 필드 유지 ...

    # ── 에이전트 체이닝 (Phase 2) ──
    agent_chain: Optional[list[str]]       # 실행된 에이전트 이력 ["document", "judgment"]
    agent_chain_depth: Optional[int]       # 현재 체인 깊이 (0부터 시작)
    chain_responses: Optional[list[dict]]  # 체인 내 모든 에이전트 결과
    chain_context: Optional[dict]          # 체인 내 공유 맥락 (이전 결과 요약)
    pending_actions: Optional[list[dict]]  # 대기 중인 후속 액션 큐
```

### 4.2 오케스트레이터 그래프 재설계

파일: `ai/agents/orchestrator.py`

**Phase 1 그래프** (기존 호환 + dispatcher 추가):
```
classify_intent
  ├── compound → decompose_query → compound_pending → format_response → END
  ├── low_confidence → clarify_with_candidates → format_response → END
  └── single → Agent → agent_dispatcher ─┬── next_agent → Agent → agent_dispatcher
                                          └── done → format_response → END
```

```python
def build_graph():
    graph = StateGraph(AgentState)

    # 기존 노드
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("decompose_query", decompose_query)
    graph.add_node("compound_pending", compound_pending)
    graph.add_node("clarify_with_candidates", clarify_with_candidates)
    graph.add_node("judgment_agent", safe_judgment_agent)
    graph.add_node("document_agent", safe_document_agent)
    graph.add_node("schedule_agent", safe_schedule_agent)
    graph.add_node("general_response", general_response_node)
    graph.add_node("format_response", format_response)

    # 새 노드
    graph.add_node("agent_dispatcher", agent_dispatcher)

    graph.set_entry_point("classify_intent")

    # classify_intent → 기존 라우팅 유지
    graph.add_conditional_edges("classify_intent", route_by_intent, { ... })

    # Agent → agent_dispatcher (format_response 대신)
    graph.add_edge("judgment_agent", "agent_dispatcher")
    graph.add_edge("document_agent", "agent_dispatcher")
    graph.add_edge("schedule_agent", "agent_dispatcher")
    graph.add_edge("general_response", "agent_dispatcher")

    # agent_dispatcher → 다음 에이전트 or 종료
    graph.add_conditional_edges("agent_dispatcher", route_after_agent, {
        "judgment_agent": "judgment_agent",
        "document_agent": "document_agent",
        "schedule_agent": "schedule_agent",
        "format_response": "format_response",
    })

    # 나머지
    graph.add_edge("decompose_query", "compound_pending")
    graph.add_edge("compound_pending", "format_response")
    graph.add_edge("clarify_with_candidates", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile()
```

### 4.3 agent_dispatcher 노드 (핵심 신규 코드)

```python
MAX_CHAIN_DEPTH = 3

ALLOWED_CHAINS = {
    "document": ["judgment", "schedule"],
    "judgment": ["document", "schedule"],
    "schedule": [],
    "general": [],
}

async def agent_dispatcher(state: AgentState) -> AgentState:
    """에이전트 실행 후 결과 수집 + 후속 에이전트 결정"""
    agent_response = state.get("agent_response", {})
    chain = state.get("agent_chain") or []
    depth = state.get("agent_chain_depth") or 0

    # 현재 에이전트 이름 추출
    current_agent = _infer_agent_name(agent_response.get("type", ""))
    if current_agent and current_agent not in chain:
        chain.append(current_agent)

    # chain_responses에 결과 누적
    chain_responses = state.get("chain_responses") or []
    chain_responses.append({
        "agent": current_agent,
        "response": agent_response,
    })

    # chain_context 업데이트 (다음 에이전트가 참조)
    state["chain_context"] = _build_chain_context(chain_responses)
    state["agent_chain"] = chain
    state["agent_chain_depth"] = depth + 1
    state["chain_responses"] = chain_responses

    # next_actions 큐잉
    next_actions = agent_response.get("next_actions", [])
    pending = state.get("pending_actions") or []

    for action in next_actions:
        target = action.get("agent", "")
        if target in ALLOWED_CHAINS.get(current_agent, []) and target not in chain:
            pending.append(action)

    state["pending_actions"] = pending
    return state
```

### 4.4 route_after_agent 라우팅 함수

```python
def route_after_agent(state: AgentState) -> str:
    depth = state.get("agent_chain_depth", 0)
    pending = state.get("pending_actions", [])

    if depth >= MAX_CHAIN_DEPTH or not pending:
        return "format_response"

    # 다음 액션 꺼내기
    next_action = pending[0]
    state["pending_actions"] = pending[1:]

    # 다음 에이전트를 위해 user_input/intent 업데이트
    target = next_action["agent"]
    state["user_input"] = next_action.get("query", state["user_input"])
    state["intent"] = _agent_to_intent(target)

    agent_map = {
        "judgment": "judgment_agent",
        "document": "document_agent",
        "schedule": "schedule_agent",
    }
    return agent_map.get(target, "format_response")
```

### 4.5 format_response 개선 (체인 결과 병합)

```python
def format_response(state: AgentState) -> AgentState:
    chain_responses = state.get("chain_responses", [])

    if len(chain_responses) <= 1:
        # 단일 에이전트 — 기존 로직 유지
        resp = state.get("agent_response", {})
        if not resp:
            state["agent_response"] = {"type": "general", "message": "응답을 생성하지 못했습니다."}
        return state

    # 멀티 에이전트 체인 — 결과 병합
    primary = chain_responses[0]["response"]  # 첫 번째 = 주 응답
    follow_ups = chain_responses[1:]          # 나머지 = 후속 결과

    state["agent_response"] = {
        **primary,
        "chain_results": [
            {"agent": cr["agent"], "type": cr["response"].get("type"), "summary": cr["response"].get("message", "")[:200]}
            for cr in follow_ups
        ],
        "is_chained": True,
    }
    return state
```

### 4.6 각 에이전트에서 next_actions 생성 (예시: document_agent)

파일: `ai/agents/document/_entry.py`

문서 생성 완료 후 규정 체크 + 일정 추가 요청:

```python
# _handle_doc_generate 내부, 생성 성공 후:
if response_data.get("sub_type") == "generate" and response_data.get("content"):
    next_actions = []

    # 규정 자동 체크 (regulation_check가 이미 있으면 스킵)
    if not response_data.get("regulation_check"):
        next_actions.append({
            "agent": "judgment",
            "query": f"'{response_data.get('title', '문서')}' 내용이 사내 규정에 부합하는지 확인",
            "reason": "auto_regulation_check",
        })

    # 마감일이 언급되었으면 일정 추가 제안
    if _has_deadline_mention(user_input):
        next_actions.append({
            "agent": "schedule",
            "query": f"'{response_data.get('title', '문서')}' 제출 마감 일정 등록",
            "reason": "auto_deadline_schedule",
        })

    if next_actions:
        response_data["next_actions"] = next_actions
```

### 4.7 chat.py SSE 스트리밍 대응

파일: `backend/app/api/v1/chat.py`

```python
elif node_name == "agent_dispatcher":
    chain_responses = node_output.get("chain_responses", [])
    pending = node_output.get("pending_actions", [])
    depth = node_output.get("agent_chain_depth", 0)

    if pending:
        next_agent = pending[0].get("agent", "")
        yield f"data: {json.dumps({
            'type': 'chain_progress',
            'depth': depth,
            'completed_agents': [cr['agent'] for cr in chain_responses],
            'next_agent': next_agent,
            'reason': pending[0].get('reason', ''),
        }, ensure_ascii=False)}\n\n"
    elif depth > 1:
        yield f"data: {json.dumps({
            'type': 'chain_complete',
            'total_agents': len(chain_responses),
            'agents': [cr['agent'] for cr in chain_responses],
        }, ensure_ascii=False)}\n\n"
```

---

## 5. 단계별 마이그레이션

### Phase 1: Foundation (2-3일) - 기존 기능 유지하면서 인프라 구축

**목표**: dispatcher 노드 추가, 체이닝 상태 필드 도입. 기존 동작 100% 호환.

1. `AgentState` 확장 (5개 필드 추가)
2. `agent_dispatcher` 노드 구현 (next_actions 없으면 바로 format_response)
3. `route_after_agent` 라우팅 함수 구현
4. `build_graph()` 수정: Agent → agent_dispatcher → conditional → format_response
5. chat.py에 `agent_dispatcher` SSE 핸들러 추가
6. **테스트**: 기존 단일 에이전트 시나리오 전부 동일하게 동작하는지 확인

### Phase 2: 첫 번째 체인 구현 (2-3일) - doc_generate → judgment

**목표**: 문서 생성 후 자동 규정 검증 체인 동작.

1. document_agent `_entry.py`에서 doc_generate 성공 시 `next_actions` 반환
2. judgment_agent가 `chain_context` 읽어서 생성된 문서 내용 기반 판단
3. format_response에서 체인 결과 병합
4. 프론트엔드: `chain_progress` / `chain_complete` SSE 이벤트 처리
5. **테스트**: "보고서 작성해줘" → 문서 생성 + 규정 체크 결과 동시 표시

### Phase 3: 일정 자동추가 체인 (2일) - doc_generate → schedule

**목표**: 마감일이 포함된 문서 생성 시 자동 일정 등록.

1. document_agent에서 마감일 감지 → schedule next_action 추가
2. schedule_agent가 chain_context에서 문서 제목/마감일 읽기
3. 프론트엔드: 일정 등록 확인 UI (자동 등록 전 사용자 컨펌)
4. **테스트**: "내일까지 매출 보고서 작성해줘" → 문서 생성 + 일정 등록

### Phase 4: 양방향 체이닝 (3일) - judgment ↔ document

**목표**: 규정 판단 후 관련 문서 검색, 문서 검색 후 규정 확인 등 양방향.

1. judgment_agent에서 규정 검색 후 관련 문서 참조가 필요하면 next_actions
2. ALLOWED_CHAINS 확장 및 검증
3. compound와의 통합: compound + chain이 동시에 일어나는 케이스 처리
4. **테스트**: 복합 시나리오 전체 리그레션

---

## 6. Risk Assessment

### High Risk

| 리스크 | 영향 | 완화 전략 |
|--------|------|-----------|
| 무한루프 | 서버 행, 타임아웃 | MAX_CHAIN_DEPTH=3, agent_chain 중복 체크, 60초 전체 타임아웃 |
| 스트리밍 깨짐 | UX 파괴 | Phase 1에서 기존 동작 100% 호환 검증 후 Phase 2 진입 |

### Medium Risk

| 리스크 | 영향 | 완화 전략 |
|--------|------|-----------|
| LLM 비용 증가 | 토큰 소비 2-3배 | chain_context 압축, 불필요한 체인 ALLOWED_CHAINS로 제한 |
| 응답 지연 | 체인 깊이 * 에이전트 시간 | 병렬 실행 가능한 액션은 asyncio.gather, 타임아웃 20초/에이전트 |
| next_actions 품질 | 엉뚱한 후속 요청 | 화이트리스트 + 규칙 기반 (LLM 판단 아닌 코드 로직) |

### Low Risk

| 리스크 | 영향 | 완화 전략 |
|--------|------|-----------|
| compound와 충돌 | 복합 + 체인 중복 | compound는 그대로 유지, 각 sub_query 내에서만 체인 허용 |
| 프론트엔드 대응 | 추가 개발 필요 | Phase 1은 백엔드만, Phase 2부터 프론트 대응 |

---

## 7. Success Metrics

| 지표 | 기준 |
|------|------|
| 기존 테스트 통과 | Phase 1 후 기존 단일 에이전트 시나리오 100% 동일 동작 |
| 체인 성공률 | doc_generate → judgment 체인 성공률 90% 이상 |
| 응답 시간 | 단일 에이전트 대비 체인 추가 시 +5초 이내 |
| 무한루프 발생 | 0건 (MAX_CHAIN_DEPTH + agent_chain 중복 체크) |

---

## 8. Dependencies

### 코드 의존성
- `ai/agents/state.py`: 필드 추가 (PM 관리)
- `ai/agents/orchestrator.py`: 그래프 재설계 (PM 관리)
- `backend/app/api/v1/chat.py`: SSE 핸들러 추가 (PM + Backend)
- `ai/agents/document/_entry.py`: next_actions 생성 (AI리드)
- `ai/agents/judgment_agent.py`: chain_context 읽기 (AI서브)
- `ai/agents/schedule_agent.py`: chain_context 읽기 (Backend)

### 외부 의존성
- 프론트엔드: chain_progress/chain_complete SSE 이벤트 처리 (Frontend)
- LLM 비용: 체인 길이에 비례하여 증가

---

## 9. Timeline

| Phase | 기간 | 핵심 산출물 |
|-------|------|------------|
| Phase 1: Foundation | 2-3일 | dispatcher 노드, 체이닝 인프라, 기존 호환 검증 |
| Phase 2: 첫 체인 | 2-3일 | doc_generate → judgment 체인 동작 |
| Phase 3: 일정 체인 | 2일 | doc_generate → schedule 체인 동작 |
| Phase 4: 양방향 | 3일 | 양방향 체이닝, 리그레션 테스트 |
| **합계** | **9-11일** | 상호작용 멀티에이전트 완성 |

---

## 10. compound vs chain 정리

| 구분 | compound (기존) | chain (신규) |
|------|----------------|-------------|
| 트리거 | 사용자 입력이 복합 질문 | 에이전트 실행 결과에 next_actions |
| 라우팅 주체 | 오케스트레이터 (ONNX + planner) | 에이전트 자체 |
| 에이전트 간 소통 | 없음 (독립 실행) | chain_context로 이전 결과 참조 |
| 결과 형태 | sub_responses (독립 병합) | chain_results (연쇄 병합) |
| 예시 | "규정 확인하고 일정 잡아줘" | "보고서 만들어줘" → 자동 규정체크 |

두 방식은 **공존**한다. compound는 사용자의 명시적 복합 요청, chain은 에이전트의 자율적 후속 처리.
