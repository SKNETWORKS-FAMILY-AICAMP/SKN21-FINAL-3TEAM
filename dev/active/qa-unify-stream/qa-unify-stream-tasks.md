# QA 스트리밍/비스트리밍 통합 — 작업 체크리스트

## 사전 확인

- [ ] `DOC_QA_SYSTEM_PROMPT`를 import하는 파일이 `_qa.py` 외에 없는지 grep 확인
- [ ] `_parse_qa_json`을 호출하는 곳이 `_qa.py` 외에 없는지 grep 확인
- [ ] `_filter_sources`를 `_stream.py` 외부에서 호출하는 곳이 없는지 확인

## Task 1: 공유 함수 추출

**파일**: `ai/agents/document/_stream.py`

- [ ] `_filter_sources` 함수를 `_stream.py`에서 `_common.py`로 이동
- [ ] `filter_and_build_citations(sources, response_text)` 함수 작성 (`_common.py`)
  - `_stream.py` L158-205의 로직을 함수로 추출
  - 입력: `sources` (RAG 검색 결과 리스트), `response_text` (LLM 답변 텍스트)
  - 출력: `(clean_response, filtered_sources, citations)` 튜플
  - 처리:
    1. `[참고: 문서제목]` 태그 파싱 → ref_titles 추출
    2. 답변에서 `[참고: ...]` 줄 제거 → clean_response
    3. ref_titles가 있으면 해당 sources만 남김
    4. 없으면 `_filter_sources`로 키워드 매칭 fallback
    5. 필터 결과 0건이면 원본 상위 1건 유지
    6. filtered_sources 기반 citations 생성 (상위 3건)
- [ ] `execute_doc_stream`의 `filter_sources` 블록을 `filter_and_build_citations` 호출로 대체
  - `_original_sources` 보존 로직은 `execute_doc_stream` 내부에 유지 (agent_response dict 직접 조작이므로)

## Task 2: 비스트리밍 경로 통합

**파일**: `ai/agents/document/_qa.py`

- [ ] import 변경: `DOC_QA_SYSTEM_PROMPT` → `DOC_QA_STREAMING_PROMPT` (L166)
- [ ] `_call_llm` 호출 변경 (L169-172):
  - 프롬프트: `DOC_QA_SYSTEM_PROMPT` → `DOC_QA_STREAMING_PROMPT`
  - `json_mode=True` → `json_mode=False` (또는 파라미터 제거)
- [ ] `_parse_qa_json` 호출 제거 (L174)
- [ ] confidence 계산 변경 (L180-191):
  - LLM+RAG 혼합 로직 전체 삭제
  - `confidence = round(min(rag_top_score, 0.85), 2)` 로 교체 (스트리밍과 동일)
- [ ] citations/sources 처리 변경 (L193-201):
  - `filter_and_build_citations(sources, answer_text)` 호출
  - 반환값에서 `clean_answer`, `filtered_sources`, `citations` 사용
- [ ] 반환 dict 수정:
  ```python
  return {
      "type": "doc_retrieve",
      "sub_type": "qa",
      "answer": clean_answer,
      "message": clean_answer,
      "citations": citations,
      "confidence": confidence,
      "sources": filtered_sources,
  }
  ```
- [ ] `_parse_qa_json` 함수 전체 삭제 (L15-38)
- [ ] 상단 `import json`, `import re` — 사용처 확인 후 불필요하면 제거

## Task 3: 프롬프트 정리

**파일**: `ai/llm/prompts.py`

- [ ] `DOC_QA_SYSTEM_PROMPT` 상수 삭제 (L196-226, 약 30줄)
- [ ] 삭제 후 남은 줄번호/공백 정리

## Task 4: Mock 응답 정리 (선택)

**파일**: `ai/agents/document/_common.py`

- [ ] `_get_mock_response`의 QA JSON mock (L308-316) → 자연어 mock으로 변경
  - `json_mode=True`일 때 QA JSON 반환하던 분기 → 비스트리밍에서 더 이상 json_mode 안 쓰므로
  - 남은 json_mode 사용처 (회의록/문서 생성)는 그대로 유지

## Task 5: 검증

- [ ] **단일 QA 테스트** (스트리밍):
  - 일반 문서 질문 → SSE 토큰 스트리밍 정상 확인
  - confidence 0.85 이하, citations/sources 표시 확인
- [ ] **복합 질문 테스트** (비스트리밍):
  - "재무 보고서 요약하고 인사 규정 알려줘" 같은 복합 질문
  - 각 sub_response의 confidence가 0.85 캡 적용되었는지 확인
  - citations가 키워드 매칭 기반으로 생성되었는지 확인
  - compound 최종 응답의 message 병합 정상 확인
- [ ] **document_content 직접 선택 테스트**:
  - 특정 문서 선택 후 질문 → confidence = 0.85 (rag_top_score=1.0이지만 캡 적용)
- [ ] **context 없음 테스트**:
  - RAG 결과 0건 → "관련 문서를 찾지 못했습니다" 응답 (기존과 동일, 변경 없음)
- [ ] **프론트엔드 렌더링**:
  - QA 카드: 신뢰도 바, 인용 카드, 출처 카드 정상 표시
  - compound 응답: sub_responses 개별 렌더링 정상

## 완료 기준

- [ ] 스트리밍/비스트리밍 QA의 confidence 계산 로직이 동일 (RAG score, 0.85 캡)
- [ ] 스트리밍/비스트리밍 QA의 citations 생성 로직이 동일 (키워드 매칭)
- [ ] 스트리밍/비스트리밍 QA의 프롬프트가 동일 (`DOC_QA_STREAMING_PROMPT`)
- [ ] `DOC_QA_SYSTEM_PROMPT` 삭제됨
- [ ] `_parse_qa_json` 삭제됨
- [ ] 기존 테스트/기능 깨지지 않음
