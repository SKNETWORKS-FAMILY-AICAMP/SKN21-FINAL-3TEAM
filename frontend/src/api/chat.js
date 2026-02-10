/**
 * 챗봇 API : 메시지 전송 및 SSE 스트리밍 연동을 위한 URL 관리(팀원 E 담당)
 */
import client from './client'

export const sendMessage = (message, sessionId) =>
  client.post('/chat/', { message, session_id: sessionId })

/**
 * SSE 스트리밍 요청 URL
 * EventSource에서 직접 사용
 */
export const STREAM_URL = '/api/v1/chat/stream'
