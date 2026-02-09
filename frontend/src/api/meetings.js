/**
 * 회의 API (팀원 E 담당)
 */
import client from './client'

export const listMeetings = () =>
  client.get('/meetings/')

export const getMeeting = (id) =>
  client.get(`/meetings/${id}`)

export const createMeeting = (data) =>
  client.post('/meetings/', data)

export const analyzeMeeting = (id) =>
  client.post(`/meetings/${id}/analyze`)
