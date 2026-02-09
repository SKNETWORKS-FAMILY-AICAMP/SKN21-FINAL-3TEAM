/**
 * 인증 API (팀원 E 담당)
 */
import client from './client'

export const login = (email, password) =>
  client.post('/auth/login', { email, password })

export const register = (email, password, name) =>
  client.post('/auth/register', { email, password, name })

export const refreshToken = (refreshToken) =>
  client.post('/auth/refresh', { refresh_token: refreshToken })
