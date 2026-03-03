/**
 * 일정 API : 일정 생성, 조회, 수정, 삭제(CRUD) 전체 기능(팀원 E 담당)
 */
import client from './client'

export const listSchedules = (params) =>
  client.get('/schedules/', { params })

export const createSchedule = (data) =>
  client.post('/schedules/', data)

export const createScheduleWithMeet = (data) =>
  client.post('/schedules/', data)

export const updateSchedule = (id, data) =>
  client.put(`/schedules/${id}`, data)

export const deleteSchedule = (id) =>
  client.delete(`/schedules/${id}`)
