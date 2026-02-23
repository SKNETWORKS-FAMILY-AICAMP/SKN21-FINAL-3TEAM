# 문서 Agent 잔여 작업 상세

> 파인튜닝(Intent BERT, 문서 sLLM) 제외, 기능 완성에 필요한 작업만 정리

## 현재 상태 (2026-02-22)

| 기능 | AI Agent | Backend | Frontend | E2E |
|------|---------|---------|----------|-----|
| doc_search | ✅ | ✅ | ✅ 카드 렌더링 | **85%** |
| doc_generate | ✅ | ✅ | ❌ | **50%** |
| doc_summary | ✅ | ✅ | ❌ | **30%** |
| doc_qa | ✅ | ✅ | ❌ | **30%** |

---

## 1. [Frontend] ChatPage 문서 선택 UI — 담당: 지영

**현재 문제**: 채팅에서 `document_id`를 보낼 방법이 없어서 doc_summary, doc_qa가 동작 불가

### 1-1. chatStore에 상태 추가

파일: `frontend/src/store/chatStore.js`

```js
// 추가할 상태
selectedDocumentId: null,
selectedDocumentTitle: null,
setSelectedDocument: (id, title) => set({ selectedDocumentId: id, selectedDocumentTitle: title }),
clearSelectedDocument: () => set({ selectedDocumentId: null, selectedDocumentTitle: null }),
```

### 1-2. useSSE.js에 document_id 전달

파일: `frontend/src/hooks/useSSE.js` (줄 36-37)

```js
// 현재
const body = { message }
if (sessionId) body.session_id = sessionId

// 변경
const body = { message }
if (sessionId) body.session_id = sessionId
if (documentId) body.document_id = documentId
```

`startStream` 함수 시그니처도 `(message, sessionId, documentId)` 로 변경 필요.

### 1-3. useChat.js 수정

파일: `frontend/src/hooks/useChat.js` (줄 19)

```js
// 현재
await startStream(text, useChatStore.getState().activeSessionId)

// 변경
const { activeSessionId, selectedDocumentId } = useChatStore.getState()
await startStream(text, activeSessionId, selectedDocumentId)
// 전송 후 선택 해제
useChatStore.getState().clearSelectedDocument()
```

### 1-4. ChatPage에 문서 선택 버튼 추가

파일: `frontend/src/pages/ChatPage.jsx`

- 채팅 입력 영역 옆에 첨부 버튼 추가
- 클릭 시 문서 목록 모달/드롭다운 표시 (API: `GET /api/v1/documents/`)
- 선택하면 `chatStore.setSelectedDocument(doc.id, doc.title)` 호출
- 입력 영역 위에 "[문서명] 선택됨 X" 인디케이터 표시

### 1-5. api/chat.js 수정

파일: `frontend/src/api/chat.js` (줄 6-7)

```js
// 현재
export const sendMessage = (message, sessionId) =>
  client.post('/chat/', { message, session_id: sessionId })

// 변경
export const sendMessage = (message, sessionId, documentId) =>
  client.post('/chat/', { message, session_id: sessionId, document_id: documentId })
```

> 참고: Backend `ChatRequest` 스키마에 `document_id: Optional[int] = None` 이미 추가됨.
> DB에서 문서 로딩하는 코드도 `backend/app/api/v1/chat.py` 줄 78-89에 구현 완료.

---

## 2. [Frontend] doc_summary / doc_qa 카드 렌더링 — 담당: 지영

**현재 문제**: ChatPage의 `renderCardMessage()`에 doc_summary, doc_qa case가 없어서 결과가 plain text로만 표시됨

### 2-1. doc_summary 카드

파일: `frontend/src/pages/ChatPage.jsx` — `renderCardMessage()` 내부

SSE 응답 구조 (현재 — 자연어 스트리밍):
- **토큰 이벤트**: 요약 텍스트가 실시간 스트리밍됨
- **result 이벤트**: `key_points`, `keywords`가 포함될 예정 (섹션 7 작업 후)

```json
{
  "type": "doc_summary",
  "answer": "**요약:** 이 문서는...\n\n* 주요 포인트:\n  - ...",
  "message": "(동일)"
}
```

렌더링 요소:
- 요약 텍스트 (마크다운 렌더링, 스트리밍 지원)
- 향후 (섹션 7 완료 후): key_points 리스트, keywords 태그

### 2-2. doc_qa 카드

