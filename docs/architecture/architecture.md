# 듀듀 (WorkFlow Agent) 전체 아키텍처 설계

## 시스템 개요

기업 업무 지원 AI — 규정 판단, 문서 관리, 일정 관리를 하나의 오케스트레이터로 통합.

---

## 1. 전체 파이프라인

```
사용자 입력 (챗봇 / 회의록 페이지 / 문서 페이지)
       │
       ▼
 Frontend (React) ── POST /api/v1/chat/stream ──→ Backend (FastAPI)
                                                       │
                                                  JWT 인증 → AgentState 초기화
                                                       │
                                                       ▼
                                          ┌─── Orchestrator (LangGraph) ───┐
                                          │                                │
                                          │  [classify_intent]             │
                                          │   BERT → Solar LLM → Embedding │
                                          │   (3단계 fallback)              │
                                          │         │                      │
                                          │   confidence < 0.7?            │
                                          │    ├─ Yes → clarify (top-3)    │
                                          │    └─ No  → Agent 라우팅        │
                                          │         │                      │
                                          │    ┌────┼────┬──────┐         │
                                          │    ▼    ▼    ▼      ▼         │
                                          │  Judge Doc  Sched  General    │
                                          │    │    │    │      │         │
                                          │    └────┴────┴──────┘         │
                                          │         │                      │
                                          │  [format_response]             │
                                          └─────────┼──────────────────────┘
                                                    │
                                                    ▼
                                          chat_logs DB 저장
                                                    │
       ┌────────────────────────────────────────────┘
       │  SSE (text/event-stream)
       ▼
 Frontend 렌더링
  intent → 처리중 표시 / token → 스트리밍 / result → 최종 응답 / done → 종료
```

### 각 Agent 워크플로우

```
┌─ Judgment Agent (경은) ─────────────────────────────────────────────────────┐
│                                                                             │
│  user_input ──→ RAG 하이브리드 검색 (규정문서, top_k=7) ──→ LLM 판단 (JSON)  │
│                    │                                          │             │
│                    │  Qdrant + BM25                            │             │
│                    │  bge-reranker                             ▼             │
│                                                   3중 보조장치 검증           │
│                                                   ├─ 환각 탐지 (인용 cross-check)
│                                                   ├─ 조항 존재 검증          │
│                                                   └─ confidence 보정        │
│                                                          │                  │
│                                                          ▼                  │
│  Output: { result: yes/no/conditional, confidence, reasoning, regulations } │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ Document Agent (승언) ─────────────────────────────────────────────────────┐
│                                                                             │
│  intent에 따라 4가지 분기 (챗봇/페이지 공용):                                  │
│                                                                             │
│  doc_generate ──→ 템플릿 로드(template_id) ──→ LLM 초안 생성 (JSON)          │
│                  → { data, preview, additional_fields }                      │
│                                                                             │
│  doc_summary ──→ 문서 로드(document_id) ──→ LLM 회사 요약 포맷 생성          │
│                  → { title, core_summary, key_points, keywords }            │
│                                                                             │
│  doc_search ──→ query(+필터) ──→ RAG 하이브리드 검색 (전체문서)               │
│                  챗봇: 질문→쿼리 변환 후 추천 / 페이지: 키워드/필터 탐색       │
│                  → { results[], message }                                    │
│                                                                             │
│  doc_qa ──→ RAG 검색 (비규정 문서) ──→ LLM 답변 + 인용 (주 사용처: 챗봇)     │
│                  → { answer, citations[] }                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ Schedule Agent (혜빈) ─────────────────────────────────────────────────────┐
│                                                                             │
│  schedule_add ──→ LLM 파싱 (자연어→구조화) ──→ Google Calendar API 등록      │
│                  → { schedule{title,start,end}, google_services{event_id} }  │
│                                                                             │
│  schedule_view ──→ LLM 기간 추출 ──→ Google Calendar API 조회               │
│                  → { schedules[], message }                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ General Response ──────────────────────────────────────────────────────────┐
│                                                                             │
│  user_input ──→ LLM 일반 응답 (업무 관련 친절 답변)                           │
│                  → { message }                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Intent 분류 체계

```
judgment       → Judgment Agent    (규정 판단/정보)
doc_generate   → Document Agent    (문서 생성)
doc_summary    → Document Agent    (문서 요약)
doc_search     → Document Agent    (문서 검색)
doc_qa         → Document Agent    (문서 QA)
schedule_add   → Schedule Agent    (일정 추가)
schedule_view  → Schedule Agent    (일정 조회)
general        → General Response  (일반 대화)
```

---

## 3. Judgment Agent (경은)

**역할:** 회사 규정/규칙 문서 기반 판단 및 정보 제공
**파인튜닝:** O (LoRA v1)

```
Input: user_input (규정 관련 질문)
        │
        ▼
