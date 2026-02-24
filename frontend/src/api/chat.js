/**
 * 챗봇 API : 메시지 전송 및 SSE 스트리밍 연동을 위한 URL 관리(팀원 E 담당)
 */
import client from './client'

export const sendMessage = (message, sessionId, documentId) =>
  client.post('/chat/', { message, session_id: sessionId, document_id: documentId })

/**
 * SSE 스트리밍 요청 URL
 * EventSource에서 직접 사용
 */
export const STREAM_URL = '/api/v1/chat/stream'

// ── 채팅 세션 CRUD ──

export const listSessions = () =>
  client.get('/chat/sessions').then((r) => r.data)

export const createSessionAPI = () =>
  client.post('/chat/sessions').then((r) => r.data)

export const getSessionMessages = (sessionId) =>
  client.get(`/chat/sessions/${sessionId}/messages`).then((r) => r.data)

export const renameSession = (sessionId, name) =>
  client.patch(`/chat/sessions/${sessionId}`, { name }).then((r) => r.data)

export const deleteSessionAPI = (sessionId) =>
  client.delete(`/chat/sessions/${sessionId}`).then((r) => r.data)

export const clearSessionMessagesAPI = (sessionId) =>
  client.delete(`/chat/sessions/${sessionId}/messages`).then((r) => r.data)
