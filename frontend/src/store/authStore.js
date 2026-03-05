/**
 * 인증 상태 관리 (팀원 E 담당)
 */
import { create } from 'zustand'
import client from '../api/client'
import useChatStore from './chatStore'
import useGoogleStore from './googleStore'

const useAuthStore = create((set, get) => ({
  user: null,
  token: sessionStorage.getItem('access_token'),
  isAuthenticated: !!sessionStorage.getItem('access_token'),
  initialized: false,

  setAuth: (user, token) => {
    sessionStorage.setItem('access_token', token)
    set({ user, token, isAuthenticated: true })
  },

  logout: () => {
    sessionStorage.removeItem('access_token')
    useChatStore.getState().reset()
    useGoogleStore.setState({
      connected: false, email: null, scopes: [],
      calendarEvents: [], tasks: [], sheets: [],
      calendarLoading: false, calendarError: null,
      tasksLoading: false, tasksError: null,
      sheetsLoading: false, sheetsError: null,
    })
    set({ user: null, token: null, isAuthenticated: false })
  },

  // 앱 시작 시 토큰이 있으면 /auth/me로 유저 정보 복원
  initialize: async () => {
    const token = sessionStorage.getItem('access_token')
    if (!token) {
      set({ initialized: true })
      return
    }
    try {
      const { data } = await client.get('/auth/me')
      set({ user: data, isAuthenticated: true, initialized: true })
    } catch (err) {
      // 401(토큰 만료/무효)일 때만 로그아웃, 그 외(네트워크 오류 등)는 토큰 유지
      if (err.response?.status === 401) {
        sessionStorage.removeItem('access_token')
        set({ user: null, token: null, isAuthenticated: false, initialized: true })
      } else {
        // 서버 오류/네트워크 오류 → 토큰은 유지하고 인증 상태만 복원
        set({ isAuthenticated: true, initialized: true })
      }
    }
  },
}))

export default useAuthStore