SSE 응답 구조:
- **토큰 이벤트**: 답변 텍스트가 실시간 스트리밍됨
- **result 이벤트**: citations, confidence, sources 포함

```json
{
  "type": "doc_qa",
  "answer": "지난 회의 결정사항은 API 스키마 확정과 DB 설계 완료입니다.",
  "citations": [
    { "source": "회의록_0212", "content": "결정사항: 1. API 스키마 확정...", "relevance": "높음" }
  ],
  "confidence": 0.95,
  "sources": []
}
```

렌더링 요소:
- 답변 텍스트 (스트리밍)
- 인용 출처 카드 (접이식, result 이벤트에서 받음)
- 신뢰도 뱃지 (높음/보통/낮음)

---

## 3. [Frontend] doc_generate 결과 카드 — 담당: 지영

**현재 문제**: 문서 생성 결과가 카드로 표시되지 않음

SSE result 이벤트 data 구조:
```json
{
  "type": "doc_generate",
  "template_type": "meeting_minutes",
  "template_name": "회의록",
  "preview": "# 2월 20일 주간회의\n## 요약\n...",
  "data": { ... },
  "document_id": null,
  "download_url": null
}
```

> 주의: 현재 `document_id`와 `download_url`은 **mock 값(123)**이 오거나 null.
> 섹션 4 (DB 저장) 완료 후에야 실제 값이 들어옴.
> 카드 렌더링 시 document_id가 null이면 다운로드 버튼 비활성화 처리 필요.

렌더링 요소:
- 마크다운 미리보기 (preview 필드)
- 템플릿 타입 뱃지 (회의록/보고서/JD/제안서)
- 다운로드 버튼 (document_id가 있을 때만 활성화)
- 편집 버튼 (문서관리 페이지로 이동)

---

## 4. [Backend] doc_generate DB 저장 — 담당: 혜빈

**현재 문제**: document_agent가 mock `document_id=123`을 반환, 실제 DB 저장 안 됨

### 저장 위치 결정

**방안 A — chat.py에서 저장** (권장):
- agent는 순수 생성 로직만 담당, chat.py에서 result 이벤트 받은 후 DB INSERT
- agent가 DB 의존성 없이 테스트 가능

**방안 B — document_agent에서 저장**:
- agent_response에 바로 실제 document_id 포함 가능
- 단, agent에 DB 세션 전달 필요

### 4-1. 문서 저장 로직

저장 시점: SSE result 이벤트 전송 직전 (chat.py)

```python
if agent_response.get("type") == "doc_generate":
    doc = Document(
        title=agent_response.get("preview", "")[:100],
        content=json.dumps(agent_response.get("data", {})),
        template_type=agent_response.get("template_type"),
        user_id=current_user.id,
    )
    db.add(doc)
    await db.commit()
    agent_response["document_id"] = doc.id
    agent_response["download_url"] = f"/api/v1/documents/{doc.id}/download"
```

### 4-2. 문서 다운로드 API

파일: `backend/app/api/v1/documents.py`

- `GET /api/v1/documents/{id}/download` — 마크다운/PDF 다운로드
- 이미 라우터가 있다면 확인, 없으면 추가

---

## 5. [AI] RAG 필터 추가 — 담당: 경은

**현재 문제**:
- doc_qa에서 특정 문서에 대해 질문해도 RAG가 전체 DB를 검색함
- doc_search에서 카테고리 구분 없이 전체 검색 (규정/업무문서 혼재)

### 5-1. retrieve()에 document_id + category 파라미터 추가

파일: `ai/rag/qdrant_pipeline.py` (줄 98)

```python
# 현재
def retrieve(self, query: str, user_id: int | None = None, top_k: int = 5)

# 변경
def retrieve(self, query: str, user_id: int | None = None, top_k: int = 5,
             document_id: int | None = None, category: str | None = None)
```

- `document_id` 있으면 → Qdrant 필터에 `document_id == N` 조건 추가 (해당 문서 청크만 검색)
- `category` 있으면 → Qdrant 필터에 `category == "regulation"` 등 조건 추가 (규정/업무 구분)

### 5-2. hybrid_search.py 동일 변경

파일: `ai/rag/hybrid_search.py` (줄 131)

retrieve → hybrid_search → qdrant_store 순서로 document_id, category 전달.

### 5-3. document_agent에서 필터 전달

파일: `ai/agents/document_agent.py`

