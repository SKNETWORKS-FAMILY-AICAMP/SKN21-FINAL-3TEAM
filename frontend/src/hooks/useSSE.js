/**
 * SSE 스트리밍 훅 (팀원 E 담당)
 *
 * 서버에서 보내는 이벤트 타입:
 *   - intent: 의도 분류 결과
 *   - status: Agent 호출 상태
 *   - token: LLM 응답 토큰
 *   - done: 완료
 */
import { useCallback, useRef } from 'react'
import useChatStore from '../store/chatStore'

export default function useSSE() {
  const eventSourceRef = useRef(null)
  const { setStreaming, setCurrentIntent, setCurrentStatus, appendToken, addMessage } = useChatStore()

  const startStream = useCallback((message) => {
    // TODO: 팀원 E - SSE 연결 및 이벤트 핸들링 구현
    // EventSource 또는 fetch + ReadableStream 사용
  }, [])

  const stopStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setStreaming(false)
  }, [])

  return { startStream, stopStream }
}
