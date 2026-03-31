# QA 스트리밍/비스트리밍 통합 — 플랜 검토

**검토일**: 2026-03-25
**검토자**: PM (지용)
**결론**: 실행 가능. 아래 이슈 5건 수정 후 진행 권장.

---

## 1. 정확성 — 파일 경로, 줄 번호, 함수명

### 1-1. 정확한 참조

| 플랜 참조 | 실제 코드 | 판정 |
|-----------|----------|------|
| `_qa.py` L15-38 `_parse_qa_json` | L15-38 맞음 | OK |
| `_qa.py` L165-201 비스트리밍 섹션 | L165 `from ai.llm.prompts import DOC_QA_SYSTEM_PROMPT` ~ L201 `return {...}` 맞음 | OK |
| `_qa.py` L166 import | L166 맞음 | OK |
| `_qa.py` L169-172 `_call_llm` 호출 | L169-172 맞음 | OK |
| `_qa.py` L174 `_parse_qa_json` 호출 | L174 맞음 | OK |
| `_qa.py` L180-191 confidence 로직 | L180-191 맞음 | OK |
| `_qa.py` L193-201 return dict | L193-201 맞음 | OK |
| `_stream.py` L158-205 filter_sources 블록 | L158-205 맞음 | OK |
| `_stream.py` L252 `_filter_sources` 함수 | L252 맞음 | OK |
| `prompts.py` L196-226 `DOC_QA_SYSTEM_PROMPT` | L196-226 맞음 (정확히 31줄) | OK |
| `prompts.py` L228 `DOC_QA_STREAMING_PROMPT` | L228 맞음 | OK |
| `chat.py` L267-293 compound 처리 | L260-314 (약간 범위 차이) | 사소 |
| `_common.py` L308-316 mock 응답 | L308-316 맞음 (QA JSON mock 부분) | OK |

### 1-2. 부정확한 참조

**없음** — 줄 번호, 함수명, 파일 경로 모두 실제 코드와 일치한다.

---

## 2. 완전성 — 누락 사항

### 2-1. [경고] `DOC_QA_SLLM_PROMPT` 미언급

`ai/llm/prompts.py` L283에 `DOC_QA_SLLM_PROMPT`가 별도로 존재한다. 이것은 sLLM 전용 간소화 QA 프롬프트인데, 플랜에서 전혀 언급되지 않았다.

현재 이 프롬프트는 실제 코드에서 사용되지 않고 있으므로 (`_qa.py`에서 import하지 않음) 당장 문제는 없다. 하지만 향후 sLLM 전환 시 혼동 가능성이 있으므로, Task 3에서 `DOC_QA_SYSTEM_PROMPT` 삭제 시 `DOC_QA_SLLM_PROMPT`의 처리 방침(유지/삭제/주석)도 명시하는 것이 좋다.

**권장**: Task 3에 "DOC_QA_SLLM_PROMPT는 4단계 파인튜닝용으로 유지" 코멘트 추가

### 2-2. [정보] `_common.py`의 `_get_mock_response` JSON 분기

Task 4에서 mock 응답 변경을 "선택" 으로 표기했는데, 변경하지 않아도 기능상 문제 없다. 비스트리밍 QA에서 `json_mode=False`로 변경되면 mock 경로도 `json_mode=False`로 진입하므로, L339-343의 일반 텍스트 mock이 반환된다. QA 전용 mock (`L308-316`)은 더 이상 QA 경로에서 호출되지 않지만, 다른 `json_mode=True` 호출(회의록/문서 생성)에서 의도치 않게 매칭될 수 있다.

**권장**: mock 코드는 프로덕션 영향이 없으므로 선택 사항 유지 OK. 다만 mock 모드에서 QA 테스트 시 자연어 mock이 나오는 것을 인지할 것.

### 2-3. [OK] 누락 파일 없음

grep 결과 `DOC_QA_SYSTEM_PROMPT`는 `_qa.py`에서만 import, `_parse_qa_json`도 `_qa.py` 내부에서만 사용. `_filter_sources`도 `_stream.py` 내부에서만 호출. 플랜의 변경 범위에 누락 파일 없다.

