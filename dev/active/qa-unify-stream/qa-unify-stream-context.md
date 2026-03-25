# QA 스트리밍/비스트리밍 통합 — 컨텍스트

## 현재 상태 요약

문서 QA(`_handle_doc_qa`)에 두 가지 경로가 존재하며, 같은 질문에 대해 다른 결과를 생성한다.

### 경로 A: 스트리밍 (stream_mode=True) — 단일 질문

| 항목 | 현재 동작 |
|------|----------|
| **프롬프트** | `DOC_QA_STREAMING_PROMPT` — 자연어 답변, 마지막에 `[참고: 문서제목]` 표기 |
| **LLM 호출** | `_stream.py`의 `execute_doc_stream` → vLLM 토큰 스트리밍 |
| **Confidence** | RAG top_score 그대로 사용, 0.85 캡 적용 (`min(rag_top_score, 0.85)`) |
| **Citations** | `post_stream.filter_sources`에서 키워드 매칭 + `[참고:]` 태그 파싱으로 생성 |
| **Sources** | RAG 검색 결과 → sLLM 답변에서 실제 참조한 문서만 필터링 |

### 경로 B: 비스트리밍 (stream_mode=False) — 복합 질문 sub_query

| 항목 | 현재 동작 |
|------|----------|
| **프롬프트** | `DOC_QA_SYSTEM_PROMPT` — JSON 강제 출력 (answer, citations, confidence) |
| **LLM 호출** | `_common.py`의 `_call_llm(json_mode=True)` → 동기 응답 |
| **Confidence** | LLM 자체 confidence + RAG top_score 평균 (최대 1.0) |
| **Citations** | LLM이 JSON으로 직접 생성 (source, content, relevance 필드) |
| **Sources** | RAG 검색 결과 그대로 반환 (필터링 없음) |

### 불일치 포인트

1. **Confidence 범위가 다름**: 스트리밍은 최대 0.85, 비스트리밍은 최대 1.0
2. **Citations 생성 방식이 다름**: 키워드 매칭 vs LLM JSON → 결과 품질 차이
3. **프롬프트가 다름**: 자연어 vs JSON 강제 → 답변 스타일/품질 차이
4. **Sources 필터링 여부가 다름**: 스트리밍은 답변에 언급된 것만 남김, 비스트리밍은 전체 반환

## 관련 파일

| 파일 | 역할 | 수정 필요 |
|------|------|----------|
| `ai/agents/document/_qa.py` | QA 핸들러 (두 경로 분기점) | **핵심 수정 대상** |
| `ai/agents/document/_stream.py` | 스트리밍 실행기 + post_stream 후처리 | 공유 함수 추출 |
| `ai/agents/document/_common.py` | `_call_llm`, `_retrieve_context` | 변경 없음 |
| `ai/llm/prompts.py` | `DOC_QA_SYSTEM_PROMPT` (삭제 대상), `DOC_QA_STREAMING_PROMPT` (유지) | 상수 삭제 |
| `backend/app/api/v1/chat.py` | compound 질문에서 sub_query 실행 (L267-293) | 변경 없음 (stream_mode=False 유지) |
| `frontend/src/pages/ChatPage.jsx` | confidence/citations/sources 렌더링 (L115-230) | 변경 없음 |

## 복합 질문 (compound query) 흐름

```
chat.py SSE 스트리밍
  → graph.ainvoke (stream_mode=True)
    → decompose_query 노드: 복합 질문 감지
    → compound_pending 노드: sub_queries 리스트 반환
  → chat.py에서 각 sub_query를 graph.ainvoke(stream_mode=False)로 순차 실행
    → classify_intent → document_agent → _handle_doc_qa(stream_mode=False)
    → 비스트리밍 경로 실행 → JSON 응답 반환
  → 전체 sub_responses 병합 → compound_response로 SSE 전송
```

비스트리밍 경로는 compound sub_query 처리에서만 사용된다. sub_query 결과는 SSE `compound_sub_done` 이벤트로 프론트에 전달되며, 각 sub_response의 `message` 필드가 최종 compound 응답에 병합된다.

## 프론트엔드 렌더링 (ChatPage.jsx)

- `data.confidence`: 숫자면 신뢰도 바 표시 (높음/보통/낮음)
- `data.citations`: 배열이면 인용 카드 표시 (source, content, relevance)
- `data.sources`: 배열이면 출처 카드 표시 (title, score)
- 모든 필드가 optional — 없으면 해당 UI 섹션을 스킵
- compound 응답은 sub_responses 배열로 개별 렌더링됨

## 통합 방향 (결정 사항)

스트리밍 방식으로 통합:
- **Confidence**: RAG score only, 0.85 캡 (더 객관적이고 재현 가능)
- **Citations**: 키워드 매칭 기반 (일관성 있음, LLM 의존 제거)
- **Prompt**: `DOC_QA_STREAMING_PROMPT` 통일 (자연어, 더 좋은 UX)
- **Sources**: 답변 내용 기반 필터링 적용 (불필요한 출처 제거)
