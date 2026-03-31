# 판단 Agent 스트리밍 수정 플랜 — 셀프 리뷰

> 작성일: 2026-03-26
> 리뷰 대상: `judgment-fix-plan.md`

---

## 1. 문제 진단 정확성 검증

### 문제 1+2 (RAG 파라미터) — 정확

orchestrator.py L146의 `pipeline.retrieve(query=user_input, user_id=user_id, top_k=10, filter={"source": "regulations"})`는 judgment_agent.py L679-684 대비 3개 파라미터(`use_reranker`, `score_threshold`, `use_hyde`)가 누락되어 있고 top_k도 10 vs 5로 다르다. 이는 명확한 버그이다.

### 문제 3 (후처리 보조장치) — 플랜에서 올바르게 "이미 해결됨"으로 재평가

원래 이슈에서는 "orchestrator streaming에 후처리가 없다"고 했으나, 실제로는 `judgment_stream.py` L129-178에서 스트리밍 완료 후 모든 3중 검증을 수행하고 있다:
- `_parse_llm_response` + `_validate_result_category` (L140-142)
- `_check_keyword_match` + `_validate_article_exists` (L145-146)
- `_calibrate_confidence` (L148-152)
- `_group_regulations` (L157)
- `_check_consistency` (L168)

**검증 완료: 문제 3은 수정 불필요.**

### 문제 4 (로직 중복) — 정확

orchestrator.py가 `_build_context_prompt`, `_build_user_prompt`, `_extract_judgment_history` 같은 `_` prefix 내부 함수를 직접 import한다. 이는 캡슐화 위반이며 RAG 파라미터 동기화 실패의 원인이기도 하다.

---

## 2. 해결책 적절성 검증

### `prepare_judgment_stream()` 함수 추출 — 적절

**장점:**
- RAG 파라미터가 judgment_agent.py 한 곳에서만 관리되므로 향후 동기화 문제 방지
- orchestrator.py에서 내부 함수 import 제거 (깔끔한 인터페이스)
- 코드량 감소 (14줄 → 5줄)
- judgment_agent.py의 `judgment_agent()` 함수 자체는 변경 없으므로 비스트리밍 경로 회귀 위험 없음

**우려사항과 대응:**

| 우려 | 평가 | 대응 |
|------|------|------|
| `prepare_judgment_stream()`과 `judgment_agent()` 사이 RAG 파라미터 중복 | 여전히 2곳에 존재 | 허용 가능. 추후 리팩토링 시 `_retrieve_regulations()` 내부 헬퍼로 추출 가능하지만 현재 스코프 밖 |
| `prepare_judgment_stream()`이 `state` dict 직접 수정하지 않고 새 dict 반환 | 좋은 설계 | orchestrator에서 명시적으로 `state` 업데이트 |
| 기존 `judgment_stream.py`와의 호환성 | 반환 구조(`agent_response` 내부 필드)가 동일 | 문제 없음. `judgment_stream.py`는 `agent_response["sys_prompt"]`, `["user_prompt"]`, `["_rag_context"]`를 기대하며, 이 구조를 그대로 유지 |

---

## 3. 빠진 항목 점검

### (a) `_group_regulations` 호출 — 플랜에서 의도적 생략

비스트리밍 경로(judgment_agent.py L693)에서는 `_group_regulations(context)`를 호출하여 규정 그룹 정보를 만들지만, `prepare_judgment_stream()`에서는 이를 포함하지 않는다. 이는 올바른 판단이다 — 규정 그룹핑은 LLM 응답 파싱 후에 의미가 있으며, `judgment_stream.py` L157에서 이미 후처리 단계에서 수행하고 있다.

### (b) consistency warning 메시지 누락 — judgment_stream.py의 기존 문제

`judgment_stream.py` L168-171에서 `_check_consistency`를 호출하지만, 비스트리밍 경로(judgment_agent.py L742-745)와 달리 `warnings` 리스트에 일관성 경고 메시지를 추가하지 않는다:

```python
# judgment_stream.py (현재)
inconsistency = _check_consistency(user_input, parsed)
if inconsistency:
    parsed["consistency_flag"] = inconsistency
    # ← warnings 추가 없음!

# judgment_agent.py (정상)
inconsistency = _check_consistency(user_input, parsed)
if inconsistency:
    parsed["consistency_flag"] = inconsistency
    parsed.setdefault("warnings", []).append(
        f"일관성 경고: 동일 질문에 이전과 다른 결과 "
        f"({inconsistency['previous_result']} → {inconsistency['current_result']})"
    )
```

**권장:** 이번 플랜 스코프에 `judgment_stream.py` L169-171의 warnings 추가를 포함할 것. 2줄 추가이므로 부담 없음.

### (c) 에러 핸들링 — 충분

`prepare_judgment_stream()`에서 RAG 검색이나 프롬프트 빌드가 실패하면 예외가 orchestrator의 `except Exception` 블록(L180-187)에서 캐치된다. 별도 에러 핸들링 불필요.

---

## 4. 위험 평가

| 위험 | 수준 | 설명 |
|------|------|------|
| 비스트리밍 경로 회귀 | 낮음 | `judgment_agent()` 함수 변경 없음 |
| 스트리밍 경로 호환성 깨짐 | 낮음 | `agent_response` 구조 동일, `judgment_stream.py` 변경 없음 |
| reranker/HyDE 추가로 응답 지연 | 중간 | reranker + HyDE가 추가되면 RAG 검색 시간이 증가할 수 있음. 하지만 비스트리밍에서 이미 사용 중이므로 허용 가능한 수준 |
| 프론트엔드 영향 | 없음 | 최종 `agent_response` 필드 구조 변경 없음 |

---

## 5. 최종 판정

**플랜 승인. 아래 보완사항 1건 추가 권장:**

1. `judgment_stream.py` L169-171: `_check_consistency` 결과에 warnings 메시지 추가 (judgment_agent.py L742-745과 동일하게)

```python
# judgment_stream.py L168-171 변경
inconsistency = _check_consistency(user_input, parsed)
if inconsistency:
    parsed["consistency_flag"] = inconsistency
    parsed.setdefault("warnings", []).append(
        f"일관성 경고: 동일 질문에 이전과 다른 결과 "
        f"({inconsistency['previous_result']} → {inconsistency['current_result']})"
    )
```

**수정 파일 최종 목록 (보완 포함):**

| 파일 | 변경 |
|------|------|
| `ai/agents/judgment_agent.py` | `prepare_judgment_stream()` 함수 추가 |
| `ai/agents/orchestrator.py` | L129-167 → `prepare_judgment_stream()` 위임 |
| `ai/agents/judgment_stream.py` | L168-171 consistency warnings 추가 (2줄) |