---

## 3. 리스크

### 3-1. [중요] `_stream.py`에서 `_filter_sources`를 `_common.py`로 이동 시 import 경로

Task 1에서 `_filter_sources`를 `_common.py`로 이동하면, `_stream.py` L182에서의 호출이 깨진다. 플랜의 Task 1 체크리스트에 "execute_doc_stream의 filter_sources 블록을 filter_and_build_citations 호출로 대체"가 있지만, `_filter_sources` 단독 호출(L182)도 `filter_and_build_citations` 내부로 흡수되는지 명확하지 않다.

`_stream.py`에서 `_filter_sources`를 직접 호출하는 곳(L182)이 `filter_and_build_citations` 내부에서 호출되도록 바뀌면 문제 없지만, 만약 `_common.py`로 이동한 `_filter_sources`를 `_stream.py`에서도 계속 import해야 한다면 import 문을 추가해야 한다.

**권장**: Task 1 체크리스트에 "`_stream.py`에서 `_filter_sources` 직접 호출 제거 확인 (filter_and_build_citations 내부로 완전 흡수)" 항목 추가

### 3-2. [중요] `filter_and_build_citations`의 `_original_sources` 보존 로직

플랜에서 "agent_response dict 직접 조작이므로 execute_doc_stream 내부에 유지"라고 했지만, 비스트리밍 경로(`_qa.py`)에서는 `agent_response`가 아니라 로컬 변수 `sources`를 다룬다. `filter_and_build_citations`가 반환하는 `filtered_sources`가 0건일 때의 "원본 상위 1건 유지" 보장 로직이 비스트리밍에서도 동일하게 동작하는지 확인 필요.

현재 `_stream.py`의 L189-194에 "최종 보장" 로직이 있는데, 이것이 `filter_and_build_citations` 함수 내부에 포함되는지, 아니면 `_qa.py`에서 별도 구현해야 하는지 명확하지 않다.

**권장**: `filter_and_build_citations` 함수 시그니처에 "filtered_sources가 0건이면 원본 상위 1건 유지" 보장이 포함되어야 함을 명시. 현재 플랜 Task 1 체크리스트 항목 5("필터 결과 0건이면 원본 상위 1건 유지")에 있지만, `_stream.py`의 L189-194 "최종 보장" 로직(ref_titles 경로에서 0건 나올 때)도 함수에 포함해야 한다.

### 3-3. [낮음] confidence 값 변경의 프론트엔드 영향

비스트리밍 QA의 confidence가 최대 1.0에서 0.85로 변경된다. 프론트엔드에서 `confidence >= 0.8`을 "높음"으로 표시하고 있다면, 0.85 캡이 적용되어도 "높음" 범위에 들어가므로 문제없다. 플랜에서 "의도된 동작"으로 명시한 것은 적절하다.

**판정**: 리스크 없음

### 3-4. [낮음] `_call_llm`의 `json_mode=False` 전환 — sLLM 모드에서의 동작

`_call_llm`에서 `json_mode=False`로 호출하면 vLLM도 자유 형식 응답을 생성한다. `DOC_QA_STREAMING_PROMPT`에 `[참고: 문서제목]` 형식을 요청하고 있으므로, sLLM이 이 지시를 따르면 `filter_and_build_citations`의 파싱이 정상 동작한다. sLLM이 지시를 무시할 경우 키워드 매칭 fallback이 동작하므로 안전하다.

**판정**: 리스크 낮음, fallback 존재

---

## 4. 순서 — 단계별 의존성

| 단계 | 의존성 | 판정 |
|------|--------|------|
| 1 (공유 함수 추출) | 없음 | OK |
| 2 (비스트리밍 경로 수정) | Task 1의 `filter_and_build_citations` 필요 | OK |
| 3 (프롬프트 정리) | Task 2에서 import 변경 후 삭제 | OK |
| 4 (Mock 정리) | Task 2 이후 (선택) | OK |
| 5 (검증) | Task 1-3 완료 후 | OK |

