# doc_retrieve 통합 파이프라인 설계

> 작성일: 2026-03-13 | 작성자: 신지용 (PM)
> 상태: ~~설계 확정 / 구현 대기~~ → **구현 완료 (2026-03-15)**
> 최종 수정: 2026-03-15 — 설계 리뷰 반영, 실제 구현 결과 §14~§17 추가

---

## 1. 배경

기존 8개 intent 중 `doc_search`, `doc_qa`, `doc_summary` 3개를 `doc_retrieve` 하나로 통합.

- **이유**: 세 개 모두 RAG 검색이 선행되는 동일 파이프라인이며, 출력 형태만 다름
- **효과**: BERT 분류기가 "문서 관련이네" 판단만 하고, 세부 처리는 sLLM(카나나)이 자연어로 판단
- **결과**: 8개 → 6개 intent로 축소하여 분류 정확도 향상

### 최종 6개 Intent

| Intent | 설명 | Agent |
|--------|------|-------|
| `doc_retrieve` | 문서 검색/QA/요약 | document_agent |
| `doc_generate` | 문서 생성 | document_agent |
| `judgment` | 규정 정보 + 규정 판단 | judgment_agent |
| `schedule_add` | 일정 추가 | schedule_agent |
| `schedule_view` | 일정 조회 | schedule_agent |
| `general` | 일반 대화 | general_response |

---

## 2. 오케스트레이터 구조

```
사용자 입력
    │
    ▼
┌──────────────┐
│ BERT 분류기   │  (6개 intent)
└──────┬───────┘
       │
  confidence >= 0.7 → 바로 라우팅
  confidence < 0.7  → 사용자에게 후보 제시 (top-3)
       │
       ▼
  각 Agent에서 sLLM(카나나)이 처리
```

### 핵심 원칙
- **BERT는 교통경찰**: 어느 agent로 보낼지만 판단
- **sLLM은 실무자**: agent 안에서 어떻게 답할지 판단
- **fallback은 사용자 재질문**: sLLM에게 라우팅 맡기지 않음 (sLLM은 라우팅용으로 학습 안 됨)

---

## 3. doc_retrieve 파이프라인 흐름

```
사용자 입력 → BERT: doc_retrieve
    │
    ▼
┌──────────────────────────────────────────────┐
│              Document Agent                   │
│                                              │
│  1. 요약 요청? ("요약해줘" 등)                 │
│     └─ YES → doc_pick 반환 (문서 선택 UI)     │
│              → 사용자가 문서 선택              │
│              → DB에서 저장된 요약 반환          │
│                                              │
│  2. 그 외 (검색/QA) → RAG 검색 실행           │
│     - top_k: 7                               │
│     - filter: {"source": "documents"}        │
│                                              │
│  3. 검색 결과 없음? → "관련 문서 없음" 반환    │
│                                              │
│  4. 통합 프롬프트 구성                        │
│     - system: DOC_RETRIEVE_SYSTEM_PROMPT      │
│     - user: [검색된 문서] + [사용자 요청]      │
│                                              │
│  5. sLLM (카나나) 호출                        │
│     - stream_mode → stream_pending 반환       │
│     - 일반 mode → 직접 호출 후 반환           │
│     - temperature: 0.1                       │
│     - LoRA: 사용 안 함 (base model)           │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│ 응답 (자연어 + sources)   │
│                          │
│ {                        │
│   type: "doc_retrieve",  │
│   message: "LLM 답변",   │
│   sources: [{title, source, score, content, document_id}] │
│ }                        │
│                          │
│ 또는 (요약 요청):         │
│ {                        │
│   type: "doc_retrieve",  │
│   subtype: "doc_pick",   │
│   message: "문서를 선택하거나 첨부해주세요" │
│ }                        │
└──────────────────────────┘
```

---

## 4. 통합 프롬프트

