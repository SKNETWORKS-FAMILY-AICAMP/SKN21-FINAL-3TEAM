# QA 스트리밍/비스트리밍 통합 — 구현 계획

## 목표

문서 QA의 스트리밍/비스트리밍 경로를 통합하여, 단일 질문이든 복합 질문의 sub_query이든 동일한 confidence/citations/sources 결과를 생성한다.

## 핵심 원칙

1. **스트리밍 경로는 건드리지 않는다** — 이미 잘 동작하는 primary path
2. **비스트리밍 경로를 스트리밍과 동일한 로직으로 교체한다**
3. **compound query 기능은 그대로 유지한다** — chat.py의 sub_query 처리 흐름 변경 없음
4. **프론트엔드 변경 없음** — 이미 optional 필드 처리가 되어 있음

## 변경 범위

### 1단계: 공유 함수 추출 (`_stream.py` → `_common.py` 또는 별도 모듈)

`_stream.py`의 post_stream 후처리 로직 중 비스트리밍에서도 쓸 부분을 독립 함수로 추출:

- **`filter_and_build_citations(sources, response_text)`**: 이미 존재하는 `_filter_sources` + citations 생성 로직을 하나의 함수로 묶음
  - `[참고: 문서제목]` 태그 파싱 → 매칭된 sources만 남김
  - fallback: 키워드 매칭 (`_filter_sources`)
  - 최종 보장: sources 0건이면 원본 상위 1건 유지
  - citations 생성: filtered sources 기반 (title, content[:200], relevance)
  - 답변에서 `[참고: ...]` 줄 제거 (clean_response)
  - 반환: `(clean_response, filtered_sources, citations)`

현재 이 로직은 `_stream.py` L158-205에 인라인으로 존재. 이를 함수로 추출하고, `execute_doc_stream`에서는 추출한 함수를 호출하도록 변경.

### 2단계: `_qa.py` 비스트리밍 경로 수정

`_handle_doc_qa`의 L165-201 (비스트리밍 섹션)을 변경:

**Before (현재):**
```python
# 5. 비스트리밍: sLLM 직접 호출 (JSON mode)
from ai.llm.prompts import DOC_QA_SYSTEM_PROMPT
answer_json_str = await _call_llm(
    DOC_QA_SYSTEM_PROMPT, user_prompt,
    json_mode=True, task="qa",
)
qa_result = _parse_qa_json(answer_json_str)
# ... LLM confidence + RAG 혼합 계산
# ... LLM이 생성한 citations 그대로 사용
```

**After (변경 후):**
```python
# 5. 비스트리밍: 스트리밍과 동일한 프롬프트 + 후처리
from ai.llm.prompts import DOC_QA_STREAMING_PROMPT
answer_text = await _call_llm(
    DOC_QA_STREAMING_PROMPT, user_prompt,
    json_mode=False, task="qa",
)
# confidence: RAG score 기반 (스트리밍과 동일)
confidence = round(min(rag_top_score, 0.85), 2)
# citations: 키워드 매칭 (스트리밍과 동일)
clean_answer, filtered_sources, citations = filter_and_build_citations(sources, answer_text)
```

### 3단계: 불필요한 코드 정리

- `_qa.py`에서 `_parse_qa_json` 함수 삭제 (더 이상 사용되지 않음)
- `ai/llm/prompts.py`에서 `DOC_QA_SYSTEM_PROMPT` 삭제
- `_common.py`의 `_get_mock_response`에서 QA JSON mock 부분도 자연어로 변경 (선택)

### 4단계: 검증

- 단일 질문 (stream_mode=True): 기존과 동일하게 동작 확인
- 복합 질문 (compound): sub_query 결과의 confidence/citations/sources 확인
- 프론트엔드 렌더링: QA 카드/신뢰도 바/인용/출처 정상 표시 확인
- document_content 직접 선택 케이스: confidence=1.0 → 0.85 캡 적용 확인

## 주의사항

### document_content 케이스 (사용자가 문서 직접 선택)
현재 `rag_top_score = 1.0`으로 설정되는데, 0.85 캡이 적용되면 최종 confidence는 0.85가 된다. 이는 의도된 동작이다 — "문서 매칭 점수"와 "답변 정확도"는 다르기 때문.

### _call_llm의 json_mode 제거
`json_mode=False`로 변경하면 LLM이 자유 형식으로 답변한다. `DOC_QA_STREAMING_PROMPT`는 이미 `[참고: 문서제목]` 형식을 요청하므로, post_stream과 동일한 파싱이 가능하다.

### compound sub_response 구조
chat.py에서 compound 결과를 병합할 때 `sub_response.get("message", "")`를 사용한다. 변경 후에도 `message` 필드는 `clean_answer`로 채워지므로 호환성 문제 없음.

### DOC_QA_SYSTEM_PROMPT 참조 확인
삭제 전에 다른 파일에서 import하는 곳이 없는지 확인 필요. `_qa.py`에서만 import하고 있는 것으로 파악되나, grep으로 최종 확인할 것.

## 영향도

| 영역 | 영향 |
|------|------|
| 단일 QA (스트리밍) | 없음 — 변경하지 않음 |
| 복합 QA (비스트리밍) | confidence 값 변경 (최대 1.0 → 0.85), citations 형식 동일하되 생성 방식 변경 |
| 프론트엔드 | 없음 — 기존 optional 필드 처리로 호환 |
| 프롬프트 | `DOC_QA_SYSTEM_PROMPT` 삭제 (JSON 강제 프롬프트) |
| Mock 응답 | QA JSON mock → 자연어 mock (선택적) |