┌───────────────┐
│ RAG 검색       │  규정 문서만 대상 (하이브리드 BM25+Vector)
│ (top_k=7)     │  다중 규정 교차 분석용으로 많이 가져옴
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ LLM 판단       │  규정 context + 판단 이력 + 대화 이력
│ (JSON mode)   │  → yes / no / conditional / no_regulation
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ 3중 보조장치    │  1) 환각 탐지 (인용 조항 cross-check)
│ + confidence  │  2) 조항 존재 검증
│   보정         │  3) 카테고리 제한 (유효하지 않은 결과 reject)
└───────┬───────┘
        │
        ▼
Output: {
  type: "judgment",
  result: "yes|no|conditional|no_regulation",
  confidence: 0.85,
  reasoning: "판단 근거",
  regulations: [{article, relevance, content}],
  cross_references: [{articles, relationship, detail}],
  message: "..."
}
```

**RAG 검색 대상:** 규정/규칙 문서 (인사규정, 보안규정, 복무규정 등)
**핵심 특징:** 3중 보조장치, confidence 보정, 일관성 모니터링

---

## 4. Document Agent (승언) — 리팩토링 대상

### 4-1. doc_generate (문서 생성) — 파인튜닝 O

등록된 템플릿(template_id)에 맞춰 초안을 생성. 챗봇/문서생성 페이지 공용.
결과로 초안과 추가로 필요한 입력 항목을 반환.

```
Input: user_input + template_id
        │
        ▼
 [템플릿 로드] → meeting_minutes | report | jd | proposal
        │
        ▼
 [LLM 초안 생성 (JSON mode)] → 템플릿 필드 채움
        │
        ▼
Output: { type: "doc_generate", data, preview, additional_fields, message }
```

- RAG: X (사용자 입력 기반 생성)
- 채워지지 않은 필드 → `additional_fields`로 반환
- meeting_minutes는 template_id로 처리 (기존 meeting_generate 통합)

### 4-2. doc_summary (문서 요약) — 파인튜닝 O

사용자가 선택한 문서(document_id)를 회사 요약 포맷으로 요약. 챗봇/페이지 공용.

```
Input: user_input + document_id
        │
        ▼
 [문서 내용 로드] → DB에서 content 가져옴
        │
        ▼
 [LLM 요약 (JSON mode)] → 회사 요약 포맷 강제
        │
        ▼
Output: { type: "doc_summary", title, core_summary, key_points, keywords }
```

- RAG: X (대상 문서가 명시적으로 주어짐)
- 회사 요약 포맷: title + core_summary(2-3문장) + key_points(3-7개) + keywords(3-5개)
- document_id 전달: 챗봇(직전 문서 참조) + 페이지(직접 전달) 둘 다 지원

### 4-3. doc_search (문서 검색) — 파인튜닝 X

query(+필터)로 문서 목록을 검색.
챗봇은 질문을 쿼리로 변환해 추천, 문서관리 페이지는 키워드/목록/필터 탐색 제공.

```
Input: user_input (query) + filters
        │
        ▼
 [RAG 하이브리드 검색] → 모든 문서 대상 (규정+비규정)
        │
        ▼
 [chatbot → 질문→쿼리 변환 후 추천 | page → 키워드/필터 탐색]
        │
        ▼
