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
 *
 * 성능 최적화:
 *   - rAF 기반 토큰 버퍼링: 16ms 내 도착 토큰을 묶어서 1번만 상태 업데이트
 */
import { useCallback, useRef } from 'react'
import useChatStore from '../store/chatStore'

export default function useSSE() {
  const abortRef = useRef(null)
  const timerRef = useRef(null)
  const currentIntentRef = useRef(null)

  // rAF 토큰 버퍼링 refs
  const tokenBufferRef = useRef('')
  const rafRef = useRef(null)
  const compoundRef = useRef(false)  // compound 처리 중 토큰 무시용

  const {
    setStreaming, setCurrentIntent, setCurrentStatus, setCurrentSubType, appendToken, saveCurrentSession,
    setLastAssistantResult, setLastAssistantError, setLastAssistantIntent,
  } = useChatStore()

  // 버퍼에 쌓인 토큰을 한 번에 flush (이중 flush 방지용 cancelAnimationFrame 포함)
  const flushTokens = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    if (tokenBufferRef.current) {
      appendToken(tokenBufferRef.current)
      tokenBufferRef.current = ''
    }
  }, [appendToken])

  // 토큰을 버퍼에 추가하고 rAF로 flush 예약
  const bufferToken = useCallback((token) => {
    tokenBufferRef.current += token
    if (!rafRef.current) {
      rafRef.current = requestAnimationFrame(flushTokens)
    }
  }, [flushTokens])

  // 실제 SSE 스트리밍
  const startStream = useCallback(async (message, sessionId, documentId, templateId, templateType, forceIntent) => {
    setStreaming(true)
    currentIntentRef.current = null
    tokenBufferRef.current = ''
    compoundRef.current = false
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
                if (compoundRef.current) break  // compound 처리 중 토큰 무시 (CompoundCard가 렌더링)
                setCurrentStatus(null)
                bufferToken(event.value)
                break
              case 'result': {
                // result 전에 미처리 토큰 먼저 반영
                flushTokens()

                setLastAssistantResult(event.intent || currentIntentRef.current, event.data)

                // clarify가 아닌 경우에만 template 선택 해제 (clarify면 다음 메시지에서 template_id 유지)
                if (event.intent !== 'clarify') {
                  useChatStore.getState().clearSelectedTemplate()
                }

                // 토큰이 오지 않은 경우(예: 판단 에이전트) reasoning을 시뮬레이션 스트리밍함
                const lastMsg = useChatStore.getState().messages.at(-1)
                if (event.data?.reasoning && lastMsg && (!lastMsg.content || lastMsg.content.trim() === '')) {
                  simulationInProgress = true
                  simulationPromise = new Promise((resolve) => {
                    const text = event.data.reasoning
                    let i = 0
                    const CHUNK = 4
                    const interval = setInterval(() => {
                      if (i < text.length) {
                        const end = Math.min(i + CHUNK, text.length)
                        bufferToken(text.slice(i, end))
                        i = end
                      } else {
                        clearInterval(interval)
                        simulationInProgress = false
                        resolve()
                      }
                    }, 16)
                  })
                }
                break
              }
              case 'done':
                if (currentIntentRef.current) {
                  setLastAssistantIntent(currentIntentRef.current)
                }
                // log_id를 마지막 assistant 메시지에 저장 (페이지 재방문 시 상태 동기화용)
                if (event.log_id) {
                  const store = useChatStore.getState()
                  const msgs = [...store.messages]
                  const last = msgs[msgs.length - 1]
                  if (last && last.role === 'assistant') {
                    msgs[msgs.length - 1] = { ...last, logId: event.log_id }
                    useChatStore.setState({ messages: msgs })
                  }
                }
                break
              case 'error':
                flushTokens()
                console.error('[SSE] 서버 에러:', event.message || event.value)
                setLastAssistantError(event.message || event.value || '서버 오류가 발생했습니다')
                useChatStore.getState().clearSelectedTemplate()
                break
              case 'doc_sub_type':
                // 문서 Agent sub_type 조기 알림 (검색/QA/요약)
                setCurrentSubType(event.value)
                setCurrentStatus(event.value === 'search' ? '문서 검색 중...' : event.value === 'qa' ? '문서 질의응답 준비 중...' : event.value === 'summary' ? '문서 요약 준비 중...' : event.value === 'generate' ? '문서 생성 준비 중...' : `${event.value} 처리 중...`)
                break
              case 'compound_start':
                compoundRef.current = true
                setCurrentStatus(`복합 질문 감지: ${event.total || ''}개 하위 질문 처리 중...`)
                break
              case 'compound_sub':
                setCurrentStatus(`[${(event.index || 0) + 1}/${event.total || ''}] ${event.query || ''} 처리 중...`)
                break
              case 'compound_sub_done':
                break
              case 'clarify_candidates':
                setLastAssistantResult('clarify', event.data)
                if (event.data?.message) bufferToken(event.data.message)
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

      // 잔여 버퍼 flush 후 1프레임 대기하여 마지막 토큰이 화면에 반영된 후 스트리밍 종료
      flushTokens()
      await new Promise((resolve) => requestAnimationFrame(resolve))

      setStreaming(false)
      setCurrentIntent(null)
      setCurrentStatus(null)
      setCurrentSubType(null)
      saveCurrentSession()
    } catch (err) {
      if (err.name === 'AbortError') return // 사용자가 중단

      flushTokens()
      setStreaming(false)
      setCurrentStatus(null)

      if (err.status === 401) {
        throw err
      }

      // 에러를 메시지에 기록 → UI에 표시
      setLastAssistantError(err.message || '서버 연결에 실패했습니다')
    }
  }, [setStreaming, setCurrentIntent, setCurrentStatus, setCurrentSubType, appendToken, setLastAssistantResult, setLastAssistantError, setLastAssistantIntent, bufferToken, flushTokens])

  // 스트리밍 중단
  const stopStream = useCallback(() => {
    // 잔여 토큰 버퍼 즉시 flush
    flushTokens()

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
    useChatStore.getState().clearSelectedTemplate()
  }, [setStreaming, setCurrentIntent, setCurrentStatus, setCurrentSubType, flushTokens])

  return { startStream, stopStream }
}
