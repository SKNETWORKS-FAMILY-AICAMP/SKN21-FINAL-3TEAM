/**
 * 관리자 API : 사용자 관리, 시스템 통계 데이터, 질의 로그 모니터링(팀원 E 담당)
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
