/**
 * 관리자 API (팀원 E 담당)
 */
import client from './client'

export const listUsers = () =>
  client.get('/admin/users')

export const getSystemStats = () =>
  client.get('/admin/stats')

export const getQueryLogs = () =>
  client.get('/admin/logs')

export const listRegulations = () =>
  client.get('/admin/regulations')
