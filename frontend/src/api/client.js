/**
 * Axios 인스턴스 (팀원 E 담당)
 */
import axios from 'axios'

const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

// 요청 인터셉터: JWT 토큰 자동 첨부
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 응답 인터셉터: 401이면 토큰 삭제 후 로그인 페이지로 이동
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || ''
    // Google 연동 API(calendar, google)의 401은 연동 안 된 것이지 인증 만료가 아님
    const isGoogleApi = /\/(calendar|google)\//.test(url)
    if (error.response?.status === 401 && window.location.pathname !== '/login' && !isGoogleApi) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('cached_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