Output: { type: "doc_search", results: [{title, source, snippet, score}], message }
```

- RAG: O — 모든 문서 검색 (유형 제한 없음)
- LLM은 결과 정리(presentation)용으로만 사용
- chatbot: 질문→쿼리 변환 후 자연어 추천 / document_page: 키워드/목록/필터 탐색

### 4-4. doc_qa (문서 QA) — 파인튜닝 O

질문(question)에 대해 RAG로 근거를 찾아 답변+인용을 반환. 주 사용처: 챗봇.

```
Input: user_input (question)
        │
        ▼
 [RAG 하이브리드 검색] → 비규정 업무 문서만 대상
        │
        ▼
 [LLM 답변 (JSON mode)] → 답변 + 인용 생성
        │
        ▼
Output: { type: "doc_qa", answer, citations: [{source, content, relevance}], confidence }
```

- RAG: O — 비규정 문서만 (회의록, 보고서, 기획서 등)
- 반드시 인용(citations) 포함
- 파인튜닝 데이터: (question + context_chunks) → (answer + citations)

### 4-5. risk_detect — 추후 구현

---

## 5. Schedule Agent (혜빈)

**역할:** Google Calendar 연동 일정 관리
**파인튜닝:** X

### 5-1. schedule_add (일정 추가)

```
Input: user_input ("내일 오후 2시 회의 잡아줘")
        │
        ▼
 [LLM 파싱 (JSON mode)] → 자연어 → 구조화 일정 데이터
        │                   {title, start_time, end_time, description}
        ▼
 [Google Calendar API] → 일정 등록
        │
        ▼
Output: { type: "schedule_add", schedule: {...}, google_services: {synced, event_id} }
```

### 5-2. schedule_view (일정 조회)

```
Input: user_input ("이번 주 일정 알려줘")
        │
        ▼
 [LLM 파싱] → 기간 추출 (start_date, end_date)
        │
        ▼
 [Google Calendar API] → 일정 조회
        │
        ▼
Output: { type: "schedule_view", schedules: [...], message }
```

---

## 6. General Response

**역할:** 위 어떤 agent에도 해당하지 않는 일반 대화
**파인튜닝:** X

```
Input: user_input
        │
        ▼
 [LLM 일반 응답] → 업무 관련 질문에 친절히 답변
        │
        ▼
Output: { type: "general", message: "..." }
```

---

## 7. RAG 검색 대상 정리

| Agent/기능 | RAG | 검색 대상 | 비고 |
|-----------|-----|----------|------|
| Judgment | O | 규정/규칙 문서 | 문서 카테고리 필터 |
| doc_search | O | 모든 문서 | 필터 없음 |
| doc_qa | O | 비규정 업무 문서 | 문서 카테고리 필터 |
| doc_generate | X | - | |
| doc_summary | X | - | |
| Schedule | X | - | |
| General | X | - | |

---

## 8. RAG 문서 데이터 파이프라인

### 문서 유형 및 인덱싱

| 문서 유형 | 예시 | 인덱싱 방식 | 사용 Agent |
|----------|------|-----------|-----------|
| 규정 문서 (regulation) | 인사규정, 보안규정, 복무규정, 출장규정 | 관리자가 사전 등록 (시스템 문서) | Judgment, risk_detect |
| 업무 문서 (business) | 회의록, 보고서, 기획서, 제안서, 프로젝트 문서 | 사용자 업로드 | doc_qa, doc_search |

### Qdrant 메타데이터 설계

각 문서 청크에 필요한 메타데이터:

```json
{
  "source": "인사규정.pdf",
  "title": "인사규정",
  "chapter": "제3장 근로시간 및 휴가",
  "article": "제8조",
  "category": "regulation | business",
  "scope": "company | personal",
  "user_id": 123,
  "uploaded_at": "2026-02-22"
}
```

- `category: "regulation"` → Judgment Agent가 RAG 검색 시 필터
- `category: "business"` → doc_qa가 RAG 검색 시 필터
- doc_search는 category 필터 없이 전체 검색

### 문서 인덱싱 플로우

```
문서 업로드/등록
      │
      ▼
[Document Parser] → 텍스트 추출 (Docling/python-docx/OCR)
      │
      ▼
[Chunking] → 의미 단위 분할 (조항별 or 단락별)
      │
      ▼
