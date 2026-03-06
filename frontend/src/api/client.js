/**
 * Axios 인스턴스 (팀원 E 담당)
 */
import axios from 'axios'

const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// 요청 인터셉터: JWT 토큰 자동 첨부
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 응답 인터셉터: 에러 전파만 (토큰 관리는 authStore에서 처리)
client.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(error)
)

export default client
