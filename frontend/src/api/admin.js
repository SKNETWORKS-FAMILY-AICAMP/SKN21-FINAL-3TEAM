/**
 * 관리자 API (팀원 E 담당)
 */
import client from './client'

// ── 사용자 ──
export const listUsers = () =>
  client.get('/admin/users')

export const createUser = (data) =>
  client.post('/admin/users', data)

export const updateUserPermissions = (userId, data) =>
  client.put(`/admin/users/${userId}/permissions`, data)

export const deleteUser = (userId) =>
  client.delete(`/admin/users/${userId}`)

// ── 통계 ──
export const getSystemStats = (params = {}) =>
  client.get('/admin/stats', { params })

export const getQueryLogs = (page = 1, perPage = 20) =>
  client.get('/admin/query-logs', { params: { page, per_page: perPage } })

export const getTopQueries = (period = 'daily', limit = 10, team = null) =>
  client.get('/admin/top-queries', { params: { period, limit, ...(team ? { team } : {}) } })

// ── 규정 ──
export const listRegulations = () =>
  client.get('/admin/regulations')

export const createRegulation = (data) =>
  client.post('/admin/regulations', data)

export const updateRegulation = (regulationId, data) =>
  client.put(`/admin/regulations/${regulationId}`, data)

export const deleteRegulation = (regulationId) =>
  client.delete(`/admin/regulations/${regulationId}`)