[Embedding] → 벡터 변환 (bge-m3, 768dim)
      │
      ▼
[Qdrant 저장] → 벡터 + 메타데이터 (category, scope 등)
      │
      ▼
[BM25 인덱스 갱신] → 하이브리드 검색용
```

---

## 9. 파인튜닝 데이터 수집 전략

| Agent/기능 | 파인튜닝 | 수집 형태 | 학습 목표 |
|-----------|---------|----------|----------|
| Judgment | O (LoRA v1) | (question, regulations) → judgment_json | 정확한 규정 판단 |
| doc_generate | O (LoRA v2) | (request, template_type) → filled_json | 템플릿 문서 생성 |
| doc_summary | O (LoRA v2) | (document_text) → summary_json | 일관된 요약 |
| doc_qa | O (LoRA v2) | (question, context_chunks) → answer_json | 정확한 답변+인용 |
| doc_search | X | - | LLM은 정리용만 |
| Schedule | X | - | 파싱은 규칙 기반 |
| General | X | - | - |

**수집 방식:** LLM 호출 시 input/output을 chat_logs에 자동 저장 → JSON이라 그대로 학습 데이터
**sLLM 교체:** `get_llm()` → vLLM + LoRA adapter (코드 변경 없음, 팩토리 패턴)

---

## 10. Intent 분류 경계

| 사용자 입력 | intent | Agent | 이유 |
|------------|--------|-------|------|
| "연차 규정 알려줘" | judgment | Judgment | 규정 질문 |
| "출장비 기준?" | judgment | Judgment | 규정 질문 |
| "15일 연차 쓸 수 있어?" | judgment | Judgment | 규정 판단 |
| "보고서 만들어줘" | doc_generate | Document | 문서 생성 |
| "회의록 작성해줘" | doc_generate | Document | 생성 (meeting 템플릿) |
| "이 문서 요약해줘" | doc_summary | Document | 문서 요약 |
| "관련 문서 찾아줘" | doc_search | Document | 문서 검색 |
| "지난 회의 결정사항?" | doc_qa | Document | 비규정 문서 QA |
| "프로젝트 예산 얼마야?" | doc_qa | Document | 비규정 문서 QA |
| "내일 2시 회의 잡아줘" | schedule_add | Schedule | 일정 추가 |
| "이번 주 일정?" | schedule_view | Schedule | 일정 조회 |
| "안녕" | general | General | 일반 대화 |

**핵심 원칙:**
- 규정/규칙 → judgment (판단이든 정보 요청이든)
- 비규정 문서 QA → doc_qa
- 문서 찾기 → doc_search (모든 유형)
- 문서 만들기 → doc_generate (템플릿 기반)
- 문서 요약하기 → doc_summary (document_id 기반)

---

## 11. 리팩토링 범위 (문서 Agent만)

| 파일 | 변경 |
|------|------|
| `ai/agents/document_agent.py` | 4 핸들러로 재작성 |
| `ai/agents/state.py` | document_id, document_content 추가 |
| `ai/agents/intent_classifier.py` | intent 라벨 + 예시 수정 |
| `ai/agents/orchestrator.py` | 라우팅 + 한국어 라벨 수정 |
| `ai/llm/prompts.py` | 시스템 프롬프트 추가 |

Judgment Agent, Schedule Agent는 변경 없음.
Backend 연동은 별도 작업.

---

## 12. meeting_generate 제거 → doc_summary/doc_qa 추가 리팩토링

### 변경 이유

현재 코드는 `meeting_generate`가 별도 intent로 존재하지만, 실제로는 문서 요약 기능에 해당.
설계상 Document Agent의 4기능은 **검색 / 생성 / 요약 / QA**이므로 intent 체계를 맞춤.

- `meeting_generate` → `doc_generate`에 통합 (template_id = meeting_minutes)
- `doc_summary` 신규 추가
- `doc_qa` 신규 추가

### 파일별 변경 사항

#### 1) `ai/agents/intent_classifier.py`

```python
# Before
INTENT_LABELS = [
    "judgment",
    "doc_search",
    "doc_generate",
    "meeting_generate",   # ← 제거
    "schedule_add",
    "schedule_view",
    "general",
]