```
당신은 기업 내부 문서 전문가입니다.
제공된 문서 내용을 기반으로 사용자의 요청에 가장 적절한 형태로 답변합니다.

규칙:
- 반드시 제공된 문서 내용만을 근거로 답변하세요.
- 답변의 근거가 되는 문서 제목이나 출처를 언급하세요.
- 문서에서 답을 찾을 수 없으면 "관련 내용을 찾지 못했습니다"라고 답하세요.
- 추측이나 외부 지식으로 답변을 보충하지 마세요.
- 한국어로 답변하세요.
```

- JSON 모드 사용 안 함 → **자연어 응답**
- sLLM이 질문 맥락에 따라 검색결과/QA답변 형태를 자연스럽게 결정 (요약은 doc_pick → DB)
- 프론트엔드는 message를 마크다운으로 렌더링 + sources 목록 표시

---

## 5. 응답 형식

```python
# 검색/QA 응답
{
    "type": "doc_retrieve",
    "message": "sLLM 자연어 답변",
    "answer": "message와 동일 (하위 호환)",
    "sources": [
        {
            "title": "문서 제목",
            "source": "파일명",
            "score": 0.85,
            "content": "청크 미리보기",
            "document_id": 123,
        }
    ],
    "model_name": "kanana-1.5-8b",
}

# 요약 요청 → doc_pick 응답
{
    "type": "doc_retrieve",
    "subtype": "doc_pick",
    "message": "요약할 문서를 선택하거나 파일을 첨부해주세요.",
    "sources": [],
}
```

- 기존 `citations`, `confidence`, `tags`, `category` 필드 제거
- `sources`는 RAG 검색 결과에서 추출
- 프론트엔드는 `type: "doc_retrieve"` 하나만 처리

---

## 6. 요약 처리

### 현재 단계: 요약 요청 → 무조건 doc_pick

```python
# 1. 요약 키워드 감지 ("요약", "정리", "핵심", "간추려")
if _is_summary_request(user_input):
    return {
        "type": "doc_retrieve",
        "subtype": "doc_pick",
        "message": "요약할 문서를 선택하거나 파일을 첨부해주세요.",
        "sources": [],
    }
    # → 프론트에서 문서 목록 UI 노출
    # → 사용자가 문서 선택 → document_id로 DB에서 저장된 요약 반환 (sLLM 재호출 없음)

# 2. 그 외 (검색/QA) → RAG 검색 → sLLM 답변
else:
    results = rag_pipeline.retrieve(query, top_k=7)
    → sLLM 호출
```

### 왜 DB에서 가져오는가?
- 문서관리 페이지에서 업로드 시 이미 sLLM이 요약 생성 → DB에 `summary`, `tags`, `category` 저장
- 관련 코드: `document_service.py:286-292`, `document_agent.py:83-99`
- 채팅에서 요약 재요청 시 sLLM 재호출 불필요

### 추후 구현 예정
- 파일 첨부 + 채팅 요약 (document_content → RAG 스킵 → sLLM 요약)
- "계약서 요약해줘" (문서명 지정) → RAG → DB 저장된 요약 반환

---

## 7. doc_retrieve vs judgment 구분

### BERT 분류 기준
- **doc_retrieve**: "알려줘", "뭐야?", "찾아줘" (정보 요청)
- **judgment**: "맞아?", "가능해?", "위반이야?" (판단 요청)

### 학습 데이터 예시

```
# doc_retrieve
"출장 보고서 찾아줘"          → doc_retrieve
"계약서 해지 조건 알려줘"      → doc_retrieve
"이 문서 내용이 뭐야?"        → doc_retrieve

# judgment (규정 정보 + 판단 모두 포함)
"출장 규정 알려줘"            → judgment
"출장비 30만원 청구 가능해?"   → judgment
"재택근무 주 3회 해도 돼?"     → judgment
```

### 핵심 차이
- "규정" 키워드 → judgment (규정 전담 agent가 처리)
- 일반 문서 → doc_retrieve
- judgment agent 내부에서 정보/판단을 sLLM이 구분

### 경계 쌍 데이터 중요
- `doc_retrieve`와 `judgment` 사이 경계 데이터를 충분히 학습시킬 것
- intent당 50개 정도의 경계 쌍 데이터 권장

