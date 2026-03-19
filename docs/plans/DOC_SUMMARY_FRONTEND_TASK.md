# doc_summary 프론트엔드 연동 작업

## 현황

Backend/AI는 `document_id` → 문서 로드 → 요약까지 **완료**됨.
프론트엔드에서 채팅 요청 시 `document_id`를 보내는 부분이 **미구현**.

현재 "이 문서 요약해줘" 입력 시 → `doc_summary` intent 정상 분류 → 하지만 `document_content`가 없어서 빈 응답 반환.

---

## 수정 필요 파일 (6개)

### 1. `frontend/src/hooks/useSSE.js`

fetch body에 `document_id` 추가:

```js
// 현재
const body = { message }
if (sessionId) body.session_id = sessionId

// 변경
const body = { message }
if (sessionId) body.session_id = sessionId
if (documentId) body.document_id = documentId  // 추가
```

### 2. `frontend/src/hooks/useChat.js`

`sendMessage` 호출 시 `document_id` 전달:

```js
// 현재
await startStream(text, useChatStore.getState().activeSessionId)

// 변경
const { activeSessionId, selectedDocumentId } = useChatStore.getState()
await startStream(text, activeSessionId, selectedDocumentId)
```

### 3. `frontend/src/store/chatStore.js`

상태 추가:

```js
selectedDocumentId: null,
setSelectedDocumentId: (id) => set({ selectedDocumentId: id }),
clearSelectedDocument: () => set({ selectedDocumentId: null }),
```

### 4. `frontend/src/pages/ChatPage.jsx`

문서 선택 UI 추가 (채팅 입력 영역 근처에 문서 선택 버튼/드롭다운):

- 문서 목록 API 호출 → 선택 가능한 드롭다운 or 모달
- 선택하면 `chatStore.setSelectedDocumentId(doc.id)` 호출
- 메시지 전송 후 자동 초기화 (`clearSelectedDocument`)

### 5. `frontend/src/components/chat/ChatWindow.jsx`

선택된 문서가 있을 때 채팅 입력 영역에 표시:

```
📎 [문서명] 선택됨  ✕
```

### 6. `frontend/src/api/chat.js`

`sendMessage` 시그니처 수정:

```js
// 현재
export const sendMessage = (message, sessionId) =>
  client.post('/chat/', { message, session_id: sessionId })

// 변경
export const sendMessage = (message, sessionId, documentId) =>
  client.post('/chat/', { message, session_id: sessionId, document_id: documentId })
```

---

## Backend 스키마 (이미 완료)

```python
# backend/app/schemas/chat.py
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[int] = None
    document_id: Optional[int] = None  # ← 이미 추가됨
```

---

## 사용 시나리오

1. 채팅 페이지에서 문서 선택 버튼 클릭
2. 문서 목록에서 요약할 문서 선택
3. "이 문서 요약해줘" 입력 → `{ message, document_id }` 전송
4. Backend가 `document_id`로 DB에서 본문 로드 → AI가 요약 반환
5. 전송 후 선택된 문서 자동 해제

---

## 참고

- 문서관리 페이지(`DocumentsPage.jsx`)에 이미 문서 선택 로직(`handleSelectDoc`)이 있음 — 재사용 가능
- `doc_qa`도 동일한 `document_id` 흐름 사용 가능
