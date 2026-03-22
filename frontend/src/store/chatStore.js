/**
 * 챗봇 상태 관리 (팀원 E 담당)
 * - 세션 메타데이터: 서버(PostgreSQL) 저장
 * - 메시지: 스트리밍 중 메모리 유지, 세션 전환 시 서버에서 로드
 */
import { create } from 'zustand'
import {
  listSessions,
  createSessionAPI,
  getSessionMessages,
  renameSession,
  deleteSessionAPI,
  clearSessionMessagesAPI,
} from '../api/chat'

const useChatStore = create((set, get) => ({
  messages: [],
  isStreaming: false,
  currentIntent: null,
  currentStatus: null,

  // 대시보드 → 챗 이동 시 자동 전송할 질문
  pendingQuestion: null,
  setPendingQuestion: (q) => set({ pendingQuestion: q }),
  clearPendingQuestion: () => set({ pendingQuestion: null }),

  // 문서 요약용 선택 문서
  selectedDocumentId: null,
  selectedDocumentName: null,
  setSelectedDocument: (id, name) => set({ selectedDocumentId: id, selectedDocumentName: name }),
  clearSelectedDocument: () => set({ selectedDocumentId: null, selectedDocumentName: null }),

  // 템플릿 선택 (챗봇 문서 생성 시)
  selectedTemplateId: null,
  selectedTemplateName: null,
  selectedTemplateType: null,
  setSelectedTemplate: (id, name, type) => set({ selectedTemplateId: id, selectedTemplateName: name, selectedTemplateType: type || null }),
  clearSelectedTemplate: () => set({ selectedTemplateId: null, selectedTemplateName: null, selectedTemplateType: null }),

  // 세션 관리
  sessions: [],
  activeSessionId: null,

  // 서버에서 세션 목록 로드 (로그인 후 / 페이지 진입 시)
  fetchSessions: async () => {
    try {
      const sessions = await listSessions()
      const { activeSessionId } = get()
      set({ sessions })

      // 활성 세션이 없으면 첫 번째 세션 메시지 로드
      if (!activeSessionId && sessions.length > 0) {
        await get().switchSession(sessions[0].session_id)
      }
    } catch (e) {
      console.error('[ChatStore] 세션 목록 로드 실패:', e)
    }
  },

  // 챗봇 페이지 진입 시 초기화:
  // 기존 세션 목록은 사이드바용으로 불러오되, 항상 새 대화창으로 시작
  // 세션은 첫 메시지 전송 시 생성 (빈 세션이 목록에 쌓이는 것 방지)
  initSession: async () => {
    try {
      const sessions = await listSessions()

      // "새 대화" 이름의 세션 중 메시지가 없는 빈 세션 정리
      const newTitleSessions = sessions.filter((s) => s.name === '새 대화')
      if (newTitleSessions.length > 0) {
        const msgResults = await Promise.allSettled(
          newTitleSessions.map((s) => getSessionMessages(s.session_id))
        )
        const toDelete = newTitleSessions.filter((s, i) => {
          const r = msgResults[i]
          return r.status === 'fulfilled' && r.value.length === 0
        })
        if (toDelete.length > 0) {
          await Promise.allSettled(toDelete.map((s) => deleteSessionAPI(s.session_id)))
          const deleteIds = new Set(toDelete.map((s) => s.session_id))
          const cleaned = sessions.filter((s) => !deleteIds.has(s.session_id))
          set({ sessions: cleaned, activeSessionId: null, messages: [], currentIntent: null, currentStatus: null })
          return
        }
      }

      set({ sessions, activeSessionId: null, messages: [], currentIntent: null, currentStatus: null })
    } catch (e) {
      console.error('[ChatStore] 세션 목록 로드 실패:', e)
    }
  },

  // 새 대화 시작 (서버 세션 생성 없이 로컬 상태만 초기화)
  // 실제 세션은 첫 메시지 전송 시 생성됨
  startNewSession: () => {
    set({ activeSessionId: null, messages: [], currentIntent: null, currentStatus: null })
  },

  // 새 세션 생성 (서버 + 상태)
  createSession: async () => {
    try {
      const { activeSessionId, messages, sessions } = get()

      // 현재 빈 세션이 있으면 목록에서 제거
      let newSessions = sessions
      if (activeSessionId && messages.length === 0) {
        newSessions = sessions.filter((s) => s.session_id !== activeSessionId)
      }

      const session = await createSessionAPI()
      newSessions = [session, ...newSessions]
      set({
        sessions: newSessions,
        activeSessionId: session.session_id,
        messages: [],
        currentIntent: null,
        currentStatus: null,
      })
    } catch (e) {
      console.error('[ChatStore] 세션 생성 실패:', e)
    }
  },

  // 세션 전환 (서버에서 메시지 로드)
  switchSession: async (sessionId) => {
    try {
      const messages = await getSessionMessages(sessionId)
      set({ activeSessionId: sessionId, messages, currentIntent: null, currentStatus: null })
    } catch (e) {
      console.error('[ChatStore] 세션 전환 실패:', e)
      set({ activeSessionId: sessionId, messages: [], currentIntent: null, currentStatus: null })
    }
  },

  // 세션 삭제 (서버 + 상태)
  deleteSession: async (sessionId) => {
    try {
      await deleteSessionAPI(sessionId)
      const { sessions, activeSessionId } = get()
      const newSessions = sessions.filter((s) => s.session_id !== sessionId)

      if (activeSessionId === sessionId) {
        if (newSessions.length > 0) {
          set({ sessions: newSessions })
          await get().switchSession(newSessions[0].session_id)
        } else {
          set({ sessions: newSessions, activeSessionId: null, messages: [] })
        }
      } else {
        set({ sessions: newSessions })
      }
    } catch (e) {
      console.error('[ChatStore] 세션 삭제 실패:', e)
    }
  },

  // 사용자가 직접 세션 이름 변경
  renameSessionById: async (sessionId, name) => {
    const trimmed = name.trim()
    if (!trimmed) return
    try {
      await renameSession(sessionId, trimmed)
      const { sessions } = get()
      set({
        sessions: sessions.map((s) =>
          s.session_id === sessionId ? { ...s, name: trimmed } : s
        ),
      })
    } catch (e) {
      console.error('[ChatStore] 세션 이름 변경 실패:', e)
    }
  },

  // 스트리밍 완료 후 세션 이름 저장 (첫 메시지 기준)
  saveCurrentSession: async () => {
    const { activeSessionId, messages, sessions } = get()
    if (!activeSessionId || messages.length === 0) return

    const session = sessions.find((s) => s.session_id === activeSessionId)
    if (!session || session.name !== '새 대화') return  // 이미 이름 있으면 skip

    const firstUserMsg = messages.find((m) => m.role === 'user')
    const name = firstUserMsg ? firstUserMsg.content.slice(0, 30) : '새 대화'

    try {
      await renameSession(activeSessionId, name)
      const newSessions = sessions.map((s) =>
        s.session_id === activeSessionId ? { ...s, name } : s
      )
      set({ sessions: newSessions })
    } catch (e) {
      console.error('[ChatStore] 세션 이름 저장 실패:', e)
    }
  },

  // 메시지 추가 (메모리 only — 서버 저장은 stream 엔드포인트가 담당)
  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  setStreaming: (isStreaming) => set({ isStreaming }),

  setCurrentIntent: (intent) => set({ currentIntent: intent }),

  setCurrentStatus: (status) => set({ currentStatus: status }),

  // 토큰 배치 버퍼 — 빠르게 오는 토큰을 모아서 한번에 렌더링 (부드러운 스트리밍)
  _tokenBuffer: '',
  _tokenFlushTimer: null,

  appendToken: (token) => {
    const store = useChatStore.getState()
    store._tokenBuffer += token

    if (!store._tokenFlushTimer) {
      store._tokenFlushTimer = requestAnimationFrame(() => {
        const buffered = useChatStore.getState()._tokenBuffer
        if (buffered) {
          set((state) => {
            const messages = [...state.messages]
            const last = messages[messages.length - 1]
            if (last && last.role === 'assistant') {
              messages[messages.length - 1] = { ...last, content: last.content + buffered }
            }
            return { messages, _tokenBuffer: '', _tokenFlushTimer: null }
          })
        } else {
          set({ _tokenFlushTimer: null })
        }
      })
    }
  },

  setLastAssistantResult: (intent, agentResponse) =>
    set((state) => {
      const messages = [...state.messages]
      const last = messages[messages.length - 1]
      if (last && last.role === 'assistant') {
        messages[messages.length - 1] = { ...last, resultIntent: intent, agentResponse }
      }
      return { messages }
    }),

  setLastAssistantError: (errorMsg) =>
    set((state) => {
      const messages = [...state.messages]
      const last = messages[messages.length - 1]
      if (last && last.role === 'assistant') {
        messages[messages.length - 1] = { ...last, error: errorMsg }
      }
      return { messages }
    }),

  setLastAssistantIntent: (intent) =>
    set((state) => {
      const messages = [...state.messages]
      const last = messages[messages.length - 1]
      if (last && last.role === 'assistant') {
        messages[messages.length - 1] = { ...last, intent }
      }
      return { messages }
    }),

  // 대화 초기화 (현재 세션 메시지만 삭제, 세션 유지)
  clearMessages: async () => {
    const { activeSessionId } = get()
    if (activeSessionId) {
      try {
        await clearSessionMessagesAPI(activeSessionId)
      } catch (e) {
        console.warn('[chatStore] clearMessages API 실패:', e)
      }
    }
    set({ messages: [] })
    // 세션 목록의 이름도 "새 대화"로 갱신
    set((s) => ({
      sessions: s.sessions.map((sess) =>
        sess.session_id === activeSessionId ? { ...sess, name: '새 대화' } : sess
      ),
    }))
  },

  // 로그아웃 시 전체 상태 초기화
  reset: () =>
    set({
      messages: [],
      sessions: [],
      activeSessionId: null,
      isStreaming: false,
      currentIntent: null,
      currentStatus: null,
      pendingQuestion: null,
      selectedDocumentId: null,
      selectedDocumentName: null,
      selectedTemplateId: null,
      selectedTemplateName: null,
    }),
}))

export default useChatStore