---

## 8. RAG 파라미터

| 파라미터 | 값 | 이유 |
|----------|-----|------|
| top_k | 7 | search(10)과 QA(5)의 균형. 카나나 8K context 내 충분 |
| use_reranker | False | +2~5초 지연. RRF hybrid search로 충분 |
| use_hyde | False | 추가 LLM 호출 비용. 기본 검색으로 시작 |
| filter | `{"source": "documents"}` | 규정은 judgment agent가 처리 |

---

## 9. LoRA 처리

- 기존 `v2_summary` LoRA는 "분류:/태그:/요약:" 형식으로 학습됨
- 통합 프롬프트와 호환 안 됨 → **base model 사용**
- 추후 통합 프롬프트로 `v2_retrieve` LoRA 학습 가능
- `DOC_SLLM_TASKS` 환경변수에 "retrieve" 추가하면 전환 가능

---

## 10. 스트리밍

기존 stream_pending 패턴 그대로 사용:

```python
# stream_mode=True일 때
return {
    "type": "doc_retrieve",
    "stream_pending": True,
    "sys_prompt": DOC_RETRIEVE_SYSTEM_PROMPT,
    "user_prompt": user_prompt,
    "sources": sources,
}
# → chat.py가 sLLM 스트리밍 호출 → SSE 토큰 전달
```

---

## 11. 수정 대상 파일 (구현 시 참고)

| 파일 | 변경 내용 |
|------|----------|
| `ai/llm/prompts.py` | `DOC_RETRIEVE_SYSTEM_PROMPT` 추가 |
| `ai/agents/document_agent.py` | `_handle_doc_retrieve()` 추가, dispatch에 `doc_retrieve` 분기 추가 |
| `ai/agents/orchestrator.py` | `route_by_intent`에 `doc_retrieve` 추가, `clarify_with_candidates` 라벨 추가 |
| `backend/app/api/v1/chat.py` | 스트리밍 task 매핑에 `"retrieve"` 추가 |

### 재사용할 기존 코드
- `_build_sources()` (document_agent.py:1039-1065) — RAG 결과 → sources 변환
- `_call_llm()` (document_agent.py:1070-1138) — sLLM/API 모드 분기 + fallback
- stream_pending 패턴 (chat.py:422-495) — SSE 스트리밍

### 정리 대상 (BERT 재학습 후)
- `_handle_doc_search`, `_handle_doc_qa`, `_handle_doc_summary` 제거
- `DOC_SEARCH_SYSTEM_PROMPT`, `DOC_QA_SYSTEM_PROMPT`, `DOC_QA_SLLM_PROMPT`, `DOC_SUMMARY_SLLM_PROMPT` 제거
- orchestrator에서 기존 intent 분기 제거

---

## 12. 검증 방법

1. 검색 테스트: "계약서 관련 자료 찾아줘" → sources + 문서 목록 설명 응답
2. QA 테스트: "계약서 해지 조건이 뭐야?" → 구체적 답변 + 출처 언급
3. 요약 테스트: "요약해줘" → doc_pick 응답 (문서 선택 UI 노출)
4. RAG 없는 경우: "존재하지 않는 문서 찾아줘" → "관련 문서 없음" 응답
5. 스트리밍: SSE 토큰 단위 응답 확인

---

## 13. BERT 분류기 학습 데이터 (지영님 전달용)

### 6개 Intent 목록

| Intent | 설명 | 예시 |
|--------|------|------|
| `doc_retrieve` | 문서 검색/QA/요약 | "계약서 찾아줘", "해지 조건 뭐야?", "요약해줘" |
| `doc_generate` | 문서 생성 | "회의록 만들어줘", "보고서 작성해줘" |
| `judgment` | 규정 정보 + 판단 | "규정 알려줘", "이거 가능해?" |
| `schedule_add` | 일정 추가 | "내일 3시 회의 잡아줘" |
| `schedule_view` | 일정 조회 | "이번 주 일정 알려줘" |
| `general` | 일반 대화 | "안녕", "고마워" |

