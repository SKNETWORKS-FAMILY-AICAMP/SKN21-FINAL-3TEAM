/**
 * 챗봇 상태 관리 (팀원 E 담당)
 */
import { create } from 'zustand'

const useChatStore = create((set, get) => ({
  messages: [],
  isStreaming: false,
  currentIntent: null,
  currentStatus: null,

  // 대화 세션 관리
  sessions: [],
  activeSessionId: null,

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

  // 세션 생성 (첫 메시지 시 자동 호출)
  createSession: () => {
    const { messages } = get();
    if (messages.length === 0) return;

    const firstUserMsg = messages.find(m => m.role === 'user');
    const sessionName = firstUserMsg?.content.slice(0, 30) || '새 대화';
    const newSession = {
      id: Date.now().toString(),
      name: sessionName,
      messages,
      createdAt: new Date().toISOString(),
    };

    set((state) => ({
      sessions: [newSession, ...state.sessions],
      activeSessionId: newSession.id,
    }));

    // localStorage 저장
    localStorage.setItem('chatSessions', JSON.stringify([newSession, ...get().sessions]));
  },

  // 세션 전환
  switchSession: (sessionId) => {
    const { sessions } = get();
    const session = sessions.find(s => s.id === sessionId);
    if (!session) return;

    set({
      messages: session.messages,
      activeSessionId: sessionId,
      currentIntent: null,
      currentStatus: null,
    });
  },

  // 세션 삭제
  deleteSession: (sessionId) => {
    const { sessions, activeSessionId } = get();
    const newSessions = sessions.filter(s => s.id !== sessionId);

    set({
      sessions: newSessions,
      activeSessionId: activeSessionId === sessionId ? null : activeSessionId,
      messages: activeSessionId === sessionId ? [] : get().messages,
    });

    localStorage.setItem('chatSessions', JSON.stringify(newSessions));
  },

  // 현재 세션 저장 (메시지 변경 시 호출)
  saveCurrentSession: () => {
    const { sessions, activeSessionId, messages } = get();
    if (!activeSessionId || messages.length === 0) return;

    const newSessions = sessions.map(s =>
      s.id === activeSessionId ? { ...s, messages } : s
    );

    set({ sessions: newSessions });
    localStorage.setItem('chatSessions', JSON.stringify(newSessions));
  },

  // 초기화 (localStorage에서 불러오기)
  initSession: () => {
    const saved = localStorage.getItem('chatSessions');
    if (saved) {
      const sessions = JSON.parse(saved);
      set({ sessions });
    }
  },
}))

export default useChatStore
