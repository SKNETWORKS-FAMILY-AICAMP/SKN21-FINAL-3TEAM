/**
 * SSE 스트리밍 훅 (팀원 E 담당)
 *
 * 서버에서 보내는 이벤트 타입:
 *   - intent: 의도 분류 결과
 *   - status: Agent 호출 상태
 *   - token: LLM 응답 토큰
 *   - done: 완료
 *
 * 현재: Mock 모드 (백엔드 없이 동작)
 * TODO: 백엔드 연결 시 EventSource 또는 fetch + ReadableStream으로 교체
 */
import { useCallback, useRef } from 'react'
import useChatStore from '../store/chatStore'
import { MOCK_RESPONSES } from '../utils/mockData'

export default function useSSE() {
  // 1. 상태 및 도구 준비 
  const timerRef = useRef(null)
  const { setStreaming, setCurrentIntent, setCurrentStatus, appendToken } = useChatStore()

  // 2. 스트리밍 시작 로직. 사용자가 메시지를 보내면 실행되는 핵심 함수.
  const startStream = useCallback((message) => {
    setStreaming(true)

    // ① 답변찾기 (Matching) : 메시지 키워드로 mock 응답 매칭
    const mock = findMockResponse(message)

    // ② 1단계: 생각하는 척하기 (의도 분석) (300ms 후)
    const intentTimer = setTimeout(() => {
      setCurrentIntent(mock.intent)
      setCurrentStatus(mock.status)
    }, 300)

    // ③ 2단계: 한 글자씩 타이핑 (토큰 스트리밍) (800ms 후 시작, 글자당 30ms)
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
        }
      }, 30)
    }, 800)

    // cleanup용으로 타이머 ID 저장
    timerRef.current = { intentTimer, streamTimer }
  }, [setStreaming, setCurrentIntent, setCurrentStatus, appendToken])

  // 3. 스트리밍 중단 로직 (stopStream)
  const stopStream = useCallback(() => {
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
  return MOCK_RESPONSES[MOCK_RESPONSES.length - 1] // fallback: 일반 응답
}
