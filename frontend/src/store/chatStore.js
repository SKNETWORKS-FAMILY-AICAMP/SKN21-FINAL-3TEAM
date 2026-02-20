/**
 * 챗봇 상태 관리 (팀원 E 담당)
 */
import { create } from 'zustand'

const SESSIONS_KEY = 'chat_sessions'
const ACTIVE_SESSION_KEY = 'chat_active_session'

function loadSessions() {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

function saveSessions(sessions) {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions))
}

function saveActiveId(id) {
  localStorage.setItem(ACTIVE_SESSION_KEY, id || '')
}

const useChatStore = create((set, get) => ({
  messages: [],
  isStreaming: false,
  currentIntent: null,
  currentStatus: null,

  // 대시보드 → 챗 이동 시 자동 전송할 질문
  pendingQuestion: null,
  setPendingQuestion: (q) => set({ pendingQuestion: q }),
  clearPendingQuestion: () => set({ pendingQuestion: null }),

  // 세션 관리
  sessions: [],
  activeSessionId: null,

  initSession: () => {
    const sessions = loadSessions()
    const savedId = localStorage.getItem(ACTIVE_SESSION_KEY)
    const activeSession = sessions.find(s => s.id === savedId)

    if (activeSession) {
      const state = get()
      // 이미 같은 세션이 활성화되어 메시지가 있으면 in-memory 메시지를 보존
      if (state.activeSessionId === activeSession.id && state.messages.length > 0) {
        set({ sessions })
      } else {
        set({ sessions, activeSessionId: activeSession.id, messages: activeSession.messages || [] })
      }
    } else {
      set({ sessions, activeSessionId: null, messages: [] })
    }
  },

  createSession: () => {
    const state = get()
    let sessions = state.sessions

    if (state.activeSessionId && state.messages.length === 0) {
      // 현재 세션이 비어있으면 제거 (빈 세션 정리)
      sessions = sessions.filter(s => s.id !== state.activeSessionId)
      saveSessions(sessions)
    } else if (state.activeSessionId && state.messages.length > 0) {
      // 현재 대화 저장
      sessions = sessions.map(s =>
        s.id === state.activeSessionId ? { ...s, messages: state.messages, updatedAt: Date.now() } : s
      )
      saveSessions(sessions)
    }

    const id = `session-${Date.now()}`
    const newSession = {
      id,
      name: '새 대화',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }
    const newSessions = [newSession, ...sessions]
    saveSessions(newSessions)
    saveActiveId(id)
    set({ sessions: newSessions, activeSessionId: id, messages: [], currentIntent: null, currentStatus: null })
  },

  switchSession: (id) => {
    const state = get()
    // 현재 대화 저장
    if (state.activeSessionId && state.messages.length > 0) {
      const sessions = state.sessions.map(s =>
        s.id === state.activeSessionId ? { ...s, messages: state.messages, updatedAt: Date.now() } : s
      )
      saveSessions(sessions)
      set({ sessions })
    }

    const target = get().sessions.find(s => s.id === id)
    if (target) {
      saveActiveId(id)
      set({ activeSessionId: id, messages: target.messages || [], currentIntent: null, currentStatus: null })
    }
  },

  deleteSession: (id) => {
    const state = get()
    const sessions = state.sessions.filter(s => s.id !== id)
    saveSessions(sessions)

    if (state.activeSessionId === id) {
      const next = sessions[0]
      if (next) {
        saveActiveId(next.id)
        set({ sessions, activeSessionId: next.id, messages: next.messages || [] })
      } else {
        saveActiveId(null)
        set({ sessions, activeSessionId: null, messages: [] })
      }
    } else {
      set({ sessions })
    }
  },

  saveCurrentSession: () => {
    const state = get()
    if (!state.activeSessionId || state.messages.length === 0) return

    // 첫 사용자 메시지를 세션 이름으로
    const firstUserMsg = state.messages.find(m => m.role === 'user')
    const name = firstUserMsg ? firstUserMsg.content.slice(0, 30) : '새 대화'

    const sessions = state.sessions.map(s =>
      s.id === state.activeSessionId
        ? { ...s, messages: state.messages, name, updatedAt: Date.now() }
        : s
    )
    saveSessions(sessions)
    set({ sessions })
  },

  addMessage: (message) =>
    set((state) => {
      const newMessages = [...state.messages, message]

      // 첫 메시지 시 세션 자동 생성
      if (!state.activeSessionId && message.role === 'user') {
        const id = `session-${Date.now()}`
        const newSession = {
          id,
          name: message.content.slice(0, 30),
          messages: newMessages,
          createdAt: Date.now(),
          updatedAt: Date.now(),
        }
        const sessions = [newSession, ...state.sessions]
        saveSessions(sessions)
        saveActiveId(id)
        return { messages: newMessages, sessions, activeSessionId: id }
      }

      return { messages: newMessages }
    }),

  setStreaming: (isStreaming) =>
    set({ isStreaming }),

  setCurrentIntent: (intent) =>
    set({ currentIntent: intent }),

  setCurrentStatus: (status) =>
    set({ currentStatus: status }),

  appendToken: (token) =>
    set((state) => {
      const messages = [...state.messages]
      const last = messages[messages.length - 1]
      if (last && last.role === 'assistant') {
        messages[messages.length - 1] = { ...last, content: last.content + token }
      }
      return { messages }
    }),

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

  clearMessages: () => {
    const state = get()
    if (state.activeSessionId) {
      const sessions = state.sessions.map(s =>
        s.id === state.activeSessionId ? { ...s, messages: [], updatedAt: Date.now() } : s
      )
      saveSessions(sessions)
      set({ messages: [], currentIntent: null, currentStatus: null, sessions })
    } else {
      set({ messages: [], currentIntent: null, currentStatus: null })
    }
  },
}))

export default useChatStore