**doc_qa** (`_handle_doc_qa`, 줄 421):
```python
# 현재
search_results = rag_pipeline.retrieve(query, user_id=user_id, top_k=5)

# 변경
doc_id = state.get("document_id")
search_results = rag_pipeline.retrieve(query, user_id=user_id, top_k=5, document_id=doc_id)
```

**doc_search** (`_handle_doc_search`, 줄 200):
```python
# category 필터 추가 가능 (추후)
search_results = rag_pipeline.retrieve(query, user_id=user_id, top_k=5, category=category)
```

---

## 6. [AI] doc_generate 회의록 빈 틀 개선 — 담당: 지용

**현재 문제**: "회의록 만들어줘"만 입력하면 Solar LLM이 placeholder만 생성

```
# 회의 제목
## 요약
전체 요약          ← 실제 내용 없음
## 결정사항
- 결정사항1        ← placeholder
```

### 해결 방안

파일: `ai/agents/document_agent.py` — `_generate_meeting_minutes()`

회의 내용이 부족할 때 LLM이 빈 틀 대신 추가 정보를 요청하도록 프롬프트 수정:

```
사용자 입력에 회의 날짜, 참석자, 논의 내용이 충분하지 않으면
문서를 생성하지 말고, 부족한 정보를 구체적으로 물어보세요.
예: "회의 날짜와 참석자, 주요 논의 내용을 알려주세요."
```

---

## 7. [AI] doc_summary 구조화 응답 — 담당: 승언

**현재 문제**: doc_summary가 plain text만 반환, 스키마 기대값과 불일치

### 현재 동작
- 스트리밍: 자연어 요약 텍스트가 토큰 단위로 전송됨 (stream_pending 패턴)
- result 이벤트: `{ type, answer, message }` — 구조화 필드 없음

### 기대 응답 (DocSummaryResultData 스키마)
```json
{
  "type": "doc_summary",
  "title": "Q3 매출 보고서",
  "core_summary": "3분기 매출이 전년 대비 15% 증가...",
  "key_points": ["매출 15% 증가", "신규 고객 200명 확보", "마케팅 비용 10% 절감"],
  "keywords": ["매출", "Q3", "성장률"]
}
```

### 구현 방안 (스트리밍 유지)

파일: `ai/agents/document_agent.py` — `_handle_doc_summary()`

스트리밍을 깨지 않으려면 **2단계 처리**:
1. **토큰 스트리밍**: 기존대로 자연어 요약 텍스트를 실시간 전송 (사용자 UX)
2. **result 이벤트**: 스트리밍 완료 후 별도 LLM 호출 (JSON mode)로 key_points, keywords 추출 → result 이벤트에 포함

> 주의: JSON mode로 전환하면 토큰 스트리밍이 불가능해짐.
> 스트리밍 UX를 유지하면서 구조화 데이터도 제공하려면 위 2단계 방식 필요.

---

## 8. [Frontend] 템플릿 선택 UI — 담당: 지영

**현재 문제**: doc_generate 시 템플릿을 사용자가 선택할 수 없음 (키워드 감지에 의존)

### 구현 방안

- 문서 생성 페이지 또는 채팅에서 템플릿 선택 드롭다운
- 선택 가능 템플릿: 회의록, 보고서, JD, 제안서
- 선택 시 `template_type`을 ChatRequest에 포함
- useSSE.js에서 `body.template_type = templateType` 추가

---

## 작업 의존 관계

```
1. chatStore 상태 추가
   └── 2. useSSE/useChat document_id 전달
       └── 3. ChatPage 문서 선택 UI
           └── doc_summary / doc_qa 실사용 가능

4. doc_summary/doc_qa 카드 렌더링 (독립)
5. doc_generate 카드 렌더링 (독립)
6. doc_generate DB 저장 (독립, 완료 후 섹션 3 다운로드 버튼 활성화)
7. RAG document_id + category 필터 (독립, doc_qa/doc_search 정확도 향상)
8. 회의록 빈 틀 개선 (독립)
9. doc_summary 구조화 응답 (독립, 완료 후 섹션 2-1 카드에 key_points 표시)
10. 템플릿 선택 UI (독립)
```

---

## 참고 문서

- 리팩토링 변경 기록: `docs/지용/REFACTORING_DOC_AGENT_v2.md`
- 프론트엔드 연동 상세: `docs/지용/DOC_SUMMARY_FRONTEND_TASK.md`
- Intent 파인튜닝 계획: `docs/지용/EXPERIMENT_PLAN_v2.md`
