/**
 * 챗봇 상태 관리 (팀원 E 담당)
 */
import { create } from 'zustand'

const useChatStore = create((set) => ({
  messages: [],
  isStreaming: false,
  currentIntent: null,
  currentStatus: null,

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

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

  clearMessages: () =>
    set({ messages: [], currentIntent: null, currentStatus: null }),
}))

export default useChatStore
