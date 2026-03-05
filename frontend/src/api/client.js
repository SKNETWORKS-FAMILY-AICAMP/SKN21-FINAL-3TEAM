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
  const token = sessionStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 응답 인터셉터: 401(토큰 만료/무효)만 토큰 제거, 403(권한 없음)은 유지
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      sessionStorage.removeItem('access_token')
    }
    return Promise.reject(error)
  }
)

export default client