# After
INTENT_LABELS = [
    "judgment",
    "doc_search",
    "doc_generate",
    "doc_summary",        # ← 추가
    "doc_qa",             # ← 추가
    "schedule_add",
    "schedule_view",
    "general",
]
```

- LLM 프롬프트의 카테고리 설명도 동일하게 수정
- Embedding fallback 예시 문장에 doc_summary, doc_qa 추가
- KNOWN_OVERRIDES에 요약/QA 패턴 추가

#### 2) `ai/agents/orchestrator.py`

```python
# Before (route_by_intent)
elif intent in ("doc_search", "doc_generate", "meeting_generate"):
    route = "document_agent"

# After
elif intent in ("doc_search", "doc_generate", "doc_summary", "doc_qa"):
    route = "document_agent"
```

```python
# Before (intent_labels_kr)
intent_labels_kr = {
    ...
    "doc_generate": "문서 작성",
    "meeting_generate": "회의록 작성",   # ← 제거
    ...
}

# After
intent_labels_kr = {
    ...
    "doc_generate": "문서 작성",
    "doc_summary": "문서 요약",          # ← 추가
    "doc_qa": "문서 QA",                # ← 추가
    ...
}
```

#### 3) `ai/agents/document_agent.py`

```python
# Before — 분기
if intent == "doc_search":
    response_data = _handle_doc_search(...)
elif intent == "doc_generate":
    response_data = _handle_doc_generate(...)
elif intent == "meeting_generate":          # ← 제거
    response_data = _handle_meeting_generate(...)

# After — 분기
if intent == "doc_search":
    response_data = _handle_doc_search(...)
elif intent == "doc_generate":
    response_data = _handle_doc_generate(...)  # meeting_minutes는 template_type으로 처리
elif intent == "doc_summary":               # ← 추가
    response_data = _handle_doc_summary(...)
elif intent == "doc_qa":                    # ← 추가
    response_data = _handle_doc_qa(...)
```

- `_handle_meeting_generate()` 삭제
- `_handle_doc_summary(user_input, document_id)` 신규 작성
- `_handle_doc_qa(user_input, context, user_id)` 신규 작성
- `_handle_doc_generate()`에 template_type="meeting_minutes" 분기 추가

#### 4) `ai/agents/state.py`

```python
# 추가 필드
document_id: Optional[int]       # doc_summary 대상 문서 ID
document_content: Optional[str]  # doc_summary용 문서 본문
```

#### 5) BERT 재학습 (선택)

intent 라벨이 7개 → 8개로 변경되므로 BERT 가중치가 있는 경우 `train_intent.py` 재학습 필요.
가중치 없으면 Solar LLM / Embedding fallback이 자동 적용되므로 즉시 동작.

---

## 13. Agent별 Backend 후처리

Agent가 `agent_response`를 반환한 뒤, Backend에서 어떤 추가 처리가 필요한지 정리.

### 현재 흐름

```
Agent → agent_response → format_response → chat.py (SSE 전송 + chat_logs 저장) → END
```

chat.py는 **모든 Agent의 응답을 SSE로 프론트에 전달하고 chat_logs에 저장**하는 것까지만 담당.
그 이후 DB 저장, 파일 생성 등의 후처리는 Agent/intent별로 다름.

### Agent별 후처리 요약

| intent | Backend 후처리 | 현재 상태 |
|--------|--------------|----------|
| judgment | 없음 (chat_logs만) | ✅ 완료 |
| doc_search | 없음 (검색 결과 전달만) | ✅ 완료 |
| doc_generate | Document DB 저장 + 파일 렌더링 | ❌ 미구현 |
| doc_summary | 없음 (JSON → 프론트 렌더링) | ✅ 완료 |
| doc_qa | 없음 (JSON → 프론트 렌더링) | ✅ 완료 |
| schedule_add | DB 저장 + Google Calendar 동기화 | ✅ 완료 |
| schedule_view | 없음 (조회 결과 전달만) | ✅ 완료 |
| general | 없음 (chat_logs만) | ✅ 완료 |

**미구현은 doc_generate 하나.**

### doc_generate 후처리 (혜빈)

문서 생성은 Agent가 JSON 데이터를 만든 뒤, Backend에서 실제 문서로 저장해야 함.

```
Document Agent
 → agent_response: { type, preview(MD), data(JSON), template_name }
       │
       ▼
 chat.py: SSE로 preview 전달 → 프론트에서 미리보기 표시
       │
       ▼
 사용자가 "저장" 클릭 (프론트)
       │
       ▼
 POST /api/v1/documents/generate   ← 미구현
       │
       ▼
 document_service.generate_document()
  1. Document 레코드 생성 (title, content=JSON, scope, status="completed")
  2. 템플릿 렌더링 → DOCX/PDF 파일 생성
  3. 파일 저장 (로컬 /uploads/ 또는 S3)
  4. document_id + download_url 반환
       │
       ▼
 GET /api/v1/documents/{id}/download   ← 미구현
  → 저장된 파일 반환
