/**
 * 일정 API (팀원 E 담당)
 */
import client from './client'

export const listSchedules = () =>
  client.get('/schedules/')

export const createSchedule = (data) =>
  client.post('/schedules/', data)

export const createScheduleWithMeet = (data) =>
  client.post('/schedules/', data)

export const updateSchedule = (id, data) =>
  client.put(`/schedules/${id}`, data)

export const deleteSchedule = (id) =>
  client.delete(`/schedules/${id}`)
