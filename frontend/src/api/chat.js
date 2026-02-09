/**
 * 챗봇 API (팀원 E 담당)
 */
import client from './client'

export const sendMessage = (message, sessionId) =>
  client.post('/chat/', { message, session_id: sessionId })

/**
 * SSE 스트리밍 요청 URL
 * EventSource에서 직접 사용
 */
export const STREAM_URL = '/api/v1/chat/stream'