### 멀티라벨 (복합질문)
- sigmoid 멀티라벨 방식 추천
- "회의록 작성하고 내일 일정도 잡아줘" → `[doc_generate, schedule_add]`
- 복합질문 데이터: intent 조합별 50개씩

### 기존 데이터 라벨 매핑
- `doc_search` → `doc_retrieve`
- `doc_qa` → `doc_retrieve`
- `doc_summary` → `doc_retrieve`

### 아웃풋 형태

```python
# 싱글 입력
classify("계약서 해지 조건 알려줘")
→ {"intent": "doc_retrieve", "confidence": 0.92}

# 복합 입력
classify("회의록 작성하고 내일 일정도 잡아줘")
→ {"intents": [
     {"intent": "doc_generate", "confidence": 0.88},
     {"intent": "schedule_add", "confidence": 0.85}
   ],
   "is_compound": true}

# 낮은 confidence
classify("그거 처리해줘")
→ {"intent": "general", "confidence": 0.45,
   "candidates": ["doc_retrieve", "schedule_view", "general"]}
```

---

## 14. 설계 리뷰 결과 — 변경 사항 (2026-03-15)

설계 리뷰를 거쳐 아래 3가지가 원안(§3~§5)에서 변경됨.

| 항목 | 원안 (§3~§5) | 변경 후 |
|------|-------------|---------|
| 프롬프트 전략 | 통합 프롬프트 1개 (`DOC_RETRIEVE_SYSTEM_PROMPT`) | **태스크별 sLLM 프롬프트 유지** — 기존 LoRA + 학습 데이터 활용 |
| 파이프라인 분기 | 요약 vs 그 외 (2-way) | **summary → QA → search (3-way)** |
| 응답 형식 | `type: "doc_retrieve"` + 단일 구조 | `type: "doc_retrieve"` + **`sub_type`** (summary\|qa\|search) |

### 변경 이유
- **통합 프롬프트 폐기**: v2_qa / v2_summary LoRA가 각각 900+100건으로 학습됨. 통합 프롬프트로 바꾸면 기존 LoRA + 데이터를 버리게 됨
- **3-way 분기 추가**: QA(질문형)와 검색(찾기형)은 출력 형식이 다름 — QA는 citations+confidence, 검색은 문서 목록
- **sub_type 추가**: 프론트엔드가 요약(태그 배지)/QA(신뢰도 바)/검색(출처 목록) 각각 다른 카드로 렌더링

---

## 15. 실제 구현 파이프라인 (TO-BE)

```
doc_retrieve 진입
    │
    ├─ 1) _is_summary?
    │   조건: document_content 있음 / document_id 있음 / 요약키워드+동사어미
    │   │
    │   ├─ content 없음 → doc_pick (문서선택 UI)
    │   ├─ document_id + DB요약 있음 → DB 반환 (sLLM 스킵)
    │   └─ DB 없음 → DOC_SUMMARY_SLLM_PROMPT + v2_summary LoRA
    │       출력: {type: "doc_retrieve", sub_type: "summary", tags, summary}
    │
    ├─ 2) _is_qa_query?
    │   조건: 질문형 패턴 (뭐야/알려줘/어떻게) + 의문형 어미 + explain 의도
    │   │
    │   └─ RAG(top_k=7) → DOC_QA_SYSTEM_PROMPT (API) / DOC_QA_SLLM_PROMPT + v2_qa LoRA (sLLM)
    │       출력: {type: "doc_retrieve", sub_type: "qa", answer, citations, confidence, sources}
    │
    └─ 3) 검색 (그 외)
        │
        └─ RAG(top_k=7) → _build_search_prompt (API) / DOC_SEARCH_SLLM_PROMPT (sLLM, base model)
            출력: {type: "doc_retrieve", sub_type: "search", answer, sources}
```

### 요약 키워드 오탐 방지

