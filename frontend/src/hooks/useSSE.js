/**
 * SSE 스트리밍 훅 (팀원 E 담당)
 *
 * 서버에서 보내는 이벤트 타입:
 *   - intent: 의도 분류 결과
 *   - status: Agent 호출 상태
 *   - token: LLM 응답 토큰
 *   - done: 완료
 *   - error: 에러
 *
 * 동작 방식:
 *   1) fetch + ReadableStream으로 POST /api/v1/chat/stream 호출
 *   2) 네트워크 에러 시 기존 Mock 모드로 자동 폴백
 */
import { useCallback, useRef } from 'react'
import useChatStore from '../store/chatStore'
import { MOCK_RESPONSES } from '../utils/mockData'

export default function useSSE() {
  const abortRef = useRef(null)
  const timerRef = useRef(null)
  const { setStreaming, setCurrentIntent, setCurrentStatus, appendToken, saveCurrentSession } = useChatStore()

  // 실제 SSE 스트리밍
  const startStream = useCallback(async (message) => {
    setStreaming(true)
    const token = localStorage.getItem('access_token')
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const res = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const err = new Error(`HTTP ${res.status}`)
        err.status = res.status
        throw err
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // SSE 형식: "data: {...}\n\n" 패턴 파싱
        const chunks = buffer.split('\n\n')
        buffer = chunks.pop() // 마지막 불완전한 청크 보존

        for (const chunk of chunks) {
          const match = chunk.match(/^data:\s*(.+)/m)
          if (!match) continue

          try {
            const event = JSON.parse(match[1])

            switch (event.type) {
              case 'intent':
                setCurrentIntent(event.value)
                break
              case 'status':
                setCurrentStatus(event.value)
                break
              case 'token':
                setCurrentStatus(null)
                appendToken(event.value)
                break
              case 'done':
                break
              case 'error':
                console.error('[SSE] 서버 에러:', event.value)
                break
            }
          } catch {
            // JSON 파싱 실패 시 무시
          }
        }
      }

      setStreaming(false)
      setCurrentIntent(null)
      setCurrentStatus(null)
      saveCurrentSession() // 스트리밍 완료 시 세션 저장
    } catch (err) {
      if (err.name === 'AbortError') return // 사용자가 중단

      console.warn('[SSE] 백엔드 연결 실패, Mock 모드로 폴백:', err.message)

      // 401이면 폴백 없이 에러 전파
      if (err.status === 401) {
        setStreaming(false)
        throw err
      }

      // 네트워크 에러 → Mock 폴백
      startMockStream(message)
    }
  }, [setStreaming, setCurrentIntent, setCurrentStatus, appendToken])

  // Mock 스트리밍 (백엔드 미연결 시 폴백)
  const startMockStream = useCallback((message) => {
    const mock = findMockResponse(message)

    const intentTimer = setTimeout(() => {
      setCurrentIntent(mock.intent)
      setCurrentStatus(mock.status)
    }, 300)

    const tokens = mock.content.split('')
    let index = 0

    const streamTimer = setTimeout(() => {
      setCurrentStatus(null)
      timerRef.current = setInterval(() => {
        if (index < tokens.length) {
          appendToken(tokens[index])
          index++
        } else {
          clearInterval(timerRef.current)
          timerRef.current = null
          setStreaming(false)
          setCurrentIntent(null)
          saveCurrentSession()
        }
      }, 30)
    }, 800)

    timerRef.current = { intentTimer, streamTimer }
  }, [setStreaming, setCurrentIntent, setCurrentStatus, appendToken, saveCurrentSession])

  // 스트리밍 중단
  const stopStream = useCallback(() => {
    // 실제 SSE 중단
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }

    // Mock 타이머 정리
    if (timerRef.current) {
      if (timerRef.current.intentTimer) {
        clearTimeout(timerRef.current.intentTimer)
        clearTimeout(timerRef.current.streamTimer)
      } else {
        clearInterval(timerRef.current)
      }
      timerRef.current = null
    }

    setStreaming(false)
    setCurrentIntent(null)
    setCurrentStatus(null)
  }, [setStreaming, setCurrentIntent, setCurrentStatus])

  return { startStream, stopStream }
}

function findMockResponse(message) {
  const msg = message.toLowerCase()
  for (const mock of MOCK_RESPONSES) {
    if (mock.keywords.some((kw) => msg.includes(kw))) {
      return mock
    }
  }
  return MOCK_RESPONSES[MOCK_RESPONSES.length - 1]
}