**순서 논리적으로 문제 없음.** Task 1 → 2 → 3 의존성이 올바르다.

---

## 5. Compound Query 영향 분석

### 5-1. `message` 필드 병합 — 문제 없음

`chat.py` L319-321에서 compound 응답 병합:
```python
"message": "\n\n---\n\n".join(
    r["response"].get("message", "") for r in all_sub_responses
),
```

변경 후 비스트리밍 QA의 반환값에 `"message": clean_answer`가 포함되므로 (플랜 Task 2의 반환 dict), 이 병합 로직은 정상 동작한다.

### 5-2. sub_response 토큰 스트리밍 — 문제 없음

`chat.py` L296-302에서 `sub_message = sub_response.get("message", "")`를 10자 단위로 잘라 SSE 토큰으로 전송. `clean_answer`는 `[참고: ...]` 태그가 제거된 깨끗한 텍스트이므로 오히려 더 나은 UX.

### 5-3. sub_response의 confidence/citations/sources 전달 — 확인 필요

`chat.py` L308-312에서 `sub_response` 전체가 `all_sub_responses[i]["response"]`에 저장된다. L536에서 `agent_response` 전체가 SSE `result` 이벤트의 `data`로 전송된다. **하지만 compound 경로에서는 L324에서 `compound_response`로 덮어쓰므로**, 개별 sub_response의 confidence/citations/sources는 `compound_response["sub_responses"][i]["response"]` 안에만 존재한다.

프론트엔드가 compound 응답의 `sub_responses` 배열 내 개별 response의 confidence/citations/sources를 렌더링하고 있다면, 변경 후에도 이 필드들이 존재하므로 문제없다 (오히려 이전에 비해 더 일관된 형식).

**판정**: compound query 영향 없음. 호환성 완전.

---

## 종합 의견

### 수정 권장 사항 (실행 전)

| # | 중요도 | 내용 | 대상 문서 |
|---|--------|------|----------|
| 1 | 중요 | Task 1에 "`_stream.py`에서 `_filter_sources` 직접 호출 제거 확인" 항목 추가 | tasks.md |
| 2 | 중요 | `filter_and_build_citations` 함수에 "최종 보장" 로직(L189-194) 포함 여부 명확화 | plan.md, tasks.md |
| 3 | 권장 | Task 3에 `DOC_QA_SLLM_PROMPT` 처리 방침 명시 (유지/삭제 중 택 1) | tasks.md |
| 4 | 선택 | Task 2 반환 dict에서 `model_name` 필드 추가 누락 확인 — 스트리밍 경로는 `execute_doc_stream`에서 설정하지만 비스트리밍은 `_call_llm` 후 `get_last_model_name()`으로 가져와야 할 수 있음 | plan.md |
| 5 | 정보 | `_qa.py` 상단의 `import json`, `import re` — Task 2 완료 후 `json`은 불필요 (사용처 없음), `re`도 불필요 (`filter_and_build_citations`가 `_common.py`에 있으므로). tasks.md에 이미 언급되어 있으나, `time`과 `typing` import는 여전히 필요함을 확인 | tasks.md |

### 추가 발견: `model_name` 필드 누락 (항목 4 상세)

현재 비스트리밍 반환값(`_qa.py` L193-201)에 `model_name`이 없다. 스트리밍 경로에서는 `execute_doc_stream`이 `agent_response["model_name"]`을 설정한다(L139). 플랜의 Task 2 반환 dict에도 `model_name`이 없는데, 이는 현재 코드에서도 없으므로 기존 동작과 동일하다 (신규 이슈 아님). 하지만 일관성을 위해 추가를 검토할 수 있다.

---

**최종 판정**: 플랜은 정확하고 실행 가능하다. 위 5건의 수정 권장 사항 중 #1, #2는 구현 시 버그 방지를 위해 반영할 것을 권장한다.