| 입력 | 이전 | 개선 후 |
|------|------|---------|
| "요약해줘" | ✅ summary | ✅ summary |
| "정리해줘" | ✅ summary | ✅ summary |
| "정리된 자료 찾아줘" | ❌ summary (오탐) | ✅ search |
| "핵심만 알려줘" | ✅ summary | ✅ summary |

개선 방법: 요약 키워드 뒤에 **동사어미**(해/해줘/해주세요/부탁/하자/할래) 확인

### QA 감지 로직 (`_is_qa_query`)

```python
# 1. 명시적 질문형: 뭐야, 알려줘, 설명해, 어떻게, 왜, 무엇, 무슨
# 2. 의문형 어미: ~인가요, ~나요, ~ㅂ니까, ~한가요
# 3. _detect_search_intent()가 "explain" 반환 → QA로 분류
```

---

## 16. 실제 응답 형식

```python
# 검색 응답
{
    "type": "doc_retrieve",
    "sub_type": "search",
    "answer": "LLM 자연어 답변",
    "message": "answer와 동일 (하위 호환)",
    "sources": [{"title", "source", "score", "content", "document_id"}],
}

# QA 응답
{
    "type": "doc_retrieve",
    "sub_type": "qa",
    "answer": "질문에 대한 답변",
    "message": "answer와 동일",
    "citations": [{"source", "content", "relevance"}],
    "confidence": 0.85,
    "sources": [{"title", "source", "score", "content", "document_id"}],
}

# 요약 응답 (DB 반환 또는 sLLM 생성)
{
    "type": "doc_retrieve",
    "sub_type": "summary",
    "answer": "태그: #태그1 ... 요약: ...",
    "message": "answer와 동일",
    "tags": ["태그1", "태그2"],
    "summary": "요약문",
}

# 요약 요청 (문서 미선택) → doc_pick
{
    "type": "doc_pick",
    "message": "요약할 문서를 선택해주세요:",
    "documents": [{"document_id", "title"}],
}
```

---

## 17. 실제 수정 파일 (4개)

| 파일 | 변경 내용 | 커밋 |
|------|----------|------|
| `ai/llm/prompts.py` | `DOC_SEARCH_SLLM_PROMPT` 추가 (검색 전용 sLLM 프롬프트) | `66eae46` |
| `ai/agents/document_agent.py` | 3-way 라우팅, `_is_qa_query()` 추가, 응답 `sub_type` 통일, top_k=7 | `66eae46` |
| `backend/app/api/v1/chat.py` | `sub_type` 기반 태스크 매핑, summary DB 업데이트 조건 수정 | `66eae46` |
| `frontend/src/pages/ChatPage.jsx` | `doc_retrieve` 통합 렌더러 (sub_type별 카드 분기), 레거시 위임 | `66eae46` |

### 프론트엔드 렌더링 매핑

| sub_type | 카드 헤더 | 핵심 UI |
|----------|----------|---------|
| `search` | "문서 검색 결과" | 마크다운 답변 + 출처 목록 |
| `qa` | "문서 Q&A" | 신뢰도 바 + 마크다운 답변 + 인용 + 출처 |
| `summary` | "문서 요약" | 태그 배지 + 요약문 |

### 레거시 호환

| 이전 응답 타입 | 프론트엔드 처리 |
|---------------|----------------|
| `doc_search` | `doc_retrieve` 케이스로 처리 (기존과 동일) |
| `doc_summary` | `doc_retrieve`로 위임 → `tags` 존재 시 summary 카드 |
| `doc_qa` / `doc_search_qa` | `doc_retrieve`로 위임 → `citations` 존재 시 QA 카드 |

### LoRA 활용 (sLLM 모드)

| 경로 | 프롬프트 | LoRA | 학습 데이터 |
|------|---------|------|------------|
| 요약 | `DOC_SUMMARY_SLLM_PROMPT` | v2_summary | 900+100건 |
| QA | `DOC_QA_SLLM_PROMPT` | v2_qa | 900+100건 |
| 검색 | `DOC_SEARCH_SLLM_PROMPT` (신규) | 없음 (base model) | - |
