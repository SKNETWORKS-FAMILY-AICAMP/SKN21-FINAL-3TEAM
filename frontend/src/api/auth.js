/**
 * 인증 API: 로그인, 회원가입, 토큰 갱신, 비밀번호 재설정 (팀원 E 담당)
 */
import client from './client'

export const login = (email, password) =>
  client.post('/auth/login', { email, password })

export const register = (email, password, name, team) =>
  client.post('/auth/register', { email, password, name, team })

export const refreshToken = (refreshToken) =>
  client.post('/auth/refresh', { refresh_token: refreshToken })

export const requestPasswordReset = (email) =>
  client.post('/auth/password-reset/request', { email })

export const confirmPasswordReset = (token, newPassword) =>
  client.post('/auth/password-reset/confirm', { token, new_password: newPassword })

export const changePassword = (currentPassword, newPassword) =>
  client.post('/auth/change-password', { current_password: currentPassword, new_password: newPassword })

export const getTeamMembers = () => client.get('/auth/team-members')

export const updateProfile = (payload) => client.put('/auth/me', payload)

export const uploadAvatar = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return client.post('/auth/me/avatar', formData)
}