```

**template_type별 처리:**

| template_type | 렌더링 방식 | 비고 |
|---------------|-----------|------|
| meeting_minutes | JSON → 회의록 DOCX | 제목, 참석자, 결정사항, 액션아이템 |
| report | JSON → 보고서 DOCX | 목차, 본문, 결론 |
| jd | JSON → JD DOCX | 직무, 자격요건, 우대사항 |
| proposal | JSON → 제안서 DOCX | 배경, 제안내용, 기대효과 |

**meeting_minutes인 경우 추가 처리:**

```
document_service.generate_document() 내부:

  if template_type == "meeting_minutes":
    1. Meeting 레코드 생성 (title, summary, decisions, meeting_date)
    2. ActionItem 레코드 bulk 생성
       → [{content, assignee, due_date, priority}]
    3. (선택) ActionItem → Schedule 자동 생성
       → schedule_service.create_from_action_item()
```

### 관련 Backend 파일 현황

| 파일 | 현재 상태 | 필요 작업 |
|------|----------|----------|
| `api/v1/documents.py` | POST /generate → 501 stub | 구현 필요 |
| `api/v1/documents.py` | GET /{id}/download → 501 stub | 구현 필요 |
| `services/document_service.py` | upload/list/get/delete만 있음 | generate_document() 추가 |
| `api/v1/meetings.py` | POST /analyze, /generate → 501 stub | meeting_minutes 연동 시 구현 |
| `services/meeting_service.py` | create/list/get만 있음 | analyze + bulk action_items 추가 |
| `services/schedule_service.py` | ✅ 완전 구현 | 변경 없음 |

### 데이터 흐름 정리 (intent별 최종)

```
judgment
  AI: RAG → LLM 판단 → agent_response
  Backend: chat_logs 저장
  Frontend: 판단 결과 + 근거 조항 렌더링

doc_search
  AI: RAG 하이브리드 검색 → agent_response
  Backend: chat_logs 저장
  Frontend: 검색 결과 목록 렌더링

doc_generate
  AI: 템플릿 + LLM → preview(MD) + data(JSON)
  Backend: chat_logs 저장 → (사용자 저장 시) Document DB + 파일 생성
  Frontend: 미리보기 → 저장 버튼 → 다운로드

doc_summary
  AI: 문서 로드 → LLM 요약 → { title, core_summary, key_points, keywords }
  Backend: chat_logs 저장
  Frontend: 요약 카드 렌더링

doc_qa
  AI: RAG → LLM 답변 → { answer, citations[] }
  Backend: chat_logs 저장
  Frontend: 답변 + 인용 출처 렌더링

schedule_add
  AI: LLM 파싱 → 구조화 데이터
  Backend: Schedule DB 저장 + Google Calendar/Tasks/Gmail/Sheets 동기화
  Frontend: 등록 완료 표시

schedule_view
  AI: LLM 기간 추출 → Google Calendar 조회
  Backend: chat_logs 저장
  Frontend: 일정 목록/캘린더 렌더링

general
  AI: LLM 일반 응답
  Backend: chat_logs 저장
  Frontend: 텍스트 렌더링
```
