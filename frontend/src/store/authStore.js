/**
 * 인증 상태 관리 (팀원 E 담당)
 */
import { create } from 'zustand'
import client from '../api/client'
import useChatStore from './chatStore'

const useAuthStore = create((set, get) => ({
  user: null,
  token: localStorage.getItem('access_token'),
  isAuthenticated: !!localStorage.getItem('access_token'),
  initialized: false,

  setAuth: (user, token) => {
    localStorage.setItem('access_token', token)
    set({ user, token, isAuthenticated: true })
  },

  logout: () => {
    localStorage.removeItem('access_token')
    useChatStore.getState().reset()
    set({ user: null, token: null, isAuthenticated: false })
  },

  // 앱 시작 시 토큰이 있으면 /auth/me로 유저 정보 복원
  initialize: async () => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      set({ initialized: true })
      return
    }
    try {
      const { data } = await client.get('/auth/me')
      set({ user: data, isAuthenticated: true, initialized: true })
    } catch {
      localStorage.removeItem('access_token')
      set({ user: null, token: null, isAuthenticated: false, initialized: true })
    }
  },
}))

export default useAuthStore
