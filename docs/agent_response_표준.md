# agent_response 표준 형식

> 모든 Agent의 응답은 `AgentState.agent_response` (dict)에 저장된다.
> `format_response` 노드가 `type`과 `message` 필드를 보장한다.

---

## 공통 필수 필드

모든 Agent 응답에 반드시 포함되어야 하는 필드:

| 필드 | 타입 | 설명 |
|------|------|------|
| `type` | `str` | Agent 유형 식별자. intent와 동일한 값 사용 |
| `message` | `str` | 사용자에게 보여줄 텍스트 메시지 (다른 Agent가 참조할 때도 사용) |

---

## Agent별 응답 형식

### 1. judgment (판단 Agent — 경은)

```json
{
  "type": "judgment",
  "result": "yes | no | conditional | no_regulation",
  "confidence": 0.85,
  "confidence_breakdown": {
    "llm_raw": 0.90,
    "llm_weighted": 0.540,
    "rag_score": 0.75,
    "rag_weighted": 0.234,
    "coverage_score": 1.0,
    "coverage_weighted": 0.150,
    "conflict_penalty": 0.0,
    "hallucination_penalty": 0.0,
    "article_penalty": 0.0,
    "final": 0.85
  },
  "reasoning": "판단 근거 상세 설명",
  "message": "= reasoning (format_response 호환)",
  "regulations": [
    {"article": "제8조", "relevance": "높음", "content": "관련 내용 요약"}
  ],
  "cross_references": [
    {"articles": ["제8조", "제12조"], "relationship": "보완|충돌|상위규정", "detail": "관계 설명"}
  ],
  "conditions": "조건부일 때 조건 설명 (null이면 없음)",
  "alternatives": ["대안1", "대안2"],
  "regulation_groups": ["제3장 근로시간 및 휴가"],
  "article_validations": [{"article": "제8조", "exists": true}],
  "consistency_flag": null,
  "warnings": []
}
```

**`confidence_breakdown` 필드 상세:**

| 키 | 설명 | 범위 |
|---|---|---|
| `llm_raw` | LLM이 출력한 원본 confidence | 0.0~1.0 |
| `llm_weighted` | LLM raw × 0.6 (60% 가중치) | 0.0~0.6 |
| `rag_score` | RAG 검색 결과 평균 점수 | 0.0~1.0 |
| `rag_weighted` | RAG factor × 0.25 (25% 가중치) | 0.0~0.25 |
| `coverage_score` | 규정 커버리지 (규정 그룹 수 / 2) | 0.0~1.0+ |
| `coverage_weighted` | 커버리지 factor × 0.15 (15% 가중치) | 0.0~0.15 |
| `conflict_penalty` | 규정 충돌 감점 (0.1/건) | 0.0~ |
| `hallucination_penalty` | 환각 탐지 감점 (인용 조항 미매칭) | 0.0~0.15 |
| `article_penalty` | 존재하지 않는 조항 감점 (0.05/건) | 0.0~ |
| `final` | 최종 보정된 confidence | 0.0~1.0 |

### 2. doc_search (문서 검색 — 승언)

```json
{
  "type": "doc_search",
  "answer": "검색 결과 기반 답변",
  "message": "= answer",
  "sources": [
    {"title": "문서명", "source": "파일명", "score": 0.85, "content": "미리보기..."}
  ],
  "context": ["검색된 문서 텍스트 1", "..."]
}
```

### 3. doc_generate (문서 생성 — 승언)

```json
{
  "type": "doc_generate",
  "template_name": "보고서",
  "preview": "마크다운 미리보기",
  "message": "문서가 생성되었습니다.",
  "data": {"title": "...", "content": "..."},
  "document_id": 123,
  "download_url": "/api/v1/documents/123/download"
}
```

### 4. meeting_generate (회의록 생성 — 승언)

```json
{
  "type": "meeting_generate",
  "summary": "회의 전체 요약",
  "message": "= summary",
  "decisions": ["결정사항1"],
  "action_items": [{"content": "할일", "assignee": "담당자", "due_date": "기한"}],
  "risks": [{"description": "리스크", "level": "중간", "regulation": "관련 규정"}],
  "preview": "마크다운 미리보기",
  "document_id": 456,
  "download_url": "/api/v1/meetings/456/download"
}
```

### 5. schedule_add / schedule_view (일정 Agent — 혜빈)

```json
{
  "type": "schedule_add | schedule_view",
  "message": "일정 처리 결과 메시지",
  "google_services_result": {}
}
```

### 6. general (일반 응답 — 지용)

```json
{
  "type": "general",
  "message": "LLM이 생성한 일반 응답"
}
```

### 7. multi_intent (복합 질문 — 지용)

```json
{
  "type": "multi_intent",
  "message": "통합 텍스트 포맷",
  "summary": "마지막 성공 결과 요약",
  "sections": [
    {
      "step": 1,
      "intent": "judgment",
      "query": "분해된 질문",
      "status": "success | failed | skipped",
      "result": {}
    }
  ]
}
```

---

## 복합 쿼리에서 이전 Agent 결과 참조

판단 Agent 결과가 다른 Agent의 입력으로 들어가는 시나리오:

```python
# orchestrator.py — execute_sub_queries에서 이미 구현됨
async def _execute_single_agent(sub_query, parent_state, prev_context):
    sub_state = dict(parent_state)
    # 이전 단계의 context를 전달
    if prev_context:
        sub_state["context"] = prev_context
```

다른 Agent가 judgment 결과를 참조하려면:
1. `state["agent_response"]`에서 `type == "judgment"` 확인
2. `result`, `confidence`, `regulations` 필드 활용
3. `context`에 RAG 검색 결과가 저장되어 있음

---

## 주의사항

- `message` 필드는 반드시 문자열이어야 함 (프론트엔드 렌더링용)
- `format_response` 노드가 `message`가 없으면 빈 문자열로 설정함
- 새 필드를 추가할 때는 PM(지용)에게 공유 필요
