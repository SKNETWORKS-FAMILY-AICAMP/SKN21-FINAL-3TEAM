/**
 * 인증 상태 관리 (팀원 E 담당)
 */
import { create } from 'zustand'
import client from '../api/client'
import useChatStore from './chatStore'
import useGoogleStore from './googleStore'

function loadCachedUser() {
  try {
    const saved = localStorage.getItem('cached_user')
    return saved ? JSON.parse(saved) : null
  } catch { return null }
}

const useAuthStore = create((set, get) => ({
  user: loadCachedUser(),
  token: localStorage.getItem('access_token'),
  isAuthenticated: !!localStorage.getItem('access_token'),
  initialized: false,

  setAuth: (user, token) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('cached_user', JSON.stringify(user))
    set({ user, token, isAuthenticated: true })
  },

  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('cached_user')
    // sessionStorage도 정리 (이전 버전 호환)
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
    const token = localStorage.getItem('access_token')
    if (!token) {
      set({ initialized: true })
      return
    }
    // 캐시된 유저 정보로 즉시 인증 상태 복원
    const cached = loadCachedUser()
    if (cached) {
      set({ user: cached, isAuthenticated: true, initialized: true })
    }
    try {
      const { data } = await client.get('/auth/me')
      localStorage.setItem('cached_user', JSON.stringify(data))
      set({ user: data, isAuthenticated: true, initialized: true })
    } catch {
      // API 실패해도 캐시된 유저+토큰이 있으면 로그인 상태 유지
      if (cached) {
        set({ user: cached, isAuthenticated: true, initialized: true })
      } else {
        localStorage.removeItem('access_token')
        localStorage.removeItem('cached_user')
        set({ user: null, token: null, isAuthenticated: false, initialized: true })
      }
    }
  },
}))

export default useAuthStore
