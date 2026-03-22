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
 *   2) 네트워크 에러 시 UI에 에러 메시지 표시
 */
import { useCallback, useRef } from 'react'
import useChatStore from '../store/chatStore'

export default function useSSE() {
  const abortRef = useRef(null)
  const timerRef = useRef(null)
  const currentIntentRef = useRef(null)
  const {
    setStreaming, setCurrentIntent, setCurrentStatus, setCurrentSubType, appendToken, saveCurrentSession,
    setLastAssistantResult, setLastAssistantError, setLastAssistantIntent,
  } = useChatStore()

  // 실제 SSE 스트리밍
  const startStream = useCallback(async (message, sessionId, documentId, templateId, templateType, forceIntent) => {
    setStreaming(true)
    currentIntentRef.current = null
    const token = localStorage.getItem('access_token')
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const body = { message }
      if (sessionId) body.session_id = sessionId
      if (documentId) body.document_id = documentId
      if (templateId) body.template_id = templateId
      if (templateType) body.template_type = templateType
      if (forceIntent) body.force_intent = forceIntent

      const res = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
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
      let simulationInProgress = false
      let simulationPromise = Promise.resolve()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        const chunks = buffer.split('\n\n')
        buffer = chunks.pop()

        for (const chunk of chunks) {
          const match = chunk.match(/^data:\s*(.+)/m)
          if (!match) continue

          try {
            const event = JSON.parse(match[1])

            switch (event.type) {
              case 'intent':
                currentIntentRef.current = event.intent || event.agent_type
                setCurrentIntent(currentIntentRef.current)
                break
              case 'intent_update':
                currentIntentRef.current = event.intent
                setCurrentIntent(event.intent)
                break
              case 'status':
                setCurrentStatus(event.value)
                break
              case 'token':
                setCurrentStatus(null)
                appendToken(event.value)
                break
              case 'result': {
                setLastAssistantResult(event.intent || currentIntentRef.current, event.data)

                // 토큰이 오지 않은 경우(예: 판단 에이전트) reasoning을 시뮬레이션 스트리밍함
                const lastMsg = useChatStore.getState().messages.at(-1)
                if (event.data?.reasoning && lastMsg && (!lastMsg.content || lastMsg.content.trim() === '')) {
                  simulationInProgress = true
                  simulationPromise = new Promise((resolve) => {
                    const text = event.data.reasoning
                    let i = 0
                    const interval = setInterval(() => {
                      if (i < text.length) {
                        appendToken(text[i])
                        i++
                      } else {
                        clearInterval(interval)
                        simulationInProgress = false
                        resolve()
                      }
                    }, 20) // 자연스러운 스트리밍 속도 (20ms)
                  })
                }
                break
              }
              case 'done':
                if (currentIntentRef.current) {
                  setLastAssistantIntent(currentIntentRef.current)
                }
                break
              case 'error':
                console.error('[SSE] 서버 에러:', event.message || event.value)
                setLastAssistantError(event.message || event.value || '서버 오류가 발생했습니다')
                break
              case 'doc_sub_type':
                // 문서 Agent sub_type 조기 알림 (검색/QA/요약)
                setCurrentSubType(event.value)
                setCurrentStatus(event.value === 'search' ? '문서 검색 중...' : event.value === 'qa' ? '문서 질의응답 준비 중...' : event.value === 'summary' ? '문서 요약 준비 중...' : event.value === 'generate' ? '문서 생성 준비 중...' : `${event.value} 처리 중...`)
                break
              case 'compound_start':
                setCurrentStatus(`복합 질문 감지: ${event.total || ''}개 하위 질문 처리 중...`)
                break
              case 'compound_sub':
                setCurrentStatus(`[${(event.index || 0) + 1}/${event.total || ''}] ${event.query || ''} 처리 중...`)
                if (event.index > 0) appendToken('\n\n---\n\n')
                break
              case 'compound_sub_done':
                break
              case 'clarify_candidates':
                setLastAssistantResult('clarify', event.data)
                if (event.data?.message) appendToken(event.data.message)
                break
            }
          } catch {
            // JSON 파싱 실패
          }
        }
      }

      // 시뮬레이션이 진행 중이면 끝날 때까지 대기
      if (simulationInProgress) {
        await simulationPromise
      }

      setStreaming(false)
      setCurrentIntent(null)
      setCurrentStatus(null)
      setCurrentSubType(null)
      saveCurrentSession()
    } catch (err) {
      if (err.name === 'AbortError') return // 사용자가 중단

      setStreaming(false)
      setCurrentStatus(null)

      if (err.status === 401) {
        throw err
      }

      // 에러를 메시지에 기록 → UI에 표시
      setLastAssistantError(err.message || '서버 연결에 실패했습니다')
    }
  }, [setStreaming, setCurrentIntent, setCurrentStatus, setCurrentSubType, appendToken, setLastAssistantResult, setLastAssistantError, setLastAssistantIntent])

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
    setCurrentSubType(null)
  }, [setStreaming, setCurrentIntent, setCurrentStatus, setCurrentSubType])

  return { startStream, stopStream }
}
